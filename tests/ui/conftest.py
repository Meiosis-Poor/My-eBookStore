from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait


def pytest_addoption(parser) -> None:
    parser.addoption("--headed", action="store_true", help="show the Chrome window")


@pytest.fixture
def base_url() -> str:
    return os.getenv("EBOOKSTORE_UI_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@pytest.fixture
def browser(request, base_url):
    options = Options()
    if not request.config.getoption("--headed"):
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    options.add_experimental_option(
        "prefs", {"credentials_enable_service": False, "profile.password_manager_enabled": False}
    )
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(20)
    driver.get(base_url)
    driver.delete_all_cookies()
    driver.execute_script("localStorage.clear(); sessionStorage.clear();")
    request.node._selenium_driver = driver
    try:
        yield driver
    finally:
        driver.quit()


@pytest.fixture
def wait(browser):
    return WebDriverWait(browser, 15)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or not report.failed:
        return
    driver = getattr(item, "_selenium_driver", None)
    if driver is None:
        return
    root = Path(os.getenv("EBOOKSTORE_UI_RESULT_DIR", "test-results/selenium/manual")) / "failures"
    root.mkdir(parents=True, exist_ok=True)
    name = item.nodeid.replace("/", "_").replace("\\", "_").replace("::", "__").replace("[", "_").replace("]", "_")
    driver.save_screenshot(str(root / f"{name}.png"))
    (root / f"{name}.html").write_text(driver.page_source, encoding="utf-8")
    (root / f"{name}.console.json").write_text(
        json.dumps(driver.get_log("browser"), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def save_milestone(driver, name: str) -> None:
    root = Path(os.getenv("EBOOKSTORE_UI_RESULT_DIR", "test-results/selenium/manual")) / "screenshots"
    root.mkdir(parents=True, exist_ok=True)
    driver.save_screenshot(str(root / f"{name}.png"))
