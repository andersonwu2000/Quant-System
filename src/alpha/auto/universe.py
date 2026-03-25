"""UniverseSelector — dynamic stock pool combining Scanner and static constraints."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig

logger = logging.getLogger(__name__)


@dataclass
class UniverseResult:
    """Result of universe selection."""

    symbols: list[str] = field(default_factory=list)
    excluded_disposition: list[str] = field(default_factory=list)
    excluded_attention: list[str] = field(default_factory=list)
    total_candidates: int = 0


class UniverseSelector:
    """Daily dynamic universe selection.

    Combines ShioajiScanner (dynamic candidates by volume rank) with
    static constraints from UniverseFilter (liquidity, listing age, etc.).
    Falls back to using data keys as universe when scanner is unavailable.
    """

    def __init__(
        self,
        config: AutoAlphaConfig,
        scanner: object | None = None,
    ) -> None:
        self._config = config
        self._scanner = scanner

    def select(
        self,
        data: dict[str, pd.DataFrame] | None = None,
    ) -> UniverseResult:
        """Select today's tradeable universe.

        Parameters
        ----------
        data : dict[str, pd.DataFrame] | None
            Historical OHLCV data keyed by symbol.  Used as fallback
            universe when scanner is unavailable, and for static
            constraint filtering (ADV, listing days).

        Returns
        -------
        UniverseResult
        """
        cfg = self._config

        # Stage 1: obtain dynamic candidates from scanner or data keys
        candidates: list[str]
        excluded_disposition: list[str] = []
        excluded_attention: list[str] = []
        disposition_set: set[str] = set()
        attention_set: set[str] = set()

        if self._scanner is not None:
            try:
                scanner = self._scanner
                # Get top volume stocks
                volume_list = scanner.top_volume(count=cfg.universe_count)  # type: ignore[attr-defined]
                candidates = [d["code"] for d in volume_list]

                # Regulatory exclusions
                if cfg.exclude_disposition:
                    disposition_set = scanner.get_disposition_stocks()  # type: ignore[attr-defined]
                if cfg.exclude_attention:
                    attention_set = scanner.get_attention_stocks()  # type: ignore[attr-defined]
            except Exception:
                logger.warning(
                    "Scanner unavailable, falling back to data keys",
                    exc_info=True,
                )
                candidates = sorted(data.keys()) if data else []
        else:
            # No scanner available — use data keys as universe
            candidates = sorted(data.keys()) if data else []

        total_candidates = len(candidates)

        # Stage 2: apply exclusions
        filtered: list[str] = []
        for sym in candidates:
            if sym in disposition_set:
                excluded_disposition.append(sym)
                continue
            if sym in attention_set:
                excluded_attention.append(sym)
                continue
            filtered.append(sym)

        # Stage 3: apply static constraints from data (ADV, listing days)
        if data:
            filtered = self._apply_static_constraints(filtered, data)

        return UniverseResult(
            symbols=filtered,
            excluded_disposition=excluded_disposition,
            excluded_attention=excluded_attention,
            total_candidates=total_candidates,
        )

    def _apply_static_constraints(
        self,
        candidates: list[str],
        data: dict[str, pd.DataFrame],
    ) -> list[str]:
        """Filter candidates by ADV and listing days using historical data."""
        cfg = self._config
        result: list[str] = []

        for sym in candidates:
            if sym not in data:
                continue
            df = data[sym]
            if df.empty:
                continue

            # Listing days check
            if len(df) < cfg.min_listing_days:
                continue

            # ADV check (average daily volume over last 60 days)
            recent = df.tail(60)
            if "volume" in recent.columns:
                avg_vol = float(recent["volume"].mean())
                if avg_vol < cfg.min_adv:
                    continue

            result.append(sym)

        return result
