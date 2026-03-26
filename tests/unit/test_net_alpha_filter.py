"""Tests for net alpha factor filtering in AlphaDecisionEngine."""

from __future__ import annotations

from src.alpha.auto.config import (
    AutoAlphaConfig,
    DecisionConfig,
    FactorScore,
    ResearchSnapshot,
)
from src.alpha.auto.decision import AlphaDecisionEngine
from src.alpha.regime import MarketRegime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_score(
    name: str,
    ic: float = 0.03,
    icir: float = 0.6,
    hit_rate: float = 0.55,
    cost_drag_bps: float = 100.0,
) -> FactorScore:
    return FactorScore(
        name=name,
        ic=ic,
        icir=icir,
        hit_rate=hit_rate,
        decay_half_life=5,
        turnover=0.1,
        cost_drag_bps=cost_drag_bps,
        long_short_sharpe=1.0,
        eligible=True,
    )


def _make_snapshot(
    factor_scores: dict[str, FactorScore],
    regime: MarketRegime = MarketRegime.SIDEWAYS,
) -> ResearchSnapshot:
    return ResearchSnapshot(
        regime=regime,
        universe=["A", "B", "C"],
        factor_scores=factor_scores,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNetAlphaHighCostRejected:
    """Factor with high cost_drag is rejected even if ICIR is high."""

    def test_high_cost_drag_rejected(self) -> None:
        """Factor with cost_drag > gross alpha (IC * 10000) is rejected."""
        # IC = 0.03 -> gross_alpha_bps = 300
        # cost_drag_bps = 400 -> net_alpha = -100 bps -> REJECT
        scores = {
            "expensive": _make_score(
                "expensive", ic=0.03, icir=0.8, cost_drag_bps=400.0,
            ),
            "cheap": _make_score(
                "cheap", ic=0.03, icir=0.6, cost_drag_bps=100.0,
            ),
        }
        cfg = AutoAlphaConfig(
            decision=DecisionConfig(
                regime_aware=False,
                require_positive_net_alpha=True,
            ),
        )
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert "expensive" not in result.selected_factors
        assert "cheap" in result.selected_factors


class TestNetAlphaLowCostAccepted:
    """Factor with low cost_drag is accepted."""

    def test_low_cost_drag_accepted(self) -> None:
        """Factor with cost_drag well below gross alpha passes."""
        # IC = 0.05 -> gross_alpha_bps = 500
        # cost_drag_bps = 50 -> net_alpha = 450 bps -> ACCEPT
        scores = {
            "good": _make_score(
                "good", ic=0.05, icir=0.7, cost_drag_bps=50.0,
            ),
        }
        cfg = AutoAlphaConfig(
            decision=DecisionConfig(
                regime_aware=False,
                require_positive_net_alpha=True,
            ),
        )
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert "good" in result.selected_factors


class TestNetAlphaDisabled:
    """require_positive_net_alpha=False disables the check."""

    def test_disabled_allows_negative_net_alpha(self) -> None:
        """When disabled, factor with net_alpha < 0 still passes other filters."""
        # IC = 0.01 -> gross_alpha_bps = 100
        # cost_drag_bps = 150 -> net_alpha = -50 bps
        # But cost_drag < max_cost_drag (200), so it would pass without net alpha check
        scores = {
            "marginal": _make_score(
                "marginal", ic=0.01, icir=0.6, cost_drag_bps=150.0,
            ),
        }
        cfg = AutoAlphaConfig(
            decision=DecisionConfig(
                regime_aware=False,
                require_positive_net_alpha=False,
            ),
        )
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert "marginal" in result.selected_factors


class TestAlpha33Rejected:
    """alpha_33 with cost_drag=2432 would be rejected."""

    def test_alpha_33_high_cost_rejected(self) -> None:
        """alpha_33 (cost_drag_bps=2432, IC=0.02) has net_alpha = 200 - 2432 = -2232 bps."""
        scores = {
            "alpha_33": _make_score(
                "alpha_33", ic=0.02, icir=0.6, cost_drag_bps=2432.0,
            ),
        }
        # Need to raise max_cost_drag so the old filter wouldn't catch it
        cfg = AutoAlphaConfig(
            decision=DecisionConfig(
                regime_aware=False,
                require_positive_net_alpha=True,
                max_cost_drag=3000.0,  # old filter would pass
            ),
        )
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert "alpha_33" not in result.selected_factors
        assert result.selected_factors == []


class TestMeanReversionNetAlpha:
    """mean_reversion with cost_drag=985 and IC=0.05: check net alpha."""

    def test_mean_reversion_positive_net_alpha(self) -> None:
        """IC=0.05 -> gross=500bps, cost=985bps -> net=-485bps -> REJECTED."""
        scores = {
            "mean_reversion": _make_score(
                "mean_reversion", ic=0.05, icir=0.6, cost_drag_bps=985.0,
            ),
        }
        cfg = AutoAlphaConfig(
            decision=DecisionConfig(
                regime_aware=False,
                require_positive_net_alpha=True,
                max_cost_drag=2000.0,  # old filter won't block it
            ),
        )
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        # gross_alpha_bps = 0.05 * 10000 = 500
        # net_alpha_bps = 500 - 985 = -485 < 0 -> REJECTED
        assert "mean_reversion" not in result.selected_factors


class TestNetAlphaEdgeCases:
    """Edge cases for net alpha calculation."""

    def test_exact_zero_net_alpha_rejected(self) -> None:
        """Factor with net_alpha exactly 0 is rejected (must be strictly positive)."""
        # IC = 0.03 -> gross = 300, cost = 300 -> net = 0 -> REJECT
        scores = {
            "zero_net": _make_score(
                "zero_net", ic=0.03, icir=0.6, cost_drag_bps=300.0,
            ),
        }
        cfg = AutoAlphaConfig(
            decision=DecisionConfig(
                regime_aware=False,
                require_positive_net_alpha=True,
            ),
        )
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert "zero_net" not in result.selected_factors
