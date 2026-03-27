"""Auto-generated research factor: rev_triple_composite

accel × zscore × new_high
Academic basis: Multi-signal composite
Direction: factor_combination
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


def compute_rev_triple_composite(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_triple_composite for all symbols at as_of date."""
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

            if len(revenues) < 24:
                continue
            rev_3m = float(np.mean(revenues[-3:]))
            rev_12m = float(np.mean(revenues[-12:]))
            if rev_12m <= 0:
                continue
            accel = rev_3m / rev_12m
            mean_24 = float(np.mean(revenues[-24:]))
            std_24 = float(np.std(revenues[-24:], ddof=1))
            zscore = (revenues[-1] - mean_24) / std_24 if std_24 > 0 else 0
            past_max = float(np.max(revenues[-13:-1])) if len(revenues) >= 13 else float(revenues[-1])
            newhigh = revenues[-1] / past_max if past_max > 0 else 0
            results[sym] = float(accel * zscore * newhigh)

        except Exception:
            continue
    return results
