"""Tests for Fama-French fundamental factors (Phase I1) and registry entries."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.strategy import factors as flib
from src.strategy.research import FUNDAMENTAL_REGISTRY


# ---------------------------------------------------------------------------
# size_factor
# ---------------------------------------------------------------------------


class TestSizeFactor:
    """size_factor with explicit market_cap and proxy fallback."""

    def test_with_market_cap(self) -> None:
        """Explicit market_cap => -log(market_cap)."""
        bars = pd.DataFrame({"close": [100.0], "volume": [1000]})
        result = flib.size_factor(bars, market_cap=1e10)
        assert "size" in result
        assert result["size"] == pytest.approx(-math.log(1e10))

    def test_with_small_market_cap(self) -> None:
        """Smaller market_cap should give a HIGHER (less negative) score."""
        bars = pd.DataFrame({"close": [100.0], "volume": [1000]})
        small = flib.size_factor(bars, market_cap=1e8)
        large = flib.size_factor(bars, market_cap=1e12)
        assert small["size"] > large["size"]

    def test_proxy_uses_price_times_volume(self) -> None:
        """When market_cap is None, use close[-1] * mean(volume[-20:]) as proxy."""
        dates = pd.date_range("2024-01-01", periods=25, freq="B")
        bars = pd.DataFrame(
            {"close": [50.0] * 25, "volume": [10000] * 25},
            index=dates,
        )
        result = flib.size_factor(bars, market_cap=None)
        expected_proxy = 50.0 * 10000
        assert "size" in result
        assert result["size"] == pytest.approx(-math.log(expected_proxy))

    def test_proxy_short_volume(self) -> None:
        """With fewer than 20 bars, mean all available volume."""
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        bars = pd.DataFrame(
            {"close": [100.0] * 5, "volume": [5000] * 5},
            index=dates,
        )
        result = flib.size_factor(bars, market_cap=None)
        assert "size" in result
        assert result["size"] == pytest.approx(-math.log(100.0 * 5000))

    def test_zero_market_cap_uses_proxy(self) -> None:
        """market_cap=0 falls through to proxy."""
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        bars = pd.DataFrame(
            {"close": [100.0] * 5, "volume": [5000] * 5},
            index=dates,
        )
        result = flib.size_factor(bars, market_cap=0.0)
        assert "size" in result


# ---------------------------------------------------------------------------
# investment_factor
# ---------------------------------------------------------------------------


class TestInvestmentFactor:
    """investment_factor: negative asset growth = CMA direction."""

    def test_positive_growth(self) -> None:
        """Positive asset growth => negative score (aggressive = low)."""
        result = flib.investment_factor(120.0, 100.0)
        assert result == pytest.approx(-0.20)

    def test_negative_growth(self) -> None:
        """Negative asset growth (shrinking) => positive score (conservative = high)."""
        result = flib.investment_factor(80.0, 100.0)
        assert result == pytest.approx(0.20)

    def test_zero_growth(self) -> None:
        """No change => score = 0."""
        result = flib.investment_factor(100.0, 100.0)
        assert result == pytest.approx(0.0)

    def test_zero_prev_assets(self) -> None:
        """Zero previous assets => safe return 0."""
        result = flib.investment_factor(100.0, 0.0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# gross_profitability_factor
# ---------------------------------------------------------------------------


class TestGrossProfitabilityFactor:
    """gross_profitability_factor: (revenue - cogs) / total_assets."""

    def test_positive(self) -> None:
        """Standard case: positive gross profit."""
        result = flib.gross_profitability_factor(revenue=200.0, cogs=120.0, total_assets=400.0)
        assert result == pytest.approx(0.20)

    def test_negative_margin(self) -> None:
        """COGS > Revenue => negative result."""
        result = flib.gross_profitability_factor(revenue=80.0, cogs=120.0, total_assets=400.0)
        assert result == pytest.approx(-0.10)

    def test_zero_total_assets(self) -> None:
        """Zero total_assets => safe return 0."""
        result = flib.gross_profitability_factor(revenue=100.0, cogs=50.0, total_assets=0.0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# Registry entries
# ---------------------------------------------------------------------------


class TestFundamentalRegistryEntries:
    """All three new factors are registered in FUNDAMENTAL_REGISTRY."""

    def test_size_registered(self) -> None:
        assert "size" in FUNDAMENTAL_REGISTRY
        fdef = FUNDAMENTAL_REGISTRY["size"]
        assert fdef.name == "size"
        assert fdef.metric_key == "market_cap"

    def test_investment_registered(self) -> None:
        assert "investment" in FUNDAMENTAL_REGISTRY
        fdef = FUNDAMENTAL_REGISTRY["investment"]
        assert fdef.name == "investment"
        assert fdef.metric_keys == ["total_assets_current", "total_assets_prev"]

    def test_gross_profit_registered(self) -> None:
        assert "gross_profit" in FUNDAMENTAL_REGISTRY
        fdef = FUNDAMENTAL_REGISTRY["gross_profit"]
        assert fdef.name == "gross_profit"
        assert fdef.metric_keys == ["revenue", "cogs", "total_assets"]

    def test_compute_single_metric(self) -> None:
        """FundamentalFactorDef.compute works for single-metric (backward compat)."""
        fdef = FUNDAMENTAL_REGISTRY["value_pe"]
        val = fdef.compute({"pe_ratio": 15.0})
        assert val is not None
        assert val == pytest.approx(1.0 / 15.0)

    def test_compute_multi_metric(self) -> None:
        """FundamentalFactorDef.compute works for multi-metric factors."""
        fdef = FUNDAMENTAL_REGISTRY["gross_profit"]
        val = fdef.compute({"revenue": 200.0, "cogs": 120.0, "total_assets": 400.0})
        assert val is not None
        assert val == pytest.approx(0.20)

    def test_compute_missing_metric_returns_none(self) -> None:
        """Missing metric key returns None."""
        fdef = FUNDAMENTAL_REGISTRY["investment"]
        val = fdef.compute({"total_assets_current": 100.0})  # missing total_assets_prev
        assert val is None

    def test_total_registry_count(self) -> None:
        """FUNDAMENTAL_REGISTRY now has 6 entries (3 original + 3 new)."""
        assert len(FUNDAMENTAL_REGISTRY) == 6
