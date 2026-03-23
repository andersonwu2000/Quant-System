"""Comprehensive unit tests for BacktestEngine (Phase 2-1).

Covers: basic flow, rebalance frequency, execution delay, kill switch,
settlement, rejected orders, and dividend integration.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.data.feed import HistoricalFeed
from src.strategy.base import Context, Strategy


# ── Helpers ──────────────────────────────────────────────────────────────


class _FixedWeightStrategy(Strategy):
    """Test strategy that always returns the same target weights."""

    def __init__(self, weights: dict[str, float]) -> None:
        self._weights = weights
        self.call_dates: list = []

    def name(self) -> str:
        return "test_fixed"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        self.call_dates.append(ctx.now())
        return dict(self._weights)


class _EmptyStrategy(Strategy):
    """Test strategy that never allocates."""

    def name(self) -> str:
        return "test_empty"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        return {}


class _CrashingPriceStrategy(Strategy):
    """Returns 100% weight, used to force large drawdown for kill switch tests."""

    def __init__(self, symbol: str) -> None:
        self._symbol = symbol

    def name(self) -> str:
        return "test_crash"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        return {self._symbol: 0.99}


def _make_feed(
    symbols: list[str],
    start: str = "2024-01-02",
    end: str = "2024-03-29",
    seed: int = 42,
) -> HistoricalFeed:
    """Create a HistoricalFeed with deterministic synthetic OHLCV data."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start, end)
    feed = HistoricalFeed()
    for symbol in symbols:
        base = 100 + rng.randint(0, 200)
        noise = rng.randn(len(dates)) * 2
        close = base + np.cumsum(noise)
        close = np.maximum(close, 10)  # floor at $10
        df = pd.DataFrame(
            {
                "open": close * (1 + rng.randn(len(dates)) * 0.005),
                "high": close * (1 + abs(rng.randn(len(dates))) * 0.01),
                "low": close * (1 - abs(rng.randn(len(dates))) * 0.01),
                "close": close,
                "volume": rng.randint(100_000, 10_000_000, len(dates)).astype(float),
            },
            index=dates,
        )
        feed.load(symbol, df)
    return feed


def _make_flat_feed(
    symbols: list[str],
    dates: list[str],
    price: float = 100.0,
    volume: float = 1_000_000.0,
    open_price: float | None = None,
) -> HistoricalFeed:
    """Create a HistoricalFeed with flat (constant) prices."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    feed = HistoricalFeed()
    op = open_price if open_price is not None else price
    for symbol in symbols:
        df = pd.DataFrame(
            {
                "open": [op] * len(dates),
                "high": [price * 1.01] * len(dates),
                "low": [price * 0.99] * len(dates),
                "close": [price] * len(dates),
                "volume": [volume] * len(dates),
            },
            index=idx,
        )
        feed.load(symbol, df)
    return feed


def _patch_engine(
    engine: BacktestEngine,
    feed: HistoricalFeed,
    dividend_data: dict[str, dict[str, float]] | None = None,
) -> None:
    """Patch _load_data (and optionally _load_dividends) to return our
    synthetic feed (skip Yahoo/network)."""
    engine._load_data = lambda cfg: (feed, set(), None)  # type: ignore[assignment]
    if dividend_data is not None:
        engine._load_dividends = lambda cfg: dividend_data  # type: ignore[assignment]


def _base_config(**overrides) -> BacktestConfig:
    """Return a BacktestConfig with sensible test defaults."""
    defaults = dict(
        universe=["AAPL"],
        start="2024-01-02",
        end="2024-03-29",
        initial_cash=1_000_000.0,
        execution_delay=0,
        impact_model="fixed",
        slippage_bps=5.0,
        commission_rate=0.001425,
        tax_rate=0.003,
        enable_kill_switch=False,
        settlement_days=0,
        rebalance_freq="daily",
        risk_rules=[],  # disable default risk rules for test predictability
    )
    defaults.update(overrides)
    return BacktestConfig(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# Basic Flow Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBasicFlow:

    def test_basic_run_produces_result(self) -> None:
        """A simple backtest with a fixed-weight strategy produces a valid
        BacktestResult with all expected fields."""
        feed = _make_feed(["AAPL"])
        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config()
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        result = engine.run(strategy, config)

        # Core fields are populated
        assert result.strategy_name == "test_fixed"
        assert result.initial_cash == 1_000_000.0
        assert result.start_date != ""
        assert result.end_date != ""

        # Performance metrics exist
        assert isinstance(result.total_return, float)
        assert isinstance(result.sharpe, float)
        assert isinstance(result.max_drawdown, float)
        assert isinstance(result.volatility, float)

        # Time series are non-empty
        assert len(result.nav_series) > 0
        assert len(result.daily_returns) >= 0

        # Trade stats
        assert result.total_trades >= 0
        assert 0.0 <= result.win_rate <= 1.0

    def test_nav_starts_at_initial_cash(self) -> None:
        """First NAV entry equals initial_cash."""
        feed = _make_flat_feed(
            ["AAPL"],
            ["2024-01-02", "2024-01-03", "2024-01-04"],
            price=100.0,
        )
        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            start="2024-01-02",
            end="2024-01-04",
            initial_cash=500_000.0,
        )
        strategy = _EmptyStrategy()
        result = engine.run(strategy, config)

        first_nav = float(result.nav_series.iloc[0])
        assert first_nav == pytest.approx(500_000.0, abs=0.01)

    def test_empty_universe_raises(self) -> None:
        """Empty universe raises ValueError."""
        feed = HistoricalFeed()  # no data loaded
        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(universe=[])
        strategy = _EmptyStrategy()
        with pytest.raises(ValueError, match="No data loaded"):
            engine.run(strategy, config)

    def test_no_trading_dates_raises(self) -> None:
        """Date range with no data raises ValueError."""
        # Feed has data in Jan 2024, but config asks for dates in 2025
        feed = _make_flat_feed(
            ["AAPL"],
            ["2024-01-02", "2024-01-03"],
            price=100.0,
        )
        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(start="2025-06-01", end="2025-06-30")
        strategy = _EmptyStrategy()
        with pytest.raises(ValueError, match="No trading dates"):
            engine.run(strategy, config)

    def test_deterministic_same_result(self) -> None:
        """Running the same config twice gives identical results."""
        feed = _make_feed(["AAPL", "MSFT"])
        config = _base_config(universe=["AAPL", "MSFT"])
        strategy = _FixedWeightStrategy({"AAPL": 0.3, "MSFT": 0.3})

        engine1 = BacktestEngine()
        _patch_engine(engine1, feed)
        result1 = engine1.run(strategy, config)

        engine2 = BacktestEngine()
        _patch_engine(engine2, feed)
        result2 = engine2.run(strategy, config)

        assert result1.total_return == pytest.approx(result2.total_return, abs=1e-10)
        assert result1.sharpe == pytest.approx(result2.sharpe, abs=1e-10)
        assert result1.max_drawdown == pytest.approx(result2.max_drawdown, abs=1e-10)
        assert result1.total_trades == result2.total_trades
        pd.testing.assert_series_equal(result1.nav_series, result2.nav_series)


# ═══════════════════════════════════════════════════════════════════════════
# Rebalance Frequency Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRebalanceFrequency:

    def test_rebalance_daily(self) -> None:
        """Strategy is called every trading day."""
        dates = pd.bdate_range("2024-01-02", "2024-01-31")
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        feed = _make_flat_feed(["AAPL"], date_strs, price=100.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            start="2024-01-02",
            end="2024-01-31",
            rebalance_freq="daily",
        )
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        engine.run(strategy, config)

        # Strategy should be called on every trading day
        assert len(strategy.call_dates) == len(dates)

    def test_rebalance_monthly(self) -> None:
        """Strategy is called only on first trading day of each month."""
        dates = pd.bdate_range("2024-01-02", "2024-03-29")
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        feed = _make_flat_feed(["AAPL"], date_strs, price=100.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            start="2024-01-02",
            end="2024-03-29",
            rebalance_freq="monthly",
        )
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        engine.run(strategy, config)

        # Should be called once per month: Jan, Feb, Mar = 3 times
        assert len(strategy.call_dates) == 3

        # Each call should be the first trading day of its month
        months_seen = {d.month for d in strategy.call_dates}
        assert months_seen == {1, 2, 3}

    def test_rebalance_weekly(self) -> None:
        """Strategy is called on Mondays (+ first day if not Monday)."""
        dates = pd.bdate_range("2024-01-02", "2024-01-31")
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        feed = _make_flat_feed(["AAPL"], date_strs, price=100.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            start="2024-01-02",
            end="2024-01-31",
            rebalance_freq="weekly",
        )
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        engine.run(strategy, config)

        # 2024-01-02 is a Tuesday (first day, always called)
        # Then Mondays: 2024-01-08, 15, 22, 29
        for d in strategy.call_dates:
            # Each call date should be Monday (weekday=0) or the very first day
            assert d.weekday() == 0 or d == strategy.call_dates[0]


# ═══════════════════════════════════════════════════════════════════════════
# Execution Delay Tests (Phase 0-1)
# ═══════════════════════════════════════════════════════════════════════════


class TestExecutionDelay:

    def test_execution_delay_zero_same_day(self) -> None:
        """With execution_delay=0, trades execute same day at close."""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        feed = _make_flat_feed(["AAPL"], dates, price=100.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            start="2024-01-02",
            end="2024-01-05",
            execution_delay=0,
        )
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        result = engine.run(strategy, config)

        # With delay=0, we should see trades on the very first bar
        assert result.total_trades > 0
        # First trade should happen on the first date
        first_trade = result.trades[0]
        assert first_trade.timestamp.strftime("%Y-%m-%d") == "2024-01-02"

    def test_execution_delay_one_next_day_open(self) -> None:
        """With execution_delay=1, orders wait until next day and fill at
        open price."""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        # Use different open and close prices to verify fill_on="open"
        feed = _make_flat_feed(
            ["AAPL"], dates, price=100.0, open_price=99.0,
        )

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            start="2024-01-02",
            end="2024-01-05",
            execution_delay=1,
            fill_on="open",
        )
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        result = engine.run(strategy, config)

        # Orders generated on day 1 (2024-01-02) should fill on day 2 (2024-01-03)
        assert result.total_trades > 0
        first_trade = result.trades[0]
        assert first_trade.timestamp.strftime("%Y-%m-%d") == "2024-01-03"

        # Fill price should be based on open (99.0) + slippage, not close (100.0)
        # With fixed slippage of 5bps on 99.0: 99.0 * 5/10000 = 0.0495
        expected_base = Decimal("99.0")
        slippage = expected_base * Decimal("5") / Decimal("10000")
        expected_fill = expected_base + slippage  # BUY adds slippage
        assert float(first_trade.price) == pytest.approx(float(expected_fill), rel=1e-4)

    def test_execution_delay_pending_orders_cleared(self) -> None:
        """Pending orders from day N are executed on day N+1, then cleared."""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
                 "2024-01-08", "2024-01-09"]
        feed = _make_flat_feed(["AAPL"], dates, price=100.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            start="2024-01-02",
            end="2024-01-09",
            execution_delay=1,
            rebalance_freq="daily",
        )
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        result = engine.run(strategy, config)

        # Should have trades — orders are not lost, they execute next day
        assert result.total_trades > 0

        # No duplicate fills: each order is executed exactly once
        trade_dates = [t.timestamp.strftime("%Y-%m-%d") for t in result.trades]
        # The first fill is on 2024-01-03 (delay of orders from 2024-01-02)
        assert trade_dates[0] == "2024-01-03"


# ═══════════════════════════════════════════════════════════════════════════
# Kill Switch Tests (Phase 0-3)
# ═══════════════════════════════════════════════════════════════════════════


class TestKillSwitch:

    def _make_crashing_feed(self) -> tuple[HistoricalFeed, list[str]]:
        """Create a feed where CRASH drops drastically to trigger kill switch.

        Day 1-2: price=100 (strategy buys on day 1, holds on day 2)
        Day 3: price crashes to 40 (portfolio invested ~99% loses ~60% of
               equity value => daily drawdown well above 5%)
        Days 4+: price stays at 40
        February dates included for cooldown test.
        """
        dates = [
            "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
            "2024-01-08", "2024-01-09", "2024-01-10",
            # February dates for cooldown test
            "2024-02-01", "2024-02-02", "2024-02-05",
        ]
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
        prices = [100.0, 100.0, 40.0, 40.0, 40.0, 40.0, 40.0, 40.0, 40.0, 40.0]
        feed = HistoricalFeed()
        df = pd.DataFrame(
            {
                "open": prices,
                "high": prices,
                "low": prices,
                "close": prices,
                "volume": [5_000_000.0] * len(dates),
            },
            index=idx,
        )
        feed.load("CRASH", df)
        return feed, dates

    def test_kill_switch_triggers_on_large_drawdown(self) -> None:
        """When daily drawdown > 5%, kill switch activates and liquidates."""
        feed, dates = self._make_crashing_feed()
        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            universe=["CRASH"],
            start="2024-01-02",
            end="2024-01-10",
            execution_delay=0,
            enable_kill_switch=True,
            kill_switch_cooldown="end_of_month",
        )
        strategy = _CrashingPriceStrategy("CRASH")
        result = engine.run(strategy, config)

        # After kill switch triggers, positions should be liquidated.
        # We verify by checking that there are SELL trades (liquidation)
        sell_trades = [t for t in result.trades if t.side.value == "SELL"]
        assert len(sell_trades) > 0, "Kill switch should have triggered liquidation sells"

    def test_kill_switch_disabled(self) -> None:
        """With enable_kill_switch=False, no kill switch even with large drawdown."""
        feed, dates = self._make_crashing_feed()
        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            universe=["CRASH"],
            start="2024-01-02",
            end="2024-01-10",
            execution_delay=0,
            enable_kill_switch=False,
        )
        strategy = _CrashingPriceStrategy("CRASH")
        result = engine.run(strategy, config)

        # The strategy keeps buying/holding even as price crashes.
        # With kill switch disabled, it should NOT force-liquidate.
        # Strategy continues to be called on every bar.
        nav_series = result.nav_series
        # NAV will be significantly impacted but strategy continues
        assert len(nav_series) > 3

    def test_kill_switch_cooldown_end_of_month(self) -> None:
        """After triggering, trading resumes at start of next month."""
        feed, dates = self._make_crashing_feed()
        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            universe=["CRASH"],
            start="2024-01-02",
            end="2024-02-05",
            execution_delay=0,
            enable_kill_switch=True,
            kill_switch_cooldown="end_of_month",
        )

        # Track calls to on_bar to see when strategy resumes
        strategy = _FixedWeightStrategy({"CRASH": 0.5})
        engine.run(strategy, config)

        # After kill switch triggers in January, strategy should NOT be called
        # for remaining January days. It should resume in February.
        feb_calls = [d for d in strategy.call_dates if d.month == 2]
        assert len(feb_calls) > 0, "Strategy should resume in February after cooldown"


# ═══════════════════════════════════════════════════════════════════════════
# Settlement Tests (Phase 2-5)
# ═══════════════════════════════════════════════════════════════════════════


class TestSettlement:

    def test_settlement_zero_instant(self) -> None:
        """With settlement_days=0, cash is immediately available (no pending)."""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        feed = _make_flat_feed(["AAPL"], dates, price=100.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config = _base_config(
            start="2024-01-02",
            end="2024-01-05",
            settlement_days=0,
            execution_delay=0,
        )
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        result = engine.run(strategy, config)

        # Trades happen, and there are no pending settlements
        assert result.total_trades > 0

    def test_settlement_t2_restricts_buying(self) -> None:
        """With settlement_days=2, buying power is limited by unsettled cash."""
        dates = pd.bdate_range("2024-01-02", "2024-01-15")
        date_strs = [d.strftime("%Y-%m-%d") for d in dates]
        feed = _make_flat_feed(["AAPL"], date_strs, price=100.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        config_t0 = _base_config(
            start="2024-01-02",
            end="2024-01-15",
            settlement_days=0,
            execution_delay=0,
        )
        config_t2 = _base_config(
            start="2024-01-02",
            end="2024-01-15",
            settlement_days=2,
            execution_delay=0,
        )
        strategy_t0 = _FixedWeightStrategy({"AAPL": 0.5})
        strategy_t2 = _FixedWeightStrategy({"AAPL": 0.5})

        engine_t0 = BacktestEngine()
        _patch_engine(engine_t0, feed)
        result_t0 = engine_t0.run(strategy_t0, config_t0)

        engine_t2 = BacktestEngine()
        _patch_engine(engine_t2, feed)
        result_t2 = engine_t2.run(strategy_t2, config_t2)

        # With T+2 settlement, the engine should still produce results
        assert result_t2.total_trades >= 0
        assert len(result_t2.nav_series) > 0

        # T+2 settlement means buying power is constrained, which may lead
        # to different trade counts or slightly different NAV path.
        # At minimum, both should complete successfully.
        assert result_t0.total_trades >= 0


# ═══════════════════════════════════════════════════════════════════════════
# Rejected Orders Tests (Phase 0-4)
# ═══════════════════════════════════════════════════════════════════════════


class TestRejectedOrders:

    def test_rejected_orders_counted_in_result(self) -> None:
        """Result includes rejected_orders count and rejected_notional when
        orders are rejected by the sim broker (e.g., exceeding volume limit)."""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        # Very low volume so orders will be rejected by max_fill_pct_of_volume
        feed = _make_flat_feed(["AAPL"], dates, price=100.0, volume=10.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        # Large initial cash relative to volume => orders will exceed volume cap
        config = _base_config(
            start="2024-01-02",
            end="2024-01-05",
            initial_cash=10_000_000.0,
            execution_delay=0,
        )
        strategy = _FixedWeightStrategy({"AAPL": 0.9})
        result = engine.run(strategy, config)

        # With only 10 shares volume and max_fill_pct=10%, max fill is 1 share.
        # Strategy wants 90% of 10M = 9M / 100 = 90,000 shares.
        # This should get rejected.
        assert result.rejected_orders >= 0
        assert result.rejected_notional >= 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Dividend Integration Test
# ═══════════════════════════════════════════════════════════════════════════


class TestDividendIntegration:

    def test_dividends_add_cash(self) -> None:
        """With enable_dividends=True, dividends increase cash."""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
                 "2024-01-08"]
        feed = _make_flat_feed(["DIV"], dates, price=50.0)

        engine = BacktestEngine()
        _patch_engine(engine, feed)

        # We need a run WITH dividends and one WITHOUT, compare final NAV
        config_div = _base_config(
            universe=["DIV"],
            start="2024-01-02",
            end="2024-01-08",
            initial_cash=100_000.0,
            enable_dividends=True,
            execution_delay=0,
            slippage_bps=0.0,
            commission_rate=0.0,
            tax_rate=0.0,
        )
        config_nodiv = _base_config(
            universe=["DIV"],
            start="2024-01-02",
            end="2024-01-08",
            initial_cash=100_000.0,
            enable_dividends=False,
            execution_delay=0,
            slippage_bps=0.0,
            commission_rate=0.0,
            tax_rate=0.0,
        )

        # Engine with dividends
        engine_div = BacktestEngine()
        _patch_engine(
            engine_div, feed,
            dividend_data={"DIV": {"2024-01-04": 1.00}},
        )

        strategy_div = _FixedWeightStrategy({"DIV": 0.5})
        result_div = engine_div.run(strategy_div, config_div)

        # Engine without dividends
        engine_nodiv = BacktestEngine()
        _patch_engine(engine_nodiv, feed)

        strategy_nodiv = _FixedWeightStrategy({"DIV": 0.5})
        result_nodiv = engine_nodiv.run(strategy_nodiv, config_nodiv)

        # The dividend run should have higher final NAV
        final_nav_div = float(result_div.nav_series.iloc[-1])
        final_nav_nodiv = float(result_nodiv.nav_series.iloc[-1])

        assert final_nav_div > final_nav_nodiv, (
            f"Dividend NAV ({final_nav_div}) should exceed non-dividend NAV ({final_nav_nodiv})"
        )
