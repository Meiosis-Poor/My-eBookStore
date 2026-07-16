from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


def open_page(browser, base_url: str, path: str) -> None:
    browser.get(f"{base_url}/{path.lstrip('/')}")


def login(browser, wait, base_url: str, user_name: str, role: str = "customer", password: str = "Demo123") -> None:
    open_page(browser, base_url, "login.html")
    if role != "customer":
        browser.find_element(By.CSS_SELECTOR, f'#loginRoleSwitch [data-role="{role}"]').click()
    browser.find_element(By.NAME, "userName").send_keys(user_name)
    browser.find_element(By.NAME, "password").send_keys(password)
    browser.find_element(By.CSS_SELECTOR, "#loginForm button[type=submit]").click()
    expected = "admin/dashboard.html" if role in {"seller", "platform_admin"} else "index.html"
    wait.until(EC.url_contains(expected))


def token(browser) -> str:
    return browser.execute_script("return localStorage.getItem('ebs_token') || '';")


def browser_api(browser, path: str, method: str = "GET", body=None):
    return browser.execute_async_script(
        """
        const [path, method, body, done] = arguments;
        const token = localStorage.getItem('ebs_token') || '';
        fetch('/api' + path, {
          method,
          headers: {'Content-Type':'application/json', ...(token ? {Authorization:'Bearer ' + token} : {})},
          body: body === null ? undefined : JSON.stringify(body)
        }).then(async r => done({status:r.status, payload:await r.json().catch(() => ({}))}))
          .catch(e => done({status:0, payload:{message:e.message}}));
        """,
        path,
        method,
        body,
    )
