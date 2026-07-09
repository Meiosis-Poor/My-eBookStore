"""Statistics, risk analysis, export, and recommendation settings helpers."""

from __future__ import annotations

from typing import Any

from ..db import get_conn, many, one


def _days(range_name: str | None) -> int:
    return {"7d": 7, "30d": 30, "90d": 90}.get(range_name or "7d", 7)


def overview(store_id: int | None = None, range_name: str = "7d") -> dict[str, Any]:
    days = _days(range_name)
    with get_conn() as conn:
        if store_id:
            revenue = conn.cursor().execute(
                """
                SELECT COALESCE(SUM(oi.subtotal), 0)
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.order_id
                JOIN book_items b ON b.book_item_id = oi.book_item_id
                WHERE o.payment_status = N'已支付'
                  AND o.created_time >= DATEADD(day, -?, SYSDATETIME())
                  AND b.store_id = ?
                """,
                days,
                store_id,
            ).fetchval()
            order_count = conn.cursor().execute(
                """
                SELECT COUNT(DISTINCT o.order_id)
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.order_id
                JOIN book_items b ON b.book_item_id = oi.book_item_id
                WHERE o.created_time >= DATEADD(day, -?, SYSDATETIME())
                  AND b.store_id = ?
                """,
                days,
                store_id,
            ).fetchval()
        else:
            revenue = conn.cursor().execute(
                """
                SELECT COALESCE(SUM(o.actual_amount), 0)
                FROM orders o
                WHERE o.payment_status = N'已支付'
                  AND o.created_time >= DATEADD(day, -?, SYSDATETIME())
                """,
                days,
            ).fetchval()
            order_count = conn.cursor().execute(
                """
                SELECT COUNT(DISTINCT o.order_id)
                FROM orders o
                WHERE o.created_time >= DATEADD(day, -?, SYSDATETIME())
                """,
                days,
            ).fetchval()
        hot = many(
            conn.cursor().execute(
                f"""
                SELECT TOP 5 bi.book_name AS bookName, SUM(oi.quantity) AS salesCount
                FROM order_items oi
                JOIN orders o ON o.order_id = oi.order_id
                JOIN book_items b ON b.book_item_id = oi.book_item_id
                JOIN book_infos bi ON bi.book_info_id = b.book_info_id
                WHERE o.payment_status = N'已支付'
                  AND o.created_time >= DATEADD(day, -?, SYSDATETIME())
                  {"AND b.store_id = ?" if store_id else ""}
                GROUP BY bi.book_name
                ORDER BY SUM(oi.quantity) DESC
                """,
                days,
                *([store_id] if store_id else []),
            )
        )
        if store_id:
            total_users = conn.cursor().execute(
                """
                SELECT COUNT(DISTINCT o.user_id)
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.order_id
                JOIN book_items b ON b.book_item_id = oi.book_item_id
                WHERE b.store_id = ?
                """,
                store_id,
            ).fetchval()
            total_stores = 1
            total_books = conn.cursor().execute("SELECT COUNT(*) FROM book_items WHERE store_id = ? AND status = N'在售'", store_id).fetchval()
            sales_trend = many(
                conn.cursor().execute(
                    """
                    SELECT CONVERT(varchar(5), CAST(o.created_time AS date), 110) AS label,
                           COALESCE(SUM(oi.subtotal), 0) AS value
                    FROM orders o
                    JOIN order_items oi ON oi.order_id = o.order_id
                    JOIN book_items b ON b.book_item_id = oi.book_item_id
                    WHERE o.payment_status = N'已支付'
                      AND o.created_time >= DATEADD(day, -?, SYSDATETIME())
                      AND b.store_id = ?
                    GROUP BY CONVERT(varchar(5), CAST(o.created_time AS date), 110), CAST(o.created_time AS date)
                    ORDER BY CAST(o.created_time AS date)
                    """,
                    days,
                    store_id,
                )
            )
        else:
            total_users = conn.cursor().execute("SELECT COUNT(*) FROM users WHERE user_type = N'普通用户'").fetchval()
            total_stores = conn.cursor().execute("SELECT COUNT(*) FROM stores WHERE status = N'正常'").fetchval()
            total_books = conn.cursor().execute("SELECT COUNT(*) FROM book_items WHERE status = N'在售'").fetchval()
            sales_trend = many(
                conn.cursor().execute(
                    """
                    SELECT CONVERT(varchar(5), CAST(o.created_time AS date), 110) AS label,
                           COALESCE(SUM(o.actual_amount), 0) AS value
                    FROM orders o
                    WHERE o.payment_status = N'已支付'
                      AND o.created_time >= DATEADD(day, -?, SYSDATETIME())
                    GROUP BY CONVERT(varchar(5), CAST(o.created_time AS date), 110), CAST(o.created_time AS date)
                    ORDER BY CAST(o.created_time AS date)
                    """,
                    days,
                )
            )
    for row in sales_trend:
        row["value"] = float(row.get("value") or 0)
    return {
        "kpi": {
            "todaySales": float(revenue or 0),
            "todayOrders": int(order_count or 0),
            "totalUsers": int(total_users or 0),
            "totalStores": int(total_stores or 0),
            "totalBooks": int(total_books or 0),
        },
        "salesTrend": sales_trend,
        "hotBooks": hot,
    }


def risk_stores() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                WITH store_orders AS (
                    SELECT s.store_id, s.store_name, COUNT(DISTINCT o.order_id) AS order_count,
                           COUNT(DISTINCT CASE WHEN o.order_status = N'已退款' OR o.payment_status = N'已退款' THEN o.order_id END) AS refund_count,
                           COUNT(DISTINCT o.user_id) AS buyer_count,
                           COUNT(DISTINCT CASE WHEN o.created_time >= DATEADD(day, -1, SYSDATETIME()) THEN o.order_id END) AS recent_count
                    FROM stores s
                    LEFT JOIN book_items b ON b.store_id = s.store_id
                    LEFT JOIN order_items oi ON oi.book_item_id = b.book_item_id
                    LEFT JOIN orders o ON o.order_id = oi.order_id
                    GROUP BY s.store_id, s.store_name
                )
                SELECT TOP 20 store_id AS storeId, store_name AS storeName,
                       CASE
                           WHEN order_count = 0 THEN 0
                           ELSE
                               CASE WHEN (refund_count * 100.0 / NULLIF(order_count, 0)) > 50 THEN 40 ELSE 0 END +
                               CASE WHEN recent_count >= 10 THEN 30 ELSE 0 END +
                               CASE WHEN buyer_count > 0 AND (order_count * 1.0 / buyer_count) >= 5 THEN 30 ELSE 0 END
                       END AS riskScore,
                       CONCAT(N'订单', order_count, N'笔，退款', refund_count, N'笔，近24小时', recent_count, N'笔') AS reason
                FROM store_orders
                WHERE order_count > 0
                ORDER BY riskScore DESC, order_count DESC
                """
            )
        )
    return [row for row in rows if int(row.get("riskScore") or 0) > 0]


def export_rows(store_id: int | None = None, range_name: str = "7d") -> list[dict[str, Any]]:
    days = _days(range_name)
    params: list[Any] = [days]
    store_where = ""
    if store_id:
        store_where = "AND b.store_id = ?"
        params.append(store_id)
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                f"""
                SELECT CAST(o.created_time AS date) AS date,
                       s.store_name AS storeName,
                       bi.book_name AS bookName,
                       SUM(oi.quantity) AS quantity,
                       SUM(oi.subtotal) AS salesAmount
                FROM orders o
                JOIN order_items oi ON oi.order_id = o.order_id
                JOIN book_items b ON b.book_item_id = oi.book_item_id
                JOIN book_infos bi ON bi.book_info_id = b.book_info_id
                JOIN stores s ON s.store_id = b.store_id
                WHERE o.payment_status = N'已支付'
                  AND o.created_time >= DATEADD(day, -?, SYSDATETIME())
                  {store_where}
                GROUP BY CAST(o.created_time AS date), s.store_name, bi.book_name
                ORDER BY CAST(o.created_time AS date) DESC, s.store_name, bi.book_name
                """,
                *params,
            )
        )
    for row in rows:
        row["date"] = str(row.get("date"))
        row["salesAmount"] = float(row.get("salesAmount") or 0)
    return rows


def ensure_recommendation_settings() -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            """
            IF OBJECT_ID(N'dbo.recommendation_settings', N'U') IS NULL
            BEGIN
                CREATE TABLE dbo.recommendation_settings(
                    setting_id INT NOT NULL CONSTRAINT PK_recommendation_settings PRIMARY KEY DEFAULT 1,
                    guess_weight FLOAT NOT NULL DEFAULT 1,
                    hot_weight FLOAT NOT NULL DEFAULT 1,
                    search_embedding_enabled BIT NOT NULL DEFAULT 1,
                    detail_same_store_enabled BIT NOT NULL DEFAULT 1,
                    updated_time DATETIME2 NOT NULL DEFAULT SYSDATETIME(),
                    CONSTRAINT CK_recommendation_settings_singleton CHECK(setting_id = 1)
                );
            END
            IF NOT EXISTS (SELECT 1 FROM dbo.recommendation_settings WHERE setting_id = 1)
            BEGIN
                INSERT INTO dbo.recommendation_settings(setting_id) VALUES(1);
            END
            """
        )


def recommendation_settings() -> dict[str, Any]:
    ensure_recommendation_settings()
    with get_conn() as conn:
        row = one(conn.cursor().execute("SELECT * FROM recommendation_settings WHERE setting_id = 1"))
    return {
        "guessWeight": float(row["guess_weight"]),
        "hotWeight": float(row["hot_weight"]),
        "searchEmbeddingEnabled": bool(row["search_embedding_enabled"]),
        "detailSameStoreEnabled": bool(row["detail_same_store_enabled"]),
        "updatedTime": str(row["updated_time"]),
    }


def update_recommendation_settings(payload: dict[str, Any]) -> dict[str, Any]:
    ensure_recommendation_settings()
    with get_conn() as conn:
        conn.cursor().execute(
            """
            UPDATE recommendation_settings
            SET guess_weight = COALESCE(?, guess_weight),
                hot_weight = COALESCE(?, hot_weight),
                search_embedding_enabled = COALESCE(?, search_embedding_enabled),
                detail_same_store_enabled = COALESCE(?, detail_same_store_enabled),
                updated_time = SYSDATETIME()
            WHERE setting_id = 1
            """,
            payload.get("guessWeight"),
            payload.get("hotWeight"),
            None if payload.get("searchEmbeddingEnabled") is None else (1 if payload.get("searchEmbeddingEnabled") else 0),
            None if payload.get("detailSameStoreEnabled") is None else (1 if payload.get("detailSameStoreEnabled") else 0),
        )
    return recommendation_settings()
