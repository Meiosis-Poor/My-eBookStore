"""Promotion, coupon, reward, and points data access helpers."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import pyodbc

from ..db import get_conn, many, one, procedure_result
from . import points_dao


STATUS_ACTIVE = "进行中"
STATUS_ENABLED = "启用"
COUPON_UNUSED = "未使用"
COUPON_USED = "已使用"
COUPON_EXPIRED = "已过期"


def _front_coupon_type(db_value: str | None) -> str | None:
    return {"平台券": "platform", "店铺券": "store"}.get(db_value or "", db_value)


def _db_coupon_type(front_value: str | None, store_id: int | None = None) -> str:
    if front_value == "store" or store_id:
        return "店铺券"
    return "平台券"


def _front_reward_type(db_value: str | None) -> str | None:
    return {"实物": "physical", "代金券": "coupon", "虚拟商品": "virtual"}.get(db_value or "", db_value)


def _db_reward_type(front_value: str | None) -> str:
    return {"physical": "实物", "coupon": "代金券", "virtual": "虚拟商品"}.get(front_value or "", "实物")


def _procedure_error(exc: pyodbc.Error, fallback: str) -> ValueError:
    message = " ".join(str(part) for part in getattr(exc, "args", ()))
    known_messages = (
        "今日已签到，请勿重复操作",
        "用户资料不存在",
        "奖品不存在",
        "积分不足",
        "等级不够",
        "库存不足",
    )
    return ValueError(next((known for known in known_messages if known in message), fallback))


def _store_participation_summary(conn: Any, store_id: int, activity_id: int) -> dict[str, Any]:
    participation = one(
        conn.cursor().execute(
            """
            SELECT participate_status AS participationStatus,
                   coupon_amount AS couponAmount,
                   coupon_quantity AS couponQuantity
            FROM store_activity_participation
            WHERE store_id = ? AND activity_id = ?
            """,
            store_id,
            activity_id,
        )
    )
    book_rows = many(
        conn.cursor().execute(
            """
            SELECT book_item_id AS bookItemId
            FROM activity_books
            WHERE store_id = ? AND activity_id = ?
            ORDER BY book_item_id
            """,
            store_id,
            activity_id,
        )
    )
    coupon = one(
        conn.cursor().execute(
            """
            SELECT TOP 1 coupon_id AS couponId, min_amount AS couponMinAmount
            FROM coupons
            WHERE store_id = ? AND activity_id = ? AND coupon_type = N'店铺券'
            ORDER BY coupon_id DESC
            """,
            store_id,
            activity_id,
        )
    )
    coupon_quantity = int(participation.get("couponQuantity") or 0) if participation else 0
    claimed_count = 0
    if coupon:
        claimed_count = int(
            conn.cursor()
            .execute(
                """
                SELECT COUNT(*)
                FROM user_coupons uc
                JOIN coupons c ON c.coupon_id = uc.coupon_id
                WHERE c.activity_id = ? AND c.store_id = ? AND c.coupon_type = N'店铺券'
                """,
                activity_id,
                store_id,
            )
            .fetchval()
            or 0
        )
    status = participation.get("participationStatus") if participation else "未参与"
    return {
        "participate": status == "已参与",
        "participationStatus": status,
        "selectedBookItemIds": [int(row["bookItemId"]) for row in book_rows],
        "couponAmount": float(participation.get("couponAmount") or 0) if participation else 0,
        "couponQuantity": coupon_quantity,
        "couponRemainingQuantity": max(coupon_quantity - claimed_count, 0),
        "couponMinAmount": float(coupon.get("couponMinAmount") or 0) if coupon else 0,
    }


def list_activities(admin_view: bool = False, store_id: int | None = None) -> list[dict[str, Any]]:
    where = "" if admin_view else "WHERE status IN (N'未开始', N'进行中')"
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                f"""
                SELECT activity_id AS activityId, activity_name AS activityName,
                       activity_type AS activityType, description,
                       start_time AS startTime, end_time AS endTime, status
                FROM promotion_activities
                {where}
                ORDER BY start_time DESC
                """
            )
        )
    for row in rows:
        row["startTime"] = str(row.get("startTime")) if row.get("startTime") is not None else ""
        row["endTime"] = str(row.get("endTime")) if row.get("endTime") is not None else ""
    if store_id is not None:
        with get_conn() as conn:
            for row in rows:
                row.update(_store_participation_summary(conn, store_id, int(row["activityId"])))
    return rows


def checkin(user_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        cursor = conn.cursor()
        try:
            result = procedure_result(
                cursor,
                """
                DECLARE @success BIT, @continuous_days INT, @reward_points INT, @got_coupon BIT;
                EXEC sp_CheckIn
                    @user_id = ?, @success = @success OUTPUT,
                    @continuous_days = @continuous_days OUTPUT,
                    @reward_points = @reward_points OUTPUT,
                    @got_coupon = @got_coupon OUTPUT;
                SELECT @success AS success, @continuous_days AS continuousDays,
                       @reward_points AS rewardPoints, @got_coupon AS gotCoupon;
                """,
                user_id,
            )
        except pyodbc.Error as exc:
            raise _procedure_error(exc, "签到失败，请稍后重试") from exc
        if not result or not result.get("success"):
            raise ValueError("签到失败，请稍后重试")
        return {
            "continuousDays": int(result.get("continuousDays") or 0),
            "rewardPoints": int(result.get("rewardPoints") or 0),
            "gotCoupon": bool(result.get("gotCoupon")),
        }


def list_user_coupons(user_id: int, status: str = "unused") -> list[dict[str, Any]]:
    db_status = {"unused": COUPON_UNUSED, "used": COUPON_USED, "expired": COUPON_EXPIRED}.get(status, COUPON_UNUSED)
    extra_where = "AND c.status = N'启用' AND c.valid_end >= SYSDATETIME()" if status == "unused" else ""
    with get_conn() as conn:
        conn.cursor().execute("EXEC sp_ExpireCoupons")
        rows = many(
            conn.cursor().execute(
                f"""
                SELECT c.coupon_id AS couponId, c.coupon_name AS couponName,
                       c.coupon_type AS couponType, c.store_id AS storeId,
                       s.store_name AS storeName, c.amount, c.min_amount AS minAmount,
                       c.valid_start AS validStart, c.valid_end AS validEnd,
                       uc.status
                FROM user_coupons uc
                JOIN coupons c ON c.coupon_id = uc.coupon_id
                LEFT JOIN stores s ON s.store_id = c.store_id
                WHERE uc.user_id = ? AND uc.status = ?
                  {extra_where}
                ORDER BY c.valid_end
                """,
                user_id,
                db_status,
            )
        )
    for row in rows:
        row["couponType"] = _front_coupon_type(row.get("couponType"))
        row["storeId"] = row.get("storeId")
        row["amount"] = float(row.get("amount") or 0)
        row["minAmount"] = float(row.get("minAmount") or 0)
        row["validStart"] = str(row.get("validStart")) if row.get("validStart") is not None else ""
        row["validEnd"] = str(row.get("validEnd")) if row.get("validEnd") is not None else ""
    return rows


def list_points(user_id: int, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    offset = max(page - 1, 0) * page_size
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT record_id AS recordId, points_change AS pointsChange, reason,
                       related_id AS relatedId, created_time AS createdTime
                FROM points_records
                WHERE user_id = ?
                ORDER BY created_time DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
                """,
                user_id,
                offset,
                page_size,
            )
        )
        total = int(conn.cursor().execute("SELECT COUNT(*) FROM points_records WHERE user_id = ?", user_id).fetchval() or 0)
    for row in rows:
        row["createdTime"] = str(row.get("createdTime")) if row.get("createdTime") is not None else ""
    return {"list": rows, "total": total}


def list_rewards() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = many(
            conn.cursor().execute(
                """
                SELECT reward_id AS rewardId, reward_name AS rewardName,
                       reward_type AS rewardType, required_points AS requiredPoints,
                       required_level AS requiredLevel, stock
                FROM point_rewards
                WHERE status = N'启用'
                ORDER BY required_points
                """
            )
        )
    for row in rows:
        row["rewardType"] = _front_reward_type(row.get("rewardType"))
    return rows


def redeem_reward(user_id: int, reward_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        cursor = conn.cursor()
        profile = one(
            cursor.execute(
                "SELECT * FROM ordinary_users WITH (UPDLOCK, HOLDLOCK) WHERE user_id = ?",
                user_id,
            )
        )
        reward = one(
            cursor.execute(
                "SELECT * FROM point_rewards WITH (UPDLOCK, HOLDLOCK) WHERE reward_id = ? AND status = N'启用'",
                reward_id,
            )
        )
        if not reward:
            raise ValueError("奖品不存在")
        if not profile:
            raise ValueError("用户资料不存在")
        if int(profile["available_points"]) < int(reward["required_points"]):
            raise ValueError("积分不足")
        if int(profile["level"]) < int(reward["required_level"]):
            raise ValueError("等级不够")
        if int(reward["stock"]) <= 0:
            raise ValueError("库存不足")
        try:
            result = procedure_result(
                cursor,
                """
                DECLARE @success BIT;
                EXEC sp_RedeemReward @user_id = ?, @reward_id = ?, @success = @success OUTPUT;
                SELECT @success AS success;
                """,
                user_id,
                reward_id,
            )
        except pyodbc.Error as exc:
            raise _procedure_error(exc, "兑换失败，请稍后重试") from exc
        if not result or not result.get("success"):
            raise ValueError("兑换失败，请稍后重试")
        available_points = cursor.execute(
            "SELECT available_points FROM ordinary_users WHERE user_id = ?", user_id
        ).fetchval()
        return {"availablePoints": int(available_points or 0)}


def join_activity(user_id: int, activity_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        activity = one(
            conn.cursor().execute(
                """
                SELECT * FROM promotion_activities
                WHERE activity_id = ?
                  AND status = N'进行中'
                  AND start_time <= SYSDATETIME()
                  AND end_time >= SYSDATETIME()
                """,
                activity_id,
            )
        )
        if not activity:
            raise ValueError("活动不存在或已结束")
        if conn.cursor().execute(
            """
            SELECT 1 FROM (
                SELECT uc.user_id, c.activity_id
                FROM user_coupons uc
                JOIN coupons c ON c.coupon_id = uc.coupon_id
                UNION ALL
                SELECT pr.user_id, pr.related_id
                FROM points_records pr
                WHERE pr.reason = N'等级周奖励'
            ) participation
            WHERE participation.user_id = ? AND participation.activity_id = ?
            """,
            user_id,
            activity_id,
        ).fetchone():
            raise ValueError("奖励已领取，请勿重复操作")

        coupon = one(
            conn.cursor().execute(
                """
                SELECT TOP 1 *
                FROM coupons
                WHERE activity_id = ?
                  AND status = N'启用'
                  AND valid_start <= SYSDATETIME()
                  AND valid_end >= SYSDATETIME()
                ORDER BY amount DESC, coupon_id
                """,
                activity_id,
            )
        )
        if coupon:
            conn.cursor().execute(
                "INSERT INTO user_coupons(user_id, coupon_id, status) VALUES (?, ?, N'未使用')",
                user_id,
                coupon["coupon_id"],
            )
            return {"ok": True, "activityId": activity_id, "rewardCouponName": coupon["coupon_name"]}

        reward_points = 20
        points_dao.add_points(conn, user_id, reward_points, "等级周奖励", activity_id)
        return {"ok": True, "activityId": activity_id, "rewardPoints": reward_points, "rewardCouponName": None}


def claim_weekly_coupon(user_id: int) -> dict[str, Any]:
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    valid_end = today + timedelta(days=7)
    with get_conn() as conn:
        level = int(conn.cursor().execute("SELECT level FROM ordinary_users WHERE user_id = ?", user_id).fetchval() or 1)
        if level < 3:
            raise ValueError("当前等级暂不能领取周代金券")
        if conn.cursor().execute(
            """
            SELECT 1
            FROM user_coupons uc
            JOIN coupons c ON c.coupon_id = uc.coupon_id
            WHERE uc.user_id = ? AND c.coupon_name = N'每周等级代金券'
              AND uc.received_time >= ?
            """,
            user_id,
            week_start,
        ).fetchone():
            raise ValueError("本周代金券已领取，请勿重复操作")
        activity_id = conn.cursor().execute(
            "SELECT TOP 1 activity_id FROM promotion_activities WHERE activity_name = N'等级周代金券' ORDER BY activity_id"
        ).fetchval()
        if not activity_id:
            admin_id = conn.cursor().execute("SELECT TOP 1 user_id FROM system_admins ORDER BY user_id").fetchval()
            if not admin_id:
                raise ValueError("缺少系统管理员，无法创建周代金券活动")
            activity_id = int(
                conn.cursor()
                .execute(
                    """
                    INSERT INTO promotion_activities(activity_name, activity_type, description, start_time, end_time, status, created_admin)
                    OUTPUT INSERTED.activity_id
                    VALUES (N'等级周代金券', N'等级奖励', N'会员等级周代金券领取活动', SYSDATETIME(), DATEADD(year, 1, SYSDATETIME()), N'进行中', ?)
                    """,
                    admin_id,
                )
                .fetchone()[0]
            )
        coupon_id = int(
            conn.cursor()
            .execute(
                """
                INSERT INTO coupons(activity_id, coupon_name, coupon_type, amount, min_amount, valid_start, valid_end, status)
                OUTPUT INSERTED.coupon_id
                VALUES (?, N'每周等级代金券', N'平台券', ?, ?, SYSDATETIME(), ?, N'启用')
                """,
                activity_id,
                10,
                0,
                valid_end,
            )
            .fetchone()[0]
        )
        conn.cursor().execute(
            "INSERT INTO user_coupons(user_id, coupon_id, status) VALUES (?, ?, N'未使用')",
            user_id,
            coupon_id,
        )
    return {"ok": True, "couponId": coupon_id, "couponName": "每周等级代金券"}


def create_activity(payload: dict[str, Any], admin_id: int) -> int:
    with get_conn() as conn:
        return int(
            conn.cursor()
            .execute(
                """
                INSERT INTO promotion_activities(activity_name, activity_type, description, start_time, end_time, status, created_admin)
                OUTPUT INSERTED.activity_id
                VALUES (?, ?, ?, ?, ?, N'进行中', ?)
                """,
                payload.get("activityName"),
                payload.get("activityType"),
                payload.get("description") or "",
                payload.get("startTime"),
                payload.get("endTime"),
                admin_id,
            )
            .fetchone()[0]
        )


def update_activity(activity_id: int, payload: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.cursor().execute(
            """
            UPDATE promotion_activities
            SET activity_name = COALESCE(?, activity_name), activity_type = COALESCE(?, activity_type),
                description = COALESCE(?, description), start_time = COALESCE(?, start_time),
                end_time = COALESCE(?, end_time)
            WHERE activity_id = ?
            """,
            payload.get("activityName"),
            payload.get("activityType"),
            payload.get("description"),
            payload.get("startTime"),
            payload.get("endTime"),
            activity_id,
        )


def save_platform_coupon(payload: dict[str, Any], admin_id: int | None = None) -> int:
    valid_start = payload.get("validStart") or datetime.now()
    valid_end = payload.get("validEnd") or (datetime.now() + timedelta(days=7))
    with get_conn() as conn:
        activity_id = payload.get("activityId")
        if not activity_id:
            activity_id = conn.cursor().execute(
                """
                SELECT TOP 1 activity_id
                FROM promotion_activities
                WHERE activity_name = N'平台代金券' AND status = N'进行中'
                ORDER BY activity_id DESC
                """
            ).fetchval()
        if not activity_id:
            created_admin = admin_id or conn.cursor().execute("SELECT TOP 1 user_id FROM system_admins ORDER BY user_id").fetchval()
            if not created_admin:
                raise ValueError("缺少系统管理员信息，无法创建平台券活动")
            activity_id = int(
                conn.cursor()
                .execute(
                    """
                    INSERT INTO promotion_activities(activity_name, activity_type, description, start_time, end_time, status, created_admin)
                    OUTPUT INSERTED.activity_id
                    VALUES (N'平台代金券', N'coupon', N'平台通用代金券发放活动', SYSDATETIME(), DATEADD(year, 10, SYSDATETIME()), N'进行中', ?)
                    """,
                    created_admin,
                )
                .fetchone()[0]
            )
        return int(
            conn.cursor()
            .execute(
                """
                INSERT INTO coupons(activity_id, coupon_name, coupon_type, amount, min_amount, valid_start, valid_end, status)
                OUTPUT INSERTED.coupon_id
                VALUES (?, ?, N'平台券', ?, ?, ?, ?, N'启用')
                """,
                activity_id,
                payload.get("couponName") or "平台代金券",
                payload.get("amount") or 0,
                payload.get("minAmount") or 0,
                valid_start,
                valid_end,
            )
            .fetchone()[0]
        )


def set_store_participation(store_id: int, activity_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    participate = bool(payload.get("participate", True))
    status = "已参与" if participate else "已退出"
    coupon_amount = float(payload.get("couponAmount") or 0)
    coupon_quantity = int(payload.get("couponQuantity") or 0)
    coupon_min_amount = float(payload.get("couponMinAmount") or 0)
    books = payload.get("bookItemIds") if payload.get("bookItemIds") is not None else payload.get("books")
    books = books or []
    with get_conn() as conn:
        if not conn.cursor().execute("SELECT 1 FROM promotion_activities WHERE activity_id = ?", activity_id).fetchone():
            raise ValueError("活动不存在")
        conn.cursor().execute(
            """
            MERGE store_activity_participation AS target
            USING (SELECT ? AS store_id, ? AS activity_id) AS src
            ON target.store_id = src.store_id AND target.activity_id = src.activity_id
            WHEN MATCHED THEN UPDATE SET participate_status = ?, coupon_amount = ?, coupon_quantity = ?
            WHEN NOT MATCHED THEN INSERT(store_id, activity_id, participate_status, coupon_amount, coupon_quantity)
            VALUES(src.store_id, src.activity_id, ?, ?, ?);
            """,
            store_id,
            activity_id,
            status,
            coupon_amount,
            coupon_quantity,
            status,
            coupon_amount,
            coupon_quantity,
        )
        conn.cursor().execute(
            "DELETE FROM activity_books WHERE store_id = ? AND activity_id = ?",
            store_id,
            activity_id,
        )
        if not participate:
            conn.cursor().execute(
                """
                UPDATE coupons
                SET status = N'停用'
                WHERE activity_id = ? AND store_id = ? AND coupon_type = N'店铺券'
                """,
                activity_id,
                store_id,
            )
            return _store_participation_summary(conn, store_id, activity_id)
        for raw in books:
            token = str(raw).strip()
            if not token:
                continue
            book = one(
                conn.cursor().execute(
                    """
                    SELECT TOP 1 b.book_item_id AS bookItemId, b.price
                    FROM book_items b
                    JOIN book_infos bi ON bi.book_info_id = b.book_info_id
                    WHERE b.store_id = ? AND (bi.ISBN = ? OR CAST(b.book_item_id AS nvarchar(50)) = ?)
                    """,
                    store_id,
                    token,
                    token,
                )
            )
            if not book:
                raise ValueError("参与书目不存在或不属于当前店铺")
            conn.cursor().execute(
                """
                INSERT INTO activity_books(store_id, activity_id, book_item_id, activity_price, discount_rate, activity_stock, status)
                VALUES (?, ?, ?, ?, ?, ?, N'参与中')
                """,
                store_id,
                activity_id,
                book["bookItemId"],
                book["price"],
                1,
                payload.get("activityStock") or 0,
            )
        if coupon_amount > 0 and coupon_quantity > 0:
            existing = conn.cursor().execute(
                """
                SELECT TOP 1 coupon_id FROM coupons
                WHERE activity_id = ? AND store_id = ? AND coupon_type = N'店铺券'
                ORDER BY coupon_id DESC
                """,
                activity_id,
                store_id,
            ).fetchval()
            if existing:
                conn.cursor().execute(
                    "UPDATE coupons SET amount = ?, min_amount = ?, status = N'启用' WHERE coupon_id = ?",
                    coupon_amount,
                    coupon_min_amount,
                    existing,
                )
            else:
                conn.cursor().execute(
                    """
                    INSERT INTO coupons(activity_id, coupon_name, coupon_type, store_id, amount, min_amount, valid_start, valid_end, status)
                    SELECT ?, CONCAT(s.store_name, N'活动店铺券'), N'店铺券', ?, ?, ?, a.start_time, a.end_time, N'启用'
                    FROM stores s CROSS JOIN promotion_activities a
                    WHERE s.store_id = ? AND a.activity_id = ?
                    """,
                    activity_id,
                    store_id,
                    coupon_amount,
                    coupon_min_amount,
                    store_id,
                    activity_id,
                )
        else:
            conn.cursor().execute(
                """
                UPDATE coupons
                SET status = N'停用'
                WHERE activity_id = ? AND store_id = ? AND coupon_type = N'店铺券'
                """,
                activity_id,
                store_id,
            )
        return _store_participation_summary(conn, store_id, activity_id)


def save_reward(payload: dict[str, Any], admin_id: int, reward_id: int | None = None) -> int:
    reward_type = _db_reward_type(payload.get("rewardType"))
    with get_conn() as conn:
        if reward_id:
            conn.cursor().execute(
                """
                UPDATE point_rewards
                SET reward_name = ?, reward_type = ?, required_points = ?, required_level = ?, stock = ?
                WHERE reward_id = ?
                """,
                payload.get("rewardName"),
                reward_type,
                payload.get("requiredPoints"),
                payload.get("requiredLevel") or 1,
                payload.get("stock") or 0,
                reward_id,
            )
            return reward_id
        return int(
            conn.cursor()
            .execute(
                """
                INSERT INTO point_rewards(reward_name, reward_type, required_points, required_level, stock, manage_admin)
                OUTPUT INSERTED.reward_id
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                payload.get("rewardName"),
                reward_type,
                payload.get("requiredPoints"),
                payload.get("requiredLevel") or 1,
                payload.get("stock") or 0,
                admin_id,
            )
            .fetchone()[0]
        )
