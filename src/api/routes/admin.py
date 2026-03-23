"""Admin API routes — 使用者管理 CRUD（僅 admin 角色）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from src.api.auth import require_role, verify_api_key
from src.api.password import hash_password
from src.api.schemas import (
    CreateUserRequest,
    MessageResponse,
    ResetPasswordRequest,
    UpdateUserRequest,
    UserResponse,
)
from src.data.user_store import get_user_store

router = APIRouter(prefix="/admin", tags=["admin"])


def _to_response(user: dict[str, Any]) -> UserResponse:
    return UserResponse(
        id=user["id"],
        username=user["username"],
        display_name=user["display_name"],
        role=user["role"],
        is_active=bool(user["is_active"]),
        failed_login_count=user["failed_login_count"],
        locked_until=user.get("locked_until"),
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("admin")),
) -> list[UserResponse]:
    """列出所有使用者（不含密碼欄位）。"""
    store = get_user_store()
    return [_to_response(u) for u in store.list_all()]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: CreateUserRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("admin")),
) -> UserResponse:
    """建立使用者。"""
    store = get_user_store()
    pw_hash, pw_salt = hash_password(req.password)
    try:
        user = store.create(
            username=req.username,
            display_name=req.display_name,
            password_hash=pw_hash,
            password_salt=pw_salt,
            role=req.role,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{req.username}' already exists",
        )
    return _to_response(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    req: UpdateUserRequest,
    api_key: str = Depends(verify_api_key),
    payload: dict[str, Any] = Depends(require_role("admin")),
) -> UserResponse:
    """修改使用者角色/啟用狀態/顯示名稱。"""
    store = get_user_store()
    user = store.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    caller = payload.get("sub", "")

    # admin 不能降級自己
    if user["username"] == caller and req.role is not None and req.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot downgrade your own role")

    # admin 不能停用自己
    if user["username"] == caller and req.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    fields: dict[str, Any] = {}
    if req.display_name is not None:
        fields["display_name"] = req.display_name
    if req.role is not None:
        fields["role"] = req.role
    if req.is_active is not None:
        fields["is_active"] = req.is_active

    if not fields:
        return _to_response(user)

    updated = store.update(user_id, **fields)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return _to_response(updated)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    api_key: str = Depends(verify_api_key),
    payload: dict[str, Any] = Depends(require_role("admin")),
) -> MessageResponse:
    """刪除使用者（禁止刪除自己）。"""
    store = get_user_store()
    user = store.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    caller = payload.get("sub", "")
    if user["username"] == caller:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    # 確保至少保留一個 active admin
    if user["role"] == "admin" and user["is_active"] and store.count_active_admins() <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the last active admin")

    store.delete(user_id)
    return MessageResponse(message=f"User '{user['username']}' deleted")


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
async def reset_password(
    user_id: int,
    req: ResetPasswordRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("admin")),
) -> MessageResponse:
    """重設使用者密碼。"""
    store = get_user_store()
    user = store.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    pw_hash, pw_salt = hash_password(req.new_password)
    store.update(user_id, password_hash=pw_hash, password_salt=pw_salt, failed_login_count=0, locked_until=None)
    return MessageResponse(message=f"Password reset for '{user['username']}'")
