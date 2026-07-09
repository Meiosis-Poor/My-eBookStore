"""Book data access helpers."""

from __future__ import annotations

from typing import Any, Optional

from ..db import get_conn, many, one


BOOK_SELECT = """
    SELECT
        bi.book_info_id AS bookInfoId,
        b.book_item_id AS bookItemId,
        bi.book_name AS bookName,
        bi.author AS author,
        bi.publisher AS publisher,
        bi.ISBN AS isbn,
        bi.publish_date AS publishDate,
        bi.description AS description,
        bi.cover_image AS cover,
        bi.embedding AS embedding,
        bc.category_id AS categoryId,
        bc.category_name AS categoryName,
        b.store_id AS storeId,
        s.store_name AS storeName,
        b.price AS price,
        b.price AS originPrice,
        b.stock AS stock,
        b.locked_stock AS lockedStock,
        b.sales_count AS salesCount,
        b.status AS itemStatus,
        bi.status AS infoStatus
    FROM book_items b
    JOIN book_infos bi ON bi.book_info_id = b.book_info_id
    JOIN book_categories bc ON bc.category_id = bi.category_id
    JOIN stores s ON s.store_id = b.store_id
    WHERE bi.status = N'正常' AND b.status = N'在售' AND s.status = N'正常'
"""


def list_categories() -> list[dict[str, Any]]:
    with get_conn() as conn:
        return many(
            conn.cursor().execute(
                """
                SELECT category_id AS categoryId, category_name AS categoryName, description
                FROM book_categories
                WHERE status = N'启用'
                ORDER BY category_id
                """
            )
        )


def list_books(
    keyword: Optional[str] = None,
    category_id: Optional[int] = None,
    sort: str = "default",
    in_stock_only: bool = False,
    store_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    where: list[str] = []
    params: list[Any] = []
    if category_id:
        where.append("AND bc.category_id = ?")
        params.append(category_id)
    if store_id:
        where.append("AND b.store_id = ?")
        params.append(store_id)
    if in_stock_only:
        where.append("AND b.stock > 0")
    if keyword and sort != "default":
        where.append("AND (bi.book_name LIKE ? OR bi.author LIKE ? OR bi.ISBN LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like, like])

    order = {
        "sales": "ORDER BY b.sales_count DESC, b.book_item_id DESC",
        "price_asc": "ORDER BY b.price ASC, b.book_item_id DESC",
        "price_desc": "ORDER BY b.price DESC, b.book_item_id DESC",
    }.get(sort, "ORDER BY b.book_item_id DESC")

    with get_conn() as conn:
        return many(conn.cursor().execute(f"{BOOK_SELECT} {' '.join(where)} {order}", *params))


def get_detail(book_item_id: int) -> Optional[dict[str, Any]]:
    with get_conn() as conn:
        return one(conn.cursor().execute(f"{BOOK_SELECT} AND b.book_item_id = ?", book_item_id))


def get_reviews(book_item_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return many(
            conn.cursor().execute(
                """
                SELECT r.review_id AS reviewId, r.rating, r.content, r.created_time AS createdTime,
                       u.user_name AS userName
                FROM reviews r
                JOIN users u ON u.user_id = r.user_id
                WHERE r.book_item_id = ?
                ORDER BY r.created_time DESC
                """,
                book_item_id,
            )
        )


def average_rating(book_item_id: int) -> float:
    with get_conn() as conn:
        value = conn.cursor().execute(
            "SELECT AVG(CAST(rating AS FLOAT)) FROM reviews WHERE book_item_id = ?",
            book_item_id,
        ).fetchval()
        return float(value or 0)


def get_similar_same_store_category(book_item_id: int, limit: int = 3) -> list[dict[str, Any]]:
    with get_conn() as conn:
        current = one(conn.cursor().execute(f"{BOOK_SELECT} AND b.book_item_id = ?", book_item_id))
        if not current:
            return []
        return many(
            conn.cursor().execute(
                f"""
                {BOOK_SELECT}
                AND bc.category_id = ? AND b.store_id = ? AND b.book_item_id <> ?
                ORDER BY b.sales_count DESC, b.book_item_id DESC
                """,
                current["categoryId"],
                current["storeId"],
                book_item_id,
            )
        )[:limit]


def save_search_history(user_id: int, keyword: str, keyword_embedding: str) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO search_history(user_id, keyword, keyword_embedding) VALUES (?, ?, ?)",
            user_id,
            keyword,
            keyword_embedding,
        )
        cursor.execute(
            """
            WITH ranked AS (
                SELECT search_id,
                       ROW_NUMBER() OVER (ORDER BY created_time DESC, search_id DESC) AS rn
                FROM search_history
                WHERE user_id = ?
            )
            DELETE FROM ranked WHERE rn > 5
            """,
            user_id,
        )


def latest_searches(user_id: int, limit: int = 5) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return many(
            conn.cursor().execute(
                f"""
                SELECT TOP {int(limit)} keyword, keyword_embedding AS embedding
                FROM search_history
                WHERE user_id = ?
                ORDER BY created_time DESC, search_id DESC
                """,
                user_id,
            )
        )


def create_book(book_info_data: dict[str, Any], book_item_data: dict[str, Any]) -> int:
    with get_conn() as conn:
        info_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO book_infos(category_id, book_name, author, publisher, ISBN, publish_date,
                                       description, cover_image, embedding)
                OUTPUT INSERTED.book_info_id
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                book_info_data["categoryId"],
                book_info_data["bookName"],
                book_info_data["author"],
                book_info_data.get("publisher"),
                book_info_data.get("isbn"),
                book_info_data.get("publishDate"),
                book_info_data.get("description"),
                book_info_data.get("cover") or "📘",
                book_info_data.get("embedding"),
            )
            .fetchone()[0]
        )
        return int(
            conn.cursor()
            .execute(
                """
                INSERT INTO book_items(book_info_id, store_id, price, stock)
                OUTPUT INSERTED.book_item_id
                VALUES (?, ?, ?, ?)
                """,
                info_id,
                book_item_data["storeId"],
                book_item_data["price"],
                book_item_data.get("stock", 0),
            )
            .fetchone()[0]
        )


def update_book(book_item_id: int, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    with get_conn() as conn:
        current = one(conn.cursor().execute(f"{BOOK_SELECT} AND b.book_item_id = ?", book_item_id))
        if not current:
            return None
        conn.cursor().execute(
            """
            UPDATE book_infos
            SET category_id = COALESCE(?, category_id), book_name = COALESCE(?, book_name),
                author = COALESCE(?, author), publisher = COALESCE(?, publisher),
                ISBN = COALESCE(?, ISBN), description = COALESCE(?, description),
                embedding = COALESCE(?, embedding)
            WHERE book_info_id = ?
            """,
            payload.get("categoryId"),
            payload.get("bookName"),
            payload.get("author"),
            payload.get("publisher"),
            payload.get("isbn"),
            payload.get("description"),
            payload.get("embedding"),
            current["bookInfoId"],
        )
        conn.cursor().execute(
            "UPDATE book_items SET price = COALESCE(?, price), stock = COALESCE(?, stock) WHERE book_item_id = ?",
            payload.get("price"),
            payload.get("stock"),
            book_item_id,
        )
        return current


def set_status(book_item_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE book_items SET status = ? WHERE book_item_id = ?", status, book_item_id)
