from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.app.main import app


HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
PUBLIC_EXACT = {
    ("GET", "/api/health"),
    ("GET", "/api/categories"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("POST", "/api/auth/register/user"),
    ("POST", "/api/auth/register/seller"),
    ("GET", "/api/search/history"),
    ("POST", "/api/search/history"),
}
PUBLIC_GET_PREFIXES = (
    "/api/books",
    "/api/stores",
    "/api/recommendations",
    "/api/promotions/activities",
    "/api/promotions/rewards",
    "/api/promotions/coupons",
)
EXPLICIT_POSITIVE = {
    ("POST", "/api/auth/register/user"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/cart"),
    ("GET", "/api/cart"),
    ("DELETE", "/api/cart/{bookItemId}"),
    ("POST", "/api/addresses"),
    ("POST", "/api/orders"),
    ("POST", "/api/orders/{orderId}/pay"),
    ("POST", "/api/orders/{orderId}/cancel"),
    ("POST", "/api/orders/{orderId}/refund"),
    ("POST", "/api/orders/{orderId}/reviews"),
}
EXPLICIT_INVALID = EXPLICIT_POSITIVE | {
    ("GET", "/api/books"),
    ("GET", "/api/orders/{orderId}"),
}


@dataclass(frozen=True)
class CoverageRow:
    method: str
    path: str
    positive: str
    invalid: str
    unauthenticated: str
    wrong_role: str
    generated: str


def operation_rows() -> list[CoverageRow]:
    rows = []
    for path, item in app.openapi()["paths"].items():
        if not path.startswith("/api/"):
            continue
        for method in item:
            if method not in HTTP_METHODS:
                continue
            operation = (method.upper(), path)
            public = operation in PUBLIC_EXACT or (
                method == "get" and path.startswith(PUBLIC_GET_PREFIXES)
            )
            rows.append(
                CoverageRow(
                    *operation,
                    positive="explicit" if operation in EXPLICIT_POSITIVE else ("generated-read" if method == "get" else "gap"),
                    invalid="explicit" if operation in EXPLICIT_INVALID else "generated",
                    unauthenticated="n/a-public" if public else "explicit-matrix",
                    wrong_role="explicit-matrix" if path.startswith("/api/admin/") else "n/a-no-role-rule",
                    generated="yes",
                )
            )
    return sorted(rows, key=lambda row: (row.path, row.method))


def write_markdown(path: Path) -> dict[str, int]:
    rows = operation_rows()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# API black-box coverage matrix",
        "",
        "`gap` is intentionally visible and must not be counted as covered.",
        "",
        "| Method | Path | Positive | Invalid | Unauthenticated | Wrong role | Schemathesis |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row.method} | `{row.path}` | {row.positive} | {row.invalid} | "
            f"{row.unauthenticated} | {row.wrong_role} | {row.generated} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "operations": len(rows),
        "positive_gaps": sum(row.positive == "gap" for row in rows),
        "authentication_gaps": sum(row.unauthenticated == "gap" for row in rows),
        "role_gaps": sum(row.wrong_role == "gap" for row in rows),
    }
