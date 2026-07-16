from __future__ import annotations

import os
from statistics import median
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
@pytest.mark.parametrize(
    ("search_type", "expect_empty"),
    [("title", False), ("author", True), ("isbn", True)],
)
def test_search_input_is_treated_as_data(client, search_type, expect_empty) -> None:
    marker = "' OR 1=1--"
    injection = client.get(
        "/api/books",
        params={"keyword": marker, "searchType": search_type, "page": 1, "pageSize": 10},
    )
    assert injection.status_code == 200
    payload = injection.json()
    assert payload["code"] == 0
    if expect_empty:
        assert payload["data"]["total"] == 0
    assert marker not in injection.text

    xss_marker = "<script>acceptance_xss_marker</script>"
    xss = client.get(
        "/api/books",
        params={"keyword": xss_marker, "searchType": search_type, "page": 1, "pageSize": 10},
    )
    assert xss.status_code == 200
    assert xss.json()["code"] == 0
    assert xss_marker not in xss.text


@pytest.mark.integration
@pytest.mark.performance
def test_course_acceptance_response_time_thresholds(client, seeded_tokens) -> None:
    public_limit = float(os.getenv("EBOOKSTORE_PUBLIC_API_LIMIT_SECONDS", "3"))
    export_limit = float(os.getenv("EBOOKSTORE_EXPORT_LIMIT_SECONDS", "8"))
    cases = (
        ("/api/books?page=1&pageSize=12", {}, public_limit),
        ("/api/books?keyword=test&searchType=title&page=1&pageSize=12", {}, public_limit),
        (
            "/api/admin/statistics/export?range=7d",
            seeded_tokens["platform_admin"]["headers"],
            export_limit,
        ),
    )
    for path, headers, limit in cases:
        warmup = client.get(path, headers=headers)
        assert warmup.status_code == 200
        samples = []
        for _ in range(5):
            started = perf_counter()
            response = client.get(path, headers=headers)
            samples.append(perf_counter() - started)
            assert response.status_code == 200
            if "statistics/export" not in path:
                assert response.json()["code"] == 0
            else:
                assert "date,storeName,bookName,quantity,salesAmount" in response.text
        assert max(samples) < limit, (
            f"{path} exceeded {limit}s; median={median(samples):.3f}s max={max(samples):.3f}s"
        )
