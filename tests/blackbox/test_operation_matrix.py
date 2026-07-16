from __future__ import annotations

import pytest

from tests.blackbox.coverage_matrix import operation_rows


pytestmark = pytest.mark.blackbox_smoke


def test_every_api_operation_is_present_in_the_coverage_matrix() -> None:
    rows = operation_rows()
    assert len(rows) >= 60
    assert len({(row.method, row.path) for row in rows}) == len(rows)
    assert all(row.generated == "yes" for row in rows)
