"""
數據存取層 — 本地 SQLite 或 PostgreSQL。

開發階段先用 SQLite，生產切 PostgreSQL + TimescaleDB。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from src.domain.models import Trade, Side

logger = logging.getLogger(__name__)

# 開發階段使用 SQLite，避免強制依賴 PostgreSQL
DEFAULT_DB_PATH = Path("data/quant.db")


class DataStore:
    """輕量級數據存取層。"""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """建立資料表。"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS bars (
                    symbol      TEXT NOT NULL,
                    timestamp   TEXT NOT NULL,
                    freq        TEXT NOT NULL DEFAULT '1d',
                    open        REAL NOT NULL,
                    high        REAL NOT NULL,
                    low         REAL NOT NULL,
                    close       REAL NOT NULL,
                    volume      REAL NOT NULL,
                    PRIMARY KEY (symbol, timestamp, freq)
                );

                CREATE TABLE IF NOT EXISTS trades (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id        TEXT NOT NULL,
                    strategy_id     TEXT NOT NULL,
                    symbol          TEXT NOT NULL,
                    side            TEXT NOT NULL,
                    quantity        REAL NOT NULL,
                    price           REAL NOT NULL,
                    commission      REAL NOT NULL,
                    slippage_bps    REAL,
                    executed_at     TEXT NOT NULL,
                    signal_value    REAL
                );

                CREATE TABLE IF NOT EXISTS backtest_results (
                    id              TEXT PRIMARY KEY,
                    strategy_name   TEXT NOT NULL,
                    config          TEXT NOT NULL,
                    started_at      TEXT NOT NULL,
                    finished_at     TEXT,
                    status          TEXT NOT NULL DEFAULT 'running',
                    sharpe          REAL,
                    max_drawdown    REAL,
                    total_return    REAL,
                    annual_return   REAL,
                    detail          TEXT
                );

                CREATE TABLE IF NOT EXISTS risk_events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TEXT NOT NULL,
                    rule_name       TEXT NOT NULL,
                    severity        TEXT NOT NULL,
                    metric_value    REAL,
                    threshold       REAL,
                    action_taken    TEXT NOT NULL,
                    message         TEXT
                );
            """)

    # ─── Bars ────────────────────────────────────────

    def save_bars(self, symbol: str, df: pd.DataFrame, freq: str = "1d") -> int:
        """儲存 K 線數據，返回寫入筆數。"""
        if df.empty:
            return 0

        rows = []
        for ts, row in df.iterrows():
            rows.append((
                symbol,
                str(ts),
                freq,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["volume"]),
            ))

        with self._get_conn() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO bars VALUES (?,?,?,?,?,?,?,?)",
                rows,
            )

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
        query = "SELECT * FROM bars WHERE symbol=? AND freq=?"
        params: list = [symbol, freq]

        if start:
            query += " AND timestamp >= ?"
            params.append(start)
        if end:
            query += " AND timestamp <= ?"
            params.append(end)

        query += " ORDER BY timestamp"

        with self._get_conn() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        if df.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        return df[["open", "high", "low", "close", "volume"]]

    # ─── Trades ──────────────────────────────────────

    def save_trade(self, trade: Trade) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO trades
                   (order_id, strategy_id, symbol, side, quantity, price,
                    commission, slippage_bps, executed_at, signal_value)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    trade.order_id,
                    trade.strategy_id,
                    trade.symbol,
                    trade.side.value,
                    float(trade.quantity),
                    float(trade.price),
                    float(trade.commission),
                    float(trade.slippage_bps),
                    str(trade.timestamp),
                    trade.signal_value,
                ),
            )

    def save_trades(self, trades: list[Trade]) -> None:
        for t in trades:
            self.save_trade(t)

    def load_trades(
        self,
        strategy_id: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        query = "SELECT * FROM trades WHERE 1=1"
        params: list = []

        if strategy_id:
            query += " AND strategy_id=?"
            params.append(strategy_id)
        if start:
            query += " AND executed_at >= ?"
            params.append(start)
        if end:
            query += " AND executed_at <= ?"
            params.append(end)

        query += " ORDER BY executed_at"

        with self._get_conn() as conn:
            return pd.read_sql_query(query, conn, params=params)

    # ─── Backtest Results ────────────────────────────

    def save_backtest_result(
        self,
        result_id: str,
        strategy_name: str,
        config: dict,
        sharpe: float,
        max_drawdown: float,
        total_return: float,
        annual_return: float,
        detail: dict | None = None,
    ) -> None:
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO backtest_results
                   (id, strategy_name, config, started_at, finished_at, status,
                    sharpe, max_drawdown, total_return, annual_return, detail)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    result_id,
                    strategy_name,
                    json.dumps(config),
                    now,
                    now,
                    "completed",
                    sharpe,
                    max_drawdown,
                    total_return,
                    annual_return,
                    json.dumps(detail) if detail else None,
                ),
            )

    # ─── Risk Events ────────────────────────────────

    def save_risk_event(self, alert: "RiskAlert") -> None:
        from src.domain.models import RiskAlert

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO risk_events
                   (timestamp, rule_name, severity, metric_value, threshold,
                    action_taken, message)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    str(alert.timestamp),
                    alert.rule_name,
                    alert.severity.value,
                    alert.metric_value,
                    alert.threshold,
                    alert.action_taken,
                    alert.message,
                ),
            )
