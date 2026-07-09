from __future__ import annotations

import sys
from uuid import uuid4
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


def assert_ok(res, label: str) -> dict:
    payload = res.json()
    print(f"{label} -> status={res.status_code} code={payload.get('code')}")
    assert res.status_code == 200, payload
    assert payload.get("code") == 0, payload
    return payload


def assert_error(res, label: str) -> dict:
    payload = res.json()
    print(f"{label} -> status={res.status_code} code={payload.get('code')}")
    assert payload.get("code") != 0, payload
    return payload


def login(client: TestClient, user_name: str, password: str, role: str) -> tuple[str, dict]:
    payload = assert_ok(
        client.post("/api/auth/login", json={"userName": user_name, "password": password, "role": role}),
        f"login {user_name}",
    )
    return payload["data"]["token"], payload["data"]["user"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def main() -> None:
    client = TestClient(app)
    paths = [
        "/api/health",
        "/api/categories",
        "/api/books?page=1&pageSize=3",
        "/api/books?keyword=python&page=1&pageSize=3",
        "/api/books/recommended?type=hot&limit=5",
    ]
    for path in paths:
        payload = assert_ok(client.get(path), path)
        data = payload.get("data")
        if isinstance(data, dict) and "list" in data:
            size = len(data["list"])
        elif isinstance(data, list):
            size = len(data)
        else:
            size = 1 if data is not None else 0
        print(f"{path} size={size}")

    assert_error(
        client.post("/api/auth/login", json={"userName": "not_registered_demo", "password": "Demo123", "role": "customer"}),
        "unregistered login rejected",
    )

    reader_token, reader = login(client, "reader_demo", "Demo123", "customer")
    assert reader["userName"] == "reader_demo"
    reader_cart = assert_ok(client.get("/api/cart", headers=auth(reader_token)), "seed reader cart")["data"]
    assert reader_cart, "Seed cart should contain at least one item"
    seed_book = reader_cart[0].get("book") or {}
    assert seed_book.get("bookName"), reader_cart[0]
    assert seed_book.get("storeName"), reader_cart[0]
    assert isinstance(seed_book.get("price"), (int, float)), reader_cart[0]

    reader_orders = assert_ok(client.get("/api/orders?status=pending_payment", headers=auth(reader_token)), "seed pending orders")[
        "data"
    ]["list"]
    seed_pending = next((item for item in reader_orders if item["orderNo"] == "TEST-PENDING-001"), None)
    if seed_pending:
        cancelled = assert_ok(
            client.post(f"/api/orders/{seed_pending['orderId']}/cancel", headers=auth(reader_token)),
            "seed pending cancel",
        )["data"]
        assert cancelled["order"]["orderStatus"] == "cancelled", cancelled

    books = assert_ok(client.get("/api/books?page=1&pageSize=10&inStockOnly=1", headers=auth(reader_token)), "books in stock")[
        "data"
    ]["list"]
    assert books, "No in-stock books are available for checkout smoke test"
    book = next((item for item in books if int(item.get("stock") or 0) > 0), books[0])
    book_item_id = int(book["bookItemId"])

    temp_name = "smoke_" + uuid4().hex[:8]
    assert_ok(
        client.post(
            "/api/auth/register/user",
            json={"userName": temp_name, "password": "Demo123", "nickname": "Smoke Test"},
        ),
        "register temp reader",
    )
    temp_token, _ = login(client, temp_name, "Demo123", "customer")

    assert_ok(client.post("/api/cart", json={"bookItemId": book_item_id, "quantity": 1}, headers=auth(temp_token)), "cart add")
    cart = assert_ok(client.get("/api/cart", headers=auth(temp_token)), "cart list")["data"]
    assert any(int(item["bookItemId"]) == book_item_id for item in cart)
    matched_cart_item = next(item for item in cart if int(item["bookItemId"]) == book_item_id)
    assert matched_cart_item["book"]["bookName"]
    assert matched_cart_item["book"]["storeName"]
    assert isinstance(matched_cart_item["book"]["price"], (int, float))

    order = assert_ok(
        client.post(
            "/api/orders",
            json={
                "cartItemIds": [book_item_id],
                "receiverName": "Smoke Test",
                "receiverPhone": "13800000000",
                "receiverAddress": "Smoke test address",
            },
            headers=auth(temp_token),
        ),
        "order create",
    )["data"]
    assert order["orderId"]
    pay_started = perf_counter()
    payment = assert_ok(
        client.post(
            f"/api/orders/{order['orderId']}/pay",
            json={"paymentMethod": "alipay"},
            headers=auth(temp_token),
        ),
        "order pay",
    )["data"]
    assert perf_counter() - pay_started < 8
    assert payment["paymentStatus"] == "success"
    assert payment["order"]["orderStatus"] == "completed"
    assert payment["order"]["paymentStatus"] == "paid"
    assert payment["order"]["items"][0]["storeName"]
    pay_retry_started = perf_counter()
    repeat_payment = assert_ok(
        client.post(
            f"/api/orders/{order['orderId']}/pay",
            json={"paymentMethod": "wechat"},
            headers=auth(temp_token),
        ),
        "order pay idempotent retry",
    )["data"]
    assert perf_counter() - pay_retry_started < 8
    assert repeat_payment["paymentStatus"] == "success"
    assert repeat_payment["order"]["paymentStatus"] == "paid"
    points = assert_ok(client.get("/api/users/me/points", headers=auth(temp_token)), "points records")["data"]
    assert points["total"] >= 1
    assert_ok(
        client.post(
            f"/api/orders/{order['orderId']}/reviews",
            json={"bookItemId": book_item_id, "rating": 5, "content": "Smoke test review"},
            headers=auth(temp_token),
        ),
        "review create",
    )
    assert_error(
        client.post(
            f"/api/orders/{order['orderId']}/reviews",
            json={"bookItemId": book_item_id, "rating": 5, "content": "Duplicate smoke test review"},
            headers=auth(temp_token),
        ),
        "review duplicate rejected",
    )
    orders = assert_ok(client.get("/api/orders", headers=auth(temp_token)), "orders list")["data"]["list"]
    assert any(int(item["orderId"]) == int(order["orderId"]) for item in orders)
    low_name = "low_" + uuid4().hex[:8]
    assert_ok(
        client.post(
            "/api/auth/register/user",
            json={"userName": low_name, "password": "Demo123", "nickname": "Low Level"},
        ),
        "register low level reader",
    )
    low_token, _ = login(client, low_name, "Demo123", "customer")
    assert_error(
        client.post("/api/promotions/weekly-coupon/claim", headers=auth(low_token)),
        "weekly coupon level guard",
    )

    seller_token, _ = login(client, "seller_demo", "Demo123", "seller")
    assert_ok(client.get("/api/admin/books", headers=auth(seller_token)), "seller admin books")
    assert_ok(client.get("/api/admin/orders", headers=auth(seller_token)), "seller admin orders")
    assert_ok(client.get("/api/admin/statistics/overview", headers=auth(seller_token)), "seller stats overview")

    admin_token, _ = login(client, "admin", "Demo123", "platform_admin")
    assert_ok(client.get("/api/admin/stores", headers=auth(admin_token)), "platform stores")
    assert_ok(client.get("/api/admin/statistics/overview", headers=auth(admin_token)), "platform stats overview")
    assert_ok(client.get("/api/admin/statistics/risk-stores", headers=auth(admin_token)), "risk stores")
    export_res = client.get("/api/admin/statistics/export?range=7d", headers=auth(admin_token))
    print(f"statistics export -> status={export_res.status_code} content-type={export_res.headers.get('content-type')}")
    assert export_res.status_code == 200
    assert "date,storeName,bookName,quantity,salesAmount" in export_res.text
    settings = assert_ok(client.get("/api/admin/recommendation/settings", headers=auth(admin_token)), "recommendation settings")[
        "data"
    ]
    assert_ok(
        client.put(
            "/api/admin/recommendation/settings",
            json={
                "guessWeight": settings.get("guessWeight", 1),
                "hotWeight": settings.get("hotWeight", 1),
                "searchEmbeddingEnabled": settings.get("searchEmbeddingEnabled", True),
                "detailSameStoreEnabled": settings.get("detailSameStoreEnabled", True),
            },
            headers=auth(admin_token),
        ),
        "recommendation settings update",
    )
    assert_ok(
        client.post(
            "/api/admin/promotions/coupons",
            json={"couponName": "Smoke平台券", "amount": 1, "minAmount": 0, "quantity": 1},
            headers=auth(admin_token),
        ),
        "platform coupon create",
    )

    activities = assert_ok(client.get("/api/promotions/activities", headers=auth(temp_token)), "activities list")["data"]
    if activities:
        activity_id = activities[0]["activityId"]
        assert_ok(
            client.post(
                f"/api/admin/promotions/activities/{activity_id}/store-participation",
                json={"participate": True, "books": [str(book_item_id)], "couponAmount": 1, "couponQuantity": 1},
                headers=auth(seller_token),
            ),
            "seller activity participation",
        )
        assert_ok(
            client.post(f"/api/promotions/activities/{activity_id}/join", headers=auth(temp_token)),
            "activity join",
        )


if __name__ == "__main__":
    main()
