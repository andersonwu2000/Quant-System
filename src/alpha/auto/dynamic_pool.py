"""DynamicFactorPool — select/exclude/probation factors based on historical performance."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.alpha.auto.config import AutoAlphaConfig
from src.alpha.auto.factor_tracker import FactorPerformanceTracker
from src.strategy.research import FACTOR_REGISTRY, FUNDAMENTAL_REGISTRY

logger = logging.getLogger(__name__)

# Defaults — can be overridden via config or constructor args
_DEFAULT_TOP_N = 8
_DEFAULT_MIN_ICIR = 0.2
_DEFAULT_EXCLUSION_DAYS = 30


@dataclass
class FactorPoolResult:
    """Result of dynamic factor pool evaluation."""

    active: list[str] = field(default_factory=list)
    excluded: list[str] = field(default_factory=list)
    probation: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)


class DynamicFactorPool:
    """Dynamically manage which factors are active based on rolling performance.

    Decision rules:
    1. **Include**: ICIR rank in top-N *and* ICIR > ``min_icir_threshold``.
    2. **Exclude**: ICIR consistently below threshold for > ``exclusion_days``
       snapshots (approximated by avg ICIR over the lookback being below
       threshold *and* no improving trend).
    3. **Probation**: factors whose trend is "declining" — warn but keep active.
    """

    def __init__(
        self,
        tracker: FactorPerformanceTracker,
        config: AutoAlphaConfig,
        *,
        top_n: int = _DEFAULT_TOP_N,
        min_icir_threshold: float = _DEFAULT_MIN_ICIR,
        exclusion_days: int = _DEFAULT_EXCLUSION_DAYS,
    ) -> None:
        self._tracker = tracker
        self._config = config
        self._top_n = top_n
        self._min_icir = min_icir_threshold
        self._exclusion_days = exclusion_days

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def get_all_factor_names() -> list[str]:
        """Return all 14 registered factor names (FACTOR_REGISTRY + FUNDAMENTAL_REGISTRY)."""
        names = sorted(set(list(FACTOR_REGISTRY.keys()) + list(FUNDAMENTAL_REGISTRY.keys())))
        return names

    def update_pool(self, lookback: int = 60) -> FactorPoolResult:
        """Analyse all factors and return active/excluded/probation lists.

        Parameters
        ----------
        lookback:
            Number of recent snapshots to consider for ranking.
        """
        summary = self._tracker.get_factor_summary(lookback)
        # Consider both registry factors and factors observed in snapshots
        all_factors = sorted(set(self.get_all_factor_names()) | set(summary.keys()))
        ranking = self._tracker.rank_factors(metric="icir", lookback=lookback)

        # Build quick lookup: factor -> rank, factor -> avg_icir
        rank_map: dict[str, int] = {}
        icir_map: dict[str, float] = {}
        for entry in ranking:
            rank_map[entry["name"]] = entry["rank"]
            icir_map[entry["name"]] = entry["value"]

        active: list[str] = []
        excluded: list[str] = []
        probation: list[str] = []
        changes: list[str] = []

        for name in all_factors:
            info = summary.get(name)
            rank = rank_map.get(name)
            avg_icir = icir_map.get(name, 0.0)

            # Factor not seen in any snapshot — exclude
            if info is None or rank is None:
                excluded.append(name)
                changes.append(f"excluded:{name} (no data)")
                continue

            trend = info.get("trend", "stable")

            # Exclusion: avg ICIR below threshold and not improving
            if avg_icir <= self._min_icir and trend != "improving":
                excluded.append(name)
                changes.append(f"excluded:{name} (avg_icir={avg_icir:.4f})")
                continue

            # Must be in top-N by rank to be active
            if rank > self._top_n and avg_icir <= self._min_icir:
                excluded.append(name)
                changes.append(f"excluded:{name} (rank={rank}, below top-{self._top_n})")
                continue

            # Probation: declining trend but still above threshold
            if trend == "declining":
                probation.append(name)
                active.append(name)  # probation factors stay active
                changes.append(f"probation:{name} (declining trend)")
                continue

            # Active
            active.append(name)

        return FactorPoolResult(
            active=active,
            excluded=excluded,
            probation=probation,
            changes=changes,
        )
