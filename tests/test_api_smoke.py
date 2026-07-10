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
        "/api/books?keyword=test&searchType=title&page=1&pageSize=3",
        "/api/books?keyword=test&searchType=author&page=1&pageSize=3",
        "/api/books?keyword=978&searchType=isbn&page=1&pageSize=3",
        "/api/books/recommended?type=hot&limit=5",
    ):
        response = client.get(path)
        payload = response.json()
        assert response.status_code == 200
        assert payload["code"] == 0
    assert client.get("/api/search/history").json()["data"] == []
    assert client.post("/api/search/history", json={"keyword": "anonymous"}).json()["code"] == 0


def test_search_modes_match_frontend_contract() -> None:
    client = TestClient(app)
    books_payload = client.get("/api/books?page=1&pageSize=10").json()
    books = books_payload["data"]["list"]
    assert books
    book = next(item for item in books if item.get("author") and item.get("isbn"))

    title = client.get("/api/books?keyword=definitely-not-a-title-substring&searchType=title&page=1&pageSize=3").json()
    assert title["code"] == 0
    assert title["data"]["total"] >= len(title["data"]["list"])

    author_keyword = str(book["author"])[:2]
    author = client.get(f"/api/books?keyword={author_keyword}&searchType=author&page=1&pageSize=10").json()
    assert author["code"] == 0
    assert author["data"]["list"]
    assert all(author_keyword in item["author"] for item in author["data"]["list"])

    isbn = str(book["isbn"])
    exact = client.get(f"/api/books?keyword={isbn}&searchType=isbn&page=1&pageSize=10").json()
    assert exact["code"] == 0
    assert exact["data"]["list"]
    assert all(item["isbn"] == isbn for item in exact["data"]["list"])

    partial_isbn = client.get(f"/api/books?keyword={isbn}x&searchType=isbn&page=1&pageSize=10").json()
    assert partial_isbn["code"] == 0
    assert partial_isbn["data"]["total"] == 0


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


def test_search_history_endpoint_keeps_latest_five_history_rows(monkeypatch) -> None:
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
            response = client.post("/api/search/history", json={"keyword": keyword}, headers=headers)
            assert response.status_code == 200
            assert response.json()["code"] == 0

        history = client.get("/api/search/history", headers=headers)
        assert history.status_code == 200
        assert history.json()["data"] == list(reversed(keywords[1:]))

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


def test_seller_create_book_duplicate_isbn_returns_business_error(monkeypatch) -> None:
    monkeypatch.setattr("backend.app.main.embed_text", lambda text: [1.0, float(len(text or ""))])

    client = TestClient(app)
    isbn = f"978-test-{uuid4().hex[:12]}"
    try:
        login = client.post(
            "/api/auth/login",
            json={"userName": "seller_demo", "password": "Demo123", "role": "seller"},
        )
        assert login.status_code == 200
        token = login.json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}
        categories = client.get("/api/categories").json()["data"]
        category_id = categories[0]["categoryId"]
        payload = {
            "bookName": f"ISBN duplicate test {uuid4().hex[:6]}",
            "author": "Test Author",
            "publisher": "Test Publisher",
            "isbn": isbn,
            "categoryId": category_id,
            "price": 10,
            "stock": 2,
            "description": "duplicate isbn test",
        }

        first = client.post("/api/admin/books", json=payload, headers=headers)
        assert first.status_code == 200
        assert first.json()["code"] == 0

        second = client.post("/api/admin/books", json={**payload, "bookName": "Duplicate ISBN"}, headers=headers)
        body = second.json()
        assert second.status_code == 400
        assert body["code"] != 0
        assert "ISBN已存在" in body["message"]
    finally:
        with get_conn() as conn:
            conn.cursor().execute(
                "DELETE FROM book_items WHERE book_info_id IN (SELECT book_info_id FROM book_infos WHERE ISBN = ?)",
                isbn,
            )
            conn.cursor().execute("DELETE FROM book_infos WHERE ISBN = ?", isbn)
