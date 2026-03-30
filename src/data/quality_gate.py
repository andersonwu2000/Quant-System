"""Pre-trade data quality gate — fail-closed.

Runs before execute_pipeline(). If the gate fails, trading is halted.
Uses 4-level checks: L1 completeness, L2 freshness, L3 sanity, L4 consistency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from src.data.registry import parquet_path as _parquet_path

logger = logging.getLogger(__name__)

# ── Thresholds ───────────────────────────────────────────────────────

# If more than this fraction of universe fails a check, gate blocks trading
COMPLETENESS_BLOCK_THRESHOLD = 0.05   # L1: >5% missing → BLOCK
FRESHNESS_BLOCK_THRESHOLD = 0.10      # L2: >10% stale → BLOCK
SANITY_BLOCK_THRESHOLD = 0.10         # L3: >10% anomalous → BLOCK

# A symbol's data is "stale" if last bar is older than this many trading days
MAX_STALE_TRADING_DAYS = 3


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    affected_symbols: list[str] = field(default_factory=list)


@dataclass
class GateResult:
    """Result of the pre-trade quality gate."""
    passed: bool
    timestamp: datetime = field(default_factory=datetime.now)
    checks: list[CheckResult] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    universe_size: int = 0
    freshest_date: date | None = None
    stale_symbols: list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "PASS" if self.passed else "BLOCKED"
        parts = [f"QualityGate: {status} ({self.universe_size} symbols)"]
        if self.blocking:
            parts.append(f"Blocking: {'; '.join(self.blocking)}")
        if self.warnings:
            parts.append(f"Warnings: {'; '.join(self.warnings)}")
        if self.freshest_date:
            parts.append(f"Freshest: {self.freshest_date}")
        return " | ".join(parts)


def _read_last_date_fast(path: Path) -> date | None:
    """Read last_date from parquet metadata without loading the full file.

    Falls back to reading the file if metadata is missing (pre-Phase-AD files).
    """
    import pyarrow.parquet as pq

    try:
        meta = pq.read_metadata(path)
        schema_meta = meta.schema.to_arrow_schema().metadata or {}
        last_date_bytes = schema_meta.get(b"last_date")
        if last_date_bytes:
            return date.fromisoformat(last_date_bytes.decode())
    except Exception:
        pass

    # Fallback: read only the index to get max date
    try:
        df = pd.read_parquet(path, columns=[])  # reads index only (0 columns, N rows)
        if len(df) == 0:
            return None
        idx = df.index
        if not isinstance(idx, pd.DatetimeIndex):
            # Need to read at least one column to find dates
            df = pd.read_parquet(path)
            if len(df) == 0:
                return None
            idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)
        return idx.max().date()
    except Exception:
        return None


def _is_recent_trading_day(d: date, reference: date, max_gap: int = MAX_STALE_TRADING_DAYS) -> bool:
    """Check if d is within max_gap calendar days of reference (simple heuristic)."""
    return (reference - d).days <= max_gap + 2  # +2 for weekends


def pre_trade_quality_gate(
    universe: list[str],
    reference_date: date | None = None,
) -> GateResult:
    """Run all quality checks on the universe before trading.

    Args:
        universe: List of symbols to check.
        reference_date: The date we expect data to cover (default: today).

    Returns:
        GateResult with passed=True/False and detailed check results.
    """
    if reference_date is None:
        reference_date = date.today()

    result = GateResult(passed=True, universe_size=len(universe))

    if not universe:
        result.passed = False
        result.blocking.append("Empty universe")
        return result

    # ── L1: Completeness — all symbols have a price parquet ──────────
    missing_symbols = []
    for sym in universe:
        path = _parquet_path(sym, "price")
        if not path.exists():
            missing_symbols.append(sym)

    missing_ratio = len(missing_symbols) / len(universe)
    l1_passed = missing_ratio <= COMPLETENESS_BLOCK_THRESHOLD
    l1 = CheckResult(
        name="L1_completeness",
        passed=l1_passed,
        detail=f"{len(missing_symbols)}/{len(universe)} missing ({missing_ratio:.1%})",
        affected_symbols=missing_symbols,
    )
    result.checks.append(l1)
    if not l1_passed:
        result.passed = False
        result.blocking.append(f"L1: {l1.detail}")

    # ── L2: Freshness — last bar is recent ───────────────────────────
    stale_symbols = []
    freshest: date | None = None

    for sym in universe:
        if sym in missing_symbols:
            continue
        path = _parquet_path(sym, "price")
        try:
            # Try fast path: read last_date from parquet metadata (set by _atomic_write)
            last = _read_last_date_fast(path)
            if last is None:
                stale_symbols.append(sym)
                continue
            if freshest is None or last > freshest:
                freshest = last
            if not _is_recent_trading_day(last, reference_date):
                stale_symbols.append(sym)
        except Exception:
            stale_symbols.append(sym)

    available = len(universe) - len(missing_symbols)
    stale_ratio = len(stale_symbols) / available if available > 0 else 1.0
    l2_passed = stale_ratio <= FRESHNESS_BLOCK_THRESHOLD
    l2 = CheckResult(
        name="L2_freshness",
        passed=l2_passed,
        detail=f"{len(stale_symbols)}/{available} stale ({stale_ratio:.1%})",
        affected_symbols=stale_symbols,
    )
    result.checks.append(l2)
    result.freshest_date = freshest
    result.stale_symbols = stale_symbols
    if not l2_passed:
        result.passed = False
        result.blocking.append(f"L2: {l2.detail}")

    # ── L3: Sanity — close change <11%, high>=low, volume>0 ─────────
    anomalous_symbols = []
    checked = 0
    for sym in universe:
        if sym in missing_symbols or sym in stale_symbols:
            continue
        path = _parquet_path(sym, "price")
        try:
            df = pd.read_parquet(path)
            if df.empty or len(df) < 2:
                continue
            checked += 1

            # Check last bar specifically
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]

            # Daily return > 11% (TW limit is 10%, 11% allows for rounding)
            if prev_row["close"] > 0:
                daily_ret = abs(last_row["close"] / prev_row["close"] - 1)
                if daily_ret > 0.11:
                    anomalous_symbols.append(sym)
                    continue

            # high < low
            if last_row["high"] < last_row["low"]:
                anomalous_symbols.append(sym)
                continue

            # volume <= 0 (suspended stock is ok for gate, just warn)
            if last_row["volume"] <= 0:
                result.warnings.append(f"{sym}: zero volume on last bar")

        except Exception:
            continue

    anomalous_ratio = len(anomalous_symbols) / checked if checked > 0 else 0.0
    l3_passed = anomalous_ratio <= SANITY_BLOCK_THRESHOLD
    l3 = CheckResult(
        name="L3_sanity",
        passed=l3_passed,
        detail=f"{len(anomalous_symbols)}/{checked} anomalous ({anomalous_ratio:.1%})",
        affected_symbols=anomalous_symbols,
    )
    result.checks.append(l3)
    if not l3_passed:
        result.passed = False
        result.blocking.append(f"L3: {l3.detail}")

    # ── L4: Consistency — new bar open vs prev close (warning only) ──
    inconsistent = []
    for sym in universe:
        if sym in missing_symbols or sym in stale_symbols or sym in anomalous_symbols:
            continue
        path = _parquet_path(sym, "price")
        try:
            df = pd.read_parquet(path)
            if len(df) < 2:
                continue
            last_open = df.iloc[-1]["open"]
            prev_close = df.iloc[-2]["close"]
            if prev_close > 0:
                gap = abs(last_open / prev_close - 1)
                if gap > 0.11:
                    inconsistent.append(sym)
        except Exception:
            continue

    l4 = CheckResult(
        name="L4_consistency",
        passed=True,  # L4 is warning-only, never blocks
        detail=f"{len(inconsistent)} symbols with open/prev_close gap > 11%",
        affected_symbols=inconsistent,
    )
    result.checks.append(l4)
    if inconsistent:
        result.warnings.append(f"L4: {l4.detail}")

    # Final log
    if result.passed:
        logger.info(result.summary())
    else:
        logger.error(result.summary())

    return result
