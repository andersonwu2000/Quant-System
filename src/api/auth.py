"""
認證與授權 — API Key + JWT。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from src.config import get_config

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """驗證 API Key。"""
    config = get_config()
    if not api_key or api_key != config.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return api_key


def create_jwt_token(subject: str, role: str = "trader") -> str:
    """建立 JWT token。"""
    config = get_config()
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.jwt_expire_minutes)
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, config.jwt_secret, algorithm="HS256")


def verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> dict:
    """驗證 JWT token，返回 payload。"""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    config = get_config()
    try:
        payload = jwt.decode(
            credentials.credentials,
            config.jwt_secret,
            algorithms=["HS256"],
        )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )


def require_role(required_role: str):
    """角色檢查依賴。"""
    def checker(payload: dict = Depends(verify_jwt)) -> dict:
        role = payload.get("role", "")
        role_hierarchy = {"viewer": 0, "researcher": 1, "trader": 2, "risk_manager": 3, "admin": 4}
        if role_hierarchy.get(role, 0) < role_hierarchy.get(required_role, 99):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {required_role}",
            )
        return payload
    return checker
