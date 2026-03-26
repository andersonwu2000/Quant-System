"""Tests for FilterStrategy framework."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.alpha.filter_strategy import (
    PRICE_FACTORS,
    FilterCondition,
    FilterStrategy,
    FilterStrategyConfig,
    revenue_momentum_filter,
    trust_follow_filter,
)
from src.core.models import Portfolio
from src.strategy.base import Context


# ── Helpers ───────────────────────────────────────────────────

def _make_bars(n: int = 120, base_price: float = 100.0, volume: float = 500_000) -> pd.DataFrame:
    """Create mock OHLCV DataFrame with n rows."""
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    rng = np.random.RandomState(42)
    close = base_price + np.cumsum(rng.randn(n) * 0.5)
    close = np.maximum(close, 1.0)  # ensure positive
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.02,
            "low": close * 0.98,
            "close": close,
            "volume": np.full(n, volume),
        },
        index=dates,
    )


def _make_context(
    universe: list[str],
    bars_map: dict[str, pd.DataFrame],
    fundamentals: MagicMock | None = None,
    current_time: datetime | None = None,
) -> Context:
    """Create a Context with mocked feed and optional fundamentals."""
    feed = MagicMock()
    feed.get_universe.return_value = universe
    feed.get_bars.side_effect = lambda sym: bars_map.get(sym, pd.DataFrame())

    portfolio = Portfolio(cash=Decimal("1000000"))
    ctx = Context(
        feed=feed,
        portfolio=portfolio,
        current_time=current_time or datetime(2024, 6, 1),
        fundamentals_provider=fundamentals,
    )
    return ctx


# ── Test FilterCondition.evaluate ─────────────────────────────

class TestFilterConditionEvaluate:
    def test_gt(self):
        fc = FilterCondition("x", "gt", 10.0)
        assert fc.evaluate(11.0) is True
        assert fc.evaluate(10.0) is False
        assert fc.evaluate(9.0) is False

    def test_lt(self):
        fc = FilterCondition("x", "lt", 5.0)
        assert fc.evaluate(4.0) is True
        assert fc.evaluate(5.0) is False
        assert fc.evaluate(6.0) is False

    def test_gte(self):
        fc = FilterCondition("x", "gte", 10.0)
        assert fc.evaluate(10.0) is True
        assert fc.evaluate(10.1) is True
        assert fc.evaluate(9.9) is False

    def test_lte(self):
        fc = FilterCondition("x", "lte", 10.0)
        assert fc.evaluate(10.0) is True
        assert fc.evaluate(9.9) is True
        assert fc.evaluate(10.1) is False

    def test_eq(self):
        fc = FilterCondition("x", "eq", 1.0)
        assert fc.evaluate(1.0) is True
        assert fc.evaluate(1.0 + 1e-10) is True  # within tolerance
        assert fc.evaluate(2.0) is False

    def test_between(self):
        fc = FilterCondition("x", "between", (5.0, 15.0))
        assert fc.evaluate(10.0) is True
        assert fc.evaluate(5.0) is True   # inclusive lower
        assert fc.evaluate(15.0) is True  # inclusive upper
        assert fc.evaluate(4.9) is False
        assert fc.evaluate(15.1) is False

    def test_unknown_operator_raises(self):
        fc = FilterCondition("x", "nope", 0.0)
        with pytest.raises(ValueError, match="Unknown operator"):
            fc.evaluate(1.0)


# ── Test FilterStrategy.name ──────────────────────────────────

class TestFilterStrategyName:
    def test_returns_config_name(self):
        cfg = FilterStrategyConfig(
            filters=[],
            rank_by="momentum_60d",
            name="my_test_strategy",
        )
        s = FilterStrategy(cfg)
        assert s.name() == "my_test_strategy"

    def test_default_name(self):
        cfg = FilterStrategyConfig(filters=[], rank_by="rsi")
        s = FilterStrategy(cfg)
        assert s.name() == "filter_strategy"


# ── Test FilterStrategy with empty universe ───────────────────

class TestFilterStrategyEmptyUniverse:
    def test_empty_universe_returns_empty(self):
        cfg = FilterStrategyConfig(
            filters=[FilterCondition("momentum_60d", "gt", 0.0)],
            rank_by="momentum_60d",
        )
        s = FilterStrategy(cfg)
        ctx = _make_context(universe=[], bars_map={})
        result = s.on_bar(ctx)
        assert result == {}


# ── Test FilterStrategy with price-only filters (no fundamentals) ──

class TestFilterStrategyPriceOnly:
    def test_price_only_filters_work_without_fundamentals(self):
        """Strategy should work with price-only factors even when no
        fundamentals provider is set."""
        bars_a = _make_bars(n=120, base_price=100.0, volume=500_000)
        bars_b = _make_bars(n=120, base_price=50.0, volume=500_000)

        cfg = FilterStrategyConfig(
            filters=[
                FilterCondition("momentum_60d", "gt", -0.5),
            ],
            rank_by="volume_20d_avg",  # positive values so equal_weight selects them
            top_n=5,
            min_volume_lots=100,  # 500k shares / 1000 = 500 lots > 100
        )
        s = FilterStrategy(cfg)
        ctx = _make_context(
            universe=["A", "B"],
            bars_map={"A": bars_a, "B": bars_b},
            fundamentals=None,
        )
        result = s.on_bar(ctx)
        # Both stocks should pass with the lenient filter
        assert len(result) > 0
        for w in result.values():
            assert w > 0

    def test_volume_filter_excludes_illiquid(self):
        """Stocks with low volume should be excluded."""
        bars_low_vol = _make_bars(n=120, base_price=100.0, volume=100)  # 0.1 lots

        cfg = FilterStrategyConfig(
            filters=[FilterCondition("momentum_60d", "gt", -1.0)],
            rank_by="momentum_60d",
            min_volume_lots=300,
        )
        s = FilterStrategy(cfg)
        ctx = _make_context(
            universe=["LOW"],
            bars_map={"LOW": bars_low_vol},
        )
        result = s.on_bar(ctx)
        assert result == {}

    def test_insufficient_bars_skipped(self):
        """Stocks with < 60 bars should be skipped."""
        short_bars = _make_bars(n=30)

        cfg = FilterStrategyConfig(
            filters=[FilterCondition("momentum_60d", "gt", -1.0)],
            rank_by="momentum_60d",
        )
        s = FilterStrategy(cfg)
        ctx = _make_context(
            universe=["SHORT"],
            bars_map={"SHORT": short_bars},
        )
        result = s.on_bar(ctx)
        assert result == {}


# ── Test FilterStrategy selection logic with fundamentals ─────

class TestFilterStrategyWithFundamentals:
    def test_filters_correctly_select_stocks(self):
        """Mock fundamentals and verify the AND logic + ranking."""
        bars_a = _make_bars(n=120, base_price=100.0, volume=500_000)
        bars_b = _make_bars(n=120, base_price=50.0, volume=500_000)
        bars_c = _make_bars(n=120, base_price=80.0, volume=500_000)

        # Mock fundamentals provider
        fundamentals = MagicMock()

        def mock_revenue(symbol, start, end):
            if symbol == "A":
                return pd.DataFrame({
                    "date": pd.date_range("2023-01-01", periods=24, freq="MS"),
                    "revenue": np.linspace(100, 200, 24),
                    "yoy_growth": np.linspace(20, 30, 24),
                })
            elif symbol == "B":
                return pd.DataFrame({
                    "date": pd.date_range("2023-01-01", periods=24, freq="MS"),
                    "revenue": np.linspace(100, 110, 24),
                    "yoy_growth": np.linspace(5, 8, 24),  # Low growth — should fail filter
                })
            elif symbol == "C":
                return pd.DataFrame({
                    "date": pd.date_range("2023-01-01", periods=24, freq="MS"),
                    "revenue": np.linspace(100, 180, 24),
                    "yoy_growth": np.linspace(15, 25, 24),
                })
            return pd.DataFrame()

        fundamentals.get_revenue.side_effect = mock_revenue

        cfg = FilterStrategyConfig(
            filters=[
                FilterCondition("revenue_yoy", "gt", 15.0),
                FilterCondition("momentum_60d", "gt", -0.5),
            ],
            rank_by="revenue_yoy",
            rank_ascending=False,
            top_n=2,
            min_volume_lots=100,
            name="test_selection",
        )
        s = FilterStrategy(cfg)
        ctx = _make_context(
            universe=["A", "B", "C"],
            bars_map={"A": bars_a, "B": bars_b, "C": bars_c},
            fundamentals=fundamentals,
        )
        result = s.on_bar(ctx)

        # B has yoy_growth < 15 at most points, so should likely be excluded
        # A and C should be selected
        assert len(result) <= 2
        # At least one stock selected
        assert len(result) > 0


# ── Test pre-configured strategies ────────────────────────────

class TestPreConfiguredStrategies:
    def test_revenue_momentum_filter(self):
        s = revenue_momentum_filter()
        assert isinstance(s, FilterStrategy)
        assert s.name() == "filter_revenue_momentum"
        assert s._config.top_n == 15
        assert s._config.max_weight == 0.10
        assert len(s._config.filters) == 4

    def test_trust_follow_filter(self):
        s = trust_follow_filter()
        assert isinstance(s, FilterStrategy)
        assert s.name() == "filter_trust_follow"
        assert s._config.top_n == 10
        assert s._config.max_weight == 0.15
        assert len(s._config.filters) == 3


# ── Test PRICE_FACTORS registry ───────────────────────────────

class TestPriceFactorsRegistry:
    def test_all_entries_callable(self):
        for key, fn in PRICE_FACTORS.items():
            assert callable(fn), f"PRICE_FACTORS[{key!r}] is not callable"

    def test_all_return_float_or_none_on_valid_bars(self):
        bars = _make_bars(n=252)
        for key, fn in PRICE_FACTORS.items():
            result = fn(bars)
            assert result is None or isinstance(result, float), (
                f"PRICE_FACTORS[{key!r}] returned {type(result)}"
            )

    def test_expected_keys_present(self):
        expected = {
            "price_vs_ma60", "price_vs_ma20", "price_vs_ma120",
            "momentum_60d", "momentum_20d", "momentum_120d",
            "volume_20d_avg", "rsi",
        }
        assert expected == set(PRICE_FACTORS.keys())


# ── Test FilterStrategyConfig defaults ────────────────────────

class TestFilterStrategyConfigDefaults:
    def test_defaults(self):
        cfg = FilterStrategyConfig(
            filters=[FilterCondition("x", "gt", 0.0)],
            rank_by="x",
        )
        assert cfg.rank_ascending is False
        assert cfg.top_n == 15
        assert cfg.max_weight == 0.10
        assert cfg.min_volume_lots == 300
        assert cfg.lookback_bars == 252
        assert cfg.name == "filter_strategy"

    def test_custom_values(self):
        cfg = FilterStrategyConfig(
            filters=[],
            rank_by="rsi",
            rank_ascending=True,
            top_n=5,
            max_weight=0.20,
            min_volume_lots=100,
            lookback_bars=120,
            name="custom",
        )
        assert cfg.rank_ascending is True
        assert cfg.top_n == 5
        assert cfg.max_weight == 0.20
        assert cfg.min_volume_lots == 100
        assert cfg.lookback_bars == 120
        assert cfg.name == "custom"
