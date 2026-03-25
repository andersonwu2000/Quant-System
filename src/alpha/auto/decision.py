"""AlphaDecisionEngine — factor selection, regime-aware weighting, and decision output."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.alpha.auto.config import AutoAlphaConfig, FactorScore, ResearchSnapshot
from src.alpha.regime import MarketRegime

logger = logging.getLogger(__name__)


# Regime-aware factor bias multipliers.
# Factors not listed for a regime keep multiplier = 1.0.
REGIME_FACTOR_BIAS: dict[MarketRegime, dict[str, float]] = {
    MarketRegime.BULL: {
        "momentum": 1.5,
        "quality_roe": 1.3,
        "volatility": 0.7,
        "mean_reversion": 0.5,
    },
    MarketRegime.BEAR: {
        "volatility": 1.5,
        "value_pe": 1.3,
        "momentum": 0.5,
        "max_ret": 1.2,
    },
    MarketRegime.SIDEWAYS: {
        "mean_reversion": 1.5,
        "rsi": 1.3,
        "momentum": 0.8,
    },
}


@dataclass
class DecisionResult:
    """Output of the decision engine."""

    selected_factors: list[str] = field(default_factory=list)
    factor_weights: dict[str, float] = field(default_factory=dict)
    regime: MarketRegime = MarketRegime.SIDEWAYS
    reason: str = ""


class AlphaDecisionEngine:
    """Factor filtering, regime-aware weight adjustment, and final weight normalisation.

    Pipeline:
        1. Filter factors by ICIR, hit-rate, and cost-drag thresholds.
        2. Optionally apply regime bias multipliers.
        3. Normalise weights to sum = 1.
    """

    def __init__(self, config: AutoAlphaConfig) -> None:
        self._config = config

    def decide(
        self,
        snapshot: ResearchSnapshot,
        current_weights: dict[str, float] | None = None,
    ) -> DecisionResult:
        """Produce a DecisionResult from a ResearchSnapshot.

        Parameters
        ----------
        snapshot:
            Daily research snapshot containing factor scores and regime.
        current_weights:
            Current portfolio weights (reserved for future turnover-aware logic).
        """
        cfg = self._config

        # Step 1 — filter factors
        eligible: list[str] = []
        raw_weights: dict[str, float] = {}

        for name, score in snapshot.factor_scores.items():
            if not self._passes_filter(score):
                continue
            eligible.append(name)
            # Initial weight = abs(ICIR) as a quality proxy
            raw_weights[name] = abs(score.icir)

        if not eligible:
            reason = (
                f"No factors passed filter "
                f"(min_icir={cfg.min_icir}, min_hit_rate={cfg.min_hit_rate}, "
                f"max_cost_drag={cfg.max_cost_drag})"
            )
            logger.warning(reason)
            return DecisionResult(
                selected_factors=[],
                factor_weights={},
                regime=snapshot.regime,
                reason=reason,
            )

        # Step 2 — regime bias
        if cfg.regime_aware:
            bias_map = REGIME_FACTOR_BIAS.get(snapshot.regime, {})
            for name in eligible:
                multiplier = bias_map.get(name, 1.0)
                raw_weights[name] = raw_weights[name] * multiplier

        # Step 3 — normalise
        total = sum(raw_weights.values())
        if total > 0:
            factor_weights = {n: raw_weights[n] / total for n in eligible}
        else:
            factor_weights = {n: 1.0 / len(eligible) for n in eligible}

        reason_parts = [
            f"Selected {len(eligible)} factors",
            f"regime={snapshot.regime.value}",
        ]
        if cfg.regime_aware:
            reason_parts.append("regime_bias=ON")
        reason = "; ".join(reason_parts)

        return DecisionResult(
            selected_factors=eligible,
            factor_weights=factor_weights,
            regime=snapshot.regime,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _passes_filter(self, score: FactorScore) -> bool:
        """Return True if a factor passes all selection thresholds."""
        cfg = self._config
        return (
            score.icir > cfg.min_icir
            and score.hit_rate > cfg.min_hit_rate
            and score.cost_drag_bps < cfg.max_cost_drag
        )
