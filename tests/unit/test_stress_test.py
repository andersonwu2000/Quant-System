"""Unit tests for Synthetic Data Stress Test (Phase G3d)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig
from src.backtest.stress_test import (
    ALL_SCENARIOS,
    BEAR_MARKET,
    FLASH_CRASH,
    HIGH_VOLATILITY,
    REGIME_CHANGE,
    run_stress_test,
)
from src.data.feed import HistoricalFeed
from src.strategy.base import Context, Strategy


# ── Helpers ──────────────────────────────────────────────────


class _EqualWeightStrategy(Strategy):
    def name(self) -> str:
        return "test_equal_weight"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        universe = ctx.universe()
        if not universe:
            return {}
        w = 1.0 / len(universe)
        return {s: w for s in universe}


SYMBOLS = ["AAPL", "MSFT"]


def _make_feed(
    symbols: list[str],
    start: str = "2023-06-01",
    end: str = "2024-06-28",
    seed: int = 42,
) -> HistoricalFeed:
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start, end)
    feed = HistoricalFeed()
    for symbol in symbols:
        base = 150
        noise = rng.randn(len(dates)) * 1.5
        close = base + np.cumsum(noise)
        close = np.maximum(close, 10)
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


def _base_config(**overrides) -> BacktestConfig:
    defaults = dict(
        universe=SYMBOLS,
        start="2023-06-01",
        end="2024-06-28",
        initial_cash=1_000_000.0,
        execution_delay=0,
        impact_model="fixed",
        slippage_bps=5.0,
        commission_rate=0.001425,
        tax_rate=0.003,
        enable_kill_switch=False,
        settlement_days=0,
        rebalance_freq="weekly",
        risk_rules=[],
    )
    defaults.update(overrides)
    return BacktestConfig(**defaults)


# ═══════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════


class TestStressScenarios:

    def test_bear_market_modifier_reduces_prices(self) -> None:
        """Bear market modifier should create more negative returns."""
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2023-01-01", "2023-06-30")
        n = len(dates)
        close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 1, n))
        close = np.maximum(close, 10)
        df = pd.DataFrame({
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.ones(n) * 1e6,
        }, index=dates)

        modified = BEAR_MARKET.returns_modifier(df, rng)
        # Modified close should differ from original
        assert not np.allclose(df["close"].values, modified["close"].values)

    def test_high_volatility_modifier_increases_vol(self) -> None:
        """High volatility modifier should increase return standard deviation."""
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2023-01-01", "2023-12-31")
        n = len(dates)
        close = 100.0 + np.cumsum(np.random.default_rng(42).normal(0, 1, n))
        close = np.maximum(close, 10)
        df = pd.DataFrame({
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.ones(n) * 1e6,
        }, index=dates)

        modified = HIGH_VOLATILITY.returns_modifier(df, rng)
        orig_vol = df["close"].pct_change().std()
        mod_vol = modified["close"].pct_change().std()
        assert mod_vol > orig_vol

    def test_flash_crash_modifier_creates_drops(self) -> None:
        """Flash crash modifier should inject sharp drops."""
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2023-01-01", "2023-12-31")
        n = len(dates)
        close = np.full(n, 100.0)  # flat prices
        df = pd.DataFrame({
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.ones(n) * 1e6,
        }, index=dates)

        modified = FLASH_CRASH.returns_modifier(df, rng)
        # Should have some days with significant drops
        returns = modified["close"].pct_change().dropna()
        assert (returns < -0.05).any()

    def test_regime_change_modifier_inverts_second_half(self) -> None:
        """Regime change modifier should invert returns in second half."""
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2023-01-01", "2023-12-31")
        n = len(dates)
        # Create a clear uptrend
        close = 100.0 + np.arange(n) * 0.5
        df = pd.DataFrame({
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.ones(n) * 1e6,
        }, index=dates)

        modified = REGIME_CHANGE.returns_modifier(df, rng)
        mid = n // 2
        # Second half should have lower prices than first half end
        first_half_end = modified["close"].iloc[mid - 1]
        second_half_end = modified["close"].iloc[-1]
        # With inverted positive returns, second half should decline
        assert second_half_end < first_half_end

    def test_all_scenarios_defined(self) -> None:
        """ALL_SCENARIOS should contain 4 predefined scenarios."""
        assert len(ALL_SCENARIOS) == 4
        names = {s.name for s in ALL_SCENARIOS}
        assert names == {"bear_market", "high_volatility", "flash_crash", "regime_change"}


class TestStressTestIntegration:

    def test_run_stress_test_produces_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run_stress_test should produce a result for each scenario."""
        feed = _make_feed(SYMBOLS)

        # Patch create_feed at the module where it's imported
        import src.backtest.stress_test as st_mod

        def mock_create_feed(source, universe, **kwargs):
            return feed

        monkeypatch.setattr(st_mod, "create_feed", mock_create_feed)

        config = _base_config()
        results = run_stress_test(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            scenarios=[FLASH_CRASH],
            seed=42,
        )
        assert "flash_crash" in results
        result = results["flash_crash"]
        assert result.strategy_name == "test_equal_weight"
        assert len(result.nav_series) > 0
