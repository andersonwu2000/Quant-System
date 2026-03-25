"""Tests for AlphaDecisionEngine (F1d)."""

from __future__ import annotations


from src.alpha.auto.config import (
    AutoAlphaConfig,
    DecisionConfig,
    FactorScore,
    ResearchSnapshot,
)
from src.alpha.auto.decision import (
    AlphaDecisionEngine,
)
from src.alpha.regime import MarketRegime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_score(
    name: str,
    icir: float = 0.5,
    hit_rate: float = 0.55,
    cost_drag_bps: float = 100.0,
) -> FactorScore:
    return FactorScore(
        name=name,
        ic=0.03,
        icir=icir,
        hit_rate=hit_rate,
        decay_half_life=5,
        turnover=0.1,
        cost_drag_bps=cost_drag_bps,
        long_short_sharpe=1.0,
        eligible=True,
    )


def _make_snapshot(
    factor_scores: dict[str, FactorScore] | None = None,
    regime: MarketRegime = MarketRegime.SIDEWAYS,
) -> ResearchSnapshot:
    scores = factor_scores or {}
    return ResearchSnapshot(
        regime=regime,
        universe=["A", "B", "C"],
        factor_scores=scores,
    )


# ---------------------------------------------------------------------------
# Factor filtering
# ---------------------------------------------------------------------------

class TestFactorFiltering:
    """Factor filtering by ICIR, hit_rate, cost_drag."""

    def test_filter_by_icir(self) -> None:
        """Factors with ICIR below threshold are excluded."""
        scores = {
            "momentum": _make_score("momentum", icir=0.5),  # pass
            "value_pe": _make_score("value_pe", icir=0.1),  # fail
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert "momentum" in result.selected_factors
        assert "value_pe" not in result.selected_factors

    def test_filter_by_hit_rate(self) -> None:
        """Factors with hit rate below threshold are excluded."""
        scores = {
            "momentum": _make_score("momentum", hit_rate=0.60),  # pass
            "rsi": _make_score("rsi", hit_rate=0.45),  # fail
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert "momentum" in result.selected_factors
        assert "rsi" not in result.selected_factors

    def test_filter_by_cost_drag(self) -> None:
        """Factors with cost drag above threshold are excluded."""
        scores = {
            "momentum": _make_score("momentum", cost_drag_bps=50.0),   # pass
            "max_ret": _make_score("max_ret", cost_drag_bps=300.0),     # fail
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert "momentum" in result.selected_factors
        assert "max_ret" not in result.selected_factors

    def test_no_factors_pass(self) -> None:
        """When no factors pass, selected_factors is empty."""
        scores = {
            "bad1": _make_score("bad1", icir=0.01),
            "bad2": _make_score("bad2", hit_rate=0.40),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert result.selected_factors == []
        assert result.factor_weights == {}
        assert "No factors passed" in result.reason

    def test_all_factors_pass(self) -> None:
        """When all factors pass, all are selected."""
        scores = {
            "momentum": _make_score("momentum"),
            "value_pe": _make_score("value_pe"),
            "rsi": _make_score("rsi"),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert len(result.selected_factors) == 3

    def test_boundary_icir_excluded(self) -> None:
        """Factors with ICIR exactly at threshold are excluded (strict >)."""
        scores = {
            "boundary": _make_score("boundary", icir=0.3),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(min_icir=0.3, regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert result.selected_factors == []

    def test_boundary_hit_rate_excluded(self) -> None:
        """Factors with hit_rate exactly at threshold are excluded (strict >)."""
        scores = {
            "boundary": _make_score("boundary", hit_rate=0.52),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(min_hit_rate=0.52, regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert result.selected_factors == []

    def test_combined_filter(self) -> None:
        """Must pass ALL three criteria simultaneously."""
        scores = {
            # passes icir+hit_rate but fails cost_drag
            "high_cost": _make_score("high_cost", icir=0.5, hit_rate=0.6, cost_drag_bps=250.0),
            # passes all
            "good": _make_score("good", icir=0.5, hit_rate=0.6, cost_drag_bps=100.0),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert result.selected_factors == ["good"]


# ---------------------------------------------------------------------------
# Regime bias
# ---------------------------------------------------------------------------

class TestRegimeBias:
    """Regime-aware weight adjustments."""

    def test_bull_regime_boosts_momentum(self) -> None:
        """In BULL, momentum should get a higher weight than without bias."""
        scores = {
            "momentum": _make_score("momentum", icir=0.5),
            "volatility": _make_score("volatility", icir=0.5),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=True))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores, regime=MarketRegime.BULL))

        # Momentum gets 1.5x bias, volatility gets 0.7x bias
        assert result.factor_weights["momentum"] > result.factor_weights["volatility"]

    def test_bear_regime_boosts_volatility(self) -> None:
        """In BEAR, volatility factor should get higher weight."""
        scores = {
            "momentum": _make_score("momentum", icir=0.5),
            "volatility": _make_score("volatility", icir=0.5),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=True))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores, regime=MarketRegime.BEAR))

        # Volatility gets 1.5x, momentum gets 0.5x
        assert result.factor_weights["volatility"] > result.factor_weights["momentum"]

    def test_sideways_regime_boosts_mean_reversion(self) -> None:
        """In SIDEWAYS, mean reversion should get higher weight."""
        scores = {
            "mean_reversion": _make_score("mean_reversion", icir=0.5),
            "momentum": _make_score("momentum", icir=0.5),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=True))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores, regime=MarketRegime.SIDEWAYS))

        assert result.factor_weights["mean_reversion"] > result.factor_weights["momentum"]

    def test_regime_aware_false_skips_adjustment(self) -> None:
        """regime_aware=False gives equal weights when ICIR is the same."""
        scores = {
            "momentum": _make_score("momentum", icir=0.5),
            "volatility": _make_score("volatility", icir=0.5),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores, regime=MarketRegime.BULL))

        # Without regime bias, same ICIR → same weights
        assert abs(result.factor_weights["momentum"] - result.factor_weights["volatility"]) < 1e-10

    def test_unknown_factor_gets_default_multiplier(self) -> None:
        """Factors not in REGIME_FACTOR_BIAS get multiplier 1.0."""
        scores = {
            "custom_factor": _make_score("custom_factor", icir=0.5),
            "momentum": _make_score("momentum", icir=0.5),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=True))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores, regime=MarketRegime.BULL))

        # custom_factor gets 1.0x, momentum gets 1.5x
        assert result.factor_weights["momentum"] > result.factor_weights["custom_factor"]


# ---------------------------------------------------------------------------
# Weight normalisation
# ---------------------------------------------------------------------------

class TestWeightNormalisation:
    """Weights always sum to 1."""

    def test_weights_sum_to_one(self) -> None:
        scores = {
            "a": _make_score("a", icir=0.5),
            "b": _make_score("b", icir=0.8),
            "c": _make_score("c", icir=0.3001),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert abs(sum(result.factor_weights.values()) - 1.0) < 1e-10

    def test_weights_sum_to_one_with_regime(self) -> None:
        scores = {
            "momentum": _make_score("momentum", icir=0.6),
            "volatility": _make_score("volatility", icir=0.4),
            "rsi": _make_score("rsi", icir=0.35),
        }
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=True))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores, regime=MarketRegime.BEAR))

        assert abs(sum(result.factor_weights.values()) - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# DecisionResult dataclass
# ---------------------------------------------------------------------------

class TestDecisionResult:
    """DecisionResult basic checks."""

    def test_regime_stored(self) -> None:
        scores = {"m": _make_score("m")}
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores, regime=MarketRegime.BEAR))

        assert result.regime == MarketRegime.BEAR

    def test_reason_not_empty(self) -> None:
        scores = {"m": _make_score("m")}
        cfg = AutoAlphaConfig(decision=DecisionConfig(regime_aware=False))
        engine = AlphaDecisionEngine(cfg)
        result = engine.decide(_make_snapshot(scores))

        assert result.reason != ""
