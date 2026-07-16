from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.db import get_conn
from backend.app.main import app


_state_baseline: dict[str, dict[int, tuple[int, ...]]] | None = None


def pytest_collection_modifyitems(items) -> None:
    for item in items:
        if item.path.name in {"test_api_smoke.py", "test_database_workflows.py"}:
            item.add_marker(pytest.mark.integration)


def _database_state() -> dict[str, dict[int, tuple[int, ...]]]:
    with get_conn() as conn:
        cursor = conn.cursor()
        books = {
            int(row[0]): (int(row[1]), int(row[2]), int(row[3]))
            for row in cursor.execute(
                "SELECT book_item_id, stock, locked_stock, sales_count FROM book_items"
            ).fetchall()
        }
        rewards = {
            int(row[0]): (int(row[1]),)
            for row in cursor.execute("SELECT reward_id, stock FROM point_rewards").fetchall()
        }
    return {"book_items": books, "point_rewards": rewards}


def _artifact_counts() -> dict[str, int]:
    with get_conn() as conn:
        cursor = conn.cursor()
        return {
            "temporary_users": int(
                cursor.execute(
                    "SELECT COUNT(*) FROM users WHERE user_name LIKE N'acceptance[_]%' OR user_name LIKE N'workflow[_]%'"
                ).fetchval()
            ),
            "temporary_books": int(
                cursor.execute("SELECT COUNT(*) FROM book_infos WHERE ISBN LIKE N'TEST-AUTO-%'").fetchval()
            ),
            "orphan_orders": int(
                cursor.execute(
                    "SELECT COUNT(*) FROM orders o LEFT JOIN users u ON u.user_id = o.user_id WHERE u.user_id IS NULL"
                ).fetchval()
            ),
            "orphan_payments": int(
                cursor.execute(
                    "SELECT COUNT(*) FROM payment_records p LEFT JOIN orders o ON o.order_id = p.order_id WHERE o.order_id IS NULL"
                ).fetchval()
            ),
        }


def pytest_sessionfinish(session, exitstatus) -> None:
    if _state_baseline is None:
        return
    errors = []
    current = _database_state()
    if current != _state_baseline:
        errors.append("seed book/reward state changed during the test session")
    artifacts = _artifact_counts()
    leftovers = {name: count for name, count in artifacts.items() if count}
    if leftovers:
        errors.append(f"test artifacts remain: {leftovers}")
    if errors:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter:
            reporter.write_sep("=", "database isolation failure", red=True)
            for error in errors:
                reporter.write_line(error, red=True)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(autouse=True)
def test_database_guard(request) -> None:
    global _state_baseline
    if request.node.get_closest_marker("integration") is None:
        return
    env_file = os.getenv("EBOOKSTORE_ENV_FILE")
    assert env_file and Path(env_file).name.lower() == ".env.test", (
        "Integration tests require EBOOKSTORE_ENV_FILE=.env.test."
    )
    database = settings.sqlserver_database.lower()
    assert database.endswith("_test") and database not in {"master", "model", "msdb", "tempdb"}, (
        "Integration tests require a dedicated database whose name ends with '_Test'."
    )
    with get_conn() as conn:
        applied = int(
            conn.cursor().execute(
                "SELECT COUNT(*) FROM deployment_migrations WHERE migration_name = N'99_test_seed.sql'"
            ).fetchval()
            or 0
        )
    assert applied == 1, "Run scripts/init_db.py before integration tests."
    if _state_baseline is None:
        _state_baseline = _database_state()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def safe_client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def assert_ok(response) -> dict:
    payload = response.json()
    assert response.status_code == 200, payload
    assert payload["code"] == 0, payload
    return payload["data"]


def register_customer(client: TestClient, prefix: str = "acceptance") -> dict[str, Any]:
    user_name = f"{prefix}_{uuid4().hex[:12]}"
    data = assert_ok(
        client.post(
            "/api/auth/register/user",
            json={"userName": user_name, "password": "Demo123", "nickname": "Acceptance Test"},
        )
    )
    login = assert_ok(
        client.post(
            "/api/auth/login",
            json={"userName": user_name, "password": "Demo123", "role": "customer"},
        )
    )
    return {
        "userId": int(data["userId"]),
        "userName": user_name,
        "headers": {"Authorization": f"Bearer {login['token']}"},
    }


def cleanup_customer(user_id: int) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reviews WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM refund_records WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM payment_records WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM points_records WHERE user_id = ?", user_id)
        cursor.execute("UPDATE user_coupons SET order_id = NULL WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM order_items WHERE order_id IN (SELECT order_id FROM orders WHERE user_id = ?)", user_id)
        cursor.execute("DELETE FROM orders WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM cart_items WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM shipping_addresses WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM search_history WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM browse_history WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM store_blacklists WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM checkin_record WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM reward_redemptions WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM user_coupons WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM ordinary_users WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM users WHERE user_id = ?", user_id)


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
    customer = register_customer(client)
    try:
        yield customer
    finally:
        cleanup_customer(customer["userId"])


@pytest.fixture
def acceptance_context(client: TestClient, seeded_tokens) -> Iterator[dict[str, Any]]:
    customer = register_customer(client)
    token = uuid4().hex
    isbn = f"TEST-AUTO-{token}"
    book_item_id = None
    book_info_id = None
    try:
        address_id = int(
            assert_ok(
                client.post(
                    "/api/addresses",
                    json={
                        "receiverName": "Acceptance",
                        "phone": "13800000000",
                        "detail": "Acceptance test address",
                        "isDefault": True,
                    },
                    headers=customer["headers"],
                )
            )["addressId"]
        )
        category_id = int(assert_ok(client.get("/api/categories"))[0]["categoryId"])
        created = assert_ok(
            client.post(
                "/api/admin/books",
                json={
                    "bookName": f"Acceptance Book {token[:8]}",
                    "author": "Acceptance Test",
                    "publisher": "Test Publisher",
                    "isbn": isbn,
                    "categoryId": category_id,
                    "price": 25,
                    "stock": 5,
                    "description": "Temporary test-owned book",
                },
                headers=seeded_tokens["seller"]["headers"],
            )
        )
        book_item_id = int(created["bookItemId"])
        with get_conn() as conn:
            row = conn.cursor().execute(
                "SELECT book_info_id, stock, locked_stock, sales_count FROM book_items WHERE book_item_id = ?",
                book_item_id,
            ).fetchone()
        book_info_id = int(row[0])
        yield {
            **customer,
            "addressId": address_id,
            "bookItemId": book_item_id,
            "bookInfoId": book_info_id,
            "isbn": isbn,
            "stock": int(row[1]),
            "lockedStock": int(row[2]),
            "salesCount": int(row[3]),
        }
    finally:
        cleanup_customer(customer["userId"])
        if book_item_id is not None:
            with get_conn() as conn:
                conn.cursor().execute("DELETE FROM activity_books WHERE book_item_id = ?", book_item_id)
                conn.cursor().execute("DELETE FROM book_items WHERE book_item_id = ?", book_item_id)
                if book_info_id is not None:
                    conn.cursor().execute("DELETE FROM book_infos WHERE book_info_id = ?", book_info_id)
