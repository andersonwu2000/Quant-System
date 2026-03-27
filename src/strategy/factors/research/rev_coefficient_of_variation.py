"""Auto-generated research factor: rev_coefficient_of_variation

近 12 月營收變異係數的倒數（穩定成長優於暴漲暴跌）
Academic basis: Earnings quality / persistence literature
Direction: revenue_stability
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")

# Module-level revenue cache — loaded once, reused across calls
_rev_cache: dict[str, pd.DataFrame] = {}

def _get_revenue(sym: str) -> pd.DataFrame | None:
    """Get revenue DataFrame from cache (lazy-load on first access)."""
    if sym in _rev_cache:
        return _rev_cache[sym]
    rev_path = FUND_DIR / f"{sym}_revenue.parquet"
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


def compute_rev_coefficient_of_variation(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_coefficient_of_variation for all symbols at as_of date."""
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
            recent = revenues[-12:]
            std = float(np.std(recent))
            mean = float(np.mean(recent))
            if std <= 0 or mean <= 0:
                continue
            # Inverse CV: higher = more stable growth (lower relative volatility)
            results[sym] = float(mean / std)

        except Exception:
            continue
    return results
