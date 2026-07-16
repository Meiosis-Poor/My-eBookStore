from __future__ import annotations

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from backend.app.db import get_conn
from tests.ui.conftest import save_milestone
from tests.ui.helpers import browser_api, login, open_page


pytestmark = [pytest.mark.integration, pytest.mark.selenium, pytest.mark.ui_e2e]


def test_customer_promotions_and_points(browser, wait, base_url, acceptance_context, temporary_reward) -> None:
    login(browser, wait, base_url, acceptance_context["userName"])
    open_page(browser, base_url, "promotions.html")
    wait.until(lambda driver: driver.find_element(By.ID, "userLevelText").text == "Lv.3")
    wait.until(EC.visibility_of_element_located((By.ID, "weeklyCouponBtn")))
    checkin = wait.until(EC.element_to_be_clickable((By.ID, "checkinBtn")))
    checkin.click()
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-success")))
    browser.refresh()
    wait.until(lambda driver: driver.find_element(By.ID, "userLevelText").text == "Lv.3")
    wait.until(EC.element_to_be_clickable((By.ID, "checkinBtn"))).click()
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-warning")))
    points = browser_api(browser, "/users/me/points")
    assert points["status"] == 200 and points["payload"]["data"]["total"] >= 1
    browser.find_element(By.CSS_SELECTOR, '[data-panel="panelRewards"]').click()
    wait.until(EC.visibility_of_element_located((By.ID, "rewardGrid")))
    weekly = browser.find_element(By.ID, "weeklyCouponBtn")
    assert "hidden" not in weekly.get_attribute("class")
    save_milestone(browser, "customer-promotions")


def test_customer_reward_boundaries(browser, wait, base_url, acceptance_context, temporary_reward) -> None:
    login(browser, wait, base_url, acceptance_context["userName"])
    success = browser_api(browser, f"/promotions/rewards/{temporary_reward}/redeem", "POST")
    assert success["status"] == 200
    with get_conn() as conn:
        row = conn.cursor().execute("SELECT stock FROM point_rewards WHERE reward_id = ?", temporary_reward).fetchone()
        assert int(row[0]) == 1
        conn.cursor().execute("UPDATE point_rewards SET stock = 0 WHERE reward_id = ?", temporary_reward)
    no_stock = browser_api(browser, f"/promotions/rewards/{temporary_reward}/redeem", "POST")
    assert no_stock["status"] == 400
    unknown = browser_api(browser, "/promotions/rewards/2147483647/redeem", "POST")
    assert unknown["status"] == 400


def test_customer_activity_and_coupon_paths(browser, wait, base_url, acceptance_context) -> None:
    login(browser, wait, base_url, acceptance_context["userName"])
    activities = browser_api(browser, "/promotions/activities")
    assert activities["status"] == 200
    rows = activities["payload"]["data"]
    if rows:
        activity_id = rows[0]["activityId"]
        first = browser_api(browser, f"/promotions/activities/{activity_id}/join", "POST")
        second = browser_api(browser, f"/promotions/activities/{activity_id}/join", "POST")
        assert first["status"] in {200, 400} and second["status"] in {200, 400}
    coupons = browser_api(browser, "/promotions/coupons/my?status=unused")
    assert coupons["status"] == 200
    open_page(browser, base_url, "checkout.html")
    wait.until(EC.visibility_of_element_located((By.TAG_NAME, "body")))


def test_seller_promotion_paths(browser, wait, base_url) -> None:
    login(browser, wait, base_url, "seller_demo", "seller")
    open_page(browser, base_url, "admin/promotions.html")
    wait.until(EC.visibility_of_element_located((By.ID, "adminActivityList")))
    assert browser.find_element(By.ID, "adminActivityList").is_displayed()
    save_milestone(browser, "seller-promotions-extended")


def test_seller_book_crud_paths(browser, wait, base_url, acceptance_context) -> None:
    login(browser, wait, base_url, "seller_demo", "seller")
    open_page(browser, base_url, "admin/books.html")
    wait.until(EC.visibility_of_element_located((By.ID, "booksTableBody")))
    detail = browser_api(browser, f"/books/{acceptance_context['bookItemId']}")
    assert detail["status"] == 200
    updated = browser_api(browser, f"/admin/books/{acceptance_context['bookItemId']}", "PUT", {"price": 31, "stock": 3, "description": "Selenium updated"})
    assert updated["status"] == 200
    duplicate = browser_api(browser, "/admin/books", "POST", {"bookName":"Duplicate", "author":"UI", "isbn":acceptance_context["isbn"], "categoryId":1, "price":1, "stock":1})
    assert duplicate["status"] == 400
    down = browser_api(browser, f"/admin/books/{acceptance_context['bookItemId']}", "DELETE")
    assert down["status"] == 200


def test_seller_book_validation_paths(browser, wait, base_url) -> None:
    login(browser, wait, base_url, "seller_demo", "seller")
    open_page(browser, base_url, "admin/books.html")
    wait.until(EC.element_to_be_clickable((By.ID, "addBookBtn"))).click()
    price = browser.find_element(By.NAME, "price")
    stock = browser.find_element(By.NAME, "stock")
    browser.execute_script("arguments[0].value='-1'; arguments[1].value='-1';", price, stock)
    assert not price.get_property("validity")["valid"] and not stock.get_property("validity")["valid"]


def test_seller_order_refund_paths(browser, wait, base_url) -> None:
    login(browser, wait, base_url, "seller_demo", "seller")
    open_page(browser, base_url, "admin/orders.html")
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".admin-sidebar")))
    orders = browser_api(browser, "/admin/orders")
    assert orders["status"] == 200
    cross = browser_api(browser, "/admin/orders/2147483647/status", "PUT", {"status":"completed"})
    refund = browser_api(browser, "/admin/orders/2147483647/refund/approve", "POST")
    assert cross["status"] in {400, 403, 404} and refund["status"] in {400, 403, 404}


def test_seller_store_blacklist_paths(browser, wait, base_url, acceptance_context) -> None:
    login(browser, wait, base_url, "seller_demo", "seller")
    me = browser_api(browser, "/users/me")
    store_id = me["payload"]["data"]["storeId"]
    profile = browser_api(browser, f"/stores/{store_id}")
    assert profile["status"] == 200
    blocked = browser_api(browser, f"/admin/users/{acceptance_context['userId']}/blacklist", "POST", {"reason":"selenium"})
    repeated = browser_api(browser, f"/admin/users/{acceptance_context['userId']}/blacklist", "POST", {"reason":"selenium"})
    restored = browser_api(browser, f"/admin/users/{acceptance_context['userId']}/blacklist", "DELETE")
    assert blocked["status"] == 200 and repeated["status"] == 200 and restored["status"] == 200
    export = browser.execute_async_script("const done=arguments[0]; fetch('/api/admin/statistics/export',{headers:{Authorization:'Bearer '+localStorage.getItem('ebs_token')}}).then(async r=>done({status:r.status,text:await r.text()}));")
    assert export["status"] == 200 and "date,storeName" in export["text"]


def test_admin_user_store_paths(browser, wait, base_url, acceptance_context) -> None:
    login(browser, wait, base_url, "admin", "platform_admin")
    users = browser_api(browser, f"/admin/users?keyword={acceptance_context['userName']}")
    assert users["status"] == 200
    banned = browser_api(browser, f"/admin/users/{acceptance_context['userId']}/status", "PUT", {"status":"banned"})
    assert banned["status"] == 200
    denied = browser_api(browser, "/users/me", "GET")
    assert denied["status"] == 200  # administrator session remains valid
    restored = browser_api(browser, f"/admin/users/{acceptance_context['userId']}/status", "PUT", {"status":"active"})
    stores = browser_api(browser, "/admin/stores")
    assert restored["status"] == 200 and stores["status"] == 200


def test_admin_book_order_paths(browser, wait, base_url, acceptance_context) -> None:
    login(browser, wait, base_url, "admin", "platform_admin")
    first = browser_api(browser, f"/admin/books/{acceptance_context['bookItemId']}/force-takedown", "POST")
    second = browser_api(browser, f"/admin/books/{acceptance_context['bookItemId']}/force-takedown", "POST")
    orders = browser_api(browser, "/admin/orders?keyword=TEST")
    approve = browser_api(browser, "/admin/orders/2147483647/refund/approve", "POST")
    reject = browser_api(browser, "/admin/orders/2147483647/refund/reject", "POST")
    assert first["status"] == second["status"] == 200
    assert orders["status"] == 200 and approve["status"] in {400, 404} and reject["status"] in {400, 404}


def test_admin_promotion_reward_paths(browser, wait, base_url) -> None:
    login(browser, wait, base_url, "admin", "platform_admin")
    open_page(browser, base_url, "admin/promotions.html")
    wait.until(EC.visibility_of_element_located((By.ID, "addActivityBtn")))
    assert browser.find_element(By.ID, "platformCouponForm").is_enabled()
    browser.find_element(By.CSS_SELECTOR, '[data-panel="panelRewards"]').click()
    wait.until(EC.element_to_be_clickable((By.ID, "addRewardBtn"))).click()
    wait.until(EC.visibility_of_element_located((By.ID, "rewardForm")))
    form = browser.find_element(By.ID, "rewardForm")
    assert form.find_element(By.NAME, "requiredPoints").is_enabled()


def test_admin_recommendation_statistics_paths(browser, wait, base_url) -> None:
    login(browser, wait, base_url, "admin", "platform_admin")
    baseline = browser_api(browser, "/admin/recommendation/settings")["payload"]["data"]
    try:
        changed = {**baseline, "guessWeight": 1.2, "hotWeight": 0.8, "detailSameStoreEnabled": False}
        assert browser_api(browser, "/admin/recommendation/settings", "PUT", changed)["status"] == 200
        current = browser_api(browser, "/admin/recommendation/settings")["payload"]["data"]
        assert float(current["guessWeight"]) == 1.2 and current["detailSameStoreEnabled"] is False
        overview = browser_api(browser, "/admin/statistics/overview")
        risk = browser_api(browser, "/admin/statistics/risk-stores")
        assert overview["status"] == 200 and risk["status"] == 200
        open_page(browser, base_url, "admin/statistics.html")
        wait.until(EC.visibility_of_element_located((By.ID, "recommendationForm")))
        save_milestone(browser, "admin-statistics-extended")
    finally:
        browser_api(browser, "/admin/recommendation/settings", "PUT", baseline)
