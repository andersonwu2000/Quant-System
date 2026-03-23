"""Add token_valid_after column for JWT revocation.

Revision ID: 003
Revises: 002
Create Date: 2026-03-23
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_valid_after", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "token_valid_after")
