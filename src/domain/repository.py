"""Portfolio repository — CRUD for portfolios, positions, and trades."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import sqlalchemy as sa

from src.domain.models import Instrument, Portfolio, Position, Trade


class PortfolioRepository:
    """Persistence layer for portfolios, position snapshots, and trade records."""

    def __init__(self, engine: sa.Engine):
        self._engine = engine

    # ─── Create ──────────────────────────────────────────

    def create(self, name: str, initial_cash: Decimal, strategy_name: str = "") -> str:
        """Create a new portfolio. Returns portfolio ID."""
        portfolio_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO portfolios (id, name, cash, initial_cash, strategy_name, created_at, updated_at) "
                    "VALUES (:id, :name, :cash, :initial_cash, :strategy_name, :created_at, :updated_at)"
                ),
                {
                    "id": portfolio_id,
                    "name": name,
                    "cash": str(initial_cash),
                    "initial_cash": str(initial_cash),
                    "strategy_name": strategy_name,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        return portfolio_id

    # ─── Read ────────────────────────────────────────────

    def get(self, portfolio_id: str) -> Portfolio | None:
        """Load portfolio with all positions from latest snapshot."""
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT * FROM portfolios WHERE id = :id"),
                {"id": portfolio_id},
            ).mappings().first()

            if row is None:
                return None

            # Find the latest snapshot date for this portfolio
            latest = conn.execute(
                sa.text(
                    "SELECT MAX(snapshot_date) AS latest_date "
                    "FROM position_snapshots WHERE portfolio_id = :pid"
                ),
                {"pid": portfolio_id},
            ).mappings().first()

            positions: dict[str, Position] = {}
            if latest and latest["latest_date"]:
                snap_rows = conn.execute(
                    sa.text(
                        "SELECT symbol, quantity, avg_cost, market_price "
                        "FROM position_snapshots "
                        "WHERE portfolio_id = :pid AND snapshot_date = :sd"
                    ),
                    {"pid": portfolio_id, "sd": latest["latest_date"]},
                ).mappings().all()

                for sr in snap_rows:
                    symbol = sr["symbol"]
                    positions[symbol] = Position(
                        instrument=Instrument(symbol=symbol),
                        quantity=Decimal(str(sr["quantity"])),
                        avg_cost=Decimal(str(sr["avg_cost"])),
                        market_price=Decimal(str(sr["market_price"])),
                    )

            portfolio = Portfolio(
                positions=positions,
                cash=Decimal(str(row["cash"])),
                initial_cash=Decimal(str(row["initial_cash"])),
            )
            return portfolio

    def get_meta(self, portfolio_id: str) -> dict[str, Any] | None:
        """Load portfolio metadata (without building Portfolio object)."""
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.text("SELECT * FROM portfolios WHERE id = :id"),
                {"id": portfolio_id},
            ).mappings().first()
            if row is None:
                return None
            return dict(row)

    def list_all(self) -> list[dict[str, Any]]:
        """List all portfolios (summary: id, name, cash, position_count)."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT p.id, p.name, p.cash, p.initial_cash, p.strategy_name, "
                    "p.created_at, p.updated_at, "
                    "COALESCE(pc.cnt, 0) AS position_count "
                    "FROM portfolios p "
                    "LEFT JOIN ("
                    "  SELECT ps.portfolio_id, COUNT(*) AS cnt "
                    "  FROM position_snapshots ps "
                    "  INNER JOIN ("
                    "    SELECT portfolio_id, MAX(snapshot_date) AS max_date "
                    "    FROM position_snapshots GROUP BY portfolio_id"
                    "  ) latest ON ps.portfolio_id = latest.portfolio_id "
                    "    AND ps.snapshot_date = latest.max_date "
                    "  GROUP BY ps.portfolio_id"
                    ") pc ON p.id = pc.portfolio_id "
                    "ORDER BY p.created_at DESC"
                )
            ).mappings().all()

            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "cash": float(r["cash"]),
                    "initial_cash": float(r["initial_cash"]),
                    "strategy_name": r["strategy_name"] or "",
                    "position_count": r["position_count"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]

    # ─── Update ──────────────────────────────────────────

    def save_snapshot(self, portfolio_id: str, portfolio: Portfolio) -> None:
        """Save current positions as a snapshot (upsert by portfolio_id + symbol + date)."""
        today = date.today().isoformat()
        now = datetime.now(timezone.utc).isoformat()
        dialect = self._engine.dialect.name

        with self._engine.begin() as conn:
            # Update cash and updated_at
            conn.execute(
                sa.text(
                    "UPDATE portfolios SET cash = :cash, updated_at = :updated_at "
                    "WHERE id = :id"
                ),
                {"cash": str(portfolio.cash), "updated_at": now, "id": portfolio_id},
            )

            for symbol, pos in portfolio.positions.items():
                if dialect == "sqlite":
                    conn.execute(
                        sa.text(
                            "INSERT OR REPLACE INTO position_snapshots "
                            "(portfolio_id, symbol, quantity, avg_cost, market_price, snapshot_date) "
                            "VALUES (:pid, :symbol, :quantity, :avg_cost, :market_price, :snapshot_date)"
                        ),
                        {
                            "pid": portfolio_id,
                            "symbol": symbol,
                            "quantity": str(pos.quantity),
                            "avg_cost": str(pos.avg_cost),
                            "market_price": str(pos.market_price),
                            "snapshot_date": today,
                        },
                    )
                else:
                    from sqlalchemy.dialects.postgresql import insert as pg_insert
                    from src.data.store import position_snapshots_table

                    pg_stmt = pg_insert(position_snapshots_table).values(
                        portfolio_id=portfolio_id,
                        symbol=symbol,
                        quantity=str(pos.quantity),
                        avg_cost=str(pos.avg_cost),
                        market_price=str(pos.market_price),
                        snapshot_date=today,
                    )
                    pg_stmt = pg_stmt.on_conflict_do_update(
                        constraint="position_snapshots_portfolio_id_symbol_snapshot_date_key",
                        set_={
                            "quantity": pg_stmt.excluded.quantity,
                            "avg_cost": pg_stmt.excluded.avg_cost,
                            "market_price": pg_stmt.excluded.market_price,
                        },
                    )
                    conn.execute(pg_stmt)

    def update_cash(self, portfolio_id: str, cash: Decimal) -> None:
        """Update portfolio cash balance."""
        now = datetime.now(timezone.utc).isoformat()
        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE portfolios SET cash = :cash, updated_at = :updated_at "
                    "WHERE id = :id"
                ),
                {"cash": str(cash), "updated_at": now, "id": portfolio_id},
            )

    # ─── Delete ──────────────────────────────────────────

    def delete(self, portfolio_id: str) -> bool:
        """Delete portfolio and all related data. Returns True if found."""
        with self._engine.begin() as conn:
            # Delete cascading records first (for SQLite without FK enforcement)
            conn.execute(
                sa.text("DELETE FROM trade_records WHERE portfolio_id = :pid"),
                {"pid": portfolio_id},
            )
            conn.execute(
                sa.text("DELETE FROM position_snapshots WHERE portfolio_id = :pid"),
                {"pid": portfolio_id},
            )
            result = conn.execute(
                sa.text("DELETE FROM portfolios WHERE id = :id"),
                {"id": portfolio_id},
            )
            return result.rowcount > 0

    # ─── Trade Records ───────────────────────────────────

    def record_trade(
        self,
        portfolio_id: str,
        trade: Trade,
        source: str = "system",
        notes: str = "",
    ) -> None:
        """Record a trade execution."""
        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    "INSERT INTO trade_records "
                    "(portfolio_id, symbol, side, quantity, price, commission, executed_at, source, notes) "
                    "VALUES (:pid, :symbol, :side, :quantity, :price, :commission, :executed_at, :source, :notes)"
                ),
                {
                    "pid": portfolio_id,
                    "symbol": trade.symbol,
                    "side": trade.side.value,
                    "quantity": str(trade.quantity),
                    "price": str(trade.price),
                    "commission": str(trade.commission),
                    "executed_at": str(trade.timestamp),
                    "source": source,
                    "notes": notes,
                },
            )

    def get_trades(
        self,
        portfolio_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get trade history for a portfolio."""
        query = "SELECT * FROM trade_records WHERE portfolio_id = :pid"
        params: dict[str, str] = {"pid": portfolio_id}

        if start:
            query += " AND executed_at >= :start"
            params["start"] = start
        if end:
            query += " AND executed_at <= :end"
            params["end"] = end

        query += " ORDER BY executed_at DESC"

        with self._engine.connect() as conn:
            rows = conn.execute(sa.text(query), params).mappings().all()

        return [
            {
                "id": r["id"],
                "symbol": r["symbol"],
                "side": r["side"],
                "quantity": float(r["quantity"]),
                "price": float(r["price"]),
                "commission": float(r["commission"]),
                "executed_at": r["executed_at"],
                "source": r["source"] or "system",
                "notes": r["notes"] or "",
            }
            for r in rows
        ]
