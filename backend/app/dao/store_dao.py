"""
store_dao.py — 店铺与黑名单数据访问层
对应表：stores, store_blacklists
"""

from ..db import get_conn, many, one


def list_stores(page=1, page_size=20):
    """店铺列表"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.store_id, s.store_name, s.description, s.status, s.created_time,
                   u.user_name AS owner_name
            FROM stores s
            JOIN users u ON s.user_id = u.user_id
            ORDER BY s.store_id
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, [(page-1)*page_size, page_size])
        return many(cur)


def get_detail(store_id):
    """店铺详情"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.*, u.user_name AS owner_name
            FROM stores s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.store_id = ?
        """, [store_id])
        return one(cur)


def set_status(store_id, status):
    """封禁 / 解封店铺"""
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE stores SET status = ? WHERE store_id = ?", [status, store_id])


# ─── 黑名单 ───

def add_to_blacklist(store_id, user_id, reason=None):
    """书店管理员将用户加入本店黑名单"""
    with get_conn() as conn:
        conn.cursor().execute(
            "INSERT INTO store_blacklists (store_id, user_id, reason) VALUES (?, ?, ?)",
            [store_id, user_id, reason])


def get_blacklist_count(user_id):
    """查询某用户被多少家店铺拉黑"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(DISTINCT store_id) AS block_count
            FROM store_blacklists WHERE user_id = ?
        """, [user_id])
        row = cur.fetchone()
        return row[0] if row else 0
