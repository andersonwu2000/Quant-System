"""Auth API routes — login / logout via JWT."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from src.api.auth import create_jwt_token
from src.config import get_config

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    api_key: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response) -> LoginResponse:
    """驗證 API Key，回傳 JWT（同時設定 httpOnly cookie）。"""
    config = get_config()
    if not hmac.compare_digest(req.api_key, config.api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")

    token = create_jwt_token(subject="api_user", role="trader")

    # httpOnly cookie — 瀏覽器自動帶入，XSS 無法讀取
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=config.env == "prod",
        max_age=config.jwt_expire_minutes * 60,
    )

    return LoginResponse(access_token=token)


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """清除 JWT cookie。"""
    response.delete_cookie(key="access_token")
    return {"detail": "Logged out"}
