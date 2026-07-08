from fastapi.testclient import TestClient

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
