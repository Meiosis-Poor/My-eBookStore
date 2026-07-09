"""
address_dao.py — 收货地址数据访问层
对应表：shipping_addresses
"""

from ..db import get_conn, many, one, execute_scalar


def list_by_user(user_id):
    """用户的收货地址列表"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT address_id, receiver_name, phone, province, city, district, detail, is_default
            FROM shipping_addresses
            WHERE user_id = ?
            ORDER BY is_default DESC, address_id
        """, [user_id])
        return many(cur)


def create(user_id, data):
    """新增地址"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO shipping_addresses (user_id, receiver_name, phone, province, city, district, detail, is_default)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [user_id, data['receiver_name'], data['phone'],
              data['province'], data['city'], data['district'],
              data['detail'], data.get('is_default', 0)])
        return execute_scalar(conn, "SELECT SCOPE_IDENTITY()")


def update(address_id, data):
    """修改地址"""
    allowed = {'receiver_name', 'phone', 'province', 'city', 'district', 'detail', 'is_default'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return
    with get_conn() as conn:
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [address_id]
        conn.cursor().execute(f"UPDATE shipping_addresses SET {set_clause} WHERE address_id = ?", params)


def delete(address_id):
    """删除地址"""
    with get_conn() as conn:
        conn.cursor().execute("DELETE FROM shipping_addresses WHERE address_id = ?", [address_id])


def set_default(user_id, address_id):
    """设为默认（先全清再设）"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE shipping_addresses SET is_default = 0 WHERE user_id = ?", [user_id])
        cur.execute("UPDATE shipping_addresses SET is_default = 1 WHERE address_id = ? AND user_id = ?",
                    [address_id, user_id])
