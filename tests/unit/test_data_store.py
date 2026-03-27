"""
Tests for src/data/store.py — Data persistence layer (SQLAlchemy Core).

All tests use SQLite in-memory databases.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import pytest
import sqlalchemy as sa

from src.core.models import RiskAlert, Severity, Side, Trade
from src.data.store import (
    DataStore,
    _create_engine,
    portfolios_table,
    risk_events_table,
    users_table,
)


# ─── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def store() -> DataStore:
    """Create a DataStore backed by in-memory SQLite."""
    return DataStore(url="sqlite:///:memory:")


@pytest.fixture
def sample_bars_df() -> pd.DataFrame:
    """Sample OHLCV DataFrame."""
    dates = pd.date_range("2024-01-02", periods=3, freq="B")
    return pd.DataFrame(
        {
            "open": [100.0, 102.0, 101.0],
            "high": [105.0, 106.0, 104.0],
            "low": [99.0, 101.0, 100.0],
            "close": [103.0, 104.0, 102.0],
            "volume": [1000.0, 1200.0, 900.0],
        },
        index=dates,
    )


@pytest.fixture
def sample_trade() -> Trade:
    return Trade(
        timestamp=datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc),
        symbol="2330.TW",
        side=Side.BUY,
        quantity=Decimal("100"),
        price=Decimal("500"),
        commission=Decimal("71"),
        slippage_bps=Decimal("5"),
        strategy_id="momentum_v1",
        order_id="ord-abc",
        signal_value=0.85,
    )


# ─── Engine creation ──────────────────────────────────────


class TestCreateEngine:
    def test_sqlite_engine(self):
        engine = _create_engine("sqlite:///:memory:")
        assert engine.dialect.name == "sqlite"
        engine.dispose()

    def test_tables_created_on_init(self, store):
        """DataStore.__init__ calls metadata.create_all."""
        insp = sa.inspect(store._engine)
        tables = insp.get_table_names()
        assert "bars" in tables
        assert "trades" in tables
        assert "backtest_results" in tables
        assert "risk_events" in tables
        assert "users" in tables
        assert "portfolios" in tables
        assert "position_snapshots" in tables
        assert "trade_records" in tables


# ─── Bars ─────────────────────────────────────────────────


class TestBars:
    def test_save_bars_returns_count(self, store, sample_bars_df):
        count = store.save_bars("AAPL", sample_bars_df)
        assert count == 3

    def test_save_and_load_bars(self, store, sample_bars_df):
        store.save_bars("AAPL", sample_bars_df)
        loaded = store.load_bars("AAPL")
        assert len(loaded) == 3
        assert list(loaded.columns) == ["open", "high", "low", "close", "volume"]

    def test_load_bars_empty_symbol(self, store):
        loaded = store.load_bars("NONEXISTENT")
        assert loaded.empty
        assert list(loaded.columns) == ["open", "high", "low", "close", "volume"]

    def test_save_empty_dataframe(self, store):
        df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        count = store.save_bars("AAPL", df)
        assert count == 0

    def test_load_bars_with_date_filter(self, store, sample_bars_df):
        store.save_bars("AAPL", sample_bars_df)
        loaded = store.load_bars("AAPL", start="2024-01-03")
        assert len(loaded) == 2

    def test_load_bars_with_end_filter(self, store, sample_bars_df):
        store.save_bars("AAPL", sample_bars_df)
        # Timestamps stored as full datetime strings; end must cover the date
        loaded = store.load_bars("AAPL", end="2024-01-03 23:59:59")
        assert len(loaded) == 2

    def test_upsert_bars(self, store, sample_bars_df):
        """Saving same bars twice should replace, not duplicate."""
        store.save_bars("AAPL", sample_bars_df)
        store.save_bars("AAPL", sample_bars_df)
        loaded = store.load_bars("AAPL")
        assert len(loaded) == 3

    def test_save_bars_different_freq(self, store, sample_bars_df):
        store.save_bars("AAPL", sample_bars_df, freq="1d")
        store.save_bars("AAPL", sample_bars_df, freq="1h")
        daily = store.load_bars("AAPL", freq="1d")
        hourly = store.load_bars("AAPL", freq="1h")
        assert len(daily) == 3
        assert len(hourly) == 3

    def test_different_symbols_isolated(self, store, sample_bars_df):
        store.save_bars("AAPL", sample_bars_df)
        store.save_bars("MSFT", sample_bars_df)
        assert len(store.load_bars("AAPL")) == 3
        assert len(store.load_bars("MSFT")) == 3


# ─── Trades ───────────────────────────────────────────────


class TestTrades:
    def test_save_and_load_trade(self, store, sample_trade):
        store.save_trade(sample_trade)
        loaded = store.load_trades()
        assert len(loaded) == 1
        assert loaded.iloc[0]["symbol"] == "2330.TW"
        assert loaded.iloc[0]["side"] == "BUY"

    def test_save_trades_batch(self, store, sample_trade):
        t2 = Trade(
            timestamp=datetime(2024, 6, 15, 11, 0, 0, tzinfo=timezone.utc),
            symbol="2317.TW",
            side=Side.SELL,
            quantity=Decimal("50"),
            price=Decimal("120"),
            commission=Decimal("9"),
            slippage_bps=Decimal("3"),
            strategy_id="momentum_v1",
            order_id="ord-def",
        )
        store.save_trades([sample_trade, t2])
        loaded = store.load_trades()
        assert len(loaded) == 2

    def test_save_trades_empty_list(self, store):
        store.save_trades([])
        loaded = store.load_trades()
        assert len(loaded) == 0

    def test_load_trades_filter_by_strategy(self, store, sample_trade):
        t2 = Trade(
            timestamp=datetime(2024, 6, 15, 11, 0, 0, tzinfo=timezone.utc),
            symbol="2317.TW",
            side=Side.BUY,
            quantity=Decimal("50"),
            price=Decimal("120"),
            commission=Decimal("9"),
            slippage_bps=Decimal("3"),
            strategy_id="other_strategy",
            order_id="ord-xyz",
        )
        store.save_trade(sample_trade)
        store.save_trade(t2)
        loaded = store.load_trades(strategy_id="momentum_v1")
        assert len(loaded) == 1
        assert loaded.iloc[0]["strategy_id"] == "momentum_v1"

    def test_load_trades_filter_by_date_range(self, store, sample_trade):
        store.save_trade(sample_trade)
        loaded = store.load_trades(start="2024-06-15", end="2024-06-16")
        assert len(loaded) == 1

    def test_load_trades_no_results(self, store, sample_trade):
        store.save_trade(sample_trade)
        loaded = store.load_trades(start="2025-01-01")
        assert len(loaded) == 0


# ─── Backtest Results ─────────────────────────────────────


class TestBacktestResults:
    def test_save_and_load(self, store):
        store.save_backtest_result(
            result_id="bt-001",
            strategy_name="momentum",
            config={"lookback": 20},
            sharpe=1.5,
            max_drawdown=-0.12,
            total_return=0.35,
            annual_return=0.18,
        )
        results = store.load_backtest_history()
        assert len(results) == 1
        r = results[0]
        assert r["id"] == "bt-001"
        assert r["strategy_name"] == "momentum"
        assert r["sharpe"] == 1.5
        assert r["max_drawdown"] == -0.12

    def test_config_stored_as_json(self, store):
        cfg = {"lookback": 20, "universe": ["AAPL", "MSFT"]}
        store.save_backtest_result(
            result_id="bt-002",
            strategy_name="test",
            config=cfg,
            sharpe=1.0,
            max_drawdown=-0.1,
            total_return=0.2,
            annual_return=0.1,
        )
        results = store.load_backtest_history()
        assert results[0]["config"] == cfg

    def test_upsert_backtest_result(self, store):
        """Saving with same ID replaces the record."""
        store.save_backtest_result(
            result_id="bt-dup",
            strategy_name="v1",
            config={},
            sharpe=1.0,
            max_drawdown=-0.1,
            total_return=0.2,
            annual_return=0.1,
        )
        store.save_backtest_result(
            result_id="bt-dup",
            strategy_name="v2",
            config={},
            sharpe=2.0,
            max_drawdown=-0.05,
            total_return=0.4,
            annual_return=0.2,
        )
        results = store.load_backtest_history()
        assert len(results) == 1
        assert results[0]["sharpe"] == 2.0

    def test_load_filter_by_strategy(self, store):
        store.save_backtest_result("bt-a", "momentum", {}, 1.0, -0.1, 0.2, 0.1)
        store.save_backtest_result("bt-b", "mean_rev", {}, 0.8, -0.15, 0.15, 0.08)
        results = store.load_backtest_history(strategy_name="momentum")
        assert len(results) == 1
        assert results[0]["strategy_name"] == "momentum"

    def test_load_with_limit(self, store):
        for i in range(5):
            store.save_backtest_result(
                f"bt-{i}", "test", {}, 1.0, -0.1, 0.2, 0.1
            )
        results = store.load_backtest_history(limit=3)
        assert len(results) == 3

    def test_detail_field(self, store):
        detail = {"trades": 50, "win_rate": 0.6}
        store.save_backtest_result(
            "bt-detail", "test", {}, 1.0, -0.1, 0.2, 0.1, detail=detail
        )
        # detail is not returned by load_backtest_history but should not error
        results = store.load_backtest_history()
        assert len(results) == 1

    def test_empty_history(self, store):
        results = store.load_backtest_history()
        assert results == []


# ─── Risk Events ──────────────────────────────────────────


class TestRiskEvents:
    def test_save_risk_event(self, store):
        alert = RiskAlert(
            timestamp=datetime(2024, 6, 15, tzinfo=timezone.utc),
            rule_name="max_drawdown",
            severity=Severity.WARNING,
            metric_value=-0.08,
            threshold=-0.10,
            action_taken="alert_only",
            message="Drawdown approaching limit",
        )
        store.save_risk_event(alert)
        # Verify via raw SQL
        with store._engine.connect() as conn:
            rows = conn.execute(sa.select(risk_events_table)).fetchall()
        assert len(rows) == 1
        assert rows[0].rule_name == "max_drawdown"
        assert rows[0].severity == "WARNING"


# ─── Users table schema ──────────────────────────────────


class TestUsersTable:
    def test_insert_and_query_user(self, store):
        now = datetime.now(timezone.utc).isoformat()
        with store._engine.begin() as conn:
            conn.execute(
                users_table.insert().values(
                    username="testuser",
                    display_name="Test User",
                    password_hash="hash123",
                    password_salt="salt123",
                    role="admin",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        with store._engine.connect() as conn:
            row = conn.execute(
                users_table.select().where(users_table.c.username == "testuser")
            ).fetchone()
        assert row is not None
        assert row.display_name == "Test User"
        assert row.role == "admin"

    def test_unique_username_constraint(self, store):
        now = datetime.now(timezone.utc).isoformat()
        with store._engine.begin() as conn:
            conn.execute(
                users_table.insert().values(
                    username="dupuser",
                    password_hash="h",
                    password_salt="s",
                    created_at=now,
                    updated_at=now,
                )
            )
        with pytest.raises(sa.exc.IntegrityError):
            with store._engine.begin() as conn:
                conn.execute(
                    users_table.insert().values(
                        username="dupuser",
                        password_hash="h2",
                        password_salt="s2",
                        created_at=now,
                        updated_at=now,
                    )
                )


# ─── Portfolios table schema ─────────────────────────────


class TestPortfoliosTable:
    def test_insert_and_query_portfolio(self, store):
        now = datetime.now(timezone.utc).isoformat()
        with store._engine.begin() as conn:
            conn.execute(
                portfolios_table.insert().values(
                    id="pf-001",
                    name="Test Portfolio",
                    cash=5000000,
                    initial_cash=5000000,
                    strategy_name="momentum",
                    created_at=now,
                    updated_at=now,
                )
            )
        with store._engine.connect() as conn:
            row = conn.execute(
                portfolios_table.select().where(portfolios_table.c.id == "pf-001")
            ).fetchone()
        assert row is not None
        assert row.name == "Test Portfolio"


# ─── Edge cases ───────────────────────────────────────────


class TestEdgeCases:
    def test_multiple_stores_same_memory_db_are_independent(self):
        """Each in-memory SQLite is a separate database."""
        s1 = DataStore(url="sqlite:///:memory:")
        s2 = DataStore(url="sqlite:///:memory:")
        s1.save_backtest_result("bt-1", "test", {}, 1.0, -0.1, 0.2, 0.1)
        assert len(s1.load_backtest_history()) == 1
        assert len(s2.load_backtest_history()) == 0

    def test_datastore_with_db_path(self, tmp_path):
        """DataStore can be created with a file path."""
        db_file = tmp_path / "test.db"
        store = DataStore(db_path=str(db_file))
        store.save_backtest_result("bt-1", "test", {}, 1.0, -0.1, 0.2, 0.1)
        results = store.load_backtest_history()
        assert len(results) == 1
        assert db_file.exists()
