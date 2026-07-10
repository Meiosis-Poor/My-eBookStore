"""User data access helpers."""

from __future__ import annotations

from typing import Any

from ..db import get_conn, many, one


AUTH_USER_SELECT = """
    SELECT u.*, ou.nickname, ou.level, ou.total_points, ou.available_points, ou.continuous_checkin_days,
           s.store_id, s.store_name
    FROM users u
    LEFT JOIN ordinary_users ou ON ou.user_id = u.user_id
    LEFT JOIN stores s ON s.user_id = u.user_id
"""


def get_auth_user_by_id(user_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        return one(conn.cursor().execute(f"{AUTH_USER_SELECT} WHERE u.user_id = ?", user_id))


def get_auth_user_by_name(user_name: str | None) -> dict[str, Any] | None:
    with get_conn() as conn:
        return one(conn.cursor().execute(f"{AUTH_USER_SELECT} WHERE u.user_name = ?", user_name))


def create_customer(
    user_name: str,
    password_hash: str,
    nickname: str,
    phone: str | None = None,
    email: str | None = None,
) -> int:
    with get_conn() as conn:
        if conn.cursor().execute("SELECT 1 FROM users WHERE user_name = ?", user_name).fetchone():
            raise ValueError("用户名已被占用")
        user_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO users(user_name, password_hash, phone, email, user_type)
                OUTPUT INSERTED.user_id
                VALUES (?, ?, ?, ?, N'普通用户')
                """,
                user_name,
                password_hash,
                phone,
                email,
            )
            .fetchone()[0]
        )
        conn.cursor().execute(
            "INSERT INTO ordinary_users(user_id, nickname) VALUES (?, ?)",
            user_id,
            nickname or user_name,
        )
        return user_id


def create_seller(
    user_name: str,
    password_hash: str,
    store_name: str,
    nickname: str,
    phone: str | None = None,
    email: str | None = None,
    description: str | None = None,
) -> dict[str, int]:
    with get_conn() as conn:
        if conn.cursor().execute("SELECT 1 FROM users WHERE user_name = ?", user_name).fetchone():
            raise ValueError("用户名已被占用")
        if conn.cursor().execute("SELECT 1 FROM stores WHERE store_name = ?", store_name).fetchone():
            raise ValueError("店铺名已被占用")
        user_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO users(user_name, password_hash, phone, email, user_type)
                OUTPUT INSERTED.user_id
                VALUES (?, ?, ?, ?, N'书店管理员')
                """,
                user_name,
                password_hash,
                phone,
                email,
            )
            .fetchone()[0]
        )
        conn.cursor().execute(
            "INSERT INTO store_admins(user_id, admin_name) VALUES (?, ?)",
            user_id,
            nickname or user_name,
        )
        store_id = int(
            conn.cursor()
            .execute(
                "INSERT INTO stores(store_name, user_id, description) OUTPUT INSERTED.store_id VALUES (?, ?, ?)",
                store_name,
                user_id,
                description or "",
            )
            .fetchone()[0]
        )
        return {"userId": user_id, "storeId": store_id}


def update_profile(user_id: int, payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            "UPDATE users SET phone = COALESCE(?, phone), email = COALESCE(?, email) WHERE user_id = ?",
            payload.get("phone"),
            payload.get("email"),
            user_id,
        )
        if payload.get("nickname"):
            conn.cursor().execute(
                "UPDATE ordinary_users SET nickname = ? WHERE user_id = ?",
                payload["nickname"],
                user_id,
            )


def list_customers(keyword: str | None = None, store_id: int | None = None) -> list[dict[str, Any]]:
    params: list[Any] = []
    keyword_where = ""
    if keyword:
        keyword_where = " AND (u.user_name LIKE ? OR ou.nickname LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])

    with get_conn() as conn:
        if store_id:
            params = [store_id, store_id, *params]
            return many(
                conn.cursor().execute(
                    f"""
                    SELECT DISTINCT u.user_id AS userId, u.user_name AS userName,
                           COALESCE(ou.nickname, u.user_name) AS nickname,
                           CASE WHEN u.status = N'正常' THEN 'active' ELSE 'banned' END AS status,
                           u.created_time AS registeredAt,
                           CASE WHEN sb.blacklist_id IS NULL THEN CAST(0 AS BIT) ELSE CAST(1 AS BIT) END AS isBlacklisted
                    FROM users u
                    LEFT JOIN ordinary_users ou ON ou.user_id = u.user_id
                    LEFT JOIN store_blacklists sb ON sb.user_id = u.user_id AND sb.store_id = ?
                    JOIN orders o ON o.user_id = u.user_id
                    JOIN order_items oi ON oi.order_id = o.order_id
                    JOIN book_items b ON b.book_item_id = oi.book_item_id
                    WHERE u.user_type = N'普通用户' AND b.store_id = ?{keyword_where}
                    ORDER BY registeredAt DESC
                    """,
                    *params,
                )
            )
        return many(
            conn.cursor().execute(
                f"""
                SELECT u.user_id AS userId, u.user_name AS userName,
                       COALESCE(ou.nickname, u.user_name) AS nickname,
                       CASE WHEN u.status = N'正常' THEN 'active' ELSE 'banned' END AS status,
                       u.created_time AS registeredAt
                FROM users u
                LEFT JOIN ordinary_users ou ON ou.user_id = u.user_id
                WHERE u.user_type = N'普通用户'{keyword_where}
                ORDER BY u.created_time DESC
                """,
                *params,
            )
        )


def set_user_status(user_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.cursor().execute("UPDATE users SET status = ? WHERE user_id = ?", status, user_id)
