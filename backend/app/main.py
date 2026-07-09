from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, FastAPI, Query, Response
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
from .dao import address_dao, book_dao, cart_dao, order_dao, promotion_dao, review_dao, stats_dao, store_dao


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
        fail("鏃犳潈闄愮淮鎶よ搴楅摵", 403)


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
        fail("浠ｉ噾鍒镐笉鍙敤")
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
        fail("鐢ㄦ埛鍚嶆垨瀵嗙爜閿欒", 401)
    if user["user_type"] != user_type:
        fail("璐﹀彿绫诲瀷涓庣敤鎴疯韩浠戒笉鍖归厤", 403)
    if user["status"] == "封禁":
        fail("当前账号已被禁用，请联系管理员", 403)
    return ok({"token": create_token(user), "user": public_user(user)})


@api.post("/auth/logout")
def logout() -> dict[str, Any]:
    return ok({"ok": True})


@api.get("/categories")
def categories() -> dict[str, Any]:
    return ok(book_dao.list_categories())


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
    rows = book_dao.list_books(
        keyword=keyword,
        category_id=categoryId,
        sort=sort,
        in_stock_only=bool(inStockOnly),
    )
    try:
        search_embedding_enabled = stats_dao.recommendation_settings().get("searchEmbeddingEnabled", True)
    except Exception:
        search_embedding_enabled = True
    if keyword and sort == "default" and search_embedding_enabled:
        rows = sort_by_embedding(rows, keyword)
        if user:
            try:
                book_dao.save_search_history(user["user_id"], keyword, dump_embedding(embed_text(keyword)))
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
            try:
                settings = stats_dao.recommendation_settings()
            except Exception:
                settings = {"guessWeight": 1, "hotWeight": 1}
            if settings.get("guessWeight") != 1 or settings.get("hotWeight") != 1:
                hot = hot_books(conn, limit)
                by_id = {book["bookItemId"]: book for book in rows + hot}
                guess_rank = {book["bookItemId"]: idx + 1 for idx, book in enumerate(rows)}
                hot_rank = {book["bookItemId"]: idx + 1 for idx, book in enumerate(hot)}
                guess_weight = max(float(settings.get("guessWeight") or 1), 0.1)
                hot_weight = max(float(settings.get("hotWeight") or 1), 0.1)
                rows = sorted(
                    by_id.values(),
                    key=lambda book: (
                        guess_rank.get(book["bookItemId"], limit + 1) / guess_weight
                        + hot_rank.get(book["bookItemId"], limit + 1) / hot_weight
                    ),
                )[:limit]
    return ok(rows)


@api.get("/books/{bookItemId}")
def get_book(bookItemId: int) -> dict[str, Any]:
    row = book_dao.get_detail(bookItemId)
    if not row:
        fail("图书不存在", 404)
    book = normalize_book(row)
    book["averageRating"] = round(book_dao.average_rating(bookItemId), 1)
    book["reviews"] = book_dao.get_reviews(bookItemId)
    return ok(book)


@api.get("/books/{bookItemId}/similar")
def similar_books(bookItemId: int) -> dict[str, Any]:
    if not book_dao.get_detail(bookItemId):
        fail("图书不存在", 404)
    try:
        if not stats_dao.recommendation_settings().get("detailSameStoreEnabled", True):
            return ok([])
    except Exception:
        pass
    rows = book_dao.get_similar_same_store_category(bookItemId, 3)
    return ok([normalize_book(row) for row in rows[:3]])


@api.get("/stores/{storeId}")
def store_detail(storeId: int) -> dict[str, Any]:
    row = store_dao.get_detail(storeId)
    if not row:
        fail("店铺不存在", 404)
    return ok(row)


@api.get("/stores/{storeId}/books")
def store_books(storeId: int, sort: str = "default", page: int = 1, pageSize: int = 24) -> dict[str, Any]:
    rows = book_dao.list_books(sort=sort, store_id=storeId)
    return ok({"list": [normalize_book(row) for row in page_slice(rows, page, pageSize)], "total": len(rows)})


@api.put("/stores/{storeId}")
def update_store(storeId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    require_store_owner(user, storeId)
    store_dao.update_profile(storeId, payload)
    return ok({"ok": True})


@api.get("/cart")
def cart_list(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    rows = cart_dao.list_items(user["user_id"])
    items = []
    for row in rows:
        book = normalize_book(row)
        items.append(
            {
                "cartItemId": row["cartItemId"],
                "bookItemId": row["bookItemId"],
                "quantity": int(row.get("quantity") or 0),
                "book": {
                    "bookItemId": book["bookItemId"],
                    "bookInfoId": book.get("bookInfoId"),
                    "bookName": book.get("bookName"),
                    "author": book.get("author"),
                    "storeId": book.get("storeId"),
                    "storeName": book.get("storeName"),
                    "price": book.get("price"),
                    "cover": book.get("cover"),
                    "stock": book.get("stock"),
                    "salesCount": book.get("salesCount"),
                },
            }
        )
    return ok(items)


@api.post("/cart")
def cart_add(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    book_item_id = int(payload.get("bookItemId"))
    quantity = max(int(payload.get("quantity") or 1), 1)
    stock = cart_dao.get_stock(book_item_id)
    if stock is None:
        fail("图书不存在或已下架", 404)
    current_qty = next((int(row["quantity"]) for row in cart_dao.list_items(user["user_id"]) if int(row["bookItemId"]) == book_item_id), 0)
    if current_qty + quantity > stock:
        fail("当前图书库存不足")
    cart_dao.add(user["user_id"], book_item_id, quantity)
    return ok({"ok": True})


@api.put("/cart/{bookItemId}")
def cart_update(bookItemId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    quantity = max(int(payload.get("quantity") or 1), 1)
    stock = cart_dao.get_stock(bookItemId)
    if stock is None:
        fail("图书不存在", 404)
    if quantity > stock:
        fail("当前图书库存不足")
    cart_dao.update_quantity(user["user_id"], bookItemId, quantity)
    return ok({"ok": True})


@api.delete("/cart/{bookItemId}")
def cart_remove(bookItemId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    cart_dao.remove(user["user_id"], bookItemId)
    return ok({"ok": True})


@api.get("/addresses")
def address_list(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return ok(address_dao.list_by_user(user["user_id"]))


def split_address(detail: str) -> tuple[str, str, str, str]:
    return "", "", "", detail or ""


@api.post("/addresses")
def address_create(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    address_id = address_dao.create(user["user_id"], payload)
    return ok({"addressId": address_id})


@api.put("/addresses/{addressId}")
def address_update(addressId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    address_dao.update(user["user_id"], addressId, payload)
    return ok({"ok": True})


@api.delete("/addresses/{addressId}")
def address_remove(addressId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    address_dao.delete(user["user_id"], addressId)
    return ok({"ok": True})


@api.post("/orders")
def order_create(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    ids = [int(x) for x in payload.get("cartItemIds") or []]
    if not ids:
        fail("璐墿杞︿腑鏆傛棤鍟嗗搧")
    discount = float(payload.get("discountAmount") or 0)
    try:
        data = order_dao.create_from_cart(
            user_id=user["user_id"],
            book_item_ids=ids,
            receiver_name=payload.get("receiverName") or "",
            receiver_phone=payload.get("receiverPhone") or "",
            receiver_address=payload.get("receiverAddress") or "",
            discount_amount=discount,
            coupon_id=payload.get("couponId"),
        )
    except ValueError as exc:
        fail(str(exc))
    return ok(data)


@api.post("/orders/{orderId}/pay")
def order_pay(orderId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        data = order_dao.pay(user["user_id"], orderId, payload.get("paymentMethod") or "alipay")
    except ValueError as exc:
        fail(str(exc), 404 if "不存在" in str(exc) else 400)
    return ok(data)


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
    public = order_dao.list_orders(user["user_id"], status)
    return ok({"list": page_slice(public, page, pageSize), "total": len(public)})


@api.get("/orders/{orderId}")
def order_detail(orderId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    data = order_dao.get_detail(user["user_id"], orderId)
    if not data:
        fail("订单不存在", 404)
    return ok(data)


@api.post("/orders/{orderId}/cancel")
def order_cancel(orderId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        order = order_dao.cancel(user["user_id"], orderId)
    except ValueError as exc:
        fail(str(exc), 404 if "不存在" in str(exc) else 400)
    return ok({"ok": True, "order": order})


@api.post("/orders/{orderId}/refund")
def order_refund(orderId: int, payload: dict[str, Any] = Body(default={}), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        order_dao.refund(user["user_id"], orderId, payload.get("reason"))
    except ValueError as exc:
        fail(str(exc))
    return ok({"ok": True})


@api.post("/orders/{orderId}/reviews")
def order_review(orderId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        review_dao.create(
            user_id=user["user_id"],
            order_id=orderId,
            book_item_id=int(payload.get("bookItemId")),
            rating=int(payload.get("rating") or 5),
            content=payload.get("content") or "",
        )
    except ValueError as exc:
        fail(str(exc))
    return ok({"ok": True})


@api.get("/promotions/activities")
def promo_activities() -> dict[str, Any]:
    return ok(promotion_dao.list_activities())


@api.post("/promotions/checkin")
def checkin(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        return ok(promotion_dao.checkin(user["user_id"]))
    except ValueError as exc:
        fail(str(exc))


@api.post("/promotions/activities/{activityId}/join")
def join_activity(activityId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        return ok(promotion_dao.join_activity(user["user_id"], activityId))
    except ValueError as exc:
        fail(str(exc))


@api.get("/promotions/coupons/my")
def my_coupons(status: str = "unused", user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return ok(promotion_dao.list_user_coupons(user["user_id"], status))


@api.get("/promotions/rewards")
def rewards() -> dict[str, Any]:
    return ok(promotion_dao.list_rewards())


@api.post("/promotions/rewards/{rewardId}/redeem")
def redeem(rewardId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        promotion_dao.redeem_reward(user["user_id"], rewardId)
    except ValueError as exc:
        fail(str(exc))
    return ok({"ok": True})


@api.post("/promotions/weekly-coupon/claim")
def weekly_coupon(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        return ok(promotion_dao.claim_weekly_coupon(user["user_id"]))
    except ValueError as exc:
        fail(str(exc))
    if int(user.get("level") or 1) < 3:
        fail("当前等级暂不能领取周代金券")
    return ok({"ok": True})


@api.get("/users/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return ok(public_user(user))


@api.get("/users/me/points")
def my_points(page: int = 1, pageSize: int = 20, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return ok(promotion_dao.list_points(user["user_id"], page, pageSize))

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
    rows = book_dao.list_books(
        keyword=keyword,
        sort="default",
        store_id=user["store_id"] if DB_TO_ROLE.get(user["user_type"]) == "seller" else None,
    )
    if keyword:
        kw = keyword.lower()
        rows = [
            row
            for row in rows
            if kw in (row.get("bookName") or "").lower()
            or kw in (row.get("author") or "").lower()
            or kw in (row.get("isbn") or "").lower()
        ]
    return ok({"list": [normalize_book(row) for row in page_slice(rows, page, pageSize)], "total": len(rows)})


@api.post("/admin/books")
def admin_book_create(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    store_id = int(payload.get("storeId") or user.get("store_id") or 0)
    if not store_id:
        fail("缂哄皯搴楅摵淇℃伅")
    require_store_owner(user, store_id)
    book_item_id = book_dao.create_book(
        {
            **payload,
            "embedding": dump_embedding(embed_text(payload.get("bookName") or "")),
        },
        {"storeId": store_id, "price": payload.get("price"), "stock": payload.get("stock")},
    )
    return ok({"ok": True, "bookItemId": book_item_id})


@api.put("/admin/books/{bookItemId}")
def admin_book_update(bookItemId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    book = book_dao.get_detail(bookItemId)
    if not book:
        fail("图书不存在", 404)
    require_store_owner(user, book["storeId"])
    if payload.get("bookName"):
        payload = {**payload, "embedding": dump_embedding(embed_text(payload["bookName"]))}
    book_dao.update_book(bookItemId, payload)
    return ok({"ok": True})


@api.delete("/admin/books/{bookItemId}")
def admin_book_remove(bookItemId: int, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    book = book_dao.get_detail(bookItemId)
    if book:
        require_store_owner(user, book["storeId"])
    book_dao.set_status(bookItemId, "下架")
    return ok({"ok": True})


@api.post("/admin/books/{bookItemId}/force-takedown")
def admin_force_takedown(bookItemId: int, _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    book_dao.set_status(bookItemId, "下架")
    return ok({"ok": True})


@api.get("/admin/orders")
def admin_orders(status: str = "all", keyword: Optional[str] = None, page: int = 1, pageSize: int = 50, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    public = order_dao.list_admin_orders(user["store_id"] if DB_TO_ROLE.get(user["user_type"]) == "seller" else None)
    if status != "all":
        public = [o for o in public if o["orderStatus"] == status]
    if keyword:
        public = [o for o in public if keyword.lower() in o["orderNo"].lower()]
    return ok({"list": page_slice(public, page, pageSize), "total": len(public)})


@api.put("/admin/orders/{orderId}/status")
def admin_order_status(orderId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    db_status = STATUS_TO_DB.get(payload.get("status"), payload.get("status"))
    order_dao.update_status(orderId, db_status)
    return ok({"ok": True})


@api.post("/admin/orders/{orderId}/refund/{action}")
def admin_refund(orderId: int, action: str, _: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    order_dao.handle_refund(orderId, action == "approve")
    return ok({"ok": True})


@api.get("/admin/users")
def admin_users(keyword: Optional[str] = None, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        if DB_TO_ROLE.get(user["user_type"]) == "seller":
            rows = many(
                conn.cursor().execute(
                    """
                    SELECT DISTINCT u.user_id AS userId, u.user_name AS userName, COALESCE(ou.nickname, u.user_name) AS nickname,
                           CASE WHEN u.status = N'正常' THEN 'active' ELSE 'banned' END AS status,
                           u.created_time AS registeredAt
                    FROM users u
                    LEFT JOIN ordinary_users ou ON ou.user_id = u.user_id
                    JOIN orders o ON o.user_id = u.user_id
                    JOIN order_items oi ON oi.order_id = o.order_id
                    JOIN book_items b ON b.book_item_id = oi.book_item_id
                    WHERE u.user_type = N'普通用户' AND b.store_id = ?
                    ORDER BY u.created_time DESC
                    """,
                    user["store_id"],
                )
            )
        else:
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
    store_dao.add_to_blacklist(user["store_id"], userId, payload.get("reason"))
    return ok({"ok": True})


@api.put("/admin/users/{userId}/status")
def admin_user_status(userId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE users SET status = ? WHERE user_id = ?", STATUS_TO_DB.get(payload.get("status"), "正常"), userId)
    return ok({"ok": True})


@api.get("/admin/stores")
def admin_stores(_: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    rows = store_dao.list_stores()
    return ok({"list": rows, "total": len(rows)})


@api.put("/admin/stores/{storeId}/status")
def admin_store_status(storeId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    store_dao.set_status(storeId, STATUS_TO_DB.get(payload.get("status"), "正常"))
    return ok({"ok": True})


@api.get("/admin/promotions/activities")
def admin_promo_activities(_: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    return ok(promotion_dao.list_activities(admin_view=True))


@api.post("/admin/promotions/activities")
def admin_save_activity(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    activity_id = promotion_dao.create_activity(payload, user["user_id"])
    return ok({"ok": True, "activityId": activity_id})


@api.put("/admin/promotions/activities/{activityId}")
def admin_update_activity(activityId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    promotion_dao.update_activity(activityId, payload)
    return ok({"ok": True})


@api.post("/admin/promotions/activities/{activityId}/store-participation")
def admin_store_participation(activityId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller"))) -> dict[str, Any]:
    promotion_dao.set_store_participation(user["store_id"], activityId, payload)
    return ok({"ok": True})


@api.post("/admin/promotions/coupons")
def admin_coupon(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    try:
        coupon_id = promotion_dao.save_platform_coupon(payload, user["user_id"])
    except ValueError as exc:
        fail(str(exc))
    return ok({"ok": True, "couponId": coupon_id})


@api.post("/admin/promotions/rewards")
@api.put("/admin/promotions/rewards/{rewardId}")
def admin_reward(payload: dict[str, Any] = Body(...), rewardId: Optional[int] = None, user: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    rewardId = promotion_dao.save_reward(payload, user["user_id"], rewardId)
    return ok({"ok": True, "rewardId": rewardId})


@api.get("/admin/statistics/overview")
def stats_overview(range: str = "7d", user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    store_id = user.get("store_id") if DB_TO_ROLE.get(user["user_type"]) == "seller" else None
    return ok(stats_dao.overview(store_id, range))


@api.get("/admin/statistics/risk-stores")
def risk_stores(_: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    return ok(stats_dao.risk_stores())


@api.get("/admin/statistics/export")
def stats_export(range: str = "7d", storeId: Optional[int] = None, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> Response:
    store_id = user.get("store_id") if DB_TO_ROLE.get(user["user_type"]) == "seller" else storeId
    rows = stats_dao.export_rows(store_id, range)
    lines = ["date,storeName,bookName,quantity,salesAmount"]
    for row in rows:
        values = [
            str(row.get("date") or ""),
            str(row.get("storeName") or "").replace('"', '""'),
            str(row.get("bookName") or "").replace('"', '""'),
            str(row.get("quantity") or 0),
            str(row.get("salesAmount") or 0),
        ]
        lines.append(",".join(f'"{value}"' for value in values))
    return Response(
        "\ufeff" + "\n".join(lines),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ebookstore-statistics.csv"'},
    )


@api.get("/admin/recommendation/settings")
def recommendation_settings(_: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    return ok(stats_dao.recommendation_settings())


@api.put("/admin/recommendation/settings")
def update_recommendation_settings(payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    return ok(stats_dao.update_recommendation_settings(payload))


app.include_router(api)

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
