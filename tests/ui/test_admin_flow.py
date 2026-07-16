from __future__ import annotations

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

from tests.ui.conftest import save_milestone
from tests.ui.helpers import login, open_page


pytestmark = [pytest.mark.integration, pytest.mark.selenium, pytest.mark.ui_e2e]


def test_seller_admin_pages(browser, wait, base_url) -> None:
    login(browser, wait, base_url, "seller_demo", "seller")
    for path in ("admin/books.html", "admin/orders.html"):
        open_page(browser, base_url, path)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".admin-sidebar")))
    open_page(browser, base_url, "admin/books.html")
    assert browser.find_elements(By.ID, "bookForm") or browser.find_elements(By.CSS_SELECTOR, "[data-action]")
    save_milestone(browser, "seller-books")


def test_platform_admin_pages(browser, wait, base_url) -> None:
    login(browser, wait, base_url, "admin", "platform_admin")
    for path in ("admin/statistics.html", "admin/users.html", "admin/stores.html", "admin/promotions.html"):
        open_page(browser, base_url, path)
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".admin-sidebar")))
    save_milestone(browser, "platform-admin")
