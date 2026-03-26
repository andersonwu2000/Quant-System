"""Unit tests for K-Fold Cross-Validation Backtest (Phase G3c)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.backtest.kfold import run_kfold_backtest
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


SYMBOLS = ["AAPL", "MSFT", "GOOG"]


def _make_feed(
    symbols: list[str],
    start: str = "2022-01-03",
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
    original_run = BacktestEngine.run

    def patched_run(self, strategy, config, **kwargs):
        # Reset current_date so the feed returns all data for new date ranges
        feed.set_current_date(None)  # type: ignore[arg-type]
        feed._current_date = None
        self._load_data = lambda cfg: (feed, set(), None)
        return original_run(self, strategy, config, **kwargs)

    return patched_run


def _base_config(**overrides) -> BacktestConfig:
    defaults = dict(
        universe=SYMBOLS,
        start="2022-01-03",
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


class TestKFoldBacktest:

    @pytest.fixture(autouse=True)
    def _patch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.feed = _make_feed(SYMBOLS)
        monkeypatch.setattr(
            BacktestEngine, "run", _patch_engine_factory(self.feed),
        )

    def test_fold_count_matches_k(self) -> None:
        config = _base_config()
        result = run_kfold_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            k=3,
        )
        assert len(result.fold_results) == 3
        assert result.k == 3

    def test_each_fold_has_valid_result(self) -> None:
        config = _base_config()
        result = run_kfold_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            k=3,
        )
        for fold_result in result.fold_results:
            assert fold_result.strategy_name == "test_equal_weight"
            assert fold_result.total_trades >= 0
            assert len(fold_result.nav_series) > 0

    def test_avg_sharpe_is_mean_of_folds(self) -> None:
        config = _base_config()
        result = run_kfold_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            k=3,
        )
        fold_sharpes = [r.sharpe for r in result.fold_results]
        expected = float(np.mean(fold_sharpes))
        assert abs(result.avg_sharpe - expected) < 1e-10

    def test_raises_on_k_less_than_2(self) -> None:
        config = _base_config()
        with pytest.raises(ValueError, match="k must be >= 2"):
            run_kfold_backtest(
                strategy_factory=_EqualWeightStrategy,
                base_config=config,
                k=1,
            )

    def test_summary_is_string(self) -> None:
        config = _base_config()
        result = run_kfold_backtest(
            strategy_factory=_EqualWeightStrategy,
            base_config=config,
            k=3,
        )
        s = result.summary()
        assert isinstance(s, str)
        assert "K-Fold Backtest Result" in s
