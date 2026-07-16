from __future__ import annotations

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from tests.ui.conftest import save_milestone
from tests.ui.helpers import login, open_page


pytestmark = [pytest.mark.integration, pytest.mark.selenium, pytest.mark.ui_e2e]


def _add_test_book(browser, wait, base_url, context) -> None:
    book_name = f"Acceptance Book {context['isbn'].split('-')[-1][:8]}"
    open_page(browser, base_url, f"search.html?keyword={book_name}&searchType=title")
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-action="add-cart"]'))).click()
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-success")))


def test_customer_checkout_payment_review(browser, wait, base_url, acceptance_context) -> None:
    login(browser, wait, base_url, acceptance_context["userName"])
    _add_test_book(browser, wait, base_url, acceptance_context)
    open_page(browser, base_url, "cart.html")
    row = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "tr[data-id]")))
    row.find_element(By.CSS_SELECTOR, ".qty-plus").click()
    wait.until(lambda _: browser.find_element(By.CSS_SELECTOR, ".qty-input").get_attribute("value") == "2")
    qty = browser.find_element(By.CSS_SELECTOR, ".qty-input")
    browser.execute_script("arguments[0].value='0'; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));", qty)
    wait.until(lambda _: int(browser.find_element(By.CSS_SELECTOR, ".qty-input").get_attribute("value")) >= 1)
    save_milestone(browser, "customer-cart")
    browser.find_element(By.ID, "goCheckoutBtn").click()
    wait.until(EC.url_contains("checkout.html"))
    wait.until(EC.text_to_be_present_in_element((By.ID, "checkoutAddressCard"), "Acceptance"))
    browser.find_element(By.ID, "submitOrderBtn").click()
    wait.until(EC.url_contains("payment.html"))
    order_id = browser.current_url.split("orderId=")[1].split("&")[0]
    save_milestone(browser, "customer-payment")
    browser.find_element(By.ID, "confirmPayBtn").click()
    wait.until(EC.url_contains("payment-result.html"))
    save_milestone(browser, "customer-payment-success")
    open_page(browser, base_url, f"order-detail.html?id={order_id}")
    wait.until(EC.visibility_of_element_located((By.ID, "orderNo")))
    form = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".review-form")))
    form.find_element(By.NAME, "content").send_keys("Selenium UI review")
    form.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-success")))
    wait.until(EC.staleness_of(form))
    duplicate = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".review-form")))
    duplicate.find_element(By.NAME, "content").send_keys("Duplicate Selenium review")
    duplicate.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-danger")))
    browser.refresh()
    assert browser.execute_script("return !!localStorage.getItem('ebs_token')")
    save_milestone(browser, "customer-order-detail")


def test_cancel_pending_order(browser, wait, base_url, acceptance_context) -> None:
    login(browser, wait, base_url, acceptance_context["userName"])
    _add_test_book(browser, wait, base_url, acceptance_context)
    open_page(browser, base_url, "cart.html")
    wait.until(EC.element_to_be_clickable((By.ID, "goCheckoutBtn"))).click()
    wait.until(EC.element_to_be_clickable((By.ID, "submitOrderBtn"))).click()
    wait.until(EC.url_contains("payment.html"))
    order_id = browser.current_url.split("orderId=")[1].split("&")[0]
    open_page(browser, base_url, f"order-detail.html?id={order_id}")
    wait.until(EC.element_to_be_clickable((By.ID, "cancelBtn"))).click()
    wait.until(EC.text_to_be_present_in_element((By.ID, "orderStatusBadge"), "取消"))


def test_session_and_admin_guards(browser, wait, base_url) -> None:
    open_page(browser, base_url, "orders.html")
    wait.until(EC.url_contains("login.html"))
    browser.execute_script("localStorage.setItem('ebs_token','forged'); localStorage.setItem('ebs_user', JSON.stringify({userType:'customer',userName:'fake'}));")
    open_page(browser, base_url, "orders.html")
    wait.until(EC.visibility_of_element_located((By.TAG_NAME, "body")))
    login(browser, wait, base_url, "reader_demo")
    open_page(browser, base_url, "admin/dashboard.html")
    wait.until(lambda driver: "admin/dashboard.html" not in driver.current_url or "登录" in driver.page_source)
