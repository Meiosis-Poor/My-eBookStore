"""Review data access helpers."""

from __future__ import annotations

from ..db import get_conn, one


def create(user_id: int, order_id: int, book_item_id: int, rating: int, content: str) -> None:
    if rating < 1 or rating > 5:
        raise ValueError("评分必须在 1 到 5 之间")
    with get_conn() as conn:
        item = one(
            conn.cursor().execute(
                """
                SELECT o.order_id, o.payment_status, o.order_status
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.order_id
                WHERE o.order_id = ? AND o.user_id = ? AND oi.book_item_id = ?
                """,
                order_id,
                user_id,
                book_item_id,
            )
        )
        if not item:
            raise ValueError("只能评价已购买的图书")
        if item["payment_status"] != "已支付" and item["order_status"] not in ("已完成", "已退款"):
            raise ValueError("订单支付完成后才能评价")
        if conn.cursor().execute(
            "SELECT 1 FROM reviews WHERE user_id = ? AND order_id = ? AND book_item_id = ?",
            user_id,
            order_id,
            book_item_id,
        ).fetchone():
            raise ValueError("该商品已评价过")
        conn.cursor().execute(
            """
            INSERT INTO reviews(user_id, book_item_id, order_id, rating, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            user_id,
            book_item_id,
            order_id,
            rating,
            content,
        )
