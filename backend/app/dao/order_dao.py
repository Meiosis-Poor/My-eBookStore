"""Order data access helpers without stored procedure dependencies."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from ..db import get_conn, many, one


def _order_no(prefix: str) -> str:
    return prefix + datetime.now().strftime("%Y%m%d%H%M%S%f")


def _payment_method_name(method: str | None) -> str:
    mapping = {
        "alipay": "支付宝",
        "wechat": "微信支付",
        "card": "银行卡",
    }
    method = (method or "").strip()
    return mapping.get(method, method or "支付宝")


def create_from_cart(
    user_id: int,
    book_item_ids: list[int],
    receiver_name: str,
    receiver_phone: str,
    receiver_address: str,
    discount_amount: float = 0.0,
    coupon_id: Optional[int] = None,
) -> dict[str, Any]:
    if not book_item_ids:
        raise ValueError("购物车中暂无商品")
    placeholders = ",".join("?" for _ in book_item_ids)
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                f"""
                SELECT c.book_item_id AS bookItemId, c.quantity, b.price, b.stock
                FROM cart_items c
                JOIN book_items b ON b.book_item_id = c.book_item_id
                WHERE c.user_id = ? AND c.book_item_id IN ({placeholders})
                """,
                user_id,
                *book_item_ids,
            )
        )
        if len(rows) != len(set(book_item_ids)):
            raise ValueError("购物车商品不存在")

        total = 0.0
        for row in rows:
            if int(row["quantity"]) > int(row["stock"]):
                raise ValueError("部分商品库存不足，请修改后重新提交订单")
            total += float(row["price"]) * int(row["quantity"])
        discount = 0.0
        if coupon_id:
            coupon = one(
                conn.cursor().execute(
                    """
                    SELECT c.amount, c.min_amount
                    FROM user_coupons uc
                    JOIN coupons c ON c.coupon_id = uc.coupon_id
                    WHERE uc.user_id = ? AND c.coupon_id = ? AND uc.status = N'未使用'
                      AND c.status = N'启用'
                      AND c.valid_start <= SYSDATETIME() AND c.valid_end >= SYSDATETIME()
                    """,
                    user_id,
                    coupon_id,
                )
            )
            if not coupon:
                raise ValueError("代金券不可用")
            if total < float(coupon["min_amount"] or 0):
                raise ValueError("订单金额未达到代金券使用门槛")
            discount = min(float(coupon["amount"] or 0), total)
        else:
            discount = min(float(discount_amount or 0), total)
        actual = max(0.0, total - discount)
        order_no = _order_no("NO")
        order_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO orders(user_id, order_no, total_amount, discount_amount, actual_amount,
                                   receiver_name, receiver_phone, receiver_addr)
                OUTPUT INSERTED.order_id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                user_id,
                order_no,
                total,
                discount,
                actual,
                receiver_name,
                receiver_phone,
                receiver_address,
            )
            .fetchone()[0]
        )
        for row in rows:
            subtotal = float(row["price"]) * int(row["quantity"])
            conn.cursor().execute(
                "INSERT INTO order_items(order_id, book_item_id, quantity, unit_price, subtotal) VALUES (?, ?, ?, ?, ?)",
                order_id,
                row["bookItemId"],
                row["quantity"],
                row["price"],
                subtotal,
            )
        if coupon_id:
            conn.cursor().execute(
                "UPDATE user_coupons SET status = N'已使用', used_time = SYSDATETIME(), order_id = ? WHERE user_id = ? AND coupon_id = ?",
                order_id,
                user_id,
                coupon_id,
            )
        return {
            "orderId": order_id,
            "orderNo": order_no,
            "totalAmount": total,
            "discountAmount": discount,
            "actualAmount": actual,
        }


def pay(user_id: int, order_id: int, payment_method: str) -> dict[str, Any]:
    with get_conn() as conn:
        order = one(conn.cursor().execute("SELECT * FROM orders WHERE order_id = ? AND user_id = ?", order_id, user_id))
        if not order:
            raise ValueError("订单不存在")
        if order["order_status"] != "待支付" or order["payment_status"] != "未支付":
            raise ValueError("订单状态异常，无法支付")
        items = many(conn.cursor().execute("SELECT book_item_id AS bookItemId, quantity FROM order_items WHERE order_id = ?", order_id))
        if not items:
            raise ValueError("订单明细为空，无法支付")
        for item in items:
            stock = conn.cursor().execute("SELECT stock FROM book_items WHERE book_item_id = ?", item["bookItemId"]).fetchval()
            if int(stock or 0) < int(item["quantity"]):
                raise ValueError("部分商品库存不足，请重新下单")
        payment_no = _order_no("PAY")
        payment_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO payment_records(order_id, user_id, payment_no, amount, payment_method, payment_status)
                OUTPUT INSERTED.payment_id
                VALUES (?, ?, ?, ?, ?, N'未支付')
                """,
                order_id,
                user_id,
                payment_no,
                order["actual_amount"],
                _payment_method_name(payment_method),
            )
            .fetchone()[0]
        )
        for item in items:
            conn.cursor().execute(
                "UPDATE book_items SET stock = stock - ?, sales_count = sales_count + ? WHERE book_item_id = ?",
                item["quantity"],
                item["quantity"],
                item["bookItemId"],
            )
            conn.cursor().execute("DELETE FROM cart_items WHERE user_id = ? AND book_item_id = ?", user_id, item["bookItemId"])
        conn.cursor().execute(
            "UPDATE orders SET order_status = N'已完成', payment_status = N'已支付', paid_time = SYSDATETIME() WHERE order_id = ?",
            order_id,
        )
        points = max(1, int(float(order["actual_amount"] or 0)))
        conn.cursor().execute(
            """
            UPDATE ordinary_users
            SET total_points = total_points + ?, available_points = available_points + ?,
                level = CASE
                    WHEN total_points + ? >= 2000 THEN 4
                    WHEN total_points + ? >= 1000 THEN 3
                    WHEN total_points + ? >= 500 THEN 2
                    ELSE level
                END
            WHERE user_id = ?
            """,
            points,
            points,
            points,
            points,
            points,
            user_id,
        )
        conn.cursor().execute(
            "INSERT INTO points_records(user_id, points_change, reason, related_id) VALUES (?, ?, N'购买', ?)",
            user_id,
            points,
            order_id,
        )
        conn.cursor().execute(
            "UPDATE payment_records SET payment_status = N'已支付', paid_time = SYSDATETIME() WHERE payment_id = ?",
            payment_id,
        )
        updated = one(conn.cursor().execute("SELECT * FROM orders WHERE order_id = ?", order_id))
        return {"paymentStatus": "success", "paymentNo": payment_no, "order": public_order(conn, updated)}


def _order_items(conn, order_id: int) -> list[dict[str, Any]]:
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


def public_order(conn, row: dict[str, Any]) -> dict[str, Any]:
    order_to_front = {"待支付": "pending_payment", "已完成": "completed", "已取消": "cancelled", "已退款": "refunded"}
    pay_to_front = {"未支付": "unpaid", "已支付": "paid", "已退款": "refunded"}
    return {
        "orderId": row["order_id"],
        "orderNo": row["order_no"],
        "orderStatus": order_to_front.get(row["order_status"], row["order_status"]),
        "paymentStatus": pay_to_front.get(row["payment_status"], row["payment_status"]),
        "statusLabel": row["order_status"],
        "totalAmount": float(row["total_amount"]),
        "discountAmount": float(row["discount_amount"]),
        "actualAmount": float(row["actual_amount"]),
        "createdTime": str(row["created_time"]),
        "receiverName": row["receiver_name"],
        "receiverPhone": row["receiver_phone"],
        "receiverAddress": row["receiver_addr"],
        "items": _order_items(conn, row["order_id"]),
    }


def list_orders(user_id: int, status: str = "all") -> list[dict[str, Any]]:
    db_status = {"pending_payment": "待支付", "completed": "已完成", "cancelled": "已取消", "refunded": "已退款"}.get(status)
    where = "WHERE user_id = ?"
    params: list[Any] = [user_id]
    if db_status:
        where += " AND order_status = ?"
        params.append(db_status)
    with get_conn() as conn:
        rows = many(conn.cursor().execute(f"SELECT * FROM orders {where} ORDER BY created_time DESC", *params))
        return [public_order(conn, row) for row in rows]


def get_detail(user_id: int, order_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = one(conn.cursor().execute("SELECT * FROM orders WHERE order_id = ? AND user_id = ?", order_id, user_id))
        return public_order(conn, row) if row else None


def cancel(user_id: int, order_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        order = one(conn.cursor().execute("SELECT * FROM orders WHERE order_id = ? AND user_id = ?", order_id, user_id))
        if not order:
            raise ValueError("订单不存在")
        if order["order_status"] != "待支付" or order["payment_status"] != "未支付":
            raise ValueError("仅待支付订单可以取消")
        conn.cursor().execute(
            "UPDATE orders SET order_status = N'已取消' WHERE order_id = ? AND user_id = ?",
            order_id,
            user_id,
        )
        updated = one(conn.cursor().execute("SELECT * FROM orders WHERE order_id = ?", order_id))
        return public_order(conn, updated)


def refund(user_id: int, order_id: int, reason: str | None = None) -> None:
    with get_conn() as conn:
        payment = one(conn.cursor().execute("SELECT TOP 1 * FROM payment_records WHERE order_id = ? ORDER BY payment_id DESC", order_id))
        if not payment:
            raise ValueError("未找到支付记录")
        conn.cursor().execute(
            """
            INSERT INTO refund_records(order_id, user_id, payment_id, refund_no, refund_amount, refund_reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            order_id,
            user_id,
            payment["payment_id"],
            _order_no("REF"),
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


def update_status(order_id: int, db_status: str) -> None:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE orders SET order_status = ? WHERE order_id = ?", db_status, order_id)


def handle_refund(order_id: int, approved: bool) -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE refund_records SET refund_status = ?, refund_time = CASE WHEN ? = 1 THEN SYSDATETIME() ELSE refund_time END WHERE order_id = ?",
            "已退款" if approved else "已拒绝",
            1 if approved else 0,
            order_id,
        )
        if approved:
            conn.cursor().execute("UPDATE orders SET order_status = N'已退款', payment_status = N'已退款' WHERE order_id = ?", order_id)
