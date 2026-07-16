"""Order data access and transactional business operations."""

from __future__ import annotations

import json
from typing import Any, Optional

import pyodbc

from ..db import get_conn, many, one, procedure_result


def _payment_method_name(method: str | None) -> str:
    mapping = {"alipay": "支付宝", "wechat": "微信支付", "card": "银行卡"}
    value = (method or "").strip()
    return mapping.get(value, value or "支付宝")


def _procedure_error(exc: pyodbc.Error, fallback: str) -> ValueError:
    message = " ".join(str(part) for part in getattr(exc, "args", ()))
    known_messages = (
        "部分书目库存不足或已下架",
        "代金券不可用或已被使用",
        "收货地址不存在",
        "订单状态异常，无法支付",
        "订单明细为空，无法支付",
        "部分商品库存不足，无法支付",
        "未找到可批准的退款申请",
    )
    return ValueError(next((known for known in known_messages if known in message), fallback))


def _next_no(cursor: Any, sequence_type: str) -> str:
    result = procedure_result(
        cursor,
        """
        DECLARE @new_no NVARCHAR(50);
        EXEC sp_GetNextSeq @seq_type = ?, @new_no = @new_no OUTPUT;
        SELECT @new_no AS newNo;
        """,
        sequence_type,
    )
    if not result or not result.get("newNo"):
        raise ValueError("流水号生成失败")
    return str(result["newNo"])


def create_from_cart(
    user_id: int,
    book_item_ids: list[int],
    address_id: int,
    coupon_id: Optional[int] = None,
) -> dict[str, Any]:
    if not book_item_ids:
        raise ValueError("购物车中暂无商品")
    unique_ids = list(dict.fromkeys(book_item_ids))
    placeholders = ",".join("?" for _ in unique_ids)
    with get_conn() as conn:
        cursor = conn.cursor()
        rows = many(
            cursor.execute(
                f"""
                SELECT c.book_item_id AS bookItemId, c.quantity, b.price, b.stock,
                       b.locked_stock AS lockedStock, b.store_id AS storeId,
                       b.status AS itemStatus, info.status AS infoStatus, s.status AS storeStatus
                FROM cart_items c
                JOIN book_items b WITH (UPDLOCK, HOLDLOCK) ON b.book_item_id = c.book_item_id
                JOIN book_infos info ON info.book_info_id = b.book_info_id
                JOIN stores s ON s.store_id = b.store_id
                WHERE c.user_id = ? AND c.book_item_id IN ({placeholders})
                """,
                user_id,
                *unique_ids,
            )
        )
        if len(rows) != len(unique_ids):
            raise ValueError("购物车商品不存在或已被移除")
        for row in rows:
            if row["itemStatus"] != "在售" or row["infoStatus"] != "正常" or row["storeStatus"] != "正常":
                raise ValueError("部分商品已下架")
            if int(row["stock"]) - int(row["lockedStock"] or 0) < int(row["quantity"]):
                raise ValueError("部分商品库存不足，请修改后重新提交订单")
        blocked_store = cursor.execute(
            f"""
            SELECT TOP 1 s.store_name
            FROM cart_items c
            JOIN book_items b ON b.book_item_id = c.book_item_id
            JOIN stores s ON s.store_id = b.store_id
            JOIN store_blacklists sb ON sb.store_id = b.store_id AND sb.user_id = c.user_id
            WHERE c.user_id = ? AND c.book_item_id IN ({placeholders})
            """,
            user_id,
            *unique_ids,
        ).fetchone()
        if blocked_store:
            raise ValueError(f"您已被{blocked_store[0]}加入黑名单，无法提交订单")

        address = one(
            cursor.execute(
                """
                SELECT receiver_name AS receiverName, phone,
                       CONCAT(province, city, district, detail) AS receiverAddress
                FROM shipping_addresses WITH (UPDLOCK, HOLDLOCK)
                WHERE address_id = ? AND user_id = ?
                """,
                address_id,
                user_id,
            )
        )
        if not address:
            raise ValueError("收货地址不存在")

        total = sum(float(row["price"]) * int(row["quantity"]) for row in rows)
        discount = 0.0
        selected_user_coupon_id = None
        if coupon_id is not None:
            coupon = one(
                cursor.execute(
                    """
                    SELECT TOP 1 uc.user_coupon_id AS userCouponId,
                           c.amount, c.min_amount AS minAmount, c.store_id AS storeId
                    FROM user_coupons uc WITH (UPDLOCK, HOLDLOCK)
                    JOIN coupons c ON c.coupon_id = uc.coupon_id
                    WHERE uc.user_id = ? AND c.coupon_id = ?
                      AND uc.status = N'未使用' AND c.status = N'启用'
                      AND SYSDATETIME() BETWEEN c.valid_start AND c.valid_end
                    ORDER BY c.valid_end, uc.received_time, uc.user_coupon_id
                    """,
                    user_id,
                    coupon_id,
                )
            )
            if not coupon:
                raise ValueError("代金券不可用或已被使用")
            if total < float(coupon["minAmount"] or 0):
                raise ValueError("订单金额未达到代金券使用门槛")
            if coupon.get("storeId") is not None and not any(
                int(row["storeId"]) == int(coupon["storeId"]) for row in rows
            ):
                raise ValueError("店铺代金券仅可用于对应店铺商品")
            selected_user_coupon_id = int(coupon["userCouponId"])
            discount = min(float(coupon["amount"] or 0), total)

        items_json = json.dumps(
            [{"bid": int(row["bookItemId"]), "qty": int(row["quantity"])} for row in rows]
        )
        try:
            result = procedure_result(
                cursor,
                """
                DECLARE @success BIT, @order_id INT, @order_no NVARCHAR(50);
                EXEC sp_CreateOrder
                    @user_id = ?, @items_json = ?, @address_id = ?, @coupon_id = ?,
                    @success = @success OUTPUT, @order_id = @order_id OUTPUT,
                    @order_no = @order_no OUTPUT;
                SELECT @success AS success, @order_id AS orderId, @order_no AS orderNo;
                """,
                user_id,
                items_json,
                address_id,
                selected_user_coupon_id,
            )
        except pyodbc.Error as exc:
            raise _procedure_error(exc, "订单创建失败，请稍后重试") from exc
        if not result or not result.get("success") or not result.get("orderId"):
            raise ValueError("订单创建失败，请稍后重试")
        order_id = int(result["orderId"])
        created = one(cursor.execute("SELECT * FROM orders WHERE order_id = ?", order_id))
        if not created:
            raise ValueError("订单创建失败，请稍后重试")
        return {
            "orderId": order_id,
            "orderNo": result["orderNo"],
            "totalAmount": float(created["total_amount"]),
            "discountAmount": float(created["discount_amount"]),
            "actualAmount": float(created["actual_amount"]),
        }


def pay(user_id: int, order_id: int, payment_method: str) -> dict[str, Any]:
    with get_conn() as conn:
        cursor = conn.cursor()
        if hasattr(cursor, "timeout"):
            cursor.timeout = 8
        cursor.execute("SET LOCK_TIMEOUT 8000")
        order = one(
            cursor.execute(
                "SELECT * FROM orders WITH (UPDLOCK, HOLDLOCK) WHERE order_id = ? AND user_id = ?",
                order_id,
                user_id,
            )
        )
        if not order:
            raise ValueError("订单不存在")
        if order["order_status"] == "已完成" and order["payment_status"] == "已支付":
            return _payment_success(conn, order)
        if order["order_status"] != "待支付" or order["payment_status"] != "未支付":
            raise ValueError("订单状态异常，无法支付")

        items = many(
            cursor.execute(
                """
                SELECT oi.book_item_id AS bookItemId, oi.quantity,
                       b.stock, b.locked_stock AS lockedStock
                FROM order_items oi
                JOIN book_items b WITH (UPDLOCK, HOLDLOCK) ON b.book_item_id = oi.book_item_id
                WHERE oi.order_id = ?
                """,
                order_id,
            )
        )
        if not items:
            raise ValueError("订单明细为空，无法支付")
        if any(int(item["stock"] or 0) < int(item["quantity"]) for item in items):
            raise ValueError("部分商品库存不足，无法支付")

        try:
            result = procedure_result(
                cursor,
                """
                DECLARE @success BIT;
                EXEC sp_PayOrder
                    @order_id = ?, @payment_method = ?, @success = @success OUTPUT;
                SELECT @success AS success;
                """,
                order_id,
                _payment_method_name(payment_method),
            )
        except pyodbc.Error as exc:
            raise _procedure_error(exc, "支付失败，请重新尝试") from exc
        if not result or not result.get("success"):
            raise ValueError("支付失败，请重新尝试")
        payment = one(
            cursor.execute(
                "SELECT TOP 1 payment_no AS paymentNo FROM payment_records WHERE order_id = ? ORDER BY payment_id DESC",
                order_id,
            )
        )
        updated = one(cursor.execute("SELECT * FROM orders WHERE order_id = ?", order_id))
        return {
            "paymentStatus": "success",
            "paymentNo": (payment or {}).get("paymentNo") or "",
            "order": public_order(conn, updated),
        }


def _payment_success(conn: Any, order: dict[str, Any]) -> dict[str, Any]:
    payment = one(
        conn.cursor().execute(
            "SELECT TOP 1 payment_no AS paymentNo FROM payment_records WHERE order_id = ? ORDER BY payment_id DESC",
            order["order_id"],
        )
    )
    return {
        "paymentStatus": "success",
        "paymentNo": (payment or {}).get("paymentNo") or "",
        "order": public_order(conn, order),
    }


def _order_items(conn: Any, order_id: int) -> list[dict[str, Any]]:
    rows = many(
        conn.cursor().execute(
            """
            SELECT oi.book_item_id AS bookItemId, bi.book_name AS bookName, bi.cover_image AS cover,
                   oi.unit_price AS unitPrice, oi.quantity,
                   b.store_id AS storeId, s.store_name AS storeName
            FROM order_items oi
            JOIN book_items b ON b.book_item_id = oi.book_item_id
            JOIN book_infos bi ON bi.book_info_id = b.book_info_id
            JOIN stores s ON s.store_id = b.store_id
            WHERE oi.order_id = ?
            """,
            order_id,
        )
    )
    for row in rows:
        row["cover"] = row.get("cover") or "📘"
    return rows


def _points_earned(conn: Any, row: dict[str, Any]) -> int:
    if row["payment_status"] != "已支付":
        return 0
    return int(
        conn.cursor().execute(
            """
            SELECT COALESCE(SUM(points_change), 0)
            FROM points_records
            WHERE user_id = ? AND related_id = ? AND reason = N'购买'
            """,
            row["user_id"],
            row["order_id"],
        ).fetchval()
        or 0
    )


def public_order(conn: Any, row: dict[str, Any]) -> dict[str, Any]:
    order_to_front = {"待支付": "pending_payment", "已完成": "completed", "已取消": "cancelled", "已退款": "refunded"}
    pay_to_front = {"未支付": "unpaid", "已支付": "paid", "已退款": "refunded"}
    refund_status = conn.cursor().execute(
        "SELECT TOP 1 refund_status FROM refund_records WHERE order_id = ? ORDER BY refund_id DESC",
        row["order_id"],
    ).fetchval()
    order_status = "refunding" if refund_status == "处理中" else order_to_front.get(row["order_status"], row["order_status"])
    status_label = "退款中" if refund_status == "处理中" else row["order_status"]
    return {
        "orderId": row["order_id"],
        "orderNo": row["order_no"],
        "orderStatus": order_status,
        "paymentStatus": pay_to_front.get(row["payment_status"], row["payment_status"]),
        "statusLabel": status_label,
        "totalAmount": float(row["total_amount"]),
        "discountAmount": float(row["discount_amount"]),
        "actualAmount": float(row["actual_amount"]),
        "pointsEarned": _points_earned(conn, row),
        "createdTime": str(row["created_time"]),
        "receiverName": row["receiver_name"],
        "receiverPhone": row["receiver_phone"],
        "receiverAddress": row["receiver_addr"],
        "items": _order_items(conn, row["order_id"]),
    }


def list_orders(user_id: int, status: str = "all") -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = many(conn.cursor().execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_time DESC", user_id))
        public = [public_order(conn, row) for row in rows]
        return public if status == "all" else [order for order in public if order["orderStatus"] == status]


def get_detail(user_id: int, order_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = one(conn.cursor().execute("SELECT * FROM orders WHERE order_id = ? AND user_id = ?", order_id, user_id))
        return public_order(conn, row) if row else None


def cancel(user_id: int, order_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        cursor = conn.cursor()
        order = one(
            cursor.execute(
                "SELECT * FROM orders WITH (UPDLOCK, HOLDLOCK) WHERE order_id = ? AND user_id = ?",
                order_id,
                user_id,
            )
        )
        if not order:
            raise ValueError("订单不存在")
        if order["order_status"] != "待支付" or order["payment_status"] != "未支付":
            raise ValueError("仅待支付订单可以取消")
        cursor.execute("UPDATE orders SET order_status = N'已取消' WHERE order_id = ?", order_id)
        cursor.execute(
            """
            UPDATE b
            SET locked_stock = CASE WHEN locked_stock >= oi.quantity THEN locked_stock - oi.quantity ELSE 0 END
            FROM book_items b
            JOIN order_items oi ON oi.book_item_id = b.book_item_id
            WHERE oi.order_id = ?
            """,
            order_id,
        )
        cursor.execute(
            """
            UPDATE user_coupons
            SET status = N'未使用', used_time = NULL, order_id = NULL
            WHERE order_id = ? AND status = N'已使用'
            """,
            order_id,
        )
        updated = one(cursor.execute("SELECT * FROM orders WHERE order_id = ?", order_id))
        return public_order(conn, updated)


def refund(user_id: int, order_id: int, reason: str | None = None) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        order = one(
            cursor.execute(
                "SELECT * FROM orders WITH (UPDLOCK, HOLDLOCK) WHERE order_id = ? AND user_id = ?",
                order_id,
                user_id,
            )
        )
        if not order:
            raise ValueError("订单不存在")
        if order["order_status"] != "已完成" or order["payment_status"] != "已支付":
            raise ValueError("仅已支付订单可以申请退款")
        existing = one(
            cursor.execute(
                "SELECT TOP 1 refund_status FROM refund_records WHERE order_id = ? ORDER BY refund_id DESC",
                order_id,
            )
        )
        if existing and existing["refund_status"] in {"处理中", "已退款"}:
            raise ValueError("该订单已有退款申请")
        payment = one(
            cursor.execute(
                "SELECT TOP 1 * FROM payment_records WHERE order_id = ? AND payment_status = N'已支付' ORDER BY payment_id DESC",
                order_id,
            )
        )
        if not payment:
            raise ValueError("未找到有效支付记录")
        cursor.execute(
            """
            INSERT INTO refund_records(
                order_id, user_id, payment_id, refund_no, refund_amount, refund_reason, refund_status
            )
            VALUES (?, ?, ?, ?, ?, ?, N'处理中')
            """,
            order_id,
            user_id,
            payment["payment_id"],
            _next_no(cursor, "REF"),
            payment["amount"],
            reason,
        )


def list_admin_orders(store_id: int | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        if store_id:
            rows = many(
                conn.cursor().execute(
                    """
                    SELECT DISTINCT o.*
                    FROM orders o
                    JOIN order_items oi ON oi.order_id = o.order_id
                    JOIN book_items b ON b.book_item_id = oi.book_item_id
                    WHERE b.store_id = ?
                    ORDER BY o.created_time DESC
                    """,
                    store_id,
                )
            )
        else:
            rows = many(conn.cursor().execute("SELECT * FROM orders ORDER BY created_time DESC"))
        return [public_order(conn, row) for row in rows]


def _require_order_scope(cursor: Any, order_id: int, store_id: int | None) -> None:
    if not cursor.execute("SELECT 1 FROM orders WHERE order_id = ?", order_id).fetchone():
        raise ValueError("订单不存在")
    if store_id is not None and not cursor.execute(
        """
        SELECT 1
        FROM order_items oi
        JOIN book_items b ON b.book_item_id = oi.book_item_id
        WHERE oi.order_id = ? AND b.store_id = ?
        """,
        order_id,
        store_id,
    ).fetchone():
        raise ValueError("无权限处理其他店铺的订单")


def update_status(order_id: int, db_status: str, store_id: int | None = None) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        _require_order_scope(cursor, order_id, store_id)
        cursor.execute("UPDATE orders SET order_status = ? WHERE order_id = ?", db_status, order_id)


def handle_refund(order_id: int, approved: bool, store_id: int | None = None) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        _require_order_scope(cursor, order_id, store_id)
        refund_row = one(
            cursor.execute(
                """
                SELECT TOP 1 * FROM refund_records WITH (UPDLOCK, HOLDLOCK)
                WHERE order_id = ? ORDER BY refund_id DESC
                """,
                order_id,
            )
        )
        order = one(cursor.execute("SELECT * FROM orders WITH (UPDLOCK, HOLDLOCK) WHERE order_id = ?", order_id))
        if not order:
            raise ValueError("订单不存在")
        if approved and order["order_status"] == "已退款":
            return
        if not refund_row or refund_row["refund_status"] != "处理中":
            raise ValueError("未找到待处理的退款申请")
        if not approved:
            cursor.execute("UPDATE refund_records SET refund_status = N'已拒绝' WHERE refund_id = ?", refund_row["refund_id"])
            return
        if order["order_status"] != "已完成" or order["payment_status"] != "已支付":
            raise ValueError("订单当前状态无法退款")
        try:
            result = procedure_result(
                cursor,
                """
                DECLARE @success BIT;
                EXEC sp_RefundOrder
                    @order_id = ?, @refund_id = ?, @success = @success OUTPUT;
                SELECT @success AS success;
                """,
                order_id,
                refund_row["refund_id"],
            )
        except pyodbc.Error as exc:
            raise _procedure_error(exc, "退款处理失败，请稍后重试") from exc
        if not result or not result.get("success"):
            raise ValueError("退款处理失败，请稍后重试")
