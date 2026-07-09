"""Store data access helpers."""

from __future__ import annotations

from typing import Any

from ..db import get_conn, many, one


def get_detail(store_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        return one(
            conn.cursor().execute(
                """
                SELECT s.store_id AS storeId, s.store_name AS storeName, s.description,
                       s.created_time AS createdTime, COUNT(b.book_item_id) AS bookCount,
                       COALESCE(SUM(b.sales_count), 0) AS salesCount
                FROM stores s
                LEFT JOIN book_items b ON b.store_id = s.store_id AND b.status = N'在售'
                WHERE s.store_id = ?
                GROUP BY s.store_id, s.store_name, s.description, s.created_time
                """,
                store_id,
            )
        )


def update_profile(store_id: int, payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE stores SET store_name = COALESCE(?, store_name), description = COALESCE(?, description) WHERE store_id = ?",
            payload.get("storeName"),
            payload.get("description"),
            store_id,
        )


def list_stores() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return many(
            conn.cursor().execute(
                """
                SELECT s.store_id AS storeId, s.store_name AS storeName,
                       CASE WHEN s.status = N'正常' THEN 'active' ELSE 'banned' END AS status,
                       s.created_time AS createdTime,
                       COUNT(DISTINCT CASE WHEN b.status = N'在售' THEN b.book_item_id END) AS bookCount,
                       COUNT(DISTINCT o.order_id) AS orderCount
                FROM stores s
                LEFT JOIN book_items b ON b.store_id = s.store_id
                LEFT JOIN order_items oi ON oi.book_item_id = b.book_item_id
                LEFT JOIN orders o ON o.order_id = oi.order_id
                GROUP BY s.store_id, s.store_name, s.status, s.created_time
                ORDER BY s.created_time DESC
                """
            )
        )


def set_status(store_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE stores SET status = ? WHERE store_id = ?", status, store_id)


def add_to_blacklist(store_id: int, user_id: int, reason: str | None = None) -> int:
    with get_conn() as conn:
        conn.cursor().execute(
            "INSERT INTO store_blacklists(store_id, user_id, reason) VALUES (?, ?, ?)",
            store_id,
            user_id,
            reason,
        )
        count = conn.cursor().execute(
            "SELECT COUNT(DISTINCT store_id) FROM store_blacklists WHERE user_id = ?",
            user_id,
        ).fetchval()
        if int(count or 0) > 10:
            conn.cursor().execute("UPDATE users SET status = N'封禁' WHERE user_id = ?", user_id)
        return int(count or 0)
