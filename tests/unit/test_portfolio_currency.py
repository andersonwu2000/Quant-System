"""Unit tests for portfolio currency hedger.

Tests currency exposure analysis, hedge ratio computation, and edge cases.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.portfolio.currency import CurrencyHedger, HedgeConfig, HedgeRecommendation


# ===========================================================================
# 1. Basic hedge analysis
# ===========================================================================


class TestCurrencyHedgerBasic:
    """Tests for CurrencyHedger.analyze basic behavior."""

    def test_no_foreign_exposure(self):
        """Only base currency exposure produces no recommendations."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={"TWD": Decimal("1000000")},
            total_nav=Decimal("1000000"),
        )
        assert recs == []

    def test_single_foreign_exposure(self):
        """Single foreign currency produces one recommendation."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("500000"),
                "USD": Decimal("500000"),
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        assert recs[0].currency == "USD"

    def test_multiple_foreign_exposures(self):
        """Multiple foreign currencies produce multiple recommendations."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("400000"),
                "USD": Decimal("300000"),
                "JPY": Decimal("300000"),
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 2
        currencies = {r.currency for r in recs}
        assert currencies == {"USD", "JPY"}

    def test_recommendation_fields(self):
        """Recommendation has all expected fields populated."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("500000"),
                "USD": Decimal("500000"),
            },
            total_nav=Decimal("1000000"),
        )
        rec = recs[0]
        assert isinstance(rec, HedgeRecommendation)
        assert rec.currency == "USD"
        assert rec.gross_exposure == 500000.0
        assert rec.hedge_ratio >= 0.0
        assert rec.hedge_ratio <= 1.0
        assert rec.hedged_amount >= 0.0
        assert rec.unhedged_amount >= 0.0
        assert isinstance(rec.reason, str)
        assert len(rec.reason) > 0


# ===========================================================================
# 2. Hedge ratio rules
# ===========================================================================


class TestHedgeRatio:
    """Tests for hedge ratio computation rules."""

    def test_small_exposure_no_hedge(self):
        """Exposure < 10% gets hedge_ratio = 0."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("950000"),
                "USD": Decimal("50000"),  # 5%
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        assert recs[0].hedge_ratio == 0.0
        assert recs[0].hedged_amount == 0.0

    def test_moderate_exposure_partial_hedge(self):
        """Exposure 10~40% gets hedge_ratio = 0.5."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("700000"),
                "USD": Decimal("300000"),  # 30%
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        assert recs[0].hedge_ratio == 0.5
        assert recs[0].hedged_amount == pytest.approx(150000.0)

    def test_high_exposure_higher_hedge(self):
        """Exposure > 40% gets hedge to max_unhedged_pct."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("300000"),
                "USD": Decimal("700000"),  # 70%
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        rec = recs[0]
        # hedge_ratio = 1 - max_unhedged_pct / exposure_pct = 1 - 0.40/0.70 ≈ 0.4286
        expected = 1.0 - (0.40 / 0.70)
        assert rec.hedge_ratio == pytest.approx(expected, abs=0.01)
        assert rec.hedge_ratio > 0.0
        assert rec.hedge_ratio <= 1.0

    def test_exactly_10_percent(self):
        """10% exposure gets partial hedge (boundary)."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("900000"),
                "USD": Decimal("100000"),  # 10%
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        assert recs[0].hedge_ratio == 0.5

    def test_exactly_40_percent(self):
        """40% exposure gets partial hedge (boundary)."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("600000"),
                "USD": Decimal("400000"),  # 40%
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        assert recs[0].hedge_ratio == 0.5


# ===========================================================================
# 3. Below minimum threshold
# ===========================================================================


class TestMinimumThreshold:
    """Tests for min_hedge_amount threshold."""

    def test_below_minimum_no_hedge(self):
        """Exposure below min_hedge_amount gets no hedge."""
        hedger = CurrencyHedger(HedgeConfig(min_hedge_amount=20000.0))
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("990000"),
                "USD": Decimal("5000"),  # Below min
            },
            total_nav=Decimal("995000"),
        )
        assert len(recs) == 1
        assert recs[0].hedge_ratio == 0.0
        assert recs[0].reason == "Exposure below minimum threshold"

    def test_above_minimum_may_hedge(self):
        """Exposure above min_hedge_amount may get hedged."""
        hedger = CurrencyHedger(HedgeConfig(min_hedge_amount=1000.0))
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("500000"),
                "USD": Decimal("500000"),
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        # 50% exposure -> hedge_ratio > 0
        assert recs[0].hedge_ratio > 0.0


# ===========================================================================
# 4. Custom config
# ===========================================================================


class TestCustomConfig:
    """Tests with custom HedgeConfig."""

    def test_custom_base_currency(self):
        """Custom base currency filters correctly."""
        hedger = CurrencyHedger(HedgeConfig(base_currency="USD"))
        recs = hedger.analyze(
            currency_exposure={
                "USD": Decimal("500000"),
                "TWD": Decimal("300000"),
                "JPY": Decimal("200000"),
            },
            total_nav=Decimal("1000000"),
        )
        currencies = {r.currency for r in recs}
        assert "USD" not in currencies
        assert "TWD" in currencies
        assert "JPY" in currencies

    def test_custom_hedge_cost(self):
        """Custom hedge cost is reflected in annual_cost_bps."""
        hedger = CurrencyHedger(HedgeConfig(hedge_cost_annual_bps=100.0))
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("700000"),
                "USD": Decimal("300000"),
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        # 30% exp -> hedge_ratio=0.5 -> cost = 100 * 0.5 = 50 bps
        assert recs[0].annual_cost_bps == pytest.approx(50.0)

    def test_custom_max_unhedged_pct(self):
        """Custom max_unhedged_pct affects high exposure hedge ratio."""
        hedger = CurrencyHedger(HedgeConfig(max_unhedged_pct=0.20))
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("300000"),
                "USD": Decimal("700000"),  # 70%
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        # Target: unhedged = 20%, so hedge_ratio = 1 - 0.20/0.70 ≈ 0.714
        expected = 1.0 - (0.20 / 0.70)
        assert recs[0].hedge_ratio == pytest.approx(expected, abs=0.01)


# ===========================================================================
# 5. Edge cases
# ===========================================================================


class TestEdgeCases:
    """Edge cases for CurrencyHedger."""

    def test_empty_exposure(self):
        """Empty exposure dict produces no recommendations."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={},
            total_nav=Decimal("1000000"),
        )
        assert recs == []

    def test_zero_nav(self):
        """Zero NAV doesn't crash (avoids division by zero)."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={"USD": Decimal("100000")},
            total_nav=Decimal("0"),
        )
        # Should return recommendations without crashing
        assert len(recs) == 1

    def test_negative_exposure(self):
        """Negative exposure (short) is handled."""
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            currency_exposure={
                "TWD": Decimal("1200000"),
                "USD": Decimal("-200000"),  # Short USD
            },
            total_nav=Decimal("1000000"),
        )
        assert len(recs) == 1
        # -200000 -> abs = 200000 -> 20% -> hedge_ratio = 0.5
        assert recs[0].hedge_ratio == 0.5

    def test_to_dict(self):
        """HedgeRecommendation.to_dict returns expected format."""
        rec = HedgeRecommendation(
            currency="USD",
            gross_exposure=500000.0,
            hedge_ratio=0.5,
            hedged_amount=250000.0,
            unhedged_amount=250000.0,
            annual_cost_bps=25.0,
            reason="Moderate exposure (50%), partial hedge",
        )
        d = rec.to_dict()
        assert d["currency"] == "USD"
        assert d["gross_exposure"] == 500000.0
        assert d["hedge_ratio"] == 0.5
        assert d["hedged_amount"] == 250000.0
        assert d["unhedged_amount"] == 250000.0
        assert d["annual_cost_bps"] == 25.0
        assert isinstance(d["reason"], str)

    def test_only_base_currency_no_recs(self):
        """Only base currency returns empty list."""
        hedger = CurrencyHedger(HedgeConfig(base_currency="TWD"))
        recs = hedger.analyze(
            currency_exposure={"TWD": Decimal("1000000")},
            total_nav=Decimal("1000000"),
        )
        assert recs == []
