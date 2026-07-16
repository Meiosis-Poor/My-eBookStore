from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db import connect, get_conn
from backend.app.main import app


def _register_customer(client: TestClient, prefix: str) -> tuple[int, dict[str, str]]:
    user_name = f"{prefix}_{uuid4().hex[:10]}"
    registered = client.post(
        "/api/auth/register/user",
        json={"userName": user_name, "password": "Demo123", "nickname": user_name},
    )
    assert registered.status_code == 200, registered.json()
    user_id = int(registered.json()["data"]["userId"])
    logged_in = client.post(
        "/api/auth/login",
        json={"userName": user_name, "password": "Demo123", "role": "customer"},
    )
    token = logged_in.json()["data"]["token"]
    return user_id, {"Authorization": f"Bearer {token}"}


def _delete_customer(user_id: int) -> None:
    with get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_coupons WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM reward_redemptions WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM checkin_record WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM points_records WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM cart_items WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM shipping_addresses WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM store_blacklists WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM ordinary_users WHERE user_id = ?", user_id)
        cursor.execute("DELETE FROM users WHERE user_id = ?", user_id)


def test_database_objects_and_blacklist_trigger() -> None:
    client = TestClient(app)
    user_id, _ = _register_customer(client, "blacklist")
    try:
        with connect() as conn:
            cursor = conn.cursor()
            objects = {
                row[0]
                for row in cursor.execute(
                    """
                    SELECT name FROM sys.objects
                    WHERE name LIKE 'sp[_]%' OR name LIKE 'trg[_]%'
                    """
                ).fetchall()
            }
            assert {
                "sp_GetNextSeq",
                "sp_CreateOrder",
                "sp_PayOrder",
                "sp_RefundOrder",
                "sp_CheckIn",
                "sp_RedeemReward",
                "sp_ExpireCoupons",
                "trg_AfterBlacklists",
                "trg_AutoLevelUp",
            } <= objects

            admin_id = int(
                cursor.execute("SELECT TOP 1 user_id FROM users WHERE user_type = N'系统管理员'").fetchval()
            )
            store_ids: list[int] = []
            for index in range(10):
                store_id = int(
                    cursor.execute(
                        """
                        INSERT INTO stores(store_name, user_id, description)
                        OUTPUT INSERTED.store_id VALUES (?, ?, N'触发器测试')
                        """,
                        f"trigger_{uuid4().hex}_{index}",
                        admin_id,
                    ).fetchone()[0]
                )
                store_ids.append(store_id)
            cursor.executemany(
                "INSERT INTO store_blacklists(store_id, user_id, reason) VALUES (?, ?, N'测试')",
                [(store_id, user_id) for store_id in store_ids],
            )
            status = cursor.execute("SELECT status FROM users WHERE user_id = ?", user_id).fetchval()
            assert status == "封禁"
            conn.rollback()
    finally:
        _delete_customer(user_id)


def test_checkin_level_reward_and_coupon_expiration_procedures() -> None:
    client = TestClient(app)
    user_id, headers = _register_customer(client, "promotion")
    reward_id = None
    expired_coupon_id = None
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE ordinary_users SET total_points = 1245, available_points = 10000 WHERE user_id = ?",
                user_id,
            )
            reward = cursor.execute(
                """
                SELECT TOP 1 reward_id, stock
                FROM point_rewards
                WHERE status = N'启用' AND required_level <= 2 AND stock > 0
                ORDER BY required_points
                """
            ).fetchone()
            assert reward is not None
            reward_id, reward_stock = int(reward[0]), int(reward[1])
            activity_id = int(cursor.execute("SELECT TOP 1 activity_id FROM promotion_activities").fetchval())
            expired_coupon_id = int(
                cursor.execute(
                    """
                    INSERT INTO coupons(
                        activity_id, coupon_name, coupon_type, amount, min_amount,
                        valid_start, valid_end, status
                    ) OUTPUT INSERTED.coupon_id
                    VALUES (?, ?, N'平台券', 1, 0, DATEADD(day, -2, SYSDATETIME()),
                            DATEADD(day, -1, SYSDATETIME()), N'启用')
                    """,
                    activity_id,
                    f"expired_{uuid4().hex}",
                ).fetchone()[0]
            )
            cursor.execute(
                "INSERT INTO user_coupons(user_id, coupon_id, status) VALUES (?, ?, N'未使用')",
                user_id,
                expired_coupon_id,
            )

        checked_in = client.post("/api/promotions/checkin", headers=headers)
        assert checked_in.status_code == 200, checked_in.json()
        duplicate = client.post("/api/promotions/checkin", headers=headers)
        assert duplicate.status_code == 400
        profile = client.get("/api/users/me", headers=headers).json()["data"]
        assert profile["level"] == 2

        redeemed = client.post(f"/api/promotions/rewards/{reward_id}/redeem", headers=headers)
        assert redeemed.status_code == 200, redeemed.json()
        expired = client.get("/api/promotions/coupons/my?status=expired", headers=headers)
        assert any(item["couponId"] == expired_coupon_id for item in expired.json()["data"])

        with get_conn() as conn:
            cursor = conn.cursor()
            assert int(cursor.execute("SELECT stock FROM point_rewards WHERE reward_id = ?", reward_id).fetchval()) == reward_stock - 1
            assert cursor.execute(
                "SELECT 1 FROM points_records WHERE user_id = ? AND reason = N'兑换奖品' AND points_change < 0",
                user_id,
            ).fetchone()
    finally:
        with get_conn() as conn:
            if reward_id is not None:
                redemptions = int(
                    conn.cursor().execute(
                        "SELECT COUNT(*) FROM reward_redemptions WHERE user_id = ? AND reward_id = ?",
                        user_id,
                        reward_id,
                    ).fetchval()
                    or 0
                )
                if redemptions:
                    conn.cursor().execute(
                        "UPDATE point_rewards SET stock = stock + ? WHERE reward_id = ?",
                        redemptions,
                        reward_id,
                    )
            if expired_coupon_id is not None:
                conn.cursor().execute("DELETE FROM user_coupons WHERE coupon_id = ?", expired_coupon_id)
                conn.cursor().execute("DELETE FROM coupons WHERE coupon_id = ?", expired_coupon_id)
        _delete_customer(user_id)


def test_refund_request_store_scope_and_approval_procedure() -> None:
    client = TestClient(app)
    user_id, customer_headers = _register_customer(client, "refund")
    other_seller_id = None
    other_store_id = None
    order_id = None
    try:
        seller_login = client.post(
            "/api/auth/login",
            json={"userName": "seller_demo", "password": "Demo123", "role": "seller"},
        ).json()["data"]
        seller_headers = {"Authorization": f"Bearer {seller_login['token']}"}
        seller_store_id = int(seller_login["user"]["storeId"])
        with get_conn() as conn:
            book = conn.cursor().execute(
                "SELECT TOP 1 book_item_id, stock FROM book_items WHERE store_id = ? AND status = N'在售' AND stock > 0",
                seller_store_id,
            ).fetchone()
            assert book is not None
            book_item_id, original_stock = int(book[0]), int(book[1])

        address = client.post(
            "/api/addresses",
            json={"receiverName": "退款测试", "phone": "13800000000", "addressDetail": "测试地址"},
            headers=customer_headers,
        ).json()["data"]
        assert client.post(
            "/api/cart", json={"bookItemId": book_item_id, "quantity": 1}, headers=customer_headers
        ).status_code == 200
        order = client.post(
            "/api/orders",
            json={"cartItemIds": [book_item_id], "addressId": address["addressId"]},
            headers=customer_headers,
        )
        assert order.status_code == 200, order.json()
        order_id = int(order.json()["data"]["orderId"])
        paid = client.post(
            f"/api/orders/{order_id}/pay",
            json={"paymentMethod": "alipay"},
            headers=customer_headers,
        )
        assert paid.status_code == 200, paid.json()

        requested = client.post(
            f"/api/orders/{order_id}/refund",
            json={"reason": "自动化测试"},
            headers=customer_headers,
        )
        assert requested.status_code == 200, requested.json()
        detail = client.get(f"/api/orders/{order_id}", headers=customer_headers).json()["data"]
        assert detail["orderStatus"] == "refunding"

        other_name = f"seller_{uuid4().hex[:10]}"
        registered = client.post(
            "/api/auth/register/seller",
            json={"userName": other_name, "password": "Demo123", "storeName": f"store_{uuid4().hex[:10]}"},
        )
        assert registered.status_code == 200, registered.json()
        other_seller_id = int(registered.json()["data"]["userId"])
        other_store_id = int(registered.json()["data"]["storeId"])
        other_login = client.post(
            "/api/auth/login",
            json={"userName": other_name, "password": "Demo123", "role": "seller"},
        ).json()["data"]
        other_headers = {"Authorization": f"Bearer {other_login['token']}"}
        denied = client.post(f"/api/admin/orders/{order_id}/refund/approve", headers=other_headers)
        assert denied.status_code == 403

        approved = client.post(f"/api/admin/orders/{order_id}/refund/approve", headers=seller_headers)
        assert approved.status_code == 200, approved.json()
        detail = client.get(f"/api/orders/{order_id}", headers=customer_headers).json()["data"]
        assert detail["orderStatus"] == "refunded"
        with get_conn() as conn:
            cursor = conn.cursor()
            assert cursor.execute(
                "SELECT payment_status FROM payment_records WHERE order_id = ?", order_id
            ).fetchval() == "已退款"
            assert cursor.execute(
                "SELECT TOP 1 refund_status FROM refund_records WHERE order_id = ? ORDER BY refund_id DESC",
                order_id,
            ).fetchval() == "已退款"
            assert int(cursor.execute("SELECT stock FROM book_items WHERE book_item_id = ?", book_item_id).fetchval()) == original_stock

        with get_conn() as conn:
            conn.cursor().execute(
                "INSERT INTO store_blacklists(store_id, user_id, reason) VALUES (?, ?, N'访问限制测试')",
                seller_store_id,
                user_id,
            )
        assert client.get(f"/api/stores/{seller_store_id}", headers=customer_headers).status_code == 403
        assert client.post(
            "/api/cart", json={"bookItemId": book_item_id, "quantity": 1}, headers=customer_headers
        ).status_code == 403
        with get_conn() as conn:
            conn.cursor().execute(
                "INSERT INTO cart_items(user_id, book_item_id, quantity) VALUES (?, ?, 1)",
                user_id,
                book_item_id,
            )
        blocked_order = client.post(
            "/api/orders",
            json={"cartItemIds": [book_item_id], "addressId": address["addressId"]},
            headers=customer_headers,
        )
        assert blocked_order.status_code == 400
        assert "黑名单" in blocked_order.json()["message"]
    finally:
        with get_conn() as conn:
            cursor = conn.cursor()
            if order_id is not None:
                cursor.execute("DELETE FROM refund_records WHERE order_id = ?", order_id)
                cursor.execute("DELETE FROM payment_records WHERE order_id = ?", order_id)
                cursor.execute("DELETE FROM order_items WHERE order_id = ?", order_id)
                cursor.execute("DELETE FROM orders WHERE order_id = ?", order_id)
            if other_store_id is not None:
                cursor.execute("DELETE FROM stores WHERE store_id = ?", other_store_id)
            if other_seller_id is not None:
                cursor.execute("DELETE FROM store_admins WHERE user_id = ?", other_seller_id)
                cursor.execute("DELETE FROM users WHERE user_id = ?", other_seller_id)
        _delete_customer(user_id)
