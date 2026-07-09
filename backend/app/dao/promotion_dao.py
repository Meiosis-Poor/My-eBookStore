"""
promotion_dao.py — 促销活动数据访问层
对应表：promotion_activities, coupons, user_coupons, point_rewards,
         reward_redemptions, checkin_record, points_records
对应用例：4.2.6 促销活动, 4.3.5 促销活动管理
"""

from ..db import get_conn, many, one, execute_scalar


# ─── 活动 ───

def list_activities():
    """可参与的活动列表"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT activity_id, activity_name, activity_type, description,
                   start_time, end_time, status
            FROM promotion_activities
            WHERE status IN (N'未开始', N'进行中')
            ORDER BY start_time DESC
        """)
        return many(cur)


# ─── 签到 ───

def checkin(user_id):
    """每日签到 — 调存储过程 sp_CheckIn"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            DECLARE @ok BIT, @cd INT, @rp INT, @gc BIT
            EXEC sp_CheckIn @user_id = ?, @success = @ok OUTPUT,
                 @continuous_days = @cd OUTPUT, @reward_points = @rp OUTPUT,
                 @got_coupon = @gc OUTPUT
            SELECT @ok AS success, @cd AS continuous_days,
                   @rp AS reward_points, @gc AS got_coupon
        """, [user_id])
        return one(cur)


def get_checkin_status(user_id):
    """查今天是否已签到"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT checkin_id, checkin_date, continuous_checkin_days, reward_points
            FROM checkin_record
            WHERE user_id = ? AND checkin_date = CAST(SYSDATETIME() AS DATE)
        """, [user_id])
        return one(cur)


def get_checkin_history(user_id, days=30):
    """近 N 天签到记录"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT checkin_date, continuous_checkin_days, reward_points
            FROM checkin_record
            WHERE user_id = ? AND checkin_date >= DATEADD(DAY, -?, CAST(SYSDATETIME() AS DATE))
            ORDER BY checkin_date DESC
        """, [user_id, days])
        return many(cur)


# ─── 代金券 ───

def list_user_coupons(user_id, status='unused'):
    """我的代金券"""
    status_map = {'unused': N'未使用', 'used': N'已使用', 'expired': N'已过期'}
    db_status = status_map.get(status, N'未使用')

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT uc.user_coupon_id, uc.status, uc.received_time, uc.used_time, uc.order_id,
                   c.coupon_name, c.coupon_type, c.amount, c.min_amount,
                   c.valid_start, c.valid_end, s.store_name AS coupon_store
            FROM user_coupons uc
            JOIN coupons c ON uc.coupon_id = c.coupon_id
            LEFT JOIN stores s ON c.store_id = s.store_id
            WHERE uc.user_id = ? AND uc.status = ?
            ORDER BY uc.received_time DESC
        """, [user_id, db_status])
        return many(cur)


def claim_weekly_coupon(user_id):
    """高等级用户每周领代金券"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            DECLARE @lv INT
            SELECT @lv = level FROM ordinary_users WHERE user_id = ?

            IF @lv >= 5
                INSERT INTO user_coupons (user_id, coupon_id, status)
                SELECT ?, coupon_id, N'未使用'
                FROM coupons WHERE coupon_name = N'连续7天签到券' AND status = N'启用'

            SELECT @lv AS current_level
        """, [user_id, user_id])
        return one(cur)


# ─── 积分兑换 ───

def list_rewards():
    """可兑换奖品列表"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT reward_id, reward_name, reward_type,
                   required_points, required_level, stock, status
            FROM point_rewards WHERE status = N'启用'
            ORDER BY required_points
        """)
        return many(cur)


def redeem_reward(user_id, reward_id):
    """积分兑换 — 调存储过程 sp_RedeemReward"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            DECLARE @ok BIT
            EXEC sp_RedeemReward @user_id = ?, @reward_id = ?, @success = @ok OUTPUT
            SELECT @ok AS success
        """, [user_id, reward_id])
        row = cur.fetchone()
        return {'success': row[0] if row else False}


def get_points_history(user_id, page=1, page_size=20):
    """积分流水"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT record_id, points_change, reason, related_id, created_time
            FROM points_records
            WHERE user_id = ?
            ORDER BY created_time DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """, [user_id, (page-1)*page_size, page_size])
        return many(cur)


# ─── 后台管理 ───

def create_activity(data):
    """后台管理员创建活动"""
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO promotion_activities (activity_name, activity_type, description,
                                              start_time, end_time, created_admin)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [data['activity_name'], data['activity_type'], data.get('description', ''),
              data['start_time'], data['end_time'], data['created_admin']])
        return execute_scalar(conn, "SELECT SCOPE_IDENTITY()")
