from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402


def main() -> None:
    client = TestClient(app)
    paths = [
        "/api/health",
        "/api/categories",
        "/api/books?page=1&pageSize=3",
        "/api/books?keyword=python&page=1&pageSize=3",
        "/api/books/recommended?type=hot&limit=5",
    ]
    for path in paths:
        res = client.get(path)
        payload = res.json()
        data = payload.get("data")
        if isinstance(data, dict) and "list" in data:
            size = len(data["list"])
        elif isinstance(data, list):
            size = len(data)
        else:
            size = 1 if data is not None else 0
        print(f"{path} -> status={res.status_code} code={payload.get('code')} size={size}")
        assert res.status_code == 200
        assert payload.get("code") == 0

    res = client.post(
        "/api/auth/login",
        json={"userName": "reader_demo", "password": "Demo123", "role": "customer"},
    )
    payload = res.json()
    print(f"login reader_demo -> status={res.status_code} code={payload.get('code')}")
    assert res.status_code == 200
    assert payload.get("code") == 0
    assert payload["data"]["user"]["userName"] == "reader_demo"


if __name__ == "__main__":
    main()
