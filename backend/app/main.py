from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, FastAPI, Query
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import get_conn, many, one
from .embedding import cosine_distance, dumps as dump_embedding, embed_text, loads as load_embedding
from .response import fail, http_exception_handler, ok
from .security import (
    DB_TO_ROLE,
    ROLE_TO_DB,
    create_token,
    current_user,
    hash_password,
    optional_user,
    public_user,
    require_roles,
    verify_password,
)


app = FastAPI(title=settings.app_name)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api = APIRouter(prefix=settings.api_prefix)


STATUS_TO_DB = {"active": "正常", "banned": "封禁", "completed": "已完成", "cancelled": "已取消", "refunded": "已退款"}
ORDER_TO_FRONT = {"待支付": "pending_payment", "已完成": "completed", "已取消": "cancelled", "已退款": "refunded"}
PAY_TO_FRONT = {"未支付": "unpaid", "已支付": "paid", "已退款": "refunded"}
COUPON_STATUS = {"unused": "未使用", "used": "已使用", "expired": "已过期"}
COUPON_TYPE_TO_FRONT = {"平台券": "platform", "店铺券": "store"}
REWARD_TYPE_TO_FRONT = {"实物": "physical", "代金券": "coupon", "虚拟商品": "virtual"}


def now_no() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S%f")


def page_slice(items: list[dict[str, Any]], page: int, page_size: int) -> list[dict[str, Any]]:
    start = max(page - 1, 0) * page_size
    return items[start : start + page_size]


def current_store_id(user: dict[str, Any]) -> int | None:
    return user.get("store_id")


def book_select_sql(where: str = "", order: str = "") -> str:
    return f"""
        SELECT
            bi.book_info_id AS bookInfoId,
            b.book_item_id AS bookItemId,
            bi.book_name AS bookName,
            bi.author AS author,
            bi.publisher AS publisher,
            bi.ISBN AS isbn,
            bi.publish_date AS publishDate,
            bi.description AS description,
            bi.cover_image AS cover,
            bi.embedding AS embedding,
            bc.category_id AS categoryId,
            bc.category_name AS categoryName,
            b.store_id AS storeId,
            s.store_name AS storeName,
            b.price AS price,
            b.price AS originPrice,
            b.stock AS stock,
            b.locked_stock AS lockedStock,
            b.sales_count AS salesCount,
            b.status AS itemStatus,
            bi.status AS infoStatus
        FROM book_items b
        JOIN book_infos bi ON bi.book_info_id = b.book_info_id
        JOIN book_categories bc ON bc.category_id = bi.category_id
        JOIN stores s ON s.store_id = b.store_id
        WHERE bi.status = N'正常' AND b.status = N'在售' AND s.status = N'正常'
        {where}
        {order}
    """


def normalize_book(row: dict[str, Any]) -> dict[str, Any]:
    row = dict(row)
    row.pop("embedding", None)
    row["cover"] = row.get("cover") or "📘"
    if row.get("publishDate") is not None:
        row["publishDate"] = str(row["publishDate"])
    row["price"] = float(row.get("price") or 0)
    row["originPrice"] = float(row.get("originPrice") or row["price"])
    row["stock"] = int(row.get("stock") or 0)
    row["salesCount"] = int(row.get("salesCount") or 0)
    return row


def all_books(conn, where: str = "", params: tuple[Any, ...] = (), order: str = "") -> list[dict[str, Any]]:
    return many(conn.cursor().execute(book_select_sql(where, order), *params))


def book_detail(conn, book_item_id: int) -> dict[str, Any] | None:
    return one(conn.cursor().execute(book_select_sql("AND b.book_item_id = ?"), book_item_id))


def sort_by_embedding(books: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    target = embed_text(text)

    def distance(book: dict[str, Any]) -> float:
        vec = load_embedding(book.get("embedding")) or embed_text(book.get("bookName") or "")
        return cosine_distance(target, vec)

    return sorted(books, key=lambda b: (distance(b), -(b.get("salesCount") or 0)))


def hot_books(conn, limit: int) -> list[dict[str, Any]]:
    rows = all_books(conn, order="ORDER BY b.sales_count DESC, b.book_item_id DESC")
    return [normalize_book(row) for row in rows[:limit]]


def guess_books(conn, user_id: int | None, limit: int) -> list[dict[str, Any]]:
    if not user_id:
        return hot_books(conn, limit)
    try:
        searches = many(
            conn.cursor().execute(
                """
                SELECT TOP 5 keyword, keyword_embedding AS embedding
                FROM search_history
                WHERE user_id = ?
                ORDER BY created_time DESC
                """,
                user_id,
            )
        )
    except Exception:
        searches = []
    if not searches:
        return hot_books(conn, limit)

    vectors = [load_embedding(s.get("embedding")) or embed_text(s["keyword"]) for s in searches]
    best_by_info: dict[int, dict[str, Any]] = {}
    for row in all_books(conn):
        current = best_by_info.get(row["bookInfoId"])
        if current is None or (row.get("salesCount") or 0) > (current.get("salesCount") or 0):
            best_by_info[row["bookInfoId"]] = row

    def total_distance(book: dict[str, Any]) -> float:
        vec = load_embedding(book.get("embedding")) or embed_text(book.get("bookName") or "")
        return sum(cosine_distance(vec, keyword_vec) for keyword_vec in vectors)

    ranked = sorted(best_by_info.values(), key=lambda b: (total_distance(b), -(b.get("salesCount") or 0)))
    return [normalize_book(row) for row in ranked[:limit]]


def require_store_owner(user: dict[str, Any], store_id: int) -> None:
    if DB_TO_ROLE.get(user["user_type"]) != "platform_admin" and user.get("store_id") != store_id:
        fail("无权限维护该店铺", 403)


def user_coupon_discount(conn, user_id: int, coupon_id: int | None, total: float) -> float:
    if not coupon_id:
        return 0.0
    row = one(
        conn.cursor().execute(
            """
            SELECT uc.user_coupon_id, c.amount, c.min_amount
            FROM user_coupons uc
            JOIN coupons c ON c.coupon_id = uc.coupon_id
            WHERE uc.user_id = ? AND c.coupon_id = ? AND uc.status = N'未使用'
              AND c.status = N'启用' AND c.valid_start <= SYSDATETIME() AND c.valid_end >= SYSDATETIME()
            """,
            user_id,
            coupon_id,
        )
    )
    if not row:
        fail("代金券不可用")
    if total < float(row["min_amount"] or 0):
        fail("订单金额未达到代金券使用门槛")
    return min(float(row["amount"] or 0), total)


@api.get("/health")
def health() -> dict[str, Any]:
    return ok({"status": "ok", "time": datetime.now().isoformat(timespec="seconds")})


@api.post("/auth/register/user")
def register_user(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    user_name = (payload.get("userName") or "").strip()
    password = payload.get("password") or ""
    nickname = (payload.get("nickname") or user_name).strip()
    if len(user_name) < 3 or len(password) < 6:
        fail("用户名或密码格式不正确")
    with get_conn() as conn:
        if conn.cursor().execute("SELECT 1 FROM users WHERE user_name = ?", user_name).fetchone():
            fail("用户名已被占用")
        row = conn.cursor().execute(
            """
            INSERT INTO users(user_name, password_hash, phone, email, user_type)
            OUTPUT INSERTED.user_id
            VALUES (?, ?, ?, ?, N'普通用户')
            """,
            user_name,
            hash_password(password),
            payload.get("phone"),
            payload.get("email"),
        ).fetchone()
        user_id = int(row[0])
        conn.cursor().execute(
            "INSERT INTO ordinary_users(user_id, nickname) VALUES (?, ?)",
            user_id,
            nickname or user_name,
        )
    return ok({"userId": user_id})


@api.post("/auth/register/seller")
def register_seller(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    user_name = (payload.get("userName") or "").strip()
    password = payload.get("password") or ""
    store_name = (payload.get("storeName") or "").strip()
    if len(user_name) < 3 or len(password) < 6 or not store_name:
        fail("注册信息不完整或格式不正确")
    with get_conn() as conn:
        if conn.cursor().execute("SELECT 1 FROM users WHERE user_name = ?", user_name).fetchone():
            fail("用户名已被占用")
        if conn.cursor().execute("SELECT 1 FROM stores WHERE store_name = ?", store_name).fetchone():
            fail("店铺名已被占用")
        user_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO users(user_name, password_hash, phone, email, user_type)
                OUTPUT INSERTED.user_id
                VALUES (?, ?, ?, ?, N'书店管理员')
                """,
                user_name,
                hash_password(password),
                payload.get("phone"),
                payload.get("email"),
            )
            .fetchone()[0]
        )
        conn.cursor().execute("INSERT INTO store_admins(user_id, admin_name) VALUES (?, ?)", user_id, payload.get("nickname") or user_name)
        store_id = int(
            conn.cursor()
            .execute(
                "INSERT INTO stores(store_name, user_id, description) OUTPUT INSERTED.store_id VALUES (?, ?, ?)",
                store_name,
                user_id,
                payload.get("description") or "",
            )
            .fetchone()[0]
        )
    return ok({"userId": user_id, "storeId": store_id})


@api.post("/auth/login")
def login(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    role = payload.get("role") or "customer"
    user_type = ROLE_TO_DB.get(role)
    if not user_type:
        fail("账号类型不正确")
    with get_conn() as conn:
        user = one(
            conn.cursor().execute(
                """
                SELECT u.*, ou.nickname, ou.level, ou.total_points, ou.available_points, ou.continuous_checkin_days,
                       s.store_id, s.store_name
                FROM users u
                LEFT JOIN ordinary_users ou ON ou.user_id = u.user_id
                LEFT JOIN stores s ON s.user_id = u.user_id
                WHERE u.user_name = ?
                """,
                payload.get("userName"),
            )
        )
    if not user or not verify_password(payload.get("password") or "", user["password_hash"]):
        fail("用户名或密码错误", 401)
    if user["user_type"] != user_type:
        fail("账号类型与用户身份不匹配", 403)
    if user["status"] == "封禁":
        fail("当前账号已被禁用，请联系管理员", 403)
    return ok({"token": create_token(user), "user": public_user(user)})


@api.post("/auth/logout")
def logout() -> dict[str, Any]:
    return ok({"ok": True})


@api.get("/categories")
def categories() -> dict[str, Any]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                "SELECT category_id AS categoryId, category_name AS categoryName FROM book_categories WHERE status = N'启用' ORDER BY category_id"
            )
        )
    return ok(rows)


@api.get("/books")
def list_books(
    keyword: Optional[str] = None,
    categoryId: Optional[int] = None,
    sort: str = "default",
    page: int = 1,
    pageSize: int = 12,
    inStockOnly: Optional[int] = None,
    user: Optional[dict[str, Any]] = Depends(optional_user),
) -> dict[str, Any]:
    where = []
    params: list[Any] = []
    if categoryId:
        where.append("AND bc.category_id = ?")
        params.append(categoryId)
    if inStockOnly:
        where.append("AND b.stock > 0")
    if keyword and sort != "default":
        where.append("AND (bi.book_name LIKE ? OR bi.author LIKE ? OR bi.ISBN LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like])
    order = ""
    if sort == "sales":
        order = "ORDER BY b.sales_count DESC"
    elif sort == "price_asc":
        order = "ORDER BY b.price ASC"
    elif sort == "price_desc":
        order = "ORDER BY b.price DESC"
    with get_conn() as conn:
        rows = all_books(conn, " ".join(where), tuple(params), order)
        if keyword and sort == "default":
            rows = sort_by_embedding(rows, keyword)
            if user:
                try:
                    conn.cursor().execute(
                        "INSERT INTO search_history(user_id, keyword, keyword_embedding) VALUES (?, ?, ?)",
                        user["user_id"],
                        keyword,
                        dump_embedding(embed_text(keyword)),
                    )
                except Exception:
                    pass
    items = [normalize_book(row) for row in page_slice(rows, page, pageSize)]
    return ok({"list": items, "total": len(rows)})


@api.get("/books/recommended")
def recommended_books(
    limit: int = 10,
    type: str = Query("guess"),
    user: Optional[dict[str, Any]] = Depends(optional_user),
) -> dict[str, Any]:
    with get_conn() as conn:
        if type == "hot":
            rows = hot_books(conn, limit)
        else:
            rows = guess_books(conn, user["user_id"] if user else None, limit)
    return ok(rows)


@api.get("/books/{bookItemId}")
def get_book(bookItemId: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = book_detail(conn, bookItemId)
        if not row:
            fail("图书不存在", 404)
        book = normalize_book(row)
        avg = conn.cursor().execute("SELECT AVG(CAST(rating AS FLOAT)) FROM reviews WHERE book_item_id = ?", bookItemId).fetchval()
        reviews = many(
            conn.cursor().execute(
                """
                SELECT r.review_id AS reviewId, r.rating, r.content, r.created_time AS createdTime, u.user_name AS userName
                FROM reviews r JOIN users u ON u.user_id = r.user_id
                WHERE r.book_item_id = ?
                ORDER BY r.created_time DESC
                """,
                bookItemId,
            )
        )
        book["averageRating"] = round(float(avg or 0), 1)
        book["reviews"] = reviews
    return ok(book)


@api.get("/books/{bookItemId}/similar")
def similar_books(bookItemId: int) -> dict[str, Any]:
    with get_conn() as conn:
        book = book_detail(conn, bookItemId)
        if not book:
            fail("图书不存在", 404)
        rows = all_books(
            conn,
            "AND bc.category_id = ? AND b.store_id = ? AND b.book_item_id <> ?",
            (book["categoryId"], book["storeId"], bookItemId),
            "ORDER BY b.sales_count DESC",
        )
    return ok([normalize_book(row) for row in rows[:3]])


@api.get("/stores/{storeId}")
def store_detail(storeId: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = one(
            conn.cursor().execute(
                """
                SELECT s.store_id AS storeId, s.store_name AS storeName, s.description,
                       s.created_time AS createdTime, COUNT(b.book_item_id) AS bookCount,
                       COALESCE(SUM(b.sales_count), 0) AS salesCount
                FROM stores s
                LEFT JOIN book_items b ON b.store_id = s.store_id AND b.status = N'在售'
                WHERE s.store_id = ?
                GROUP BY s.store_id, s.store_name, s.description, s.created_time
                """,
                storeId,
            )
        )
    if not row:
        fail("店铺不存在", 404)
    return ok(row)


@api.get("/stores/{storeId}/books")
def store_books(storeId: int, sort: str = "default", page: int = 1, pageSize: int = 24) -> dict[str, Any]:
    order = {"sales": "ORDER BY b.sales_count DESC", "price_asc": "ORDER BY b.price ASC", "price_desc": "ORDER BY b.price DESC"}.get(sort, "")
    with get_conn() as conn:
        rows = all_books(conn, "AND b.store_id = ?", (storeId,), order)
    return ok({"list": [normalize_book(row) for row in page_slice(rows, page, pageSize)], "total": len(rows)})


@api.put("/stores/{storeId}")
def update_store(storeId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    require_store_owner(user, storeId)
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE stores SET store_name = COALESCE(?, store_name), description = COALESCE(?, description) WHERE store_id = ?",
            payload.get("storeName"),
            payload.get("description"),
            storeId,
        )
    return ok({"ok": True})


@api.get("/cart")
def cart_list(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                f"""
                SELECT c.cart_item_id AS cartItemId, c.book_item_id AS bookItemId, c.quantity,
                       q.bookInfoId, q.bookName, q.author, q.publisher, q.isbn, q.publishDate,
                       q.description, q.cover, q.categoryId, q.categoryName, q.storeId, q.storeName,
                       q.price, q.originPrice, q.stock, q.salesCount
                FROM cart_items c
                JOIN ({book_select_sql()}) q ON q.bookItemId = c.book_item_id
                WHERE c.user_id = ?
                ORDER BY c.add_time DESC
                """,
                user["user_id"],
            )
        )
    return ok([{**row, "book": normalize_book(row)} for row in rows])


@api.post("/cart")
def cart_add(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    book_item_id = int(payload.get("bookItemId"))
    quantity = max(int(payload.get("quantity") or 1), 1)
    with get_conn() as conn:
        row = one(conn.cursor().execute("SELECT stock FROM book_items WHERE book_item_id = ? AND status = N'在售'", book_item_id))
        if not row:
            fail("图书不存在或已下架", 404)
        if quantity > int(row["stock"] or 0):
            fail("当前图书库存不足")
        existing = one(conn.cursor().execute("SELECT cart_item_id, quantity FROM cart_items WHERE user_id = ? AND book_item_id = ?", user["user_id"], book_item_id))
        if existing:
            new_qty = int(existing["quantity"]) + quantity
            if new_qty > int(row["stock"] or 0):
                fail("当前图书库存不足")
            conn.cursor().execute("UPDATE cart_items SET quantity = ? WHERE cart_item_id = ?", new_qty, existing["cart_item_id"])
        else:
            conn.cursor().execute("INSERT INTO cart_items(user_id, book_item_id, quantity) VALUES (?, ?, ?)", user["user_id"], book_item_id, quantity)
    return ok({"ok": True})


@api.put("/cart/{bookItemId}")
def cart_update(bookItemId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    quantity = max(int(payload.get("quantity") or 1), 1)
    with get_conn() as conn:
        stock = conn.cursor().execute("SELECT stock FROM book_items WHERE book_item_id = ?", bookItemId).fetchval()
        if stock is None:
            fail("图书不存在", 404)
        if quantity > int(stock):
            fail("当前图书库存不足")
        conn.cursor().execute("UPDATE cart_items SET quantity = ? WHERE user_id = ? AND book_item_id = ?", quantity, user["user_id"], bookItemId)
    return ok({"ok": True})


@api.delete("/cart/{bookItemId}")
def cart_remove(bookItemId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute("DELETE FROM cart_items WHERE user_id = ? AND book_item_id = ?", user["user_id"], bookItemId)
    return ok({"ok": True})


@api.get("/addresses")
def address_list(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT address_id AS addressId, receiver_name AS recipientName, phone,
                       CONCAT(province, city, district, detail) AS addressDetail, is_default AS isDefault
                FROM shipping_addresses
                WHERE user_id = ?
                ORDER BY is_default DESC, address_id DESC
                """,
                user["user_id"],
            )
        )
    for row in rows:
        row["isDefault"] = bool(row["isDefault"])
    return ok(rows)


def split_address(detail: str) -> tuple[str, str, str, str]:
    return "", "", "", detail or ""


@api.post("/addresses")
def address_create(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    province, city, district, detail = split_address(payload.get("addressDetail") or "")
    with get_conn() as conn:
        if payload.get("isDefault"):
            conn.cursor().execute("UPDATE shipping_addresses SET is_default = 0 WHERE user_id = ?", user["user_id"])
        address_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO shipping_addresses(user_id, receiver_name, phone, province, city, district, detail, is_default)
                OUTPUT INSERTED.address_id VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                user["user_id"],
                payload.get("recipientName"),
                payload.get("phone"),
                province,
                city,
                district,
                detail,
                1 if payload.get("isDefault") else 0,
            )
            .fetchone()[0]
        )
    return ok({"addressId": address_id})


@api.put("/addresses/{addressId}")
def address_update(addressId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    province, city, district, detail = split_address(payload.get("addressDetail") or "")
    with get_conn() as conn:
        if payload.get("isDefault"):
            conn.cursor().execute("UPDATE shipping_addresses SET is_default = 0 WHERE user_id = ?", user["user_id"])
        conn.cursor().execute(
            """
            UPDATE shipping_addresses
            SET receiver_name = ?, phone = ?, province = ?, city = ?, district = ?, detail = ?, is_default = ?
            WHERE address_id = ? AND user_id = ?
            """,
            payload.get("recipientName"),
            payload.get("phone"),
            province,
            city,
            district,
            detail,
            1 if payload.get("isDefault") else 0,
            addressId,
            user["user_id"],
        )
    return ok({"ok": True})


@api.delete("/addresses/{addressId}")
def address_remove(addressId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute("DELETE FROM shipping_addresses WHERE address_id = ? AND user_id = ?", addressId, user["user_id"])
    return ok({"ok": True})


@api.post("/orders")
def order_create(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    ids = [int(x) for x in payload.get("cartItemIds") or []]
    if not ids:
        fail("购物车中暂无商品")
    with get_conn() as conn:
        placeholders = ",".join("?" for _ in ids)
        rows = many(
            conn.cursor().execute(
                f"""
                SELECT c.book_item_id AS bookItemId, c.quantity, b.price, b.stock
                FROM cart_items c
                JOIN book_items b ON b.book_item_id = c.book_item_id
                WHERE c.user_id = ? AND c.book_item_id IN ({placeholders})
                """,
                user["user_id"],
                *ids,
            )
        )
        if len(rows) != len(ids):
            fail("购物车商品不存在")
        total = 0.0
        for row in rows:
            if int(row["quantity"]) > int(row["stock"]):
                fail("部分商品库存不足，请修改后重新提交订单")
            total += float(row["price"]) * int(row["quantity"])
        discount = user_coupon_discount(conn, user["user_id"], payload.get("couponId"), total)
        actual = max(0.0, total - discount)
        order_no = "NO" + now_no()
        order_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO orders(user_id, order_no, total_amount, discount_amount, actual_amount,
                                   receiver_name, receiver_phone, receiver_addr)
                OUTPUT INSERTED.order_id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                user["user_id"],
                order_no,
                total,
                discount,
                actual,
                payload.get("receiverName"),
                payload.get("receiverPhone"),
                payload.get("receiverAddress"),
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
        if payload.get("couponId"):
            conn.cursor().execute(
                "UPDATE user_coupons SET status = N'已使用', used_time = SYSDATETIME(), order_id = ? WHERE user_id = ? AND coupon_id = ?",
                order_id,
                user["user_id"],
                payload.get("couponId"),
            )
    return ok({"orderId": order_id, "orderNo": order_no, "totalAmount": total, "discountAmount": discount, "actualAmount": actual})


@api.post("/orders/{orderId}/pay")
def order_pay(orderId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        order = one(conn.cursor().execute("SELECT * FROM orders WHERE order_id = ? AND user_id = ?", orderId, user["user_id"]))
        if not order:
            fail("订单不存在", 404)
        if order["payment_status"] == "已支付":
            return ok({"paymentStatus": "success", "paymentNo": None})
        items = many(conn.cursor().execute("SELECT book_item_id AS bookItemId, quantity FROM order_items WHERE order_id = ?", orderId))
        for item in items:
            stock = conn.cursor().execute("SELECT stock FROM book_items WHERE book_item_id = ?", item["bookItemId"]).fetchval()
            if int(stock or 0) < int(item["quantity"]):
                fail("部分商品库存不足，请重新下单")
        for item in items:
            conn.cursor().execute(
                "UPDATE book_items SET stock = stock - ?, sales_count = sales_count + ? WHERE book_item_id = ?",
                item["quantity"],
                item["quantity"],
                item["bookItemId"],
            )
            conn.cursor().execute("DELETE FROM cart_items WHERE user_id = ? AND book_item_id = ?", user["user_id"], item["bookItemId"])
        payment_no = "PAY" + now_no()
        conn.cursor().execute(
            """
            UPDATE orders SET order_status = N'已完成', payment_status = N'已支付', paid_time = SYSDATETIME()
            WHERE order_id = ?
            """,
            orderId,
        )
        conn.cursor().execute(
            """
            INSERT INTO payment_records(order_id, user_id, payment_no, amount, payment_method, payment_status, paid_time)
            VALUES (?, ?, ?, ?, ?, N'已支付', SYSDATETIME())
            """,
            orderId,
            user["user_id"],
            payment_no,
            order["actual_amount"],
            payload.get("paymentMethod") or "mock",
        )
    return ok({"paymentStatus": "success", "paymentNo": payment_no})


def order_public(conn, row: dict[str, Any]) -> dict[str, Any]:
    items = many(
        conn.cursor().execute(
            """
            SELECT oi.book_item_id AS bookItemId, bi.book_name AS bookName, bi.cover_image AS cover,
                   oi.unit_price AS unitPrice, oi.quantity
            FROM order_items oi
            JOIN book_items b ON b.book_item_id = oi.book_item_id
            JOIN book_infos bi ON bi.book_info_id = b.book_info_id
            WHERE oi.order_id = ?
            """,
            row["order_id"],
        )
    )
    return {
        "orderId": row["order_id"],
        "orderNo": row["order_no"],
        "orderStatus": ORDER_TO_FRONT.get(row["order_status"], row["order_status"]),
        "paymentStatus": PAY_TO_FRONT.get(row["payment_status"], row["payment_status"]),
        "statusLabel": row["order_status"],
        "totalAmount": float(row["total_amount"]),
        "discountAmount": float(row["discount_amount"]),
        "actualAmount": float(row["actual_amount"]),
        "createdTime": str(row["created_time"]),
        "receiverName": row["receiver_name"],
        "receiverPhone": row["receiver_phone"],
        "receiverAddress": row["receiver_addr"],
        "items": [{**item, "cover": item.get("cover") or "📘"} for item in items],
    }


@api.get("/orders")
def order_list(status: str = "all", page: int = 1, pageSize: int = 20, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    db_status = {v: k for k, v in ORDER_TO_FRONT.items()}.get(status)
    where = "WHERE user_id = ?"
    params: list[Any] = [user["user_id"]]
    if db_status:
        where += " AND order_status = ?"
        params.append(db_status)
    with get_conn() as conn:
        rows = many(conn.cursor().execute(f"SELECT * FROM orders {where} ORDER BY created_time DESC", *params))
        public = [order_public(conn, row) for row in rows]
    return ok({"list": page_slice(public, page, pageSize), "total": len(public)})


@api.get("/orders/{orderId}")
def order_detail(orderId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        row = one(conn.cursor().execute("SELECT * FROM orders WHERE order_id = ? AND user_id = ?", orderId, user["user_id"]))
        if not row:
            fail("订单不存在", 404)
        data = order_public(conn, row)
    return ok(data)


@api.post("/orders/{orderId}/cancel")
def order_cancel(orderId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE orders SET order_status = N'已取消' WHERE order_id = ? AND user_id = ? AND order_status = N'待支付'", orderId, user["user_id"])
    return ok({"ok": True})


@api.post("/orders/{orderId}/refund")
def order_refund(orderId: int, payload: dict[str, Any] = Body(default={}), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        payment = one(conn.cursor().execute("SELECT TOP 1 * FROM payment_records WHERE order_id = ? ORDER BY payment_id DESC", orderId))
        if not payment:
            fail("未找到支付记录")
        conn.cursor().execute(
            """
            INSERT INTO refund_records(order_id, user_id, payment_id, refund_no, refund_amount, refund_reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            orderId,
            user["user_id"],
            payment["payment_id"],
            "REF" + now_no(),
            payment["amount"],
            payload.get("reason"),
        )
    return ok({"ok": True})


@api.get("/promotions/activities")
def promo_activities() -> dict[str, Any]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT activity_id AS activityId, activity_name AS activityName, activity_type AS activityType,
                       description, start_time AS startTime, end_time AS endTime, status
                FROM promotion_activities
                ORDER BY start_time DESC
                """
            )
        )
    return ok(rows)


@api.post("/promotions/checkin")
def checkin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    today = date.today()
    reward_points = 10
    with get_conn() as conn:
        if conn.cursor().execute("SELECT 1 FROM checkin_record WHERE user_id = ? AND checkin_date = ?", user["user_id"], today).fetchone():
            fail("今日已签到，请勿重复操作")
        days = int(conn.cursor().execute("SELECT continuous_checkin_days FROM ordinary_users WHERE user_id = ?", user["user_id"]).fetchval() or 0) + 1
        conn.cursor().execute(
            "INSERT INTO checkin_record(user_id, checkin_date, continuous_checkin_days, reward_points) VALUES (?, ?, ?, ?)",
            user["user_id"],
            today,
            days,
            reward_points,
        )
        conn.cursor().execute(
            "UPDATE ordinary_users SET continuous_checkin_days = ?, total_points = total_points + ?, available_points = available_points + ? WHERE user_id = ?",
            days,
            reward_points,
            reward_points,
            user["user_id"],
        )
        conn.cursor().execute(
            "INSERT INTO points_records(user_id, points_change, reason, related_id) VALUES (?, ?, N'签到', ?)",
            user["user_id"],
            reward_points,
            user["user_id"],
        )
    return ok({"continuousDays": days, "rewardPoints": reward_points})


@api.post("/promotions/activities/{activityId}/join")
def join_activity(activityId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return ok({"ok": True, "activityId": activityId, "rewardCouponName": None})


@api.get("/promotions/coupons/my")
def my_coupons(status: str = "unused", user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    db_status = COUPON_STATUS.get(status, "未使用")
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT c.coupon_id AS couponId, c.coupon_name AS couponName, c.coupon_type AS couponType,
                       s.store_name AS storeName, c.amount, c.min_amount AS minAmount, c.valid_end AS validEnd
                FROM user_coupons uc
                JOIN coupons c ON c.coupon_id = uc.coupon_id
                LEFT JOIN stores s ON s.store_id = c.store_id
                WHERE uc.user_id = ? AND uc.status = ?
                ORDER BY c.valid_end
                """,
                user["user_id"],
                db_status,
            )
        )
    for row in rows:
        row["couponType"] = COUPON_TYPE_TO_FRONT.get(row["couponType"], row["couponType"])
    return ok(rows)


@api.get("/promotions/rewards")
def rewards() -> dict[str, Any]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT reward_id AS rewardId, reward_name AS rewardName, reward_type AS rewardType,
                       required_points AS requiredPoints, required_level AS requiredLevel, stock
                FROM point_rewards
                WHERE status = N'启用'
                ORDER BY required_points
                """
            )
        )
    for row in rows:
        row["rewardType"] = REWARD_TYPE_TO_FRONT.get(row["rewardType"], row["rewardType"])
    return ok(rows)


@api.post("/promotions/rewards/{rewardId}/redeem")
def redeem(rewardId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        reward = one(conn.cursor().execute("SELECT * FROM point_rewards WHERE reward_id = ? AND status = N'启用'", rewardId))
        profile = one(conn.cursor().execute("SELECT * FROM ordinary_users WHERE user_id = ?", user["user_id"]))
        if not reward:
            fail("奖品不存在")
        if int(profile["available_points"]) < int(reward["required_points"]):
            fail("积分不足")
        if int(profile["level"]) < int(reward["required_level"]):
            fail("等级不够")
        if int(reward["stock"]) <= 0:
            fail("库存不足")
        conn.cursor().execute("UPDATE ordinary_users SET available_points = available_points - ? WHERE user_id = ?", reward["required_points"], user["user_id"])
        conn.cursor().execute("UPDATE point_rewards SET stock = stock - 1 WHERE reward_id = ?", rewardId)
        conn.cursor().execute(
            "INSERT INTO reward_redemptions(user_id, reward_id, used_points) VALUES (?, ?, ?)",
            user["user_id"],
            rewardId,
            reward["required_points"],
        )
    return ok({"ok": True})


@api.post("/promotions/weekly-coupon/claim")
def weekly_coupon(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if int(user.get("level") or 1) < 3:
        fail("当前等级暂不能领取周代金券")
    return ok({"ok": True})


@api.get("/users/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return ok(public_user(user))


@api.put("/users/me")
def update_me(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE users SET phone = COALESCE(?, phone), email = COALESCE(?, email) WHERE user_id = ?",
            payload.get("phone"),
            payload.get("email"),
            user["user_id"],
        )
        if payload.get("nickname"):
            conn.cursor().execute("UPDATE ordinary_users SET nickname = ? WHERE user_id = ?", payload["nickname"], user["user_id"])
    return ok({"ok": True})


@api.get("/admin/books")
def admin_books(keyword: Optional[str] = None, page: int = 1, pageSize: int = 50, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    where = []
    params: list[Any] = []
    if DB_TO_ROLE.get(user["user_type"]) == "seller":
        where.append("AND b.store_id = ?")
        params.append(user["store_id"])
    if keyword:
        where.append("AND (bi.book_name LIKE ? OR bi.author LIKE ? OR bi.ISBN LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like])
    with get_conn() as conn:
        rows = all_books(conn, " ".join(where), tuple(params), "ORDER BY b.created_time DESC")
    return ok({"list": [normalize_book(row) for row in page_slice(rows, page, pageSize)], "total": len(rows)})


@api.post("/admin/books")
def admin_book_create(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    store_id = int(payload.get("storeId") or user.get("store_id") or 0)
    if not store_id:
        fail("缺少店铺信息")
    require_store_owner(user, store_id)
    with get_conn() as conn:
        book_info_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO book_infos(category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image, embedding)
                OUTPUT INSERTED.book_info_id VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload.get("categoryId"),
                payload.get("bookName"),
                payload.get("author"),
                payload.get("publisher"),
                payload.get("isbn"),
                payload.get("publishDate"),
                payload.get("description"),
                payload.get("cover") or "📘",
                dump_embedding(embed_text(payload.get("bookName") or "")),
            )
            .fetchone()[0]
        )
        book_item_id = int(
            conn.cursor()
            .execute(
                "INSERT INTO book_items(book_info_id, store_id, price, stock) OUTPUT INSERTED.book_item_id VALUES (?, ?, ?, ?)",
                book_info_id,
                store_id,
                payload.get("price"),
                payload.get("stock"),
            )
            .fetchone()[0]
        )
    return ok({"ok": True, "bookItemId": book_item_id})


@api.put("/admin/books/{bookItemId}")
def admin_book_update(bookItemId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        book = book_detail(conn, bookItemId)
        if not book:
            fail("图书不存在", 404)
        require_store_owner(user, book["storeId"])
        embedding = dump_embedding(embed_text(payload.get("bookName"))) if payload.get("bookName") else book.get("embedding")
        conn.cursor().execute(
            """
            UPDATE book_infos
            SET category_id = COALESCE(?, category_id), book_name = COALESCE(?, book_name),
                author = COALESCE(?, author), publisher = COALESCE(?, publisher),
                ISBN = COALESCE(?, ISBN), description = COALESCE(?, description), embedding = COALESCE(?, embedding)
            WHERE book_info_id = ?
            """,
            payload.get("categoryId"),
            payload.get("bookName"),
            payload.get("author"),
            payload.get("publisher"),
            payload.get("isbn"),
            payload.get("description"),
            embedding,
            book["bookInfoId"],
        )
        conn.cursor().execute(
            "UPDATE book_items SET price = COALESCE(?, price), stock = COALESCE(?, stock) WHERE book_item_id = ?",
            payload.get("price"),
            payload.get("stock"),
            bookItemId,
        )
    return ok({"ok": True})


@api.delete("/admin/books/{bookItemId}")
def admin_book_remove(bookItemId: int, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        book = book_detail(conn, bookItemId)
        if book:
            require_store_owner(user, book["storeId"])
        conn.cursor().execute("UPDATE book_items SET status = N'下架' WHERE book_item_id = ?", bookItemId)
    return ok({"ok": True})


@api.post("/admin/books/{bookItemId}/force-takedown")
def admin_force_takedown(bookItemId: int, _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE book_items SET status = N'下架' WHERE book_item_id = ?", bookItemId)
    return ok({"ok": True})


@api.get("/admin/orders")
def admin_orders(status: str = "all", keyword: Optional[str] = None, page: int = 1, pageSize: int = 50, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        if DB_TO_ROLE.get(user["user_type"]) == "seller":
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
                    user["store_id"],
                )
            )
        else:
            rows = many(conn.cursor().execute("SELECT * FROM orders ORDER BY created_time DESC"))
        public = [order_public(conn, row) for row in rows]
    if status != "all":
        public = [o for o in public if o["orderStatus"] == status]
    if keyword:
        public = [o for o in public if keyword.lower() in o["orderNo"].lower()]
    return ok({"list": page_slice(public, page, pageSize), "total": len(public)})


@api.put("/admin/orders/{orderId}/status")
def admin_order_status(orderId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    db_status = STATUS_TO_DB.get(payload.get("status"), payload.get("status"))
    with get_conn() as conn:
        conn.cursor().execute("UPDATE orders SET order_status = ? WHERE order_id = ?", db_status, orderId)
    return ok({"ok": True})


@api.post("/admin/orders/{orderId}/refund/{action}")
def admin_refund(orderId: int, action: str, _: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    approved = action == "approve"
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE refund_records SET refund_status = ?, refund_time = CASE WHEN ? = 1 THEN SYSDATETIME() ELSE refund_time END WHERE order_id = ?",
            "已退款" if approved else "已拒绝",
            1 if approved else 0,
            orderId,
        )
        if approved:
            conn.cursor().execute("UPDATE orders SET order_status = N'已退款', payment_status = N'已退款' WHERE order_id = ?", orderId)
    return ok({"ok": True})


@api.get("/admin/users")
def admin_users(keyword: Optional[str] = None, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT u.user_id AS userId, u.user_name AS userName, COALESCE(ou.nickname, u.user_name) AS nickname,
                       CASE WHEN u.status = N'正常' THEN 'active' ELSE 'banned' END AS status,
                       u.created_time AS registeredAt
                FROM users u LEFT JOIN ordinary_users ou ON ou.user_id = u.user_id
                WHERE u.user_type = N'普通用户'
                ORDER BY u.created_time DESC
                """
            )
        )
    if keyword:
        rows = [r for r in rows if keyword.lower() in (r["userName"] or "").lower() or keyword.lower() in (r["nickname"] or "").lower()]
    return ok({"list": rows, "total": len(rows)})


@api.post("/admin/users/{userId}/blacklist")
def admin_blacklist(userId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller"))) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute("INSERT INTO store_blacklists(store_id, user_id, reason) VALUES (?, ?, ?)", user["store_id"], userId, payload.get("reason"))
        count = conn.cursor().execute("SELECT COUNT(DISTINCT store_id) FROM store_blacklists WHERE user_id = ?", userId).fetchval()
        if int(count or 0) > 10:
            conn.cursor().execute("UPDATE users SET status = N'封禁' WHERE user_id = ?", userId)
    return ok({"ok": True})


@api.put("/admin/users/{userId}/status")
def admin_user_status(userId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE users SET status = ? WHERE user_id = ?", STATUS_TO_DB.get(payload.get("status"), "正常"), userId)
    return ok({"ok": True})


@api.get("/admin/stores")
def admin_stores(_: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT s.store_id AS storeId, s.store_name AS storeName,
                       CASE WHEN s.status = N'正常' THEN 'active' ELSE 'banned' END AS status,
                       s.created_time AS createdTime,
                       COUNT(b.book_item_id) AS bookCount,
                       COALESCE(SUM(b.sales_count), 0) AS orderCount
                FROM stores s LEFT JOIN book_items b ON b.store_id = s.store_id
                GROUP BY s.store_id, s.store_name, s.status, s.created_time
                ORDER BY s.created_time DESC
                """
            )
        )
    return ok({"list": rows, "total": len(rows)})


@api.put("/admin/stores/{storeId}/status")
def admin_store_status(storeId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE stores SET status = ? WHERE store_id = ?", STATUS_TO_DB.get(payload.get("status"), "正常"), storeId)
    return ok({"ok": True})


@api.get("/admin/promotions/activities")
def admin_promo_activities(_: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    return promo_activities()


@api.post("/admin/promotions/activities")
def admin_save_activity(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        activity_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO promotion_activities(activity_name, activity_type, description, start_time, end_time, status, created_admin)
                OUTPUT INSERTED.activity_id VALUES (?, ?, ?, ?, ?, N'进行中', ?)
                """,
                payload.get("activityName"),
                payload.get("activityType"),
                payload.get("description") or "",
                payload.get("startTime"),
                payload.get("endTime"),
                user["user_id"],
            )
            .fetchone()[0]
        )
    return ok({"ok": True, "activityId": activity_id})


@api.put("/admin/promotions/activities/{activityId}")
def admin_update_activity(activityId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute(
            """
            UPDATE promotion_activities
            SET activity_name = COALESCE(?, activity_name), activity_type = COALESCE(?, activity_type),
                description = COALESCE(?, description), start_time = COALESCE(?, start_time), end_time = COALESCE(?, end_time)
            WHERE activity_id = ?
            """,
            payload.get("activityName"),
            payload.get("activityType"),
            payload.get("description"),
            payload.get("startTime"),
            payload.get("endTime"),
            activityId,
        )
    return ok({"ok": True})


@api.post("/admin/promotions/activities/{activityId}/store-participation")
def admin_store_participation(activityId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller"))) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute(
            """
            MERGE store_activity_participation AS target
            USING (SELECT ? AS store_id, ? AS activity_id) AS src
            ON target.store_id = src.store_id AND target.activity_id = src.activity_id
            WHEN MATCHED THEN UPDATE SET participate_status = N'已参与', coupon_amount = ?, coupon_quantity = ?
            WHEN NOT MATCHED THEN INSERT(store_id, activity_id, coupon_amount, coupon_quantity) VALUES(src.store_id, src.activity_id, ?, ?);
            """,
            user["store_id"],
            activityId,
            payload.get("couponAmount"),
            payload.get("couponQuantity"),
            payload.get("couponAmount"),
            payload.get("couponQuantity"),
        )
    return ok({"ok": True})


@api.post("/admin/promotions/coupons")
def admin_coupon(payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    return ok({"ok": True})


@api.post("/admin/promotions/rewards")
@api.put("/admin/promotions/rewards/{rewardId}")
def admin_reward(payload: dict[str, Any] = Body(...), rewardId: Optional[int] = None, user: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    reward_type = {"physical": "实物", "coupon": "代金券", "virtual": "虚拟商品"}.get(payload.get("rewardType"), "实物")
    with get_conn() as conn:
        if rewardId:
            conn.cursor().execute(
                """
                UPDATE point_rewards SET reward_name = ?, reward_type = ?, required_points = ?,
                    required_level = ?, stock = ? WHERE reward_id = ?
                """,
                payload.get("rewardName"),
                reward_type,
                payload.get("requiredPoints"),
                payload.get("requiredLevel") or 1,
                payload.get("stock") or 0,
                rewardId,
            )
        else:
            rewardId = int(
                conn.cursor()
                .execute(
                    """
                    INSERT INTO point_rewards(reward_name, reward_type, required_points, required_level, stock, manage_admin)
                    OUTPUT INSERTED.reward_id VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    payload.get("rewardName"),
                    reward_type,
                    payload.get("requiredPoints"),
                    payload.get("requiredLevel") or 1,
                    payload.get("stock") or 0,
                    user["user_id"],
                )
                .fetchone()[0]
            )
    return ok({"ok": True, "rewardId": rewardId})


@api.get("/admin/statistics/overview")
def stats_overview(user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        store_filter = "WHERE b.store_id = ?" if DB_TO_ROLE.get(user["user_type"]) == "seller" else ""
        params = [user["store_id"]] if store_filter else []
        hot = many(
            conn.cursor().execute(
                f"""
                SELECT TOP 5 bi.book_name AS bookName, SUM(b.sales_count) AS salesCount
                FROM book_items b JOIN book_infos bi ON bi.book_info_id = b.book_info_id
                {store_filter}
                GROUP BY bi.book_name
                ORDER BY SUM(b.sales_count) DESC
                """,
                params,
            )
        )
        total_users = conn.cursor().execute("SELECT COUNT(*) FROM users").fetchval()
        total_stores = conn.cursor().execute("SELECT COUNT(*) FROM stores WHERE status = N'正常'").fetchval()
        total_books = conn.cursor().execute("SELECT COUNT(*) FROM book_items WHERE status = N'在售'").fetchval()
        revenue = conn.cursor().execute("SELECT COALESCE(SUM(actual_amount), 0) FROM orders WHERE payment_status = N'已支付'").fetchval()
        sales_trend = many(
            conn.cursor().execute(
                """
                SELECT TOP 7 CONVERT(varchar(5), created_time, 110) AS label, SUM(actual_amount) AS value
                FROM orders
                GROUP BY CONVERT(varchar(5), created_time, 110), CAST(created_time AS date)
                ORDER BY CAST(created_time AS date) DESC
                """
            )
        )
    return ok(
        {
            "kpi": {"todaySales": float(revenue or 0), "todayOrders": 0, "totalUsers": total_users, "totalStores": total_stores, "totalBooks": total_books},
            "salesTrend": list(reversed(sales_trend)),
            "hotBooks": hot,
        }
    )


@api.get("/admin/statistics/risk-stores")
def risk_stores(_: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    return ok([])


app.include_router(api)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
