from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db import get_conn
from backend.app.main import app


def test_public_books_and_recommendations() -> None:
    client = TestClient(app)
    for path in (
        "/api/health",
        "/api/categories",
        "/api/books?page=1&pageSize=3",
        "/api/books/recommended?type=hot&limit=5",
    ):
        response = client.get(path)
        payload = response.json()
        assert response.status_code == 200
        assert payload["code"] == 0


def test_demo_user_can_login_after_seed() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"userName": "reader_demo", "password": "Demo123", "role": "customer"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["code"] == 0
    assert payload["data"]["user"]["userName"] == "reader_demo"


def test_authenticated_search_keeps_latest_five_history_rows(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.main.embed_text", lambda text: [1.0, float(len(text or ""))])

    client = TestClient(app)
    user_name = f"search_{uuid4().hex[:10]}"
    password = "Demo123"
    user_id = None
    try:
        register = client.post(
            "/api/auth/register/user",
            json={"userName": user_name, "password": password, "nickname": user_name},
        )
        assert register.status_code == 200
        assert register.json()["code"] == 0
        user_id = register.json()["data"]["userId"]

        login = client.post(
            "/api/auth/login",
            json={"userName": user_name, "password": password, "role": "customer"},
        )
        token = login.json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        keywords = [f"history-keyword-{idx}" for idx in range(6)]
        for keyword in keywords:
            response = client.get(f"/api/books?keyword={keyword}&page=1&pageSize=3", headers=headers)
            assert response.status_code == 200
            assert response.json()["code"] == 0

        with get_conn() as conn:
            rows = conn.cursor().execute(
                """
                SELECT keyword, keyword_embedding
                FROM search_history
                WHERE user_id = ?
                ORDER BY created_time DESC, search_id DESC
                """,
                user_id,
            ).fetchall()

        assert len(rows) == 5
        assert all(row.keyword_embedding for row in rows)
        assert "history-keyword-0" not in {row.keyword for row in rows}
    finally:
        if user_id is not None:
            with get_conn() as conn:
                conn.cursor().execute("DELETE FROM search_history WHERE user_id = ?", user_id)
                conn.cursor().execute("DELETE FROM ordinary_users WHERE user_id = ?", user_id)
                conn.cursor().execute("DELETE FROM users WHERE user_id = ?", user_id)
