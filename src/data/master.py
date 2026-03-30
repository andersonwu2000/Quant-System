"""Securities Master — unified stock registry stored in SQLite.

Provides:
- Centralized symbol registry (replaces all_tw_stock_ids.txt)
- PIT universe queries via universe_at(date) — avoids survivorship bias
- Industry classification for factor neutralization
- Automatic sync from TWSE/TPEX or local parquet discovery
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import sqlalchemy as sa

from src.data.store import metadata as db_metadata

logger = logging.getLogger(__name__)

# ── Table definition (added to existing quant.db metadata) ───────────

securities_table = sa.Table(
    "securities",
    db_metadata,
    sa.Column("symbol", sa.Text, primary_key=True),       # e.g. "2330.TW"
    sa.Column("bare_id", sa.Text, nullable=False),         # e.g. "2330"
    sa.Column("name", sa.Text, nullable=True),             # e.g. "台積電"
    sa.Column("exchange", sa.Text, nullable=True),         # "TWSE" / "TPEX"
    sa.Column("industry_code", sa.Text, nullable=True),
    sa.Column("industry_name", sa.Text, nullable=True),
    sa.Column("listed_date", sa.Text, nullable=True),      # ISO date
    sa.Column("delisted_date", sa.Text, nullable=True),    # null = active
    sa.Column("status", sa.Text, nullable=False, server_default="active"),
    sa.Column("lot_size", sa.Integer, nullable=False, server_default="1000"),
    sa.Column("last_updated", sa.Text, nullable=False),
)


@dataclass
class Security:
    symbol: str
    bare_id: str
    name: str = ""
    exchange: str = ""
    industry_code: str = ""
    industry_name: str = ""
    listed_date: date | None = None
    delisted_date: date | None = None
    status: str = "active"
    lot_size: int = 1000


class SecuritiesMaster:
    """Unified stock registry backed by SQLite."""

    def __init__(self, engine: sa.Engine):
        self._engine = engine
        # Ensure table exists
        securities_table.create(engine, checkfirst=True)

    def upsert(self, security: Security) -> None:
        """Insert or update a single security."""
        now = datetime.now().isoformat()
        row = {
            "symbol": security.symbol,
            "bare_id": security.bare_id,
            "name": security.name,
            "exchange": security.exchange,
            "industry_code": security.industry_code,
            "industry_name": security.industry_name,
            "listed_date": security.listed_date.isoformat() if security.listed_date else None,
            "delisted_date": security.delisted_date.isoformat() if security.delisted_date else None,
            "status": security.status,
            "lot_size": security.lot_size,
            "last_updated": now,
        }
        with self._engine.begin() as conn:
            existing = conn.execute(
                sa.select(securities_table.c.symbol).where(
                    securities_table.c.symbol == security.symbol
                )
            ).fetchone()
            if existing:
                conn.execute(
                    securities_table.update()
                    .where(securities_table.c.symbol == security.symbol)
                    .values(**row)
                )
            else:
                conn.execute(securities_table.insert().values(**row))

    def upsert_many(self, securities: list[Security]) -> int:
        """Bulk upsert using INSERT OR REPLACE. Returns count of inserted/updated."""
        now = datetime.now().isoformat()
        if not securities:
            return 0
        with self._engine.begin() as conn:
            for sec in securities:
                row = {
                    "symbol": sec.symbol,
                    "bare_id": sec.bare_id,
                    "name": sec.name,
                    "exchange": sec.exchange,
                    "industry_code": sec.industry_code,
                    "industry_name": sec.industry_name,
                    "listed_date": sec.listed_date.isoformat() if sec.listed_date else None,
                    "delisted_date": sec.delisted_date.isoformat() if sec.delisted_date else None,
                    "status": sec.status,
                    "lot_size": sec.lot_size,
                    "last_updated": now,
                }
                conn.execute(
                    sa.text(
                        "INSERT OR REPLACE INTO securities "
                        "(symbol, bare_id, name, exchange, industry_code, industry_name, "
                        "listed_date, delisted_date, status, lot_size, last_updated) "
                        "VALUES (:symbol, :bare_id, :name, :exchange, :industry_code, "
                        ":industry_name, :listed_date, :delisted_date, :status, :lot_size, :last_updated)"
                    ),
                    row,
                )
        return len(securities)

    def get(self, symbol: str) -> Security | None:
        """Get a single security by symbol."""
        with self._engine.connect() as conn:
            row = conn.execute(
                sa.select(securities_table).where(securities_table.c.symbol == symbol)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_security(row)

    def list_active(self) -> list[Security]:
        """List all active securities."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa.select(securities_table).where(securities_table.c.status == "active")
                .order_by(securities_table.c.symbol)
            ).fetchall()
            return [self._row_to_security(r) for r in rows]

    def list_all(self) -> list[Security]:
        """List all securities including delisted."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                sa.select(securities_table).order_by(securities_table.c.symbol)
            ).fetchall()
            return [self._row_to_security(r) for r in rows]

    def universe_at(self, as_of: date) -> list[str]:
        """Get PIT universe — symbols that were active on a given date.

        A symbol is included if:
        - listed_date <= as_of (or listed_date is null)
        - delisted_date is null OR delisted_date > as_of
        """
        with self._engine.connect() as conn:
            q = (
                sa.select(securities_table.c.symbol)
                .where(
                    sa.or_(
                        securities_table.c.listed_date.is_(None),
                        securities_table.c.listed_date <= as_of.isoformat(),
                    )
                )
                .where(
                    sa.or_(
                        securities_table.c.delisted_date.is_(None),
                        securities_table.c.delisted_date > as_of.isoformat(),
                    )
                )
                .order_by(securities_table.c.symbol)
            )
            rows = conn.execute(q).fetchall()
            return [r[0] for r in rows]

    def active_symbols(self) -> list[str]:
        """Quick list of active symbol strings."""
        return [s.symbol for s in self.list_active()]

    def count(self) -> int:
        """Count all securities."""
        with self._engine.connect() as conn:
            result = conn.execute(sa.select(sa.func.count()).select_from(securities_table))
            return result.scalar() or 0

    def sync_from_parquet(self, market_dir: str | None = None) -> int:
        """Discover symbols from existing parquet files and populate the master.

        This is a bootstrap method — creates entries for all symbols found locally.
        Only sets symbol, bare_id, status=active. Other fields remain empty until
        enriched from TWSE/FinMind.
        """
        from src.data.sources.finmind_common import strip_tw_suffix
        from src.data.registry import REGISTRY

        ds = REGISTRY["price"]
        if market_dir is not None:
            search_dirs = [Path(market_dir)]
        else:
            search_dirs = list(ds.source_dirs)

        securities = []
        seen: set[str] = set()
        for market_path in search_dirs:
            if not market_path.exists():
                continue
            for p in sorted(market_path.glob(f"*_{ds.suffix}.parquet")):
                sym = p.stem.replace(f"_{ds.suffix}", "")
                if sym in seen:
                    continue
                seen.add(sym)
                bare = strip_tw_suffix(sym)
                securities.append(Security(symbol=sym, bare_id=bare))

        if not securities:
            return 0

        count = self.upsert_many(securities)
        logger.info("Synced %d securities from parquet files", count)
        return count

    @staticmethod
    def _row_to_security(row: sa.Row) -> Security:
        return Security(
            symbol=row.symbol,
            bare_id=row.bare_id,
            name=row.name or "",
            exchange=row.exchange or "",
            industry_code=row.industry_code or "",
            industry_name=row.industry_name or "",
            listed_date=date.fromisoformat(row.listed_date) if row.listed_date else None,
            delisted_date=date.fromisoformat(row.delisted_date) if row.delisted_date else None,
            status=row.status,
            lot_size=row.lot_size,
        )
