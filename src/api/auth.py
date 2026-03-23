"""
認證與授權 — API Key + JWT（支援 Bearer header 和 httpOnly cookie）。
"""

from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone

from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from src.config import get_config

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    """驗證 API Key 或 JWT Bearer token（含 httpOnly cookie fallback）。"""
    config = get_config()

    # 1. X-API-Key header (constant-time comparison)
    if api_key and hmac.compare_digest(api_key, config.api_key):
        return "api_key_authenticated"

    # 2. Bearer token
    token: str | None = None
    if credentials:
        token = credentials.credentials
    # 3. httpOnly cookie fallback
    if not token:
        token = request.cookies.get("access_token")

    if token:
        try:
            jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
            return "jwt_authenticated"
        except JWTError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


def create_jwt_token(subject: str, role: str = "trader") -> str:
    """建立 JWT token。"""
    config = get_config()
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.jwt_expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    encoded: str = jwt.encode(payload, config.jwt_secret, algorithm="HS256")
    return encoded


def verify_jwt(
    request: Request,
    api_key: str | None = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict[str, Any]:
    """驗證 JWT token（Bearer header 或 httpOnly cookie），返回 payload。API Key 視為 admin。"""
    config = get_config()

    # API Key 視為 admin 角色（持有 master key = 最高權限）
    if api_key and hmac.compare_digest(api_key, config.api_key):
        return {"sub": "api_key_user", "role": "admin"}

    token: str | None = None

    # 1. 優先從 Bearer header 取 token
    if credentials:
        token = credentials.credentials
    # 2. 回退到 httpOnly cookie
    if not token:
        token = request.cookies.get("access_token")
    # 3. 皆無 → 401
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    try:
        payload: dict[str, Any] = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def verify_ws_token(token: str) -> dict[str, Any] | None:
    """驗證 WebSocket 連線的 JWT token，返回 payload 或 None。"""
    config = get_config()
    try:
        result: dict[str, Any] = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
        return result
    except JWTError:
        return None


def require_role(required_role: str) -> Callable[..., dict[str, Any]]:
    """角色檢查依賴。"""
    def checker(payload: dict[str, Any] = Depends(verify_jwt)) -> dict[str, Any]:
        role = payload.get("role", "")
        role_hierarchy = {"viewer": 0, "researcher": 1, "trader": 2, "risk_manager": 3, "admin": 4}
        if role_hierarchy.get(role, 0) < role_hierarchy.get(required_role, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {required_role}",
            )
        return payload
    return checker
