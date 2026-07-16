from __future__ import annotations

import os
from time import perf_counter

import pytest

from conftest import assert_ok


@pytest.mark.integration
def test_authentication_and_role_boundaries(client, seeded_tokens) -> None:
    unauthenticated = client.get("/api/cart")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] != 0

    invalid_token = client.get("/api/cart", headers={"Authorization": "Bearer invalid.token.value"})
    assert invalid_token.status_code == 401
    assert invalid_token.json()["code"] != 0

    bad_password = client.post("/api/auth/login", json={"userName": "reader_demo", "password": "wrong-password", "role": "customer"})
    assert bad_password.status_code == 401
    assert bad_password.json()["code"] != 0

    customer_headers = seeded_tokens["customer"]["headers"]
    seller_headers = seeded_tokens["seller"]["headers"]
    assert client.get("/api/admin/stores", headers=customer_headers).status_code == 403
    assert client.get("/api/admin/stores", headers=seller_headers).status_code == 403
    assert client.post("/api/admin/promotions/activities", json={}, headers=seller_headers).status_code == 403


@pytest.mark.integration
def test_search_input_is_treated_as_data(client) -> None:
    injection = client.get("/api/books?keyword=%27%20OR%201%3D1--&searchType=isbn&page=1&pageSize=10")
    assert injection.status_code == 200
    payload = injection.json()
    assert payload["code"] == 0
    assert payload["data"]["total"] == 0

    xss = client.get("/api/books?keyword=%3Cscript%3Ealert(1)%3C%2Fscript%3E&searchType=title&page=1&pageSize=10")
    assert xss.status_code == 200
    assert xss.json()["code"] == 0


@pytest.mark.integration
@pytest.mark.performance
def test_course_acceptance_response_time_thresholds(client, seeded_tokens) -> None:
    public_limit = float(os.getenv("EBOOKSTORE_PUBLIC_API_LIMIT_SECONDS", "3"))
    export_limit = float(os.getenv("EBOOKSTORE_EXPORT_LIMIT_SECONDS", "8"))
    for path in ("/api/books?page=1&pageSize=12", "/api/books?keyword=test&searchType=title&page=1&pageSize=12"):
        started = perf_counter()
        assert_ok(client.get(path))
        assert perf_counter() - started < public_limit, f"{path} exceeded {public_limit}s"

    started = perf_counter()
    export = client.get("/api/admin/statistics/export?range=7d", headers=seeded_tokens["platform_admin"]["headers"])
    assert export.status_code == 200
    assert "date,storeName,bookName,quantity,salesAmount" in export.text
    assert perf_counter() - started < export_limit, f"statistics export exceeded {export_limit}s"
