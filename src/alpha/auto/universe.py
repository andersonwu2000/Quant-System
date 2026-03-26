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

        # Stage 4: size stratification (experiments show this is critical for IC)
        size_filter = getattr(cfg, "size_filter", "all")
        if size_filter != "all" and data and filtered:
            filtered = self._apply_size_filter(filtered, data, size_filter)

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

    @staticmethod
    def _apply_size_filter(
        candidates: list[str],
        data: dict[str, pd.DataFrame],
        size_filter: str,
    ) -> list[str]:
        """Filter by market cap tercile. Experiments (20260326_3.md) show
        RSI ICIR jumps from 0.08 (all) to 0.60 (large-cap) after stratification."""
        import numpy as np

        mcaps: dict[str, float] = {}
        for sym in candidates:
            if sym not in data:
                continue
            df = data[sym]
            if df.empty or "close" not in df.columns or "volume" not in df.columns:
                continue
            recent = df.tail(20)
            mcap = float(recent["close"].mean() * recent["volume"].mean())
            if mcap > 0 and not np.isnan(mcap):
                mcaps[sym] = mcap

        if len(mcaps) < 9:
            return candidates  # Too few for stratification

        sorted_syms = sorted(mcaps.items(), key=lambda x: x[1], reverse=True)
        n = len(sorted_syms) // 3

        if size_filter == "large":
            return [s for s, _ in sorted_syms[:n]]
        elif size_filter == "small":
            return [s for s, _ in sorted_syms[2 * n:]]
        return candidates
