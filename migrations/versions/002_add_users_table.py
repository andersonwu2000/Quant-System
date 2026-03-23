"""Add users table for account-based authentication.

Revision ID: 002
Revises: 001
Create Date: 2026-03-23
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("password_salt", sa.String(64), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("failed_login_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("locked_until", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Insert default admin account (password: "admin", should be changed on first login)
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", b"admin", bytes.fromhex(salt), 600_000).hex()
    now = datetime.now(timezone.utc).isoformat()
    op.execute(
        sa.text(
            "INSERT INTO users (username, display_name, password_hash, password_salt, "
            "role, is_active, failed_login_count, created_at, updated_at) "
            "VALUES (:u, :d, :h, :s, :r, 1, 0, :t, :t)"
        ).bindparams(
            u="admin", d="Administrator", h=pw_hash, s=salt, r="admin", t=now,
        )
    )


def downgrade() -> None:
    op.drop_table("users")
