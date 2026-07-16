from __future__ import annotations

import pytest

from backend.app.db import get_conn
from conftest import assert_ok


def scalar(sql: str, *params):
    with get_conn() as conn:
        return conn.cursor().execute(sql, *params).fetchval()


@pytest.mark.integration
def test_checkout_payment_is_idempotent_and_persists_consistent_state(client, temporary_customer) -> None:
    headers = temporary_customer["headers"]
    user_id = temporary_customer["userId"]
    books = assert_ok(client.get("/api/books?inStockOnly=1&page=1&pageSize=20"))["list"]
    book = next(item for item in books if int(item["stock"]) >= 2)
    book_item_id = int(book["bookItemId"])
    stock_before = int(scalar("SELECT stock FROM book_items WHERE book_item_id = ?", book_item_id))
    sales_before = int(scalar("SELECT sales_count FROM book_items WHERE book_item_id = ?", book_item_id))

    address_id = assert_ok(
        client.post(
            "/api/addresses",
            json={"receiverName": "Acceptance", "phone": "13800000000", "detail": "Test address", "isDefault": True},
            headers=headers,
        )
    )["addressId"]
    assert_ok(client.post("/api/cart", json={"bookItemId": book_item_id, "quantity": 1}, headers=headers))
    order = assert_ok(client.post("/api/orders", json={"cartItemIds": [book_item_id], "addressId": address_id}, headers=headers))
    order_id = int(order["orderId"])

    paid = assert_ok(client.post(f"/api/orders/{order_id}/pay", json={"paymentMethod": "alipay"}, headers=headers))
    assert paid["paymentStatus"] == "success"
    assert paid["order"]["orderStatus"] == "completed"
    assert paid["order"]["paymentStatus"] == "paid"
    repeated = assert_ok(client.post(f"/api/orders/{order_id}/pay", json={"paymentMethod": "wechat"}, headers=headers))
    assert repeated["paymentStatus"] == "success"

    assert int(scalar("SELECT stock FROM book_items WHERE book_item_id = ?", book_item_id)) == stock_before - 1
    assert int(scalar("SELECT sales_count FROM book_items WHERE book_item_id = ?", book_item_id)) == sales_before + 1
    assert int(scalar("SELECT COUNT(*) FROM payment_records WHERE order_id = ?", order_id)) == 1
    assert int(scalar("SELECT COUNT(*) FROM cart_items WHERE user_id = ? AND book_item_id = ?", user_id, book_item_id)) == 0
    assert int(scalar("SELECT COUNT(*) FROM points_records WHERE user_id = ? AND related_id = ?", user_id, order_id)) == 1

    assert_ok(client.post(f"/api/orders/{order_id}/reviews", json={"bookItemId": book_item_id, "rating": 5, "content": "accepted"}, headers=headers))
    duplicate = client.post(f"/api/orders/{order_id}/reviews", json={"bookItemId": book_item_id, "rating": 5, "content": "duplicate"}, headers=headers)
    assert duplicate.status_code == 400
    assert duplicate.json()["code"] != 0


@pytest.mark.integration
def test_insufficient_stock_does_not_create_an_order_or_change_inventory(client, temporary_customer) -> None:
    headers = temporary_customer["headers"]
    book = assert_ok(client.get("/api/books?inStockOnly=1&page=1&pageSize=20"))["list"][0]
    book_item_id = int(book["bookItemId"])
    stock = int(scalar("SELECT stock FROM book_items WHERE book_item_id = ?", book_item_id))
    rejected = client.post("/api/cart", json={"bookItemId": book_item_id, "quantity": stock + 1}, headers=headers)
    assert rejected.status_code == 400
    assert rejected.json()["code"] != 0
    assert int(scalar("SELECT stock FROM book_items WHERE book_item_id = ?", book_item_id)) == stock
    assert int(scalar("SELECT COUNT(*) FROM orders WHERE user_id = ?", temporary_customer["userId"])) == 0


@pytest.mark.integration
def test_cancel_and_approved_refund_restore_reserved_or_sold_inventory(client, temporary_customer, seeded_tokens) -> None:
    headers = temporary_customer["headers"]
    book = next(item for item in assert_ok(client.get("/api/books?inStockOnly=1&page=1&pageSize=20"))["list"] if int(item["stock"]) >= 2)
    book_item_id = int(book["bookItemId"])
    stock_before = int(scalar("SELECT stock FROM book_items WHERE book_item_id = ?", book_item_id))
    sales_before = int(scalar("SELECT sales_count FROM book_items WHERE book_item_id = ?", book_item_id))
    address_id = assert_ok(
        client.post(
            "/api/addresses",
            json={"receiverName": "Acceptance", "phone": "13800000000", "detail": "Test address", "isDefault": True},
            headers=headers,
        )
    )["addressId"]

    assert_ok(client.post("/api/cart", json={"bookItemId": book_item_id, "quantity": 1}, headers=headers))
    pending_id = int(assert_ok(client.post("/api/orders", json={"cartItemIds": [book_item_id], "addressId": address_id}, headers=headers))["orderId"])
    assert int(scalar("SELECT locked_stock FROM book_items WHERE book_item_id = ?", book_item_id)) == 1
    cancelled = assert_ok(client.post(f"/api/orders/{pending_id}/cancel", headers=headers))
    assert cancelled["order"]["orderStatus"] == "cancelled"
    assert int(scalar("SELECT stock FROM book_items WHERE book_item_id = ?", book_item_id)) == stock_before
    assert int(scalar("SELECT locked_stock FROM book_items WHERE book_item_id = ?", book_item_id)) == 0

    assert_ok(client.post("/api/cart", json={"bookItemId": book_item_id, "quantity": 1}, headers=headers))
    paid_id = int(assert_ok(client.post("/api/orders", json={"cartItemIds": [book_item_id], "addressId": address_id}, headers=headers))["orderId"])
    assert_ok(client.post(f"/api/orders/{paid_id}/pay", json={"paymentMethod": "alipay"}, headers=headers))
    assert_ok(client.post(f"/api/orders/{paid_id}/refund", json={"reason": "acceptance test"}, headers=headers))
    assert_ok(client.post(f"/api/admin/orders/{paid_id}/refund/approve", headers=seeded_tokens["platform_admin"]["headers"]))
    assert int(scalar("SELECT stock FROM book_items WHERE book_item_id = ?", book_item_id)) == stock_before
    assert int(scalar("SELECT sales_count FROM book_items WHERE book_item_id = ?", book_item_id)) == sales_before
