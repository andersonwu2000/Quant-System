"""
數據存取層 — SQLAlchemy Core，支援 SQLite（開發）或 PostgreSQL（生產）。

Tables defined here are shared with Alembic migrations via `metadata`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import event

from src.core.models import Trade

if TYPE_CHECKING:
    from src.core.models import RiskAlert

logger = logging.getLogger(__name__)

# ─── Schema ───────────────────────────────────────────────

metadata = sa.MetaData()

bars_table = sa.Table(
    "bars",
    metadata,
    sa.Column("symbol", sa.Text, nullable=False),
    sa.Column("timestamp", sa.Text, nullable=False),
    sa.Column("freq", sa.Text, nullable=False, server_default="1d"),
    sa.Column("open", sa.Numeric, nullable=False),
    sa.Column("high", sa.Numeric, nullable=False),
    sa.Column("low", sa.Numeric, nullable=False),
    sa.Column("close", sa.Numeric, nullable=False),
    sa.Column("volume", sa.Numeric, nullable=False),
    sa.PrimaryKeyConstraint("symbol", "timestamp", "freq"),
)

trades_table = sa.Table(
    "trades",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("order_id", sa.Text, nullable=False),
    sa.Column("strategy_id", sa.Text, nullable=False),
    sa.Column("symbol", sa.Text, nullable=False),
    sa.Column("side", sa.Text, nullable=False),
    sa.Column("quantity", sa.Numeric, nullable=False),
    sa.Column("price", sa.Numeric, nullable=False),
    sa.Column("commission", sa.Numeric, nullable=False),
    sa.Column("slippage_bps", sa.Numeric),
    sa.Column("executed_at", sa.Text, nullable=False),
    sa.Column("signal_value", sa.Numeric),
)

backtest_results_table = sa.Table(
    "backtest_results",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("strategy_name", sa.Text, nullable=False),
    sa.Column("config", sa.Text, nullable=False),
    sa.Column("started_at", sa.Text, nullable=False),
    sa.Column("finished_at", sa.Text),
    sa.Column("status", sa.Text, nullable=False, server_default="running"),
    sa.Column("sharpe", sa.Numeric),
    sa.Column("max_drawdown", sa.Numeric),
    sa.Column("total_return", sa.Numeric),
    sa.Column("annual_return", sa.Numeric),
    sa.Column("detail", sa.Text),
)

risk_events_table = sa.Table(
    "risk_events",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("timestamp", sa.Text, nullable=False),
    sa.Column("rule_name", sa.Text, nullable=False),
    sa.Column("severity", sa.Text, nullable=False),
    sa.Column("metric_value", sa.Numeric),
    sa.Column("threshold", sa.Numeric),
    sa.Column("action_taken", sa.Text, nullable=False),
    sa.Column("message", sa.Text),
)

users_table = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("username", sa.String(64), nullable=False, unique=True),
    sa.Column("display_name", sa.String(128), nullable=False, server_default=""),
    sa.Column("password_hash", sa.String(256), nullable=False),
    sa.Column("password_salt", sa.String(64), nullable=False),
    sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
    sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
    sa.Column("failed_login_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("locked_until", sa.Text, nullable=True),
    sa.Column("token_valid_after", sa.Text, nullable=True),
    sa.Column("created_at", sa.Text, nullable=False),
    sa.Column("updated_at", sa.Text, nullable=False),
)

portfolios_table = sa.Table(
    "portfolios",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("cash", sa.Numeric, nullable=False, server_default="10000000"),
    sa.Column("initial_cash", sa.Numeric, nullable=False, server_default="10000000"),
    sa.Column("strategy_name", sa.Text, server_default=""),
    sa.Column("created_at", sa.Text, nullable=False),
    sa.Column("updated_at", sa.Text, nullable=False),
)

position_snapshots_table = sa.Table(
    "position_snapshots",
    metadata,
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

trade_records_table = sa.Table(
    "trade_records",
    metadata,
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

# ─── Engine helper ────────────────────────────────────────

DEFAULT_DB_PATH = Path("data/quant.db")


def _create_engine(url: str) -> sa.Engine:
    """Create a SQLAlchemy engine. Sets WAL + busy_timeout for SQLite.
    Configures connection pool for PostgreSQL production use."""
    kwargs: dict[str, object] = {}

    # PostgreSQL 連線池配置
    if not url.startswith("sqlite"):
        kwargs.update(
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,  # 30 分鐘回收連線，避免斷線
            pool_pre_ping=True,  # 使用前 ping 偵測死連線
        )

    engine = sa.create_engine(url, **kwargs)

    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn: object, connection_record: object) -> None:
            cursor = dbapi_conn.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


# ─── DataStore ────────────────────────────────────────────


class DataStore:
    """數據存取層 — SQLAlchemy Core。"""

    def __init__(self, db_path: str | Path | None = None, url: str | None = None):
        if url:
            self._engine = _create_engine(url)
        else:
            path = Path(db_path) if db_path else DEFAULT_DB_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            self._engine = _create_engine(f"sqlite:///{path}")

        metadata.create_all(self._engine)

    # ─── Bars ────────────────────────────────────────

    def save_bars(self, symbol: str, df: pd.DataFrame, freq: str = "1d") -> int:
        """儲存 K 線數據，返回寫入筆數。"""
        if df.empty:
            return 0

        rows = []
        for ts, row in df.iterrows():
            rows.append({
                "symbol": symbol,
                "timestamp": str(ts),
                "freq": freq,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })

        with self._engine.begin() as conn:
            if self._engine.dialect.name == "sqlite":
                conn.execute(
                    sa.text(
                        "INSERT OR REPLACE INTO bars (symbol, timestamp, freq, "
                        '"open", high, low, close, volume) '
                        "VALUES (:symbol, :timestamp, :freq, :open, :high, :low, :close, :volume)"
                    ),
                    rows,
                )
            else:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                pg_stmt = pg_insert(bars_table).values(rows)
                pg_stmt = pg_stmt.on_conflict_do_update(
                    constraint=bars_table.primary_key,
                    set_={
                        "open": pg_stmt.excluded.open,
                        "high": pg_stmt.excluded.high,
                        "low": pg_stmt.excluded.low,
                        "close": pg_stmt.excluded.close,
                        "volume": pg_stmt.excluded.volume,
                    },
                )
                conn.execute(pg_stmt)

        logger.info("Saved %d bars for %s", len(rows), symbol)
        return len(rows)

    def load_bars(
        self,
        symbol: str,
        start: str | None = None,
        end: str | None = None,
        freq: str = "1d",
    ) -> pd.DataFrame:
        """從 DB 載入 K 線。"""
        t = bars_table
        stmt = t.select().where(t.c.symbol == symbol, t.c.freq == freq)

        if start:
            stmt = stmt.where(t.c.timestamp >= start)
        if end:
            stmt = stmt.where(t.c.timestamp <= end)

        stmt = stmt.order_by(t.c.timestamp)

        with self._engine.connect() as conn:
            df = pd.read_sql_query(stmt, conn)

        if df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        return df[["open", "high", "low", "close", "volume"]]

    # ─── Trades ──────────────────────────────────────

    def save_trade(self, trade: Trade) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                trades_table.insert().values(
                    order_id=trade.order_id,
                    strategy_id=trade.strategy_id,
                    symbol=trade.symbol,
                    side=trade.side.value,
                    quantity=float(trade.quantity),
                    price=float(trade.price),
                    commission=float(trade.commission),
                    slippage_bps=float(trade.slippage_bps),
                    executed_at=str(trade.timestamp),
                    signal_value=trade.signal_value,
                )
            )

    def save_trades(self, trades: list[Trade]) -> None:
        if not trades:
            return
        rows = [
            {
                "order_id": t.order_id,
                "strategy_id": t.strategy_id,
                "symbol": t.symbol,
                "side": t.side.value,
                "quantity": float(t.quantity),
                "price": float(t.price),
                "commission": float(t.commission),
                "slippage_bps": float(t.slippage_bps),
                "executed_at": str(t.timestamp),
                "signal_value": t.signal_value,
            }
            for t in trades
        ]
        with self._engine.begin() as conn:
            conn.execute(trades_table.insert(), rows)

    def load_trades(
        self,
        strategy_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        t = trades_table
        stmt = t.select()

        if strategy_id:
            stmt = stmt.where(t.c.strategy_id == strategy_id)
        if start:
            stmt = stmt.where(t.c.executed_at >= start)
        if end:
            stmt = stmt.where(t.c.executed_at <= end)

        stmt = stmt.order_by(t.c.executed_at)

        with self._engine.connect() as conn:
            return pd.read_sql_query(stmt, conn)

    # ─── Backtest Results ────────────────────────────

    def save_backtest_result(
        self,
        result_id: str,
        strategy_name: str,
        config: dict[str, object],
        sharpe: float,
        max_drawdown: float,
        total_return: float,
        annual_return: float,
        detail: dict[str, object] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "id": result_id,
            "strategy_name": strategy_name,
            "config": json.dumps(config),
            "started_at": now,
            "finished_at": now,
            "status": "completed",
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "total_return": total_return,
            "annual_return": annual_return,
            "detail": json.dumps(detail) if detail else None,
        }

        dialect = self._engine.dialect.name
        with self._engine.begin() as conn:
            if dialect == "sqlite":
                conn.execute(
                    sa.text(
                        "INSERT OR REPLACE INTO backtest_results "
                        "(id, strategy_name, config, started_at, finished_at, status, "
                        "sharpe, max_drawdown, total_return, annual_return, detail) "
                        "VALUES (:id, :strategy_name, :config, :started_at, :finished_at, "
                        ":status, :sharpe, :max_drawdown, :total_return, :annual_return, :detail)"
                    ),
                    row,
                )
            else:
                from sqlalchemy.dialects.postgresql import insert as pg_insert
                pg_stmt = pg_insert(backtest_results_table).values(**row)
                pg_stmt = pg_stmt.on_conflict_do_update(
                    constraint=backtest_results_table.primary_key,
                    set_={k: v for k, v in row.items() if k != "id"},
                )
                conn.execute(pg_stmt)

    def load_backtest_history(
        self,
        strategy_name: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """載入回測歷史記錄。"""
        t = backtest_results_table
        stmt = t.select().where(t.c.status == "completed")

        if strategy_name:
            stmt = stmt.where(t.c.strategy_name == strategy_name)

        stmt = stmt.order_by(t.c.finished_at.desc()).limit(limit)

        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()

        return [
            {
                "id": r["id"],
                "strategy_name": r["strategy_name"],
                "config": json.loads(r["config"]) if r["config"] else {},
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "sharpe": float(r["sharpe"]) if r["sharpe"] is not None else None,
                "max_drawdown": float(r["max_drawdown"]) if r["max_drawdown"] is not None else None,
                "total_return": float(r["total_return"]) if r["total_return"] is not None else None,
                "annual_return": float(r["annual_return"]) if r["annual_return"] is not None else None,
            }
            for r in rows
        ]

    # ─── Risk Events ────────────────────────────────

    def save_risk_event(self, alert: RiskAlert) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                risk_events_table.insert().values(
                    timestamp=str(alert.timestamp),
                    rule_name=alert.rule_name,
                    severity=alert.severity.value,
                    metric_value=alert.metric_value,
                    threshold=alert.threshold,
                    action_taken=alert.action_taken,
                    message=alert.message,
                )
            )
