"""
cart_dao.py — 购物车数据访问层
对应表：cart_items
"""

from ..db import get_conn, many, one


def list_items(user_id):
    """获取购物车列表（联表查价格+书名+库存）"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT ci.cart_item_id, ci.quantity, ci.add_time,
                   bi.book_item_id, bi.price, bi.stock, bi.status AS book_status,
                   binf.book_name, binf.cover_image,
                   s.store_name, s.store_id
            FROM cart_items ci
            JOIN book_items bi ON ci.book_item_id = bi.book_item_id
            JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
            JOIN stores s ON bi.store_id = s.store_id
            WHERE ci.user_id = ?
            ORDER BY ci.add_time DESC
        """, [user_id])
        return many(cur)


def add(user_id, book_item_id, quantity=1):
    """加入购物车 — 已存在则累加数量"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT cart_item_id, quantity FROM cart_items
            WHERE user_id = ? AND book_item_id = ?
        """, [user_id, book_item_id])
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE cart_items SET quantity = quantity + ? WHERE cart_item_id = ?",
                        [quantity, row[0]])
        else:
            cur.execute("INSERT INTO cart_items (user_id, book_item_id, quantity) VALUES (?, ?, ?)",
                        [user_id, book_item_id, quantity])


def update_quantity(user_id, book_item_id, quantity):
    """修改数量"""
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE cart_items SET quantity = ? WHERE user_id = ? AND book_item_id = ?",
            [quantity, user_id, book_item_id])


def remove(user_id, book_item_id):
    """删除购物车项"""
    with get_conn() as conn:
        conn.cursor().execute(
            "DELETE FROM cart_items WHERE user_id = ? AND book_item_id = ?",
            [user_id, book_item_id])


def clear(user_id, book_item_ids):
    """下单后批量清空"""
    if not book_item_ids:
        return
    with get_conn() as conn:
        placeholders = ','.join('?' * len(book_item_ids))
        conn.cursor().execute(
            f"DELETE FROM cart_items WHERE user_id = ? AND book_item_id IN ({placeholders})",
            [user_id] + list(book_item_ids))
