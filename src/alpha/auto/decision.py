"""AlphaDecisionEngine — factor selection, regime-aware weighting, and decision output."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig, FactorScore, ResearchSnapshot
from src.alpha.auto.dynamic_pool import DynamicFactorPool
from src.alpha.auto.factor_tracker import FactorPerformanceTracker
from src.alpha.auto.store import AlphaStore
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
        "momentum": 0.1,
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
        store: AlphaStore | None = None,
        market_returns: pd.Series | None = None,
    ) -> DecisionResult:
        """Produce a DecisionResult from a ResearchSnapshot.

        Parameters
        ----------
        snapshot:
            Daily research snapshot containing factor scores and regime.
        current_weights:
            Current portfolio weights (reserved for future turnover-aware logic).
        store:
            Optional AlphaStore for dynamic factor pool filtering.  When the
            store contains >= 5 snapshots, ``FactorPerformanceTracker`` and
            ``DynamicFactorPool`` are used to pre-filter factors before the
            ICIR / hit-rate checks.
        market_returns:
            Optional daily market returns series for volatility scaling.
        """
        cfg = self._config

        # Step 0 — dynamic factor pool pre-filter (if enough history)
        pool_active: set[str] | None = None
        pool_probation: list[str] = []
        pool_excluded: list[str] = []

        if store is not None:
            snapshots = store.list_snapshots(limit=5)
            if len(snapshots) >= 5:
                tracker = FactorPerformanceTracker(store)
                pool = DynamicFactorPool(tracker, cfg)
                pool_result = pool.update_pool()
                pool_active = set(pool_result.active)
                pool_probation = pool_result.probation
                pool_excluded = pool_result.excluded
                logger.info(
                    "DynamicFactorPool: %d active, %d probation, %d excluded",
                    len(pool_result.active),
                    len(pool_probation),
                    len(pool_excluded),
                )

        # Step 1 — filter factors
        eligible: list[str] = []
        raw_weights: dict[str, float] = {}

        for name, score in snapshot.factor_scores.items():
            # If dynamic pool is active, skip factors not in the active set
            if pool_active is not None and name not in pool_active:
                continue
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

        # Step 2b — volatility scaling for momentum (Daniel & Moskowitz 2016)
        if (
            cfg.volatility_scaling_enabled
            and market_returns is not None
            and len(market_returns) >= 20
            and "momentum" in raw_weights
        ):
            realized_vol_20d = float(
                market_returns.iloc[-20:].std() * np.sqrt(252)
            )
            if realized_vol_20d > 0:
                scale = cfg.volatility_scaling_target / realized_vol_20d
                raw_weights["momentum"] *= min(scale, 2.0)

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
        if pool_probation:
            reason_parts.append(
                f"probation=[{', '.join(pool_probation)}]"
            )
        if pool_excluded:
            reason_parts.append(
                f"pool_excluded={len(pool_excluded)}"
            )
        reason = "; ".join(reason_parts)

        return DecisionResult(
            selected_factors=eligible,
            factor_weights=factor_weights,
            regime=snapshot.regime,
            reason=reason,
        )

    def explain_regime_adjustment(
        self,
        base_weights: dict[str, float],
        regime: MarketRegime,
    ) -> dict[str, dict[str, Any]]:
        """Explain how regime bias adjusts each factor's weight.

        Parameters
        ----------
        base_weights:
            Pre-regime factor weights (unnormalised is fine; they will be
            treated as relative magnitudes).
        regime:
            Current market regime.

        Returns
        -------
        Dict keyed by factor name, each value containing:
            base_weight, bias, adjusted_weight (normalised), reason.
        """
        bias_map = REGIME_FACTOR_BIAS.get(regime, {})

        _REGIME_REASON: dict[MarketRegime, dict[str, str]] = {
            MarketRegime.BULL: {
                "momentum": "Bull market favors momentum",
                "quality_roe": "Bull market rewards quality growth",
                "volatility": "Volatility factor less effective in bull markets",
                "mean_reversion": "Mean reversion weakens in trending bull markets",
            },
            MarketRegime.BEAR: {
                "volatility": "Low-volatility stocks outperform in bear markets",
                "value_pe": "Value factor strengthens in bear markets",
                "momentum": "Momentum crashes are common in bear markets",
                "max_ret": "Lottery stocks revert harder in downturns",
            },
            MarketRegime.SIDEWAYS: {
                "mean_reversion": "Sideways markets favor mean-reversion strategies",
                "rsi": "RSI signals are stronger in range-bound markets",
                "momentum": "Momentum is weaker without a clear trend",
            },
        }

        regime_reasons = _REGIME_REASON.get(regime, {})

        # Compute adjusted (unnormalised) values
        adjusted_raw: dict[str, float] = {}
        for name, bw in base_weights.items():
            bias = bias_map.get(name, 1.0)
            adjusted_raw[name] = bw * bias

        # Normalise
        total = sum(adjusted_raw.values())
        if total <= 0:
            total = 1.0

        base_total = sum(base_weights.values())
        if base_total <= 0:
            base_total = 1.0

        result: dict[str, dict[str, Any]] = {}
        for name, bw in base_weights.items():
            bias = bias_map.get(name, 1.0)
            adj_norm = adjusted_raw[name] / total
            base_norm = bw / base_total

            if bias > 1.0:
                default_reason = f"{regime.value.capitalize()} market boosts {name}"
            elif bias < 1.0:
                default_reason = f"{regime.value.capitalize()} market penalises {name}"
            else:
                default_reason = "No regime adjustment"

            result[name] = {
                "base_weight": round(base_norm, 6),
                "bias": bias,
                "adjusted_weight": round(adj_norm, 6),
                "reason": regime_reasons.get(name, default_reason),
            }

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _passes_filter(self, score: FactorScore) -> bool:
        """Return True if a factor passes all selection thresholds."""
        cfg = self._config

        if score.icir <= cfg.min_icir:
            return False
        if score.hit_rate <= cfg.min_hit_rate:
            return False
        if score.cost_drag_bps >= cfg.max_cost_drag:
            return False

        # Net alpha check — reject if cost drag exceeds gross alpha
        if cfg.decision.require_positive_net_alpha:
            # Gross alpha proxy: IC * 10000 (converts correlation to bps)
            gross_alpha_bps = abs(score.ic) * 10000
            net_alpha_bps = gross_alpha_bps - score.cost_drag_bps
            if net_alpha_bps <= 0:
                logger.info(
                    "Factor %s rejected: net_alpha=%.0f bps "
                    "(gross=%.0f - cost=%.0f)",
                    score.name,
                    net_alpha_bps,
                    gross_alpha_bps,
                    score.cost_drag_bps,
                )
                return False

        return True
