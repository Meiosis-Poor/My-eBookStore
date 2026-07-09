"""
book_dao.py — 图书管理数据访问层
对应表：book_infos, book_items, book_categories
"""

from ..db import get_conn, many, one, execute_scalar


def list_categories():
    """获取所有启用的图书分类"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT category_id, category_name, description FROM book_categories WHERE status = N'启用'")
        return many(cur)


def search(keyword=None, category_id=None, page=1, page_size=20):
    """图书搜索 / 分类浏览 / 分页 / 排序
    对应用例：4.2.2 Browse and Search Books
    """
    with get_conn() as conn:
        sql = """SELECT bi.book_item_id, bi.price, bi.stock, bi.sales_count, bi.status AS item_status,
                        binf.book_name, binf.author, binf.publisher, binf.cover_image,
                        s.store_name, s.store_id,
                        cat.category_name
                 FROM book_items bi
                 JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
                 JOIN stores s ON bi.store_id = s.store_id
                 JOIN book_categories cat ON binf.category_id = cat.category_id
                 WHERE bi.status = N'在售'"""
        params = []

        if category_id:
            sql += " AND binf.category_id = ?"
            params.append(category_id)
        if keyword:
            sql += " AND (binf.book_name LIKE ? OR binf.author LIKE ? OR binf.publisher LIKE ?)"
            kw = f'%{keyword}%'
            params.extend([kw, kw, kw])

        sql += " ORDER BY bi.sales_count DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([(page-1) * page_size, page_size])

        cur = conn.cursor()
        cur.execute(sql, params)
        return many(cur)


def get_detail(book_item_id):
    """图书详情 + 店铺信息 + 分类 + 平均评分
    对应用例：4.2.2 点击某本图书查看详细信息
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT bi.*, binf.book_name, binf.author, binf.publisher, binf.ISBN,
                   binf.publish_date, binf.description, binf.cover_image,
                   s.store_name, s.store_id, cat.category_name,
                   ISNULL(r.avg_rating, 0) AS avg_rating,
                   ISNULL(r.review_count, 0) AS review_count
            FROM book_items bi
            JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
            JOIN stores s ON bi.store_id = s.store_id
            JOIN book_categories cat ON binf.category_id = cat.category_id
            LEFT JOIN (
                SELECT book_item_id,
                       AVG(CAST(rating AS FLOAT)) AS avg_rating,
                       COUNT(*) AS review_count
                FROM reviews GROUP BY book_item_id
            ) r ON bi.book_item_id = r.book_item_id
            WHERE bi.book_item_id = ?
        """, [book_item_id])
        return one(cur)


def get_reviews(book_item_id, page=1, page_size=10):
    """某本书的评价列表"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT r.review_id, r.rating, r.content, r.created_time, ou.nickname
            FROM reviews r
            JOIN ordinary_users ou ON r.user_id = ou.user_id
            WHERE r.book_item_id = ?
            ORDER BY r.created_time DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, [book_item_id, (page-1)*page_size, page_size])
        return many(cur)


def get_similar(book_item_id, limit=10):
    """同店其他图书（详情页推荐）"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT TOP ? bi.book_item_id, bi.price, binf.book_name, binf.cover_image
            FROM book_items bi
            JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
            WHERE bi.store_id = (SELECT store_id FROM book_items WHERE book_item_id = ?)
              AND bi.book_item_id != ? AND bi.status = N'在售'
            ORDER BY bi.sales_count DESC
        """, [limit, book_item_id, book_item_id])
        return many(cur)


def get_recommended(user_id, limit=12):
    """首页个性化推荐 — 基于浏览+购买的同类别热门书
    对应用例：推荐算法模块 3.1.7
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            WITH user_interests AS (
                SELECT DISTINCT binf.category_id
                FROM browse_history bh
                JOIN book_items bi ON bh.book_item_id = bi.book_item_id
                JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
                WHERE bh.user_id = ?
                UNION
                SELECT DISTINCT binf.category_id
                FROM orders o
                JOIN order_items oi ON o.order_id = oi.order_id
                JOIN book_items bi ON oi.book_item_id = bi.book_item_id
                JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
                WHERE o.user_id = ? AND o.order_status = N'已完成'
            )
            SELECT TOP ? bi.book_item_id, bi.price, bi.sales_count,
                   binf.book_name, binf.author, binf.cover_image, s.store_name
            FROM book_items bi
            JOIN book_infos binf ON bi.book_info_id = binf.book_info_id
            JOIN stores s ON bi.store_id = s.store_id
            WHERE binf.category_id IN (SELECT category_id FROM user_interests)
              AND bi.status = N'在售'
            ORDER BY bi.sales_count DESC
        """, [user_id, user_id, limit])
        return many(cur)


# ─── 管理员 ───

def create(book_info_data, book_item_data):
    """管理员新增图书：先插 book_infos 再插 book_items
    book_info_data: {category_id, book_name, author, publisher, isbn, description, ...}
    book_item_data:  {store_id, price, stock}
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO book_infos (category_id, book_name, author, publisher, ISBN, publish_date, description, cover_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            book_info_data['category_id'],
            book_info_data['book_name'],
            book_info_data['author'],
            book_info_data.get('publisher'),
            book_info_data.get('isbn'),
            book_info_data.get('publish_date'),
            book_info_data.get('description'),
            book_info_data.get('cover_image'),
        ])
        info_id = execute_scalar(conn, "SELECT SCOPE_IDENTITY()")

        cur.execute("""
            INSERT INTO book_items (book_info_id, store_id, price, stock)
            VALUES (?, ?, ?, ?)
        """, [info_id, book_item_data['store_id'], book_item_data['price'], book_item_data.get('stock', 0)])
        return execute_scalar(conn, "SELECT SCOPE_IDENTITY()")


def update(book_item_id, data):
    """修改图书价格/库存/状态"""
    allowed = {'price', 'stock', 'status'}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return

    with get_conn() as conn:
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [book_item_id]
        conn.cursor().execute(f"UPDATE book_items SET {set_clause} WHERE book_item_id = ?", params)


def set_status(book_item_id, status):
    """上架 / 下架"""
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE book_items SET status = ? WHERE book_item_id = ?",
            [status, book_item_id])
