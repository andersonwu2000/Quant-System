"""Tests for RevenueMomentumHedgedStrategy — regime detection and delegation."""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────


def _make_mock_context(symbols, bars_data, fundamentals=None, current_time=None):
    """Create a mock Context for strategy testing.

    Uses tz-naive current_time to avoid tz-aware vs tz-naive comparison
    errors when Context.bars() truncates the DataFrame index.
    """
    from src.strategy.base import Context

    feed = MagicMock()
    feed.get_universe.return_value = symbols

    def mock_get_bars(sym):
        return bars_data.get(sym, pd.DataFrame())
    feed.get_bars = mock_get_bars

    portfolio = MagicMock()
    portfolio.nav = Decimal("10000000")
    portfolio.positions = {}

    ctx = Context(
        feed=feed,
        portfolio=portfolio,
        current_time=current_time or datetime(2025, 6, 15),
        fundamentals_provider=fundamentals,
    )
    return ctx


def _make_bars(n=252, trend=0.001, start_price=100.0, volume=500000, seed=42):
    """Generate synthetic OHLCV bars with fixed random seed."""
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


def _make_bull_bars(n=252):
    """Strong uptrend — price well above MA200, low volatility.

    Deterministic: steady 0.15% daily gain, no noise.
    This ensures current >> MA200 and annualized vol << 25%.
    """
    dates = pd.bdate_range(end="2025-06-15", periods=n)
    close = 100.0 * np.cumprod(np.full(n, 1.0015))
    return pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.001,
        "low": close * 0.999,
        "close": close,
        "volume": np.full(n, 500000),
    }, index=dates)


def _make_bear_bars(n=252):
    """Strong downtrend — price below MA200 * 0.95, MA50 < MA200, low vol.

    Deterministic: steady -0.15% daily decline. After 252 days the last
    price is well below the 200-day mean, and MA50 < MA200.  Daily
    returns are constant so annualized vol is ~0 (below 25% threshold).
    """
    dates = pd.bdate_range(end="2025-06-15", periods=n)
    close = 100.0 * np.cumprod(np.full(n, 0.9985))
    return pd.DataFrame({
        "open": close * 0.999,
        "high": close * 1.001,
        "low": close * 0.999,
        "close": close,
        "volume": np.full(n, 500000),
    }, index=dates)


def _make_sideways_bars(n=252):
    """Prices near but slightly below MA200 — sideways regime.

    Flat for most of the period then a small recent dip so that
    current < MA200 but current > MA200 * 0.95 (not bear).
    Low volatility to avoid vol-based bear/sideways triggers.
    """
    dates = pd.bdate_range(end="2025-06-15", periods=n)
    prices = np.full(n, 100.0)
    # Last 30 days: slight decline to put current just below MA200
    for i in range(n - 30, n):
        prices[i] = prices[i - 1] * 0.999
    return pd.DataFrame({
        "open": prices * 0.9999,
        "high": prices * 1.0001,
        "low": prices * 0.9999,
        "close": prices,
        "volume": np.full(n, 500000),
    }, index=dates)


# ── Tests ─────────────────────────────────────────────────────────────


class TestRevenueMomentumHedgedName:
    def test_name(self):
        from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy
        s = RevenueMomentumHedgedStrategy()
        assert s.name() == "revenue_momentum_hedged"


class TestRevenueMomentumHedgedRegistry:
    def test_resolves_from_registry(self):
        from src.strategy.registry import resolve_strategy
        s = resolve_strategy("revenue_momentum_hedged")
        assert s.name() == "revenue_momentum_hedged"


class TestRevenueMomentumHedgedInner:
    def test_inner_strategy_is_revenue_momentum(self):
        from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy
        s = RevenueMomentumHedgedStrategy()
        assert s._inner.name() == "revenue_momentum"


class TestRegimeDetectionBull:
    def test_regime_detection_bull(self):
        """When market proxy is above MA200, returns full (unscaled) weights."""
        from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

        bull_bars = _make_bull_bars(252)
        bars_data = {"0050.TW": bull_bars}

        ctx = _make_mock_context([], bars_data)
        s = RevenueMomentumHedgedStrategy()
        regime = s._detect_regime(ctx)
        assert regime == "bull"

        # Full weights: on_bar delegates to inner, then returns unscaled
        inner_weights = {"2330.TW": 0.10, "2317.TW": 0.08}
        with patch.object(s._inner, "on_bar", return_value=inner_weights):
            result = s.on_bar(ctx)
        assert result == inner_weights


class TestRegimeDetectionBear:
    def test_regime_detection_bear(self):
        """When market is below MA200 * 0.95, returns scaled weights (0.0)."""
        from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

        bear_bars = _make_bear_bars(252)
        bars_data = {"0050.TW": bear_bars}

        ctx = _make_mock_context([], bars_data)
        s = RevenueMomentumHedgedStrategy()
        regime = s._detect_regime(ctx)
        assert regime == "bear"

        inner_weights = {"2330.TW": 0.10, "2317.TW": 0.08}
        with patch.object(s._inner, "on_bar", return_value=inner_weights):
            result = s.on_bar(ctx)
        # bear_scale default is 0.30, so weights should be 30% of inner
        for sym, w in result.items():
            assert abs(w - inner_weights[sym] * 0.30) < 1e-9


class TestRegimeDetectionSideways:
    def test_regime_detection_sideways(self):
        """When prices are near MA200, returns scaled weights (0.3)."""
        from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

        sideways_bars = _make_sideways_bars(252)
        bars_data = {"0050.TW": sideways_bars}

        ctx = _make_mock_context([], bars_data)
        s = RevenueMomentumHedgedStrategy()
        regime = s._detect_regime(ctx)
        assert regime == "sideways"

        inner_weights = {"2330.TW": 0.10, "2317.TW": 0.08}
        with patch.object(s._inner, "on_bar", return_value=inner_weights):
            result = s.on_bar(ctx)
        # sideways_scale default is 0.3
        assert abs(result["2330.TW"] - 0.03) < 1e-9
        assert abs(result["2317.TW"] - 0.024) < 1e-9


class TestEmptyWeightsPassthrough:
    def test_empty_weights_passthrough(self):
        """If inner strategy returns {}, hedged also returns {}."""
        from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy

        bull_bars = _make_bull_bars(252)
        bars_data = {"0050.TW": bull_bars}

        ctx = _make_mock_context([], bars_data)
        s = RevenueMomentumHedgedStrategy()

        with patch.object(s._inner, "on_bar", return_value={}):
            result = s.on_bar(ctx)
        assert result == {}
