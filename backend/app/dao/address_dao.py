"""Address data access helpers."""

from __future__ import annotations

from typing import Any

from ..db import get_conn, many


def list_by_user(user_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT address_id AS addressId, receiver_name AS recipientName, phone,
                       CONCAT(province, city, district, detail) AS addressDetail,
                       province, city, district, detail, is_default AS isDefault
                FROM shipping_addresses
                WHERE user_id = ?
                ORDER BY is_default DESC, address_id DESC
                """,
                user_id,
            )
        )
    for row in rows:
        row["isDefault"] = bool(row["isDefault"])
    return rows


def split_address(address_detail: str) -> tuple[str, str, str, str]:
    return "", "", "", address_detail or ""


def create(user_id: int, payload: dict[str, Any]) -> int:
    province, city, district, detail = split_address(payload.get("addressDetail") or payload.get("detail") or "")
    with get_conn() as conn:
        if payload.get("isDefault"):
            conn.cursor().execute("UPDATE shipping_addresses SET is_default = 0 WHERE user_id = ?", user_id)
        return int(
            conn.cursor()
            .execute(
                """
                INSERT INTO shipping_addresses(user_id, receiver_name, phone, province, city, district, detail, is_default)
                OUTPUT INSERTED.address_id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                user_id,
                payload.get("recipientName") or payload.get("receiverName") or payload.get("receiver_name"),
                payload.get("phone"),
                province,
                city,
                district,
                detail,
                1 if payload.get("isDefault") else 0,
            )
            .fetchone()[0]
        )


def update(user_id: int, address_id: int, payload: dict[str, Any]) -> None:
    province, city, district, detail = split_address(payload.get("addressDetail") or payload.get("detail") or "")
    with get_conn() as conn:
        if payload.get("isDefault"):
            conn.cursor().execute("UPDATE shipping_addresses SET is_default = 0 WHERE user_id = ?", user_id)
        conn.cursor().execute(
            """
            UPDATE shipping_addresses
            SET receiver_name = ?, phone = ?, province = ?, city = ?, district = ?, detail = ?, is_default = ?
            WHERE address_id = ? AND user_id = ?
            """,
            payload.get("recipientName") or payload.get("receiverName") or payload.get("receiver_name"),
            payload.get("phone"),
            province,
            city,
            district,
            detail,
            1 if payload.get("isDefault") else 0,
            address_id,
            user_id,
        )


def delete(user_id: int, address_id: int) -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            "DELETE FROM shipping_addresses WHERE address_id = ? AND user_id = ?",
            address_id,
            user_id,
        )
