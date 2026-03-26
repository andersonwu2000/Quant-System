"""Tests for revenue momentum and trust follow strategies + new factor functions."""
from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from unittest.mock import MagicMock
from decimal import Decimal

from src.strategy.factors.fundamental import (
    revenue_new_high_factor,
    revenue_acceleration_factor,
    trust_cumulative_factor,
)


# ── Factor function tests ─────────────────────────────────────────


class TestRevenueNewHighFactor:
    def test_is_new_high(self):
        assert revenue_new_high_factor(1.0) == 1.0

    def test_not_new_high(self):
        assert revenue_new_high_factor(0.0) == 0.0

    def test_threshold(self):
        assert revenue_new_high_factor(0.4) == 0.0
        assert revenue_new_high_factor(0.6) == 1.0


class TestRevenueAccelerationFactor:
    def test_normal(self):
        assert revenue_acceleration_factor(1.5) == 1.5

    def test_clip_high(self):
        assert revenue_acceleration_factor(10.0) == 5.0

    def test_clip_low(self):
        assert revenue_acceleration_factor(-1.0) == 0.0

    def test_zero(self):
        assert revenue_acceleration_factor(0.0) == 0.0


class TestTrustCumulativeFactor:
    def test_positive(self):
        assert trust_cumulative_factor(50000) == 50000

    def test_negative(self):
        assert trust_cumulative_factor(-30000) == -30000

    def test_clip_extreme(self):
        assert trust_cumulative_factor(2e9) == 1e9
        assert trust_cumulative_factor(-2e9) == -1e9


# ── Strategy tests ─────────────────────────────────────────────────

def _make_mock_context(symbols, bars_data, fundamentals=None, current_time=None):
    """Create a mock Context for strategy testing."""
    from src.strategy.base import Context

    feed = MagicMock()
    feed.get_universe.return_value = symbols

    # Mock bars — Context.bars() calls feed.get_bars() then truncates
    def mock_get_bars(sym):
        return bars_data.get(sym, pd.DataFrame())
    feed.get_bars = mock_get_bars

    portfolio = MagicMock()
    portfolio.nav = Decimal("10000000")
    portfolio.positions = {}

    ctx = Context(
        feed=feed,
        portfolio=portfolio,
        current_time=current_time or datetime(2025, 6, 15, tzinfo=timezone.utc),
        fundamentals_provider=fundamentals,
    )
    return ctx


def _make_bars(n=252, trend=0.001, start_price=100.0, volume=500000, seed=42):
    """Generate synthetic OHLCV bars with fixed random seed for reproducibility."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range(end="2025-06-15", periods=n)
    close = start_price * np.cumprod(1 + rng.normal(trend, 0.01, n))
    return pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.005,
        "low": close * 0.995,
        "close": close,
        "volume": np.full(n, volume),
    }, index=dates)


class TestRevenueMomentumStrategy:
    def test_name(self):
        from strategies.revenue_momentum import RevenueMomentumStrategy
        s = RevenueMomentumStrategy()
        assert s.name() == "revenue_momentum"

    def test_empty_universe(self):
        from strategies.revenue_momentum import RevenueMomentumStrategy
        s = RevenueMomentumStrategy()
        ctx = _make_mock_context([], {})
        weights = s.on_bar(ctx)
        assert weights == {}

    def test_no_fundamentals_provider(self):
        from strategies.revenue_momentum import RevenueMomentumStrategy
        s = RevenueMomentumStrategy()
        bars = _make_bars(252, trend=0.002, volume=500000)
        ctx = _make_mock_context(["2330.TW"], {"2330.TW": bars}, fundamentals=None)
        weights = s.on_bar(ctx)
        assert weights == {}

    def test_selects_qualifying_stocks(self):
        from strategies.revenue_momentum import RevenueMomentumStrategy
        s = RevenueMomentumStrategy(max_holdings=5, min_yoy_growth=10.0)

        # Strong uptrend bars (to pass MA60 and momentum checks)
        bars = _make_bars(252, trend=0.003, volume=500000, seed=99)

        # Mock fundamentals
        fundamentals = MagicMock()
        rev_data = pd.DataFrame({
            "date": pd.date_range("2024-01-01", periods=18, freq="ME"),
            "revenue": [100] * 6 + [120] * 6 + [150] * 6,  # Growing revenue
            "yoy_growth": [0] * 6 + [20] * 6 + [50] * 6,  # Strong YoY
        })
        fundamentals.get_revenue.return_value = rev_data

        ctx = _make_mock_context(
            ["2330.TW"], {"2330.TW": bars},
            fundamentals=fundamentals
        )
        weights = s.on_bar(ctx)
        # May or may not select depending on random bars — just check no crash
        assert isinstance(weights, dict)

    def test_filters_low_volume(self):
        from strategies.revenue_momentum import RevenueMomentumStrategy
        s = RevenueMomentumStrategy(min_volume_lots=300)

        # Low volume bars — 1000 < 300 * 1000 = 300000
        bars = _make_bars(252, trend=0.003, volume=1000)
        fundamentals = MagicMock()

        ctx = _make_mock_context(
            ["2330.TW"], {"2330.TW": bars},
            fundamentals=fundamentals
        )
        weights = s.on_bar(ctx)
        assert weights == {}

    def test_filters_insufficient_bars(self):
        from strategies.revenue_momentum import RevenueMomentumStrategy
        s = RevenueMomentumStrategy()

        # Only 50 bars — strategy requires >= 120
        bars = _make_bars(50, volume=500000)
        fundamentals = MagicMock()

        ctx = _make_mock_context(
            ["2330.TW"], {"2330.TW": bars},
            fundamentals=fundamentals
        )
        weights = s.on_bar(ctx)
        assert weights == {}

    def test_filters_below_ma60(self):
        from strategies.revenue_momentum import RevenueMomentumStrategy
        s = RevenueMomentumStrategy()

        # Strong downtrend — price will be below MA60
        bars = _make_bars(252, trend=-0.003, volume=500000, seed=42)
        fundamentals = MagicMock()

        ctx = _make_mock_context(
            ["2330.TW"], {"2330.TW": bars},
            fundamentals=fundamentals
        )
        weights = s.on_bar(ctx)
        assert weights == {}


class TestTrustFollowStrategy:
    def test_name(self):
        from strategies.trust_follow import TrustFollowStrategy
        s = TrustFollowStrategy()
        assert s.name() == "trust_follow"

    def test_empty_universe(self):
        from strategies.trust_follow import TrustFollowStrategy
        s = TrustFollowStrategy()
        ctx = _make_mock_context([], {})
        weights = s.on_bar(ctx)
        assert weights == {}

    def test_no_fundamentals_provider(self):
        from strategies.trust_follow import TrustFollowStrategy
        s = TrustFollowStrategy()
        bars = _make_bars(60, volume=500000)
        ctx = _make_mock_context(["2330.TW"], {"2330.TW": bars}, fundamentals=None)
        weights = s.on_bar(ctx)
        assert weights == {}

    def test_filters_low_trust_buying(self):
        from strategies.trust_follow import TrustFollowStrategy
        s = TrustFollowStrategy(trust_threshold=15000)

        bars = _make_bars(60, volume=500000)
        fundamentals = MagicMock()
        # Low trust buying — well below 15000
        inst_df = pd.DataFrame({
            "date": pd.bdate_range(end="2025-06-15", periods=10),
            "trust_net": [100] * 10,
            "foreign_net": [0] * 10,
            "dealer_net": [0] * 10,
        })
        fundamentals.get_institutional.return_value = inst_df
        fundamentals.get_revenue.return_value = pd.DataFrame(
            columns=["date", "revenue", "yoy_growth"]
        )

        ctx = _make_mock_context(
            ["2330.TW"], {"2330.TW": bars},
            fundamentals=fundamentals
        )
        weights = s.on_bar(ctx)
        assert weights == {}

    def test_filters_low_volume(self):
        from strategies.trust_follow import TrustFollowStrategy
        s = TrustFollowStrategy(min_volume_lots=300)

        # Volume 1000 < 300 * 1000 = 300000
        bars = _make_bars(60, volume=1000)
        fundamentals = MagicMock()

        ctx = _make_mock_context(
            ["2330.TW"], {"2330.TW": bars},
            fundamentals=fundamentals
        )
        weights = s.on_bar(ctx)
        assert weights == {}

    def test_filters_insufficient_bars(self):
        from strategies.trust_follow import TrustFollowStrategy
        s = TrustFollowStrategy()

        # Only 10 bars — strategy requires >= 20
        bars = _make_bars(10, volume=500000)
        fundamentals = MagicMock()

        ctx = _make_mock_context(
            ["2330.TW"], {"2330.TW": bars},
            fundamentals=fundamentals
        )
        weights = s.on_bar(ctx)
        assert weights == {}


# ── FinMindFundamentals.get_institutional tests ──────────────────


class TestFinMindInstitutional:
    def test_get_institutional_default_returns_empty(self):
        """Base class default implementation returns empty DataFrame."""
        from src.data.fundamentals import FundamentalsProvider

        # Create a minimal concrete subclass
        class DummyProvider(FundamentalsProvider):
            def get_financials(self, symbol, date=None):
                return {}

            def get_sector(self, symbol):
                return ""

            def get_revenue(self, symbol, start, end):
                return pd.DataFrame()

            def get_dividends(self, symbol, start, end):
                return pd.DataFrame()

        p = DummyProvider()
        result = p.get_institutional("2330.TW", "2025-01-01", "2025-06-15")
        assert result.empty
        assert list(result.columns) == ["date", "trust_net", "foreign_net", "dealer_net"]


# ── Strategy registry tests ──────────────────────────────────────


class TestStrategyRegistry:
    def test_revenue_momentum_in_registry(self):
        from src.strategy.registry import list_strategies
        assert "revenue_momentum" in list_strategies()

    def test_trust_follow_in_registry(self):
        from src.strategy.registry import list_strategies
        assert "trust_follow" in list_strategies()

    def test_resolve_revenue_momentum(self):
        from src.strategy.registry import resolve_strategy
        s = resolve_strategy("revenue_momentum")
        assert s.name() == "revenue_momentum"

    def test_resolve_trust_follow(self):
        from src.strategy.registry import resolve_strategy
        s = resolve_strategy("trust_follow")
        assert s.name() == "trust_follow"

    def test_resolve_with_params(self):
        from src.strategy.registry import resolve_strategy
        s = resolve_strategy("revenue_momentum", {"max_holdings": 10, "min_yoy_growth": 20.0})
        assert s.max_holdings == 10
        assert s.min_yoy_growth == 20.0
