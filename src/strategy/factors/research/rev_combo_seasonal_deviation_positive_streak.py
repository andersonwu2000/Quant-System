"""Auto-generated research factor: rev_combo_seasonal_deviation_positive_streak

auto combo: rev_seasonal_deviation × rev_positive_streak
Academic basis: Automated cross-factor combination
Direction: auto_combination
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


def compute_rev_combo_seasonal_deviation_positive_streak(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_combo_seasonal_deviation_positive_streak for all symbols at as_of date."""
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

            if len(revenues) < 36:
                continue
            # 用日期欄位的月份匹配（不依賴 index 位置，避免缺月錯位）
            dates = df["date"].values
            current_month = pd.Timestamp(dates[-1]).month
            current_rev = float(df.iloc[-1]["revenue"])
            same_month_revs = []
            for j in range(len(df) - 1):
                if pd.Timestamp(dates[j]).month == current_month:
                    v = float(df.iloc[j]["revenue"])
                    if v > 0:
                        same_month_revs.append(v)
            # 只取最近 3 年同月
            same_month_revs = same_month_revs[-3:]
            if not same_month_revs or np.mean(same_month_revs) <= 0:
                continue
            results[sym] = float(current_rev / np.mean(same_month_revs) - 1)

        except Exception:
            continue
    return results
