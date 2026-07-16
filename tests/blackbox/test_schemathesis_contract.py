from __future__ import annotations

import pytest

from tests.blackbox.openapi_contract import schema
from tests.blackbox import strategies as _strategies  # noqa: F401


pytestmark = [
    pytest.mark.integration,
    pytest.mark.blackbox_full,
    pytest.mark.schemathesis,
]


def _assert_contract_response(response) -> None:
    assert response.status_code < 500, response.text
    content_type = response.headers.get("content-type", "")
    if isinstance(content_type, list):
        content_type = "; ".join(content_type)
    if "application/json" not in content_type:
        assert "text/csv" in content_type
        return
    payload = response.json()
    if response.status_code < 400:
        assert payload["code"] == 0
        assert "data" in payload
    else:
        if {"code", "message"} <= payload.keys():
            assert payload["code"] != 0
            assert payload["message"]
        else:
            # Invalid headers, paths, and query strings can be rejected by
            # Starlette before the application's response envelope is used.
            assert "detail" in payload


@schema.include(method="GET").parametrize()
def test_authenticated_get_operations_never_break_contract(case, seeded_tokens) -> None:
    role = "platform_admin" if case.path.startswith("/api/admin/") else "customer"
    response = case.call(headers=seeded_tokens[role]["headers"])
    _assert_contract_response(response)


@schema.exclude(method="GET").exclude(
    path_regex=r"^/api/auth/register/(?:user|seller)$"
).parametrize()
def test_unauthenticated_write_operations_never_return_5xx(case) -> None:
    response = case.call()
    _assert_contract_response(response)
