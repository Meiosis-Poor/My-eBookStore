"""
stats_dao.py — 数据统计分析数据访问层
对应用例：4.3.4 Data Analysis
"""

from ..db import get_conn, one, many


def dashboard():
    """平台总览 — 用户数/店铺数/图书数/总营收/待处理"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM users WHERE user_type = N'普通用户' AND status = N'正常') AS total_users,
                (SELECT COUNT(*) FROM stores WHERE status = N'正常') AS total_stores,
                (SELECT COUNT(*) FROM book_items WHERE status = N'在售') AS total_books,
                ISNULL((SELECT SUM(actual_amount) FROM orders WHERE order_status = N'已完成'), 0) AS total_revenue,
                (SELECT COUNT(*) FROM orders WHERE order_status = N'待支付') AS pending_orders,
                (SELECT COUNT(*) FROM orders WHERE order_status = N'已退款') AS refunded_orders
        """)
        return one(cur)


def store_sales(store_id, start_date, end_date):
    """店铺销售额统计（按月）"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT YEAR(o.paid_time) AS year, MONTH(o.paid_time) AS month,
                   SUM(o.actual_amount) AS total_sales,
                   COUNT(DISTINCT o.order_id) AS order_count,
                   COUNT(DISTINCT o.user_id) AS customer_count
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN book_items bi ON oi.book_item_id = bi.book_item_id
            WHERE bi.store_id = ? AND o.order_status = N'已完成'
              AND o.paid_time >= ? AND o.paid_time <= ?
            GROUP BY YEAR(o.paid_time), MONTH(o.paid_time)
            ORDER BY year, month
        """, [store_id, start_date, end_date])
        return many(cur)


def hot_books(top_n=20):
    """热门图书排行"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT TOP {top_n} bi.book_item_id, bi.price, bi.sales_count, bi.stock,
                   binf.book_name, binf.author, binf.cover_image,
                   s.store_name,
                   ISNULL((SELECT AVG(CAST(r.rating AS FLOAT)) FROM reviews r
                           WHERE r.book_item_id = bi.book_item_id), 0) AS avg_rating
            FROM book_items bi
            JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
            JOIN stores s ON bi.store_id = s.store_id
            WHERE bi.status = N'在售'
            ORDER BY bi.sales_count DESC
        """)
        return many(cur)


def anomaly_stores():
    """异常检测 — 近 7 天销量 vs 近 30 天日均 > 3 倍"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            WITH week_sales AS (
                SELECT bi.store_id, SUM(oi.quantity) AS qty_7d
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN book_items bi ON oi.book_item_id = bi.book_item_id
                WHERE o.paid_time >= DATEADD(DAY, -7, GETDATE())
                  AND o.order_status = N'已完成'
                GROUP BY bi.store_id
            ),
            month_avg AS (
                SELECT bi.store_id, SUM(oi.quantity) / 30.0 AS avg_daily
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN book_items bi ON oi.book_item_id = bi.book_item_id
                WHERE o.paid_time >= DATEADD(DAY, -30, GETDATE())
                  AND o.order_status = N'已完成'
                GROUP BY bi.store_id
            )
            SELECT s.store_name, ISNULL(ws.qty_7d, 0) AS sales_7d,
                   ISNULL(ma.avg_daily, 0) AS avg_daily,
                   CASE WHEN ISNULL(ws.qty_7d, 0) > ISNULL(ma.avg_daily, 1) * 7 * 3
                        THEN N'异常' ELSE N'正常' END AS flag
            FROM stores s
            LEFT JOIN week_sales ws ON s.store_id = ws.store_id
            LEFT JOIN month_avg ma ON s.store_id = ma.store_id
            WHERE s.status = N'正常'
            ORDER BY sales_7d DESC
        """)
        return many(cur)
