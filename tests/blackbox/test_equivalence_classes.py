from __future__ import annotations

from uuid import uuid4

import pytest
from hypothesis import given

from conftest import assert_ok, cleanup_customer
from tests.blackbox.strategies import (
    cart_actions,
    invalid_page_values,
    invalid_passwords,
    invalid_search_types,
    invalid_usernames,
    malicious_text,
)


pytestmark = [pytest.mark.integration, pytest.mark.blackbox_smoke]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"userName": "reader_demo", "password": "wrong", "role": "customer"},
        {"userName": "reader_demo", "password": "Demo123", "role": "seller"},
        {"userName": {}, "password": "Demo123", "role": "customer"},
        {"userName": "reader_demo", "password": False, "role": "customer"},
        {"userName": "reader_demo", "password": "Demo123", "role": "unknown"},
    ],
)
def test_invalid_login_equivalence_classes_never_reach_a_server_error(safe_client, body) -> None:
    response = safe_client.post("/api/auth/login", json=body)
    assert 400 <= response.status_code < 500
    assert response.json()["code"] != 0


@given(user_name=invalid_usernames, password=invalid_passwords)
def test_invalid_registration_equivalence_classes(client, user_name, password) -> None:
    response = client.post(
        "/api/auth/register/user",
        json={"userName": user_name, "password": password, "nickname": "invalid"},
    )
    assert response.status_code == 400
    assert response.json()["code"] != 0


@pytest.mark.parametrize(
    ("user_name", "password"),
    [("abc", "123456"), ("boundary_user", "abcdef")],
)
def test_valid_registration_boundaries(client, user_name, password) -> None:
    unique_name = f"{user_name}_{uuid4().hex[:8]}"
    user_id = None
    try:
        data = assert_ok(
            client.post(
                "/api/auth/register/user",
                json={"userName": unique_name, "password": password, "nickname": unique_name},
            )
        )
        user_id = int(data["userId"])
    finally:
        if user_id is not None:
            cleanup_customer(user_id)


@given(search_type=invalid_search_types, payload=malicious_text)
def test_search_invalid_type_and_malicious_text_never_crash(client, search_type, payload) -> None:
    response = client.get(
        "/api/books",
        params={"keyword": payload, "searchType": search_type, "page": 1, "pageSize": 10},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 0
    assert payload not in response.text


@given(value=invalid_page_values)
def test_invalid_pagination_types_are_rejected(client, value) -> None:
    response = client.get("/api/books", params={"page": value, "pageSize": value})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"bookItemId": None, "quantity": 1},
        {"bookItemId": "not-an-id", "quantity": 1},
        {"bookItemId": 1, "quantity": "not-a-number"},
    ],
)
def test_invalid_cart_body_types_return_client_errors(safe_client, acceptance_context, body) -> None:
    response = safe_client.post("/api/cart", json=body, headers=acceptance_context["headers"])
    assert response.status_code in {400, 404, 422}


@pytest.mark.parametrize("quantity", [0, -1])
def test_non_positive_cart_quantities_are_invalid(client, acceptance_context, quantity) -> None:
    response = client.post(
        "/api/cart",
        json={"bookItemId": acceptance_context["bookItemId"], "quantity": quantity},
        headers=acceptance_context["headers"],
    )
    assert response.status_code == 400


def test_cart_stock_plus_one_and_unknown_book_are_invalid(client, acceptance_context) -> None:
    headers = acceptance_context["headers"]
    for book_item_id, quantity in (
        (acceptance_context["bookItemId"], acceptance_context["stock"] + 1),
        (2_147_483_647, 1),
    ):
        response = client.post(
            "/api/cart", json={"bookItemId": book_item_id, "quantity": quantity}, headers=headers
        )
        assert response.status_code in {400, 404}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"receiverName": "", "phone": "13800000000", "detail": "address"},
        {"receiverName": "receiver", "phone": "", "detail": "address"},
        {"receiverName": "receiver", "phone": "13800000000", "detail": ""},
    ],
)
def test_missing_address_fields_are_invalid(client, acceptance_context, body) -> None:
    response = client.post("/api/addresses", json=body, headers=acceptance_context["headers"])
    assert 400 <= response.status_code < 500


def test_empty_cart_and_foreign_address_are_rejected(
    client, acceptance_context, temporary_customer
) -> None:
    headers = acceptance_context["headers"]
    empty = client.post(
        "/api/orders",
        json={"cartItemIds": [], "addressId": acceptance_context["addressId"]},
        headers=headers,
    )
    assert empty.status_code == 400

    foreign_address = assert_ok(
        client.post(
            "/api/addresses",
            json={"receiverName": "Other", "phone": "13800000001", "detail": "Other address"},
            headers=temporary_customer["headers"],
        )
    )["addressId"]
    assert_ok(
        client.post(
            "/api/cart",
            json={"bookItemId": acceptance_context["bookItemId"], "quantity": 1},
            headers=headers,
        )
    )
    rejected = client.post(
        "/api/orders",
        json={"cartItemIds": [acceptance_context["bookItemId"]], "addressId": foreign_address},
        headers=headers,
    )
    assert rejected.status_code == 400


@pytest.mark.parametrize(("rating", "expected_status"), [(1, 200), (5, 200), (0, 400), (6, 400)])
def test_review_rating_equivalence_classes(client, acceptance_context, rating, expected_status) -> None:
    headers = acceptance_context["headers"]
    book_item_id = acceptance_context["bookItemId"]
    assert_ok(client.post("/api/cart", json={"bookItemId": book_item_id, "quantity": 1}, headers=headers))
    order_id = int(
        assert_ok(
            client.post(
                "/api/orders",
                json={"cartItemIds": [book_item_id], "addressId": acceptance_context["addressId"]},
                headers=headers,
            )
        )["orderId"]
    )
    assert_ok(
        client.post(
            f"/api/orders/{order_id}/pay", json={"paymentMethod": "alipay"}, headers=headers
        )
    )
    response = client.post(
        f"/api/orders/{order_id}/reviews",
        json={"bookItemId": book_item_id, "rating": rating, "content": "rating boundary"},
        headers=headers,
    )
    assert response.status_code == expected_status


def test_non_integer_review_rating_is_invalid(safe_client, acceptance_context) -> None:
    response = safe_client.post(
        "/api/orders/2147483647/reviews",
        json={"bookItemId": acceptance_context["bookItemId"], "rating": "five", "content": "invalid"},
        headers=acceptance_context["headers"],
    )
    assert 400 <= response.status_code < 500


@given(actions=cart_actions)
def test_cart_actions_follow_a_state_model(client, acceptance_context, actions) -> None:
    headers = acceptance_context["headers"]
    book_item_id = acceptance_context["bookItemId"]
    client.delete(f"/api/cart/{book_item_id}", headers=headers)
    expected_quantity = 0
    for action, quantity in actions:
        if action == "add":
            allowed = expected_quantity + quantity <= acceptance_context["stock"]
            response = client.post(
                "/api/cart",
                json={"bookItemId": book_item_id, "quantity": quantity},
                headers=headers,
            )
            if allowed:
                assert response.status_code == 200
                expected_quantity += quantity
            else:
                assert response.status_code == 400
        elif action == "update":
            response = client.put(
                f"/api/cart/{book_item_id}", json={"quantity": quantity}, headers=headers
            )
            assert response.status_code == 200
            if expected_quantity:
                expected_quantity = quantity
        else:
            assert client.delete(f"/api/cart/{book_item_id}", headers=headers).status_code == 200
            expected_quantity = 0
        cart = assert_ok(client.get("/api/cart", headers=headers))
        current = next((item for item in cart if int(item["bookItemId"]) == book_item_id), None)
        assert (int(current["quantity"]) if current else 0) == expected_quantity
    client.delete(f"/api/cart/{book_item_id}", headers=headers)
