"""Cart data access helpers."""

from __future__ import annotations

from typing import Any

from ..db import get_conn, many, one
from .book_dao import BOOK_SELECT


def list_items(user_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return many(
            conn.cursor().execute(
                f"""
                SELECT c.cart_item_id AS cartItemId, c.book_item_id AS bookItemId, c.quantity,
                       q.bookInfoId, q.bookName, q.author, q.publisher, q.isbn, q.publishDate,
                       q.description, q.cover, q.categoryId, q.categoryName, q.storeId, q.storeName,
                       q.price, q.originPrice, q.stock, q.salesCount
                FROM cart_items c
                JOIN ({BOOK_SELECT}) q ON q.bookItemId = c.book_item_id
                WHERE c.user_id = ?
                ORDER BY c.add_time DESC
                """,
                user_id,
            )
        )


def get_stock(book_item_id: int) -> int | None:
    with get_conn() as conn:
        value = conn.cursor().execute(
            "SELECT stock FROM book_items WHERE book_item_id = ? AND status = N'在售'",
            book_item_id,
        ).fetchval()
        return None if value is None else int(value)


def add(user_id: int, book_item_id: int, quantity: int) -> None:
    with get_conn() as conn:
        existing = one(
            conn.cursor().execute(
                "SELECT cart_item_id AS cartItemId, quantity FROM cart_items WHERE user_id = ? AND book_item_id = ?",
                user_id,
                book_item_id,
            )
        )
        if existing:
            conn.cursor().execute(
                "UPDATE cart_items SET quantity = quantity + ? WHERE cart_item_id = ?",
                quantity,
                existing["cartItemId"],
            )
        else:
            conn.cursor().execute(
                "INSERT INTO cart_items(user_id, book_item_id, quantity) VALUES (?, ?, ?)",
                user_id,
                book_item_id,
                quantity,
            )


def update_quantity(user_id: int, book_item_id: int, quantity: int) -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND book_item_id = ?",
            quantity,
            user_id,
            book_item_id,
        )


def remove(user_id: int, book_item_id: int) -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            "DELETE FROM cart_items WHERE user_id = ? AND book_item_id = ?",
            user_id,
            book_item_id,
        )


def clear(user_id: int, book_item_ids: list[int]) -> None:
    if not book_item_ids:
        return
    placeholders = ",".join("?" for _ in book_item_ids)
    with get_conn() as conn:
        conn.cursor().execute(
            f"DELETE FROM cart_items WHERE user_id = ? AND book_item_id IN ({placeholders})",
            user_id,
            *book_item_ids,
        )
