"""Unit tests for Randomized Backtest (Phase G3a)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.backtest.randomized import (
    RandomizedBacktestConfig,
    run_randomized_backtest,
)
from src.data.feed import HistoricalFeed
from src.strategy.base import Context, Strategy


# ── Helpers ──────────────────────────────────────────────────


class _EqualWeightStrategy(Strategy):
    """Equal-weight across universe."""

    def __init__(self) -> None:
        pass

    def name(self) -> str:
        return "test_equal_weight"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        universe = ctx.universe()
        if not universe:
            return {}
        w = 1.0 / len(universe)
        return {s: w for s in universe}


def _make_feed(
    symbols: list[str],
    start: str = "2023-01-02",
    end: str = "2024-06-28",
    seed: int = 42,
) -> HistoricalFeed:
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(start, end)
    feed = HistoricalFeed()
    for symbol in symbols:
        base = 100 + rng.randint(0, 200)
        noise = rng.randn(len(dates)) * 2
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


def _patch_engine_factory(feed: HistoricalFeed):
    """Return a monkeypatch-ready _load_data replacement."""
    original_run = BacktestEngine.run

    def patched_run(self, strategy, config, **kwargs):
        # Reset current_date so the feed returns all data for new date ranges
        feed._current_date = None
        self._load_data = lambda cfg: (feed, set(), None)
        return original_run(self, strategy, config, **kwargs)

    return patched_run


SYMBOLS = ["AAPL", "MSFT", "GOOG", "AMZN", "META"]


def _base_config(**overrides) -> BacktestConfig:
    defaults = dict(
        universe=SYMBOLS,
        start="2023-01-02",
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


class TestRandomizedBacktest:

    @pytest.fixture(autouse=True)
    def _patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.feed = _make_feed(SYMBOLS)
        monkeypatch.setattr(
            BacktestEngine, "run", _patch_engine_factory(self.feed),
        )

    def test_correct_number_of_iterations(self) -> None:
        config = _base_config()
        rc = RandomizedBacktestConfig(n_iterations=5, seed=123)
        result = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )
        assert result.iterations == 5

    def test_distributions_have_correct_length(self) -> None:
        config = _base_config()
        rc = RandomizedBacktestConfig(n_iterations=8, seed=456)
        result = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )
        assert len(result.sharpe_distribution) == result.iterations
        assert len(result.return_distribution) == result.iterations
        assert len(result.drawdown_distribution) == result.iterations

    def test_seed_reproducibility(self) -> None:
        config = _base_config()
        rc = RandomizedBacktestConfig(n_iterations=3, seed=99)

        r1 = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )
        r2 = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )

        assert r1.sharpe_distribution == r2.sharpe_distribution
        assert r1.return_distribution == r2.return_distribution

    def test_probability_positive_sharpe_range(self) -> None:
        config = _base_config()
        rc = RandomizedBacktestConfig(n_iterations=10, seed=42)
        result = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )
        assert 0.0 <= result.probability_positive_sharpe <= 1.0

    def test_percentiles_order(self) -> None:
        config = _base_config()
        rc = RandomizedBacktestConfig(n_iterations=10, seed=42)
        result = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )
        assert result.sharpe_5th_pct <= result.median_sharpe <= result.sharpe_95th_pct

    def test_summary_is_string(self) -> None:
        config = _base_config()
        rc = RandomizedBacktestConfig(n_iterations=3, seed=42)
        result = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )
        s = result.summary()
        assert isinstance(s, str)
        assert "Randomized Backtest Result" in s

    def test_asset_sampling(self) -> None:
        """With asset_sample_pct=0.4, should sample 2 of 5 assets."""
        config = _base_config()
        rc = RandomizedBacktestConfig(
            n_iterations=3, asset_sample_pct=0.4, seed=42,
        )
        result = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )
        # Should complete successfully
        assert result.iterations == 3

    def test_empty_result_on_zero_iterations(self) -> None:
        config = _base_config()
        rc = RandomizedBacktestConfig(n_iterations=0, seed=42)
        result = run_randomized_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            randomized_config=rc,
        )
        assert result.iterations == 0
        assert result.sharpe_distribution == []
        assert result.probability_positive_sharpe == 0.0
