"""FactorPerformanceTracker — historical factor IC analytics from stored snapshots."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.alpha.auto.store import AlphaStore

logger = logging.getLogger(__name__)


@dataclass
class FactorPerformanceSummary:
    """Per-factor performance summary."""

    name: str
    avg_ic: float = 0.0
    avg_icir: float = 0.0
    hit_rate: float = 0.0
    trend: str = "stable"  # "improving", "stable", "declining"
    drawdown: float = 0.0


class FactorPerformanceTracker:
    """Analyse historical factor performance from stored research snapshots.

    All lookback values refer to *number of snapshots* (typically one per
    trading day).
    """

    def __init__(self, store: AlphaStore) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute_cumulative_ic(
        self, factor_name: str, lookback: int = 60
    ) -> list[dict[str, Any]]:
        """Return cumulative IC series for *factor_name*.

        Returns list of ``{"date": <iso-str>, "cumulative_ic": <float>}``
        ordered oldest-first.
        """
        snapshots = self._store.list_snapshots(limit=lookback)
        # list_snapshots returns most-recent-first; reverse for chronological
        snapshots = list(reversed(snapshots))

        cum_ic = 0.0
        result: list[dict[str, Any]] = []
        for snap in snapshots:
            score = snap.factor_scores.get(factor_name)
            if score is not None:
                cum_ic += score.ic
            result.append({
                "date": snap.date.isoformat() if hasattr(snap.date, "isoformat") else str(snap.date),
                "cumulative_ic": round(cum_ic, 6),
            })
        return result

    def compute_factor_drawdown(self, factor_name: str) -> dict[str, Any]:
        """Compute IC drawdown (peak cumulative IC to current decline).

        Returns ``{"peak_ic": float, "current_ic": float, "drawdown": float}``.
        """
        cum_series = self.compute_cumulative_ic(factor_name, lookback=365)
        if not cum_series:
            return {"peak_ic": 0.0, "current_ic": 0.0, "drawdown": 0.0}

        peak = -float("inf")
        max_dd = 0.0
        current = 0.0
        peak_val = 0.0
        for entry in cum_series:
            val = entry["cumulative_ic"]
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
                peak_val = peak
            current = val

        return {
            "peak_ic": round(peak_val, 6),
            "current_ic": round(current, 6),
            "drawdown": round(max_dd, 6),
        }

    def rank_factors(
        self, metric: str = "icir", lookback: int = 60
    ) -> list[dict[str, Any]]:
        """Rank all factors by *metric* over *lookback* snapshots.

        Supported metrics: ``"icir"``, ``"ic"``, ``"hit_rate"``.

        Returns list of ``{"name": str, "value": float, "rank": int}``
        sorted best-first.
        """
        summary = self.get_factor_summary(lookback)
        metric_key = f"avg_{metric}" if metric in ("ic", "icir") else metric
        if metric == "hit_rate":
            metric_key = "hit_rate"

        items: list[tuple[str, float]] = []
        for name, info in summary.items():
            items.append((name, info.get(metric_key, 0.0)))

        # Sort descending (higher is better for all three metrics)
        items.sort(key=lambda x: x[1], reverse=True)

        result: list[dict[str, Any]] = []
        for rank, (name, value) in enumerate(items, start=1):
            result.append({"name": name, "value": round(value, 6), "rank": rank})
        return result

    def get_factor_summary(self, lookback: int = 60) -> dict[str, dict[str, Any]]:
        """Per-factor summary over *lookback* snapshots.

        Returns ``{factor_name: {"avg_ic", "avg_icir", "hit_rate", "trend", "drawdown"}}``.
        """
        snapshots = self._store.list_snapshots(limit=lookback)
        # chronological order
        snapshots = list(reversed(snapshots))

        # Collect per-factor time series
        factor_ics: dict[str, list[float]] = {}
        factor_icirs: dict[str, list[float]] = {}
        factor_hit_rates: dict[str, list[float]] = {}

        for snap in snapshots:
            for name, score in snap.factor_scores.items():
                factor_ics.setdefault(name, []).append(score.ic)
                factor_icirs.setdefault(name, []).append(score.icir)
                factor_hit_rates.setdefault(name, []).append(score.hit_rate)

        all_factor_names = set(factor_ics.keys())

        result: dict[str, dict[str, Any]] = {}
        for name in sorted(all_factor_names):
            ics = factor_ics.get(name, [])
            icirs = factor_icirs.get(name, [])
            hrs = factor_hit_rates.get(name, [])

            avg_ic = sum(ics) / len(ics) if ics else 0.0
            avg_icir = sum(icirs) / len(icirs) if icirs else 0.0
            hit_rate = sum(hrs) / len(hrs) if hrs else 0.0
            trend = self._detect_trend(icirs)

            dd_info = self.compute_factor_drawdown(name)

            result[name] = {
                "avg_ic": round(avg_ic, 6),
                "avg_icir": round(avg_icir, 6),
                "hit_rate": round(hit_rate, 6),
                "trend": trend,
                "drawdown": dd_info["drawdown"],
            }

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_trend(icir_series: list[float]) -> str:
        """Detect factor ICIR trend.

        Compare last-20-day average ICIR vs prior-20-day average ICIR.
        If > +10%: "improving", < -10%: "declining", else "stable".
        """
        if len(icir_series) < 2:
            return "stable"

        # Split into two halves (last 20 vs prior 20)
        mid = max(len(icir_series) - 20, 0)
        if mid == 0:
            # Fewer than 20 entries: split in half
            mid = len(icir_series) // 2

        prior = icir_series[:mid]
        recent = icir_series[mid:]

        if not prior or not recent:
            return "stable"

        avg_prior = sum(prior) / len(prior)
        avg_recent = sum(recent) / len(recent)

        if avg_prior == 0:
            # Cannot compute percentage change; use absolute
            if avg_recent > 0.05:
                return "improving"
            elif avg_recent < -0.05:
                return "declining"
            return "stable"

        pct_change = (avg_recent - avg_prior) / abs(avg_prior)
        if pct_change > 0.10:
            return "improving"
        elif pct_change < -0.10:
            return "declining"
        return "stable"
