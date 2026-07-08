from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings
from .db import get_conn, one
from .response import fail


ROLE_TO_DB = {
    "customer": "普通用户",
    "seller": "书店管理员",
    "platform_admin": "系统管理员",
}
DB_TO_ROLE = {value: key for key, value in ROLE_TO_DB.items()}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user: dict[str, Any]) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user["user_id"]),
        "role": DB_TO_ROLE.get(user["user_type"], "customer"),
        "exp": expires,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> dict[str, Any]:
    if credentials is None:
        fail("请先登录", 401)
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        fail("登录状态已失效，请重新登录", 401)

    with get_conn() as conn:
        cur = conn.cursor().execute(
            """
            SELECT u.*, ou.nickname, ou.level, ou.total_points, ou.available_points, ou.continuous_checkin_days,
                   s.store_id, s.store_name
            FROM users u
            LEFT JOIN ordinary_users ou ON ou.user_id = u.user_id
            LEFT JOIN stores s ON s.user_id = u.user_id
            WHERE u.user_id = ?
            """,
            user_id,
        )
        user = one(cur)
    if not user:
        fail("用户不存在", 401)
    if user["status"] == "封禁":
        fail("当前账号已被禁用，请联系管理员", 403)
    return user


def optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> Optional[dict[str, Any]]:
    if credentials is None:
        return None
    try:
        return current_user(credentials)
    except Exception:
        return None


def require_roles(*roles: str):
    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        role = DB_TO_ROLE.get(user["user_type"])
        if role not in roles:
            fail("无权限执行此操作", 403)
        return user

    return dependency


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    role = DB_TO_ROLE.get(user["user_type"], "customer")
    data = {
        "userId": user["user_id"],
        "userName": user["user_name"],
        "userType": role,
        "nickname": user.get("nickname") or user["user_name"],
        "phone": user.get("phone"),
        "email": user.get("email"),
        "level": user.get("level") or 1,
        "totalPoints": user.get("total_points") or 0,
        "availablePoints": user.get("available_points") or 0,
        "continuousCheckinDays": user.get("continuous_checkin_days") or 0,
    }
    if user.get("store_id"):
        data["storeId"] = user["store_id"]
        data["storeName"] = user["store_name"]
    return data
