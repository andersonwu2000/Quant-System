"""Auto-generated research factor: rev_vs_trend_residual

實際營收 vs 近 6 月線性趨勢的殘差
Academic basis: Earnings surprise (Ball-Brown 1968)
Direction: earnings_surprise_proxy
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


def compute_rev_vs_trend_residual(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_vs_trend_residual for all symbols at as_of date."""
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
            recent_6 = revenues[-6:]
            x = np.arange(len(recent_6))
            coeffs = np.polyfit(x, recent_6, 1)
            # 殘差：實際值 vs 趨勢線在最後一個點的擬合值
            fitted_last = coeffs[0] * (len(recent_6) - 1) + coeffs[1]
            actual = revenues[-1]
            if fitted_last > 0:
                results[sym] = float((actual - fitted_last) / fitted_last)

        except Exception:
            continue
    return results
