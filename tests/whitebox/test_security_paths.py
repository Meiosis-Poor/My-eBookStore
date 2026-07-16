from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError

from backend.app import security


pytestmark = [pytest.mark.whitebox, pytest.mark.whitebox_unit]


def credentials(token: str = "token") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_current_user_missing_invalid_and_unknown_paths(monkeypatch) -> None:
    with pytest.raises(HTTPException) as missing:
        security.current_user(None)
    assert missing.value.status_code == 401

    monkeypatch.setattr(security.jwt, "decode", MagicMock(side_effect=JWTError("bad")))
    with pytest.raises(HTTPException) as invalid:
        security.current_user(credentials())
    assert invalid.value.status_code == 401

    monkeypatch.setattr(security.jwt, "decode", lambda *args, **kwargs: {"sub": "7"})
    monkeypatch.setattr(security.user_dao, "get_auth_user_by_id", lambda _: None)
    with pytest.raises(HTTPException) as unknown:
        security.current_user(credentials())
    assert unknown.value.status_code == 401


def test_current_user_banned_and_success_paths(monkeypatch) -> None:
    monkeypatch.setattr(security.jwt, "decode", lambda *args, **kwargs: {"sub": "7"})
    monkeypatch.setattr(security.user_dao, "get_auth_user_by_id", lambda _: {"status": "封禁"})
    with pytest.raises(HTTPException) as banned:
        security.current_user(credentials())
    assert banned.value.status_code == 403

    user = {"user_id": 7, "status": "正常"}
    monkeypatch.setattr(security.user_dao, "get_auth_user_by_id", lambda _: user)
    assert security.current_user(credentials()) is user


def test_optional_user_and_role_condition_paths(monkeypatch) -> None:
    assert security.optional_user(None) is None
    monkeypatch.setattr(security, "current_user", MagicMock(side_effect=HTTPException(status_code=401)))
    assert security.optional_user(credentials()) is None

    dependency = security.require_roles("seller")
    seller = {"user_type": security.ROLE_TO_DB["seller"]}
    assert dependency(seller) is seller
    with pytest.raises(HTTPException) as denied:
        dependency({"user_type": security.ROLE_TO_DB["customer"]})
    assert denied.value.status_code == 403


def test_public_user_optional_store_and_default_paths() -> None:
    base = {"user_id": 1, "user_name": "reader", "user_type": security.ROLE_TO_DB["customer"]}
    public = security.public_user(base)
    assert public["nickname"] == "reader" and public["level"] == 1
    seller = {**base, "user_type": security.ROLE_TO_DB["seller"], "store_id": 2, "store_name": "Store"}
    assert security.public_user(seller)["storeName"] == "Store"
