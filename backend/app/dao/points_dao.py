"""Shared point balance and membership-level operations."""

from __future__ import annotations

from typing import Any


def add_points(conn: Any, user_id: int, points: int, reason: str, related_id: int) -> int:
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO points_records(user_id, points_change, reason, related_id) VALUES (?, ?, ?, ?)",
        user_id,
        points,
        reason,
        related_id,
    )
    cursor.execute(
        """
        UPDATE ordinary_users
        SET total_points = total_points + ?,
            available_points = available_points + ?,
            level = CASE
                WHEN total_points + ? >= 10000 THEN 5
                WHEN total_points + ? >= 5000 THEN 4
                WHEN total_points + ? >= 2500 THEN 3
                WHEN total_points + ? >= 1250 THEN 2
                ELSE 1
            END
        WHERE user_id = ?
        """,
        points,
        points,
        points,
        points,
        points,
        points,
        user_id,
    )
    value = cursor.execute(
        "SELECT available_points FROM ordinary_users WHERE user_id = ?",
        user_id,
    ).fetchval()
    if value is None:
        raise ValueError("用户资料不存在")
    return int(value)
