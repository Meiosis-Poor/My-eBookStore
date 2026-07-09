"""
review_dao.py — 评价数据访问层
对应表：reviews
"""

from ..db import get_conn, many, execute_scalar


def create(user_id, book_item_id, order_id, rating, content):
    """发表评价"""
    with get_conn() as conn:
        conn.cursor().execute("""
            INSERT INTO reviews (user_id, book_item_id, order_id, rating, content)
            VALUES (?, ?, ?, ?, ?)
        """, [user_id, book_item_id, order_id, rating, content])
