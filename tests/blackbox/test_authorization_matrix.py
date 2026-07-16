from __future__ import annotations

import re

import pytest

from tests.blackbox.coverage_matrix import operation_rows


pytestmark = [pytest.mark.integration, pytest.mark.blackbox_smoke]


def _concrete_path(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "2147483647", path)


PROTECTED_OPERATIONS = [
    pytest.param(row.method, row.path, id=f"{row.method}-{row.path}")
    for row in operation_rows()
    if row.unauthenticated != "n/a-public"
]
ADMIN_OPERATIONS = [
    pytest.param(row.method, row.path, id=f"{row.method}-{row.path}")
    for row in operation_rows()
    if row.path.startswith("/api/admin/")
]


@pytest.mark.parametrize(("method", "path"), PROTECTED_OPERATIONS)
def test_protected_operations_reject_missing_token(safe_client, method, path) -> None:
    response = safe_client.request(method, _concrete_path(path), json={})
    assert response.status_code == 401, response.text
    assert response.json()["code"] != 0


@pytest.mark.parametrize(("method", "path"), ADMIN_OPERATIONS)
def test_admin_operations_reject_customer_role(safe_client, seeded_tokens, method, path) -> None:
    response = safe_client.request(
        method,
        _concrete_path(path),
        json={},
        headers=seeded_tokens["customer"]["headers"],
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] != 0
