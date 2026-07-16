from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db import connect, get_conn
from backend.app.main import app
from conftest import cleanup_customer, register_customer


def _register_customer(client: TestClient, prefix: str) -> tuple[int, dict[str, str]]:
    customer = register_customer(client, f"workflow_{prefix}")
    return customer["userId"], customer["headers"]


def _delete_customer(user_id: int) -> None:
    cleanup_customer(user_id)


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
    reward_coupon_id = None
    activity_id = None
    expired_coupon_id = None
    try:
        with get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE ordinary_users SET total_points = 1245, available_points = 10000 WHERE user_id = ?",
                user_id,
            )
            admin_id = int(cursor.execute("SELECT TOP 1 user_id FROM system_admins ORDER BY user_id").fetchval())
            reward_name = f"10元workflow_coupon_{uuid4().hex[:10]}"
            reward_id = int(
                cursor.execute(
                    """
                    INSERT INTO point_rewards(
                        reward_name, reward_type, required_points, required_level, stock, status, manage_admin
                    ) OUTPUT INSERTED.reward_id
                    VALUES (?, N'代金券', 10, 2, 2, N'启用', ?)
                    """,
                    reward_name,
                    admin_id,
                ).fetchone()[0]
            )
            reward_stock = 2
            activity_id = int(
                cursor.execute(
                    """
                    INSERT INTO promotion_activities(
                        activity_name, activity_type, description, start_time, end_time, status, created_admin
                    ) OUTPUT INSERTED.activity_id
                    VALUES (?, N'test', N'workflow expiration test', DATEADD(day, -3, SYSDATETIME()),
                            DATEADD(day, 3, SYSDATETIME()), N'进行中', ?)
                    """,
                    f"workflow_activity_{uuid4().hex[:10]}",
                    admin_id,
                ).fetchone()[0]
            )
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
        redeemed_data = redeemed.json()["data"]
        assert redeemed_data["rewardType"] == "coupon"
        assert datetime.fromisoformat(redeemed_data["coupon"]["validEnd"]) > datetime.now()
        reward_coupon_id = int(redeemed_data["coupon"]["couponId"])
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
        _delete_customer(user_id)
        with get_conn() as conn:
            cursor = conn.cursor()
            if expired_coupon_id is not None:
                cursor.execute("DELETE FROM coupons WHERE coupon_id = ?", expired_coupon_id)
            if reward_coupon_id is not None:
                cursor.execute("DELETE FROM coupons WHERE coupon_id = ?", reward_coupon_id)
            if reward_id is not None:
                cursor.execute("DELETE FROM point_rewards WHERE reward_id = ?", reward_id)
            if activity_id is not None:
                cursor.execute("DELETE FROM promotion_activities WHERE activity_id = ?", activity_id)


def test_admin_reward_coupon_configuration_and_redemption_delivery() -> None:
    client = TestClient(app)
    customer_ids: list[int] = []
    coupon_reward_id = None
    physical_reward_id = None
    coupon_id = None
    reward_name = f"测试满减券_{uuid4().hex[:8]}"
    try:
        admin_login = client.post(
            "/api/auth/login",
            json={"userName": "admin", "password": "Demo123", "role": "platform_admin"},
        )
        assert admin_login.status_code == 200, admin_login.json()
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['data']['token']}"}

        created_coupon = client.post(
            "/api/admin/promotions/rewards",
            json={
                "rewardName": reward_name,
                "rewardType": "coupon",
                "requiredPoints": 10,
                "requiredLevel": 1,
                "stock": 5,
                "couponMinAmount": 100,
                "couponAmount": 15,
            },
            headers=admin_headers,
        )
        assert created_coupon.status_code == 200, created_coupon.json()
        coupon_reward_id = int(created_coupon.json()["data"]["rewardId"])

        duplicate = client.post(
            "/api/admin/promotions/rewards",
            json={
                "rewardName": reward_name,
                "rewardType": "coupon",
                "requiredPoints": 10,
                "requiredLevel": 1,
                "stock": 1,
                "couponMinAmount": 0,
                "couponAmount": 1,
            },
            headers=admin_headers,
        )
        assert duplicate.status_code == 400

        created_physical = client.post(
            "/api/admin/promotions/rewards",
            json={
                "rewardName": f"测试实物_{uuid4().hex[:8]}",
                "rewardType": "physical",
                "requiredPoints": 10,
                "requiredLevel": 1,
                "stock": 2,
            },
            headers=admin_headers,
        )
        assert created_physical.status_code == 200, created_physical.json()
        physical_reward_id = int(created_physical.json()["data"]["rewardId"])

        listed = client.get("/api/promotions/rewards").json()["data"]
        configured = next(item for item in listed if item["rewardId"] == coupon_reward_id)
        assert configured["couponMinAmount"] == 100
        assert configured["couponAmount"] == 15
        assert datetime.fromisoformat(configured["couponValidEnd"]) > datetime.now()

        redemptions = []
        for index in range(2):
            user_id, headers = _register_customer(client, f"reward_{index}")
            customer_ids.append(user_id)
            with get_conn() as conn:
                conn.cursor().execute(
                    "UPDATE ordinary_users SET total_points = 100, available_points = 100 WHERE user_id = ?",
                    user_id,
                )
            redeemed = client.post(
                f"/api/promotions/rewards/{coupon_reward_id}/redeem", headers=headers
            )
            assert redeemed.status_code == 200, redeemed.json()
            redemptions.append(redeemed.json()["data"])

        assert redemptions[0]["coupon"]["couponId"] == redemptions[1]["coupon"]["couponId"]
        assert redemptions[0]["coupon"]["userCouponId"] != redemptions[1]["coupon"]["userCouponId"]
        assert redemptions[0]["coupon"]["amount"] == 15
        assert redemptions[0]["coupon"]["minAmount"] == 100
        assert datetime.fromisoformat(redemptions[0]["coupon"]["validEnd"]) > datetime.now()
        coupon_id = int(redemptions[0]["coupon"]["couponId"])

        first_user_headers = _register_customer(client, "physical_reward")
        physical_user_id, physical_headers = first_user_headers
        customer_ids.append(physical_user_id)
        with get_conn() as conn:
            conn.cursor().execute(
                "UPDATE ordinary_users SET total_points = 100, available_points = 100 WHERE user_id = ?",
                physical_user_id,
            )
        physical = client.post(
            f"/api/promotions/rewards/{physical_reward_id}/redeem", headers=physical_headers
        )
        assert physical.status_code == 200, physical.json()
        assert physical.json()["data"]["rewardType"] == "physical"
        assert physical.json()["data"]["coupon"] is None
        with get_conn() as conn:
            issued_count = int(
                conn.cursor().execute(
                    "SELECT COUNT(*) FROM user_coupons WHERE coupon_id = ?", coupon_id
                ).fetchval()
            )
            assert issued_count == 2
    finally:
        for user_id in customer_ids:
            _delete_customer(user_id)
        with get_conn() as conn:
            cursor = conn.cursor()
            if coupon_reward_id is not None:
                cursor.execute("DELETE FROM point_rewards WHERE reward_id = ?", coupon_reward_id)
            if physical_reward_id is not None:
                cursor.execute("DELETE FROM point_rewards WHERE reward_id = ?", physical_reward_id)
            if coupon_id is not None:
                cursor.execute("DELETE FROM coupons WHERE coupon_id = ?", coupon_id)


def test_refund_request_store_scope_and_approval_procedure(acceptance_context) -> None:
    client = TestClient(app)
    user_id = acceptance_context["userId"]
    customer_headers = acceptance_context["headers"]
    other_seller_id = None
    other_store_id = None
    order_id = None
    book_item_id = acceptance_context["bookItemId"]
    original_inventory = (
        acceptance_context["stock"],
        acceptance_context["lockedStock"],
        acceptance_context["salesCount"],
    )
    try:
        seller_login = client.post(
            "/api/auth/login",
            json={"userName": "seller_demo", "password": "Demo123", "role": "seller"},
        ).json()["data"]
        seller_headers = {"Authorization": f"Bearer {seller_login['token']}"}
        seller_store_id = int(seller_login["user"]["storeId"])
        assert client.post(
            "/api/cart", json={"bookItemId": book_item_id, "quantity": 1}, headers=customer_headers
        ).status_code == 200
        order = client.post(
            "/api/orders",
            json={"cartItemIds": [book_item_id], "addressId": acceptance_context["addressId"]},
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
            inventory = cursor.execute(
                "SELECT stock, locked_stock, sales_count FROM book_items WHERE book_item_id = ?", book_item_id
            ).fetchone()
            assert tuple(int(value) for value in inventory) == original_inventory

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
            json={"cartItemIds": [book_item_id], "addressId": acceptance_context["addressId"]},
            headers=customer_headers,
        )
        assert blocked_order.status_code == 400
        assert "黑名单" in blocked_order.json()["message"]
    finally:
        with get_conn() as conn:
            cursor = conn.cursor()
            if other_store_id is not None:
                cursor.execute("DELETE FROM stores WHERE store_id = ?", other_store_id)
            if other_seller_id is not None:
                cursor.execute("DELETE FROM store_admins WHERE user_id = ?", other_seller_id)
                cursor.execute("DELETE FROM users WHERE user_id = ?", other_seller_id)
