from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pyodbc
from fastapi import APIRouter, Body, Depends, FastAPI, Query, Response
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from starlette.types import Scope

from .config import settings
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
from .dao import address_dao, book_dao, cart_dao, order_dao, promotion_dao, review_dao, stats_dao, store_dao, user_dao


app = FastAPI(title=settings.app_name)
app.add_exception_handler(HTTPException, http_exception_handler)


def overflow_exception_handler(_: Any, __: OverflowError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"code": 1, "message": "integer value is outside the supported range", "data": None},
    )


app.add_exception_handler(OverflowError, overflow_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api = APIRouter(prefix=settings.api_prefix)


class FrontendStaticFiles(StaticFiles):
    @staticmethod
    def _is_no_cache_asset(path: str) -> bool:
        return bool(path)

    @staticmethod
    def _set_no_cache_headers(headers: Any) -> None:
        for key in ("cache-control", "etag", "last-modified"):
            if key in headers:
                del headers[key]
        headers["cache-control"] = "no-store, max-age=0"
        headers["pragma"] = "no-cache"
        headers["expires"] = "0"

    def file_response(self, full_path: Any, stat_result: Any, scope: Scope, status_code: int = 200) -> Response:
        if self._is_no_cache_asset(str(full_path)):
            response = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
            self._set_no_cache_headers(response.headers)
            return response
        return super().file_response(full_path, stat_result, scope, status_code)


STATUS_TO_DB = {"active": "正常", "banned": "封禁", "completed": "已完成", "cancelled": "已取消", "refunded": "已退款"}


def page_slice(items: list[dict[str, Any]], page: int, page_size: int) -> list[dict[str, Any]]:
    start = max(page - 1, 0) * page_size
    return items[start : start + page_size]


def payload_int(payload: dict[str, Any], field: str, *, default: int | None = None) -> int:
    value = payload.get(field)
    if value is None:
        if default is not None:
            return default
        fail(f"{field}格式不正确")
    if isinstance(value, bool):
        fail(f"{field}格式不正确")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    fail(f"{field}格式不正确")


def require_address_fields(payload: dict[str, Any]) -> None:
    for field in ("receiverName", "phone", "detail"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            fail(f"{field} is required")


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


def sort_by_embedding(books: list[dict[str, Any]], target: list[float]) -> list[dict[str, Any]]:
    def distance(book: dict[str, Any]) -> float:
        vec = load_embedding(book.get("embedding")) or embed_text(book.get("bookName") or "")
        return cosine_distance(target, vec)

    return sorted(books, key=lambda b: (distance(b), -(b.get("salesCount") or 0)))


def title_token_match_score(title: str, keyword: str) -> tuple[int, float]:
    normalized_title = (title or "").strip().casefold()
    tokens = list(dict.fromkeys((keyword or "").strip().casefold().split()))
    if not normalized_title or not tokens:
        return 0, 0.0

    covered: set[int] = set()
    matched_tokens = 0
    for token in tokens:
        start = 0
        token_matched = False
        while True:
            match_at = normalized_title.find(token, start)
            if match_at < 0:
                break
            token_matched = True
            covered.update(range(match_at, match_at + len(token)))
            start = match_at + 1
        if token_matched:
            matched_tokens += 1
    return matched_tokens, len(covered) / len(normalized_title)


def title_token_coverage(title: str, keyword: str) -> float:
    return title_token_match_score(title, keyword)[1]


def sort_title_search_results(
    books: list[dict[str, Any]], keyword: str, target: list[float]
) -> list[dict[str, Any]]:
    ranked: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for book in books:
        matched_tokens, coverage = title_token_match_score(book.get("bookName") or "", keyword)
        vec = load_embedding(book.get("embedding")) or embed_text(book.get("bookName") or "")
        distance = cosine_distance(target, vec)
        ranked.append(
            (
                (
                    0 if matched_tokens > 0 else 1,
                    -matched_tokens,
                    -coverage,
                    distance,
                    -int(book.get("salesCount") or 0),
                    int(book.get("bookItemId") or 0),
                ),
                book,
            )
        )
    ranked.sort(key=lambda item: item[0])
    return [book for _, book in ranked]


def hot_books(limit: int) -> list[dict[str, Any]]:
    rows = book_dao.list_books(sort="sales")
    return [normalize_book(row) for row in rows[:limit]]


def guess_books(user_id: int | None, limit: int) -> list[dict[str, Any]]:
    if not user_id:
        return hot_books(limit)
    searches = book_dao.latest_searches(user_id, 5)
    if not searches:
        return hot_books(limit)

    vectors = [load_embedding(s.get("embedding")) or embed_text(s["keyword"]) for s in searches]
    best_by_info: dict[int, dict[str, Any]] = {}
    for row in book_dao.list_books():
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


def require_store_access(user: dict[str, Any] | None, store_id: int) -> None:
    if user and store_dao.is_blacklisted(store_id, user["user_id"]):
        fail("您已被该店铺加入黑名单，无法访问或购买该店商品", 403)


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
    try:
        user_id = user_dao.create_customer(
            user_name=user_name,
            password_hash=hash_password(password),
            nickname=nickname or user_name,
            phone=payload.get("phone"),
            email=payload.get("email"),
        )
    except ValueError as exc:
        fail(str(exc))
    return ok({"userId": user_id})


@api.post("/auth/register/seller")
def register_seller(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    user_name = (payload.get("userName") or "").strip()
    password = payload.get("password") or ""
    store_name = (payload.get("storeName") or "").strip()
    if len(user_name) < 3 or len(password) < 6 or not store_name:
        fail("注册信息不完整或格式不正确")
    try:
        data = user_dao.create_seller(
            user_name=user_name,
            password_hash=hash_password(password),
            store_name=store_name,
            nickname=payload.get("nickname") or user_name,
            phone=payload.get("phone"),
            email=payload.get("email"),
            description=payload.get("description"),
        )
    except ValueError as exc:
        fail(str(exc))
    return ok(data)


@api.post("/auth/login")
def login(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    user_name = payload.get("userName")
    password = payload.get("password")
    role = payload.get("role") or "customer"
    if not all(isinstance(value, str) for value in (user_name, password, role)):
        fail("login fields must be strings")
    user_type = ROLE_TO_DB.get(role)
    if not user_type:
        fail("账号类型不正确")
    user = user_dao.get_auth_user_by_name(user_name)
    if not user or not verify_password(password, user["password_hash"]):
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
    return ok(book_dao.list_categories())


@api.get("/books")
def list_books(
    keyword: Optional[str] = None,
    searchType: str = "title",
    categoryId: Optional[int] = None,
    sort: str = "default",
    page: int = 1,
    pageSize: int = 12,
    inStockOnly: Optional[int] = None,
) -> dict[str, Any]:
    search_type = searchType if searchType in {"title", "author", "isbn"} else "title"
    rows = book_dao.list_books(
        keyword=keyword,
        search_type=search_type,
        category_id=categoryId,
        sort=sort,
        in_stock_only=bool(inStockOnly),
    )
    if search_type == "title" and keyword and sort == "default":
        keyword_embedding = embed_text(keyword)
        rows = sort_title_search_results(rows, keyword, keyword_embedding)
    items = [normalize_book(row) for row in page_slice(rows, page, pageSize)]
    return ok({"list": items, "total": len(rows)})


@api.get("/search/history")
def search_history(user: Optional[dict[str, Any]] = Depends(optional_user)) -> dict[str, Any]:
    if not user:
        return ok([])
    return ok(book_dao.latest_search_keywords(user["user_id"], 5))


@api.post("/search/history")
def record_search_history(
    payload: dict[str, Any] = Body(...),
    user: Optional[dict[str, Any]] = Depends(optional_user),
) -> dict[str, Any]:
    keyword = (payload.get("keyword") or "").strip()
    if user and keyword:
        book_dao.save_search_history(user["user_id"], keyword, dump_embedding(embed_text(keyword)))
    return ok({"ok": True})


@api.get("/books/recommended")
def recommended_books(
    limit: int = 10,
    type: str = Query("guess"),
    user: Optional[dict[str, Any]] = Depends(optional_user),
) -> dict[str, Any]:
    if type == "hot":
        rows = hot_books(limit)
    else:
        rows = guess_books(user["user_id"] if user else None, limit)
        settings = stats_dao.recommendation_settings()
        if settings.get("guessWeight") != 1 or settings.get("hotWeight") != 1:
            hot = hot_books(limit)
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
    if not stats_dao.recommendation_settings().get("detailSameStoreEnabled", True):
        return ok([])
    rows = book_dao.get_similar_same_store_category(bookItemId, 3)
    return ok([normalize_book(row) for row in rows[:3]])


@api.get("/stores/{storeId}")
def store_detail(storeId: int, user: Optional[dict[str, Any]] = Depends(optional_user)) -> dict[str, Any]:
    require_store_access(user, storeId)
    row = store_dao.get_detail(storeId)
    if not row:
        fail("店铺不存在", 404)
    return ok(row)


@api.get("/stores/{storeId}/books")
def store_books(
    storeId: int,
    sort: str = "default",
    page: int = 1,
    pageSize: int = 24,
    user: Optional[dict[str, Any]] = Depends(optional_user),
) -> dict[str, Any]:
    require_store_access(user, storeId)
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
    book_item_id = payload_int(payload, "bookItemId")
    quantity = payload_int(payload, "quantity", default=1)
    if quantity < 1:
        fail("quantity必须大于0")
    book = book_dao.get_detail(book_item_id)
    if not book:
        fail("图书不存在或已下架", 404)
    require_store_access(user, int(book["storeId"]))
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
    quantity = payload_int(payload, "quantity", default=1)
    if quantity < 1:
        fail("quantity必须大于0")
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
    require_address_fields(payload)
    address_id = address_dao.create(user["user_id"], payload)
    return ok({"addressId": address_id})


@api.put("/addresses/{addressId}")
def address_update(addressId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    require_address_fields(payload)
    address_dao.update(user["user_id"], addressId, payload)
    return ok({"ok": True})


@api.delete("/addresses/{addressId}")
def address_remove(addressId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    address_dao.delete(user["user_id"], addressId)
    return ok({"ok": True})


@api.post("/orders")
def order_create(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    raw_ids = payload.get("cartItemIds") or []
    if not isinstance(raw_ids, list):
        fail("cartItemIds格式不正确")
    ids = [payload_int({"value": item}, "value") for item in raw_ids]
    if not ids:
        fail("购物车中暂无商品")
    if payload.get("addressId") is None:
        fail("请选择有效收货地址")
    address_id = payload_int(payload, "addressId")
    try:
        data = order_dao.create_from_cart(
            user_id=user["user_id"],
            book_item_ids=ids,
            address_id=address_id,
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
    except pyodbc.Error:
        fail("支付处理失败，请稍后重试", 500)
    return ok(data)


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
            book_item_id=payload_int(payload, "bookItemId"),
            rating=payload_int(payload, "rating", default=5),
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
    try:
        return ok(promotion_dao.list_user_coupons(user["user_id"], status))
    except ValueError as exc:
        fail(str(exc))


@api.get("/promotions/rewards")
def rewards() -> dict[str, Any]:
    return ok(promotion_dao.list_rewards())


@api.post("/promotions/rewards/{rewardId}/redeem")
def redeem(rewardId: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        data = promotion_dao.redeem_reward(user["user_id"], rewardId)
    except ValueError as exc:
        fail(str(exc))
    return ok({"ok": True, **data})


@api.post("/promotions/weekly-coupon/claim")
def weekly_coupon(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    try:
        return ok(promotion_dao.claim_weekly_coupon(user["user_id"]))
    except ValueError as exc:
        fail(str(exc))


@api.get("/users/me")
def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    return ok(public_user(user))


@api.get("/users/me/points")
def my_points(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    return ok(promotion_dao.list_points(user["user_id"], page, pageSize))

@api.put("/users/me")
def update_me(payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    user_dao.update_profile(user["user_id"], payload)
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
        fail("缺少店铺信息")
    require_store_owner(user, store_id)
    try:
        book_item_id = book_dao.create_book(
            {
                **payload,
                "embedding": dump_embedding(embed_text(payload.get("bookName") or "")),
            },
            {"storeId": store_id, "price": payload.get("price"), "stock": payload.get("stock")},
        )
    except ValueError as exc:
        fail(str(exc), 400)
    except pyodbc.Error:
        fail("图书保存失败，请稍后重试", 500)
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
def admin_order_status(
    orderId: int,
    payload: dict[str, Any] = Body(...),
    user: dict[str, Any] = Depends(require_roles("seller", "platform_admin")),
) -> dict[str, Any]:
    db_status = STATUS_TO_DB.get(payload.get("status"), payload.get("status"))
    store_id = user["store_id"] if DB_TO_ROLE.get(user["user_type"]) == "seller" else None
    try:
        order_dao.update_status(orderId, db_status, store_id)
    except ValueError as exc:
        fail(str(exc), 403 if "无权限" in str(exc) else 400)
    return ok({"ok": True})


@api.post("/admin/orders/{orderId}/refund/{action}")
def admin_refund(
    orderId: int,
    action: str,
    user: dict[str, Any] = Depends(require_roles("seller", "platform_admin")),
) -> dict[str, Any]:
    if action not in {"approve", "reject"}:
        fail("退款处理类型不正确")
    store_id = user["store_id"] if DB_TO_ROLE.get(user["user_type"]) == "seller" else None
    try:
        order_dao.handle_refund(orderId, action == "approve", store_id)
    except ValueError as exc:
        fail(str(exc), 403 if "无权限" in str(exc) else 400)
    return ok({"ok": True})


@api.get("/admin/users")
def admin_users(keyword: Optional[str] = None, user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    store_id = user["store_id"] if DB_TO_ROLE.get(user["user_type"]) == "seller" else None
    rows = user_dao.list_customers(keyword, store_id)
    return ok({"list": rows, "total": len(rows)})


@api.post("/admin/users/{userId}/blacklist")
def admin_blacklist(userId: int, payload: dict[str, Any] = Body(...), user: dict[str, Any] = Depends(require_roles("seller"))) -> dict[str, Any]:
    store_dao.add_to_blacklist(user["store_id"], userId, payload.get("reason"))
    return ok({"ok": True})


@api.delete("/admin/users/{userId}/blacklist")
def admin_unblacklist(userId: int, user: dict[str, Any] = Depends(require_roles("seller"))) -> dict[str, Any]:
    store_dao.remove_from_blacklist(user["store_id"], userId)
    return ok({"ok": True})


@api.put("/admin/users/{userId}/status")
def admin_user_status(userId: int, payload: dict[str, Any] = Body(...), _: dict[str, Any] = Depends(require_roles("platform_admin"))) -> dict[str, Any]:
    user_dao.set_user_status(userId, STATUS_TO_DB.get(payload.get("status"), "正常"))
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
def admin_promo_activities(user: dict[str, Any] = Depends(require_roles("seller", "platform_admin"))) -> dict[str, Any]:
    store_id = user.get("store_id") if DB_TO_ROLE.get(user["user_type"]) == "seller" else None
    return ok(promotion_dao.list_activities(admin_view=True, store_id=store_id))


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
    try:
        participation = promotion_dao.set_store_participation(user["store_id"], activityId, payload)
    except ValueError as exc:
        fail(str(exc))
    return ok({"ok": True, "participation": participation})


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
    try:
        rewardId = promotion_dao.save_reward(payload, user["user_id"], rewardId)
    except ValueError as exc:
        fail(str(exc))
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
    app.mount("/", FrontendStaticFiles(directory=frontend_dir, html=True), name="frontend")
