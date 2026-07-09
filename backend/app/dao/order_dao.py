"""
order_dao.py — 订单数据访问层
对应表：orders, order_items, payment_records, refund_records
对应用例：4.2.4 下单支付, 4.2.5 订单查询, 4.3.2 订单管理, 4.3.4 统计分析
"""

from ..db import get_conn, many, one, execute_scalar


def create(user_id, items, address_id, coupon_id=None):
    """下单事务 — 调存储过程 sp_CreateOrder
    items: [{"bid": book_item_id, "qty": quantity}, ...]
    """
    import json
    items_json = json.dumps(items, ensure_ascii=False)

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            DECLARE @ok BIT, @oid INT, @ono NVARCHAR(50)
            EXEC sp_CreateOrder @user_id = ?, @items_json = ?,
                 @address_id = ?, @coupon_id = ?,
                 @success = @ok OUTPUT, @order_id = @oid OUTPUT, @order_no = @ono OUTPUT
            SELECT @ok AS success, @oid AS order_id, @ono AS order_no
        """, [user_id, items_json, address_id, coupon_id])
        return one(cur)


def list_orders(user_id, status=None, page=1, page_size=10):
    """用户端订单列表"""
    with get_conn() as conn:
        sql = """SELECT o.order_id, o.order_no, o.actual_amount, o.order_status,
                        o.payment_status, o.created_time,
                        COUNT(oi.order_item_id) AS item_count,
                        (SELECT TOP 1 binf.cover_image FROM order_items oi2
                         JOIN book_items bi2 ON oi2.book_item_id = bi2.book_item_id
                         JOIN book_infos binf2 ON bi2.book_info_id = binf2.book_info_id
                         WHERE oi2.order_id = o.order_id) AS first_cover
                 FROM orders o
                 LEFT JOIN order_items oi ON o.order_id = oi.order_id
                 WHERE o.user_id = ?"""
        params = [user_id]

        if status and status != 'all':
            sql += " AND o.order_status = ?"
            params.append(status)

        sql += " GROUP BY o.order_id, o.order_no, o.actual_amount, o.order_status, o.payment_status, o.created_time"
        sql += " ORDER BY o.created_time DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([(page-1)*page_size, page_size])

        cur = conn.cursor()
        cur.execute(sql, params)
        return many(cur)


def get_detail(order_id):
    """订单详情（含商品明细 + 支付信息）"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT o.*,
                   oi.order_item_id, oi.quantity, oi.unit_price, oi.subtotal,
                   binf.book_name, binf.cover_image, bi.book_item_id,
                   s.store_name,
                   p.payment_method, p.paid_time AS payment_paid_time, p.payment_no
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN book_items bi ON oi.book_item_id = bi.book_item_id
            JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
            JOIN stores s ON bi.store_id = s.store_id
            LEFT JOIN payment_records p ON o.order_id = p.order_id AND p.payment_status = N'已支付'
            WHERE o.order_id = ?
        """, [order_id])
        return many(cur)


def pay(order_id, payment_method):
    """支付 — 调存储过程 sp_PayOrder"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            DECLARE @ok BIT
            EXEC sp_PayOrder @order_id = ?, @payment_method = ?, @success = @ok OUTPUT
            SELECT @ok AS success
        """, [order_id, payment_method])
        row = cur.fetchone()
        return row[0] if row else False


def cancel(order_id):
    """取消订单"""
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE orders SET order_status = N'已取消' WHERE order_id = ? AND order_status = N'待支付'",
            [order_id])


def refund(order_id, reason):
    """退款 — 调存储过程 sp_RefundOrder"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            DECLARE @ok BIT
            EXEC sp_RefundOrder @order_id = ?, @refund_reason = ?, @success = @ok OUTPUT
            SELECT @ok AS success
        """, [order_id, reason])
        row = cur.fetchone()
        return row[0] if row else False


def list_store_orders(store_id, page=1, page_size=20):
    """书店管理员 — 查看本店订单"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT o.*, u.user_name AS buyer_name
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN book_items bi ON oi.book_item_id = bi.book_item_id
            JOIN users u ON o.user_id = u.user_id
            WHERE bi.store_id = ?
            ORDER BY o.created_time DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, [store_id, (page-1)*page_size, page_size])
        return many(cur)
