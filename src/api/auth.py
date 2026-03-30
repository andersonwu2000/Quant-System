"""
認證與授權 — API Key + JWT（支援 Bearer header 和 httpOnly cookie）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from typing import Any, Callable

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from src.core.config import get_config

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    """驗證 API Key 或 JWT Bearer token（含 httpOnly cookie fallback）。"""
    config = get_config()

    # 1. X-API-Key header
    if api_key and config.resolve_api_key_role(api_key) is not None:
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
            payload = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
            # 撤銷檢查：token 的 iat 必須 >= user 的 token_valid_after
            username = payload.get("sub", "")
            if username and username != "api_key_user":
                from src.data.user_store import get_user_store
                user = get_user_store().get_by_username(username)
                if user:
                    token_valid_after = user.get("token_valid_after")
                    token_iat = payload.get("iat")
                    if token_valid_after and token_iat:
                        from datetime import datetime
                        valid_after_ts = datetime.fromisoformat(token_valid_after).timestamp()
                        if token_iat < valid_after_ts:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Token has been revoked",
                            )
            return "jwt_authenticated"
        except JWTError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )


def create_jwt_token(subject: str, role: str = "trader") -> str:
    """建立 JWT token（含 iat 供撤銷比對）。"""
    config = get_config()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=config.jwt_expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": expire,
    }
    encoded: str = jwt.encode(payload, config.jwt_secret, algorithm="HS256")
    return encoded


def verify_jwt(
    request: Request,
    api_key: str | None = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict[str, Any]:
    """驗證 JWT token（Bearer header 或 httpOnly cookie），返回 payload。

    DB 即時查詢確保：停用/刪除/角色變更立即生效，token 可被撤銷。
    API Key 不走 DB，角色由 config 決定。
    """
    config = get_config()

    # API Key 直接存取：角色由 config 查詢決定
    if api_key:
        role = config.resolve_api_key_role(api_key)
        if role is not None:
            payload = {"sub": "api_key_user", "role": role}
            request.state.user = payload["sub"]
            return payload

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
        payload = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # ── DB 即時驗證 ──
    subject = payload.get("sub", "")
    if subject and subject != "api_key_user":
        from src.data.user_store import get_user_store
        user = get_user_store().get_by_username(subject)

        if not user or not user["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account disabled or deleted",
            )

        # token 撤銷檢查：token 的 iat 必須 >= user.token_valid_after
        token_valid_after = user.get("token_valid_after")
        token_iat = payload.get("iat")
        if token_valid_after and token_iat:
            valid_after_dt = datetime.fromisoformat(token_valid_after)
            issued_at_dt = datetime.fromtimestamp(float(token_iat), tz=timezone.utc)
            if issued_at_dt < valid_after_dt:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                )

        # 使用 DB 中的即時角色，而非 token 中的快照
        payload["role"] = user["role"]

    request.state.user = payload.get("sub", "anonymous")
    return payload


def verify_ws_token(token: str) -> dict[str, Any] | None:
    """驗證 WebSocket 連線的 JWT token，返回 payload 或 None。

    Includes token revocation check (token_valid_after) consistent with verify_api_key.
    """
    config = get_config()
    try:
        result: dict[str, Any] = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
        # Revocation check: token iat must be >= user's token_valid_after
        username = result.get("sub", "")
        if username and username != "api_key_user":
            from src.data.user_store import get_user_store
            user = get_user_store().get_by_username(username)
            if user:
                token_valid_after = user.get("token_valid_after")
                token_iat = result.get("iat")
                if token_valid_after and token_iat:
                    valid_after_ts = datetime.fromisoformat(token_valid_after).timestamp()
                    if token_iat < valid_after_ts:
                        return None  # Token has been revoked
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
