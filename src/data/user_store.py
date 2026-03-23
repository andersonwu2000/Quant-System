"""使用者資料存取層 — SQLAlchemy Core CRUD。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa

from src.data.store import _create_engine, users_table
from src.config import get_config

logger = logging.getLogger(__name__)

_engine: sa.Engine | None = None


def _get_engine() -> sa.Engine:
    global _engine
    if _engine is None:
        _engine = _create_engine(get_config().database_url)
    return _engine


def _row_to_dict(row: sa.Row[Any]) -> dict[str, Any]:
    return dict(row._mapping)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserStore:
    """使用者 CRUD 操作。"""

    def __init__(self, engine: sa.Engine | None = None) -> None:
        self._engine = engine or _get_engine()

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.select(users_table).where(users_table.c.username == username)
            ).first()
            return _row_to_dict(row) if row else None

    def get_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.select(users_table).where(users_table.c.id == user_id)
            ).first()
            return _row_to_dict(row) if row else None

    def list_all(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa.select(users_table).order_by(users_table.c.id)
            ).fetchall()
            return [_row_to_dict(r) for r in rows]

    def create(
        self,
        username: str,
        display_name: str,
        password_hash: str,
        password_salt: str,
        role: str,
    ) -> dict[str, Any]:
        now = _now_iso()
        with self._engine.begin() as conn:
            result = conn.execute(
                users_table.insert().values(
                    username=username,
                    display_name=display_name,
                    password_hash=password_hash,
                    password_salt=password_salt,
                    role=role,
                    is_active=True,
                    failed_login_count=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            user_id: int = result.inserted_primary_key[0]  # type: ignore[index]
        return self.get_by_id(user_id)  # type: ignore[return-value]

    # 允許透過 update() 修改的欄位白名單
    _UPDATABLE_FIELDS = frozenset({
        "display_name", "role", "is_active",
        "password_hash", "password_salt",
        "failed_login_count", "locked_until",
        "token_valid_after",
    })

    def update(self, user_id: int, **fields: Any) -> dict[str, Any] | None:
        # 過濾不允許的欄位（防止意外修改 id, username, created_at 等）
        safe_fields = {k: v for k, v in fields.items() if k in self._UPDATABLE_FIELDS}
        safe_fields["updated_at"] = _now_iso()
        with self._engine.begin() as conn:
            conn.execute(
                users_table.update().where(users_table.c.id == user_id).values(**safe_fields)
            )
        return self.get_by_id(user_id)

    def delete(self, user_id: int) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                users_table.delete().where(users_table.c.id == user_id)
            )
            return (result.rowcount or 0) > 0

    def increment_failed_login(self, user_id: int) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                users_table.update()
                .where(users_table.c.id == user_id)
                .values(
                    failed_login_count=users_table.c.failed_login_count + 1,
                    updated_at=_now_iso(),
                )
            )

    def reset_failed_login(self, user_id: int) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                users_table.update()
                .where(users_table.c.id == user_id)
                .values(
                    failed_login_count=0,
                    locked_until=None,
                    updated_at=_now_iso(),
                )
            )

    def lock_account(self, user_id: int, until: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                users_table.update()
                .where(users_table.c.id == user_id)
                .values(locked_until=until, updated_at=_now_iso())
            )

    def invalidate_tokens(self, user_id: int) -> None:
        """撤銷該用戶所有已發出的 JWT token。"""
        self.update(user_id, token_valid_after=_now_iso())

    def count_active_admins(self) -> int:
        with self._engine.connect() as conn:
            result = conn.execute(
                sa.select(sa.func.count())
                .select_from(users_table)
                .where(
                    users_table.c.role == "admin",
                    users_table.c.is_active == True,  # noqa: E712
                )
            )
            return result.scalar() or 0


# 全局單例
_user_store: UserStore | None = None


def get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store


def override_user_store(store: UserStore) -> None:
    """測試用：注入自訂 UserStore。"""
    global _user_store
    _user_store = store
