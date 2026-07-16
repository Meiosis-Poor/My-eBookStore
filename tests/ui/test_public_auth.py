from __future__ import annotations

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from tests.ui.conftest import save_milestone
from tests.ui.helpers import login, open_page, token


pytestmark = [pytest.mark.integration, pytest.mark.selenium, pytest.mark.ui_smoke]


def test_public_pages_and_search(browser, wait, base_url, acceptance_context) -> None:
    open_page(browser, base_url, "/")
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".brand")))
    assert "My-eBookStore" in browser.title
    for path in ("promotions.html", "login.html"):
        open_page(browser, base_url, path)
        assert browser.find_element(By.TAG_NAME, "body").is_displayed()

    book_name = f"Acceptance Book {acceptance_context['isbn'].split('-')[-1][:8]}"
    open_page(browser, base_url, f"search.html?keyword={book_name}&searchType=title")
    card = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".book-card")))
    assert book_name in card.text
    card.click()
    wait.until(EC.url_contains("book-detail.html"))
    wait.until(EC.text_to_be_present_in_element((By.ID, "bookTitle"), book_name))
    assert browser.find_element(By.ID, "bookTitle").text == book_name
    save_milestone(browser, "public-book-detail")


def test_login_validation_and_wrong_password(browser, wait, base_url) -> None:
    open_page(browser, base_url, "login.html")
    browser.find_element(By.CSS_SELECTOR, "#loginForm button[type=submit]").click()
    assert "has-error" in browser.find_element(By.ID, "loginUserNameGroup").get_attribute("class")
    browser.find_element(By.NAME, "userName").send_keys("reader_demo")
    browser.find_element(By.NAME, "password").send_keys("wrong")
    browser.find_element(By.CSS_SELECTOR, "#loginForm button[type=submit]").click()
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".toast-danger")))
    assert token(browser) == ""


@pytest.mark.parametrize("user_name,role", [("reader_demo", "customer"), ("seller_demo", "seller"), ("admin", "platform_admin")])
def test_role_login(browser, wait, base_url, user_name, role) -> None:
    login(browser, wait, base_url, user_name, role)
    assert token(browser)
    save_milestone(browser, f"login-{role}")


def test_logout(browser, wait, base_url) -> None:
    login(browser, wait, base_url, "reader_demo")
    browser.find_element(By.ID, "userChipTrigger").click()
    browser.find_element(By.CSS_SELECTOR, '[data-action="logout"]').click()
    wait.until(lambda driver: token(driver) == "")
