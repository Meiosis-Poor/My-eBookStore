from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db import get_conn
from backend.app.main import app


def pytest_collection_modifyitems(items) -> None:
    """Existing API smoke tests also write data and therefore need test-db protection."""
    for item in items:
        if item.path.name == "test_api_smoke.py":
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def test_database_guard(request) -> None:
    if request.node.get_closest_marker("integration") is None:
        return
    from backend.app.config import settings

    assert settings.sqlserver_database.lower().endswith("_test"), (
        "Integration tests require a dedicated database whose name ends with '_Test'. "
        "Set EBOOKSTORE_ENV_FILE=.env.test before running pytest."
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def assert_ok(response) -> dict:
    payload = response.json()
    assert response.status_code == 200, payload
    assert payload["code"] == 0, payload
    return payload["data"]


@pytest.fixture
def seeded_tokens(client: TestClient) -> dict[str, dict]:
    result = {}
    for user_name, role in (
        ("reader_demo", "customer"),
        ("seller_demo", "seller"),
        ("admin", "platform_admin"),
    ):
        data = assert_ok(
            client.post(
                "/api/auth/login",
                json={"userName": user_name, "password": "Demo123", "role": role},
            )
        )
        result[role] = {"user": data["user"], "headers": {"Authorization": f"Bearer {data['token']}"}}
    return result


@pytest.fixture
def temporary_customer(client: TestClient) -> Iterator[dict]:
    user_name = f"acceptance_{uuid4().hex[:12]}"
    data = assert_ok(
        client.post(
            "/api/auth/register/user",
            json={"userName": user_name, "password": "Demo123", "nickname": "Acceptance Test"},
        )
    )
    user_id = int(data["userId"])
    login = assert_ok(
        client.post(
            "/api/auth/login",
            json={"userName": user_name, "password": "Demo123", "role": "customer"},
        )
    )
    try:
        yield {"userId": user_id, "headers": {"Authorization": f"Bearer {login['token']}"}}
    finally:
        # Delete dependent rows first because the course schema intentionally has no cascade deletes.
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reviews WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM points_records WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM refund_records WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM payment_records WHERE user_id = ?", user_id)
            cursor.execute("UPDATE user_coupons SET order_id = NULL WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM order_items WHERE order_id IN (SELECT order_id FROM orders WHERE user_id = ?)", user_id)
            cursor.execute("DELETE FROM orders WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM cart_items WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM shipping_addresses WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM search_history WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM user_coupons WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM ordinary_users WHERE user_id = ?", user_id)
            cursor.execute("DELETE FROM users WHERE user_id = ?", user_id)
