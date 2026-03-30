"""Auto-generated research factor: rev_slope_12m

12M linear slope
Academic basis: Trend strength
Direction: time_decay_revenue
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

from src.data.registry import parquet_path as _ppath

# Module-level revenue cache — loaded once, reused across calls
_rev_cache: dict[str, pd.DataFrame] = {}

def _get_revenue(sym: str) -> pd.DataFrame | None:
    """Get revenue DataFrame from cache (lazy-load on first access)."""
    if sym in _rev_cache:
        return _rev_cache[sym]
    rev_path = _ppath(sym, "revenue")
    if not rev_path.exists():
        _rev_cache[sym] = pd.DataFrame()
        return None
    try:
        df = pd.read_parquet(rev_path)
        if df.empty or "revenue" not in df.columns:
            _rev_cache[sym] = pd.DataFrame()
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
        _rev_cache[sym] = df
        return df
    except Exception:
        _rev_cache[sym] = pd.DataFrame()
        return None


def compute_rev_slope_12m(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_slope_12m for all symbols at as_of date."""
    results = {}
    usable_cutoff = as_of - pd.DateOffset(days=40)
    for sym in symbols:
        try:
            df = _get_revenue(sym)
            if df is None or df.empty:
                continue
            usable = df[df["date"] <= usable_cutoff]
            if len(usable) < 12:
                continue

            revenues = usable["revenue"].astype(float).values

            if len(revenues) < 12:
                continue
            x = np.arange(12)
            coeffs = np.polyfit(x, revenues[-12:], 1)
            results[sym] = float(coeffs[0])  # slope

        except Exception:
            continue
    return results
