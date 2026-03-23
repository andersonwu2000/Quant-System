"""Portfolio persistence tables: portfolios, position_snapshots, trade_records.

Revision ID: 004
Revises: 003
Create Date: 2026-03-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("cash", sa.Numeric, nullable=False, server_default="10000000"),
        sa.Column("initial_cash", sa.Numeric, nullable=False, server_default="10000000"),
        sa.Column("strategy_name", sa.Text, server_default=""),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )

    op.create_table(
        "position_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "portfolio_id",
            sa.Text,
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric, nullable=False),
        sa.Column("avg_cost", sa.Numeric, nullable=False),
        sa.Column("market_price", sa.Numeric, nullable=False, server_default="0"),
        sa.Column("snapshot_date", sa.Text, nullable=False),
        sa.UniqueConstraint("portfolio_id", "symbol", "snapshot_date"),
    )

    op.create_table(
        "trade_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "portfolio_id",
            sa.Text,
            sa.ForeignKey("portfolios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("side", sa.Text, nullable=False),
        sa.Column("quantity", sa.Numeric, nullable=False),
        sa.Column("price", sa.Numeric, nullable=False),
        sa.Column("commission", sa.Numeric, nullable=False, server_default="0"),
        sa.Column("executed_at", sa.Text, nullable=False),
        sa.Column("source", sa.Text, server_default="system"),
        sa.Column("notes", sa.Text, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("trade_records")
    op.drop_table("position_snapshots")
    op.drop_table("portfolios")
