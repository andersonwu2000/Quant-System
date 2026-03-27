"""Auto-generated research factor: rev_yoy_acceleration

營收 YoY 的月度加速度（本月 YoY - 上月 YoY）
Academic basis: Earnings momentum acceleration
Direction: seasonal_revenue_patterns
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


def compute_rev_yoy_acceleration(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_yoy_acceleration for all symbols at as_of date."""
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

            # YoY for each month, then 1st derivative (acceleration)
            if len(revenues) < 24:
                continue
            yoy = []
            for i in range(12, len(revenues)):
                if revenues[i-12] > 0:
                    yoy.append(revenues[i] / revenues[i-12] - 1)
                else:
                    yoy.append(0)
            if len(yoy) < 2:
                continue
            # 1st derivative: latest YoY - previous YoY
            results[sym] = float(yoy[-1] - yoy[-2])

        except Exception:
            continue
    return results
