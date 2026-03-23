"""Auth API routes — login / logout via JWT（支援 username+password 和 API Key 雙模登入）。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from src.api.auth import create_jwt_token
from src.api.password import verify_password
from src.config import get_config
from src.data.user_store import get_user_store

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    api_key: str | None = None
    username: str | None = None
    password: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _set_cookie(response: Response, token: str) -> None:
    config = get_config()
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=config.env == "prod",
        max_age=config.jwt_expire_minutes * 60,
    )


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response) -> LoginResponse:
    """雙模登入：username+password 或 API Key。"""
    config = get_config()

    # ── 路徑 A：username + password ──
    if req.username and req.password:
        store = get_user_store()
        user = store.get_by_username(req.username)

        # 統一錯誤訊息，不洩漏帳號是否存在
        if not user or not user["is_active"]:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # 帳號鎖定檢查
        if user.get("locked_until"):
            locked = datetime.fromisoformat(user["locked_until"])
            if datetime.now(timezone.utc) < locked:
                raise HTTPException(status_code=423, detail="Account locked, try again later")
            # 鎖定已過期，重設
            store.reset_failed_login(user["id"])

        # 密碼驗證
        if not verify_password(req.password, user["password_hash"], user["password_salt"]):
            store.increment_failed_login(user["id"])
            new_count = user["failed_login_count"] + 1
            if new_count >= config.max_failed_logins:
                until = (
                    datetime.now(timezone.utc) + timedelta(minutes=config.lockout_minutes)
                ).isoformat()
                store.lock_account(user["id"], until)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # 登入成功
        store.reset_failed_login(user["id"])
        token = create_jwt_token(subject=user["username"], role=user["role"])
        _set_cookie(response, token)
        return LoginResponse(access_token=token)

    # ── 路徑 B：API Key（向後相容） ──
    if req.api_key:
        role = config.resolve_api_key_role(req.api_key)
        if role is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        token = create_jwt_token(subject="api_key_user", role=role)
        _set_cookie(response, token)
        return LoginResponse(access_token=token)

    raise HTTPException(status_code=400, detail="Provide username+password or api_key")


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    """清除 JWT cookie。"""
    response.delete_cookie(key="access_token")
    return {"detail": "Logged out"}
