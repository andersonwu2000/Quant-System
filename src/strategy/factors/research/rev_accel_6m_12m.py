"""Auto-generated research factor: rev_accel_6m_12m

6M/12M ratio（standard）
Academic basis: Revenue momentum with varying windows
Direction: multi_period_momentum
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_accel_6m_12m(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_accel_6m_12m for all symbols at as_of date."""
    results = {}
    for sym in symbols:
        try:
            rev_path = FUND_DIR / f"{sym}_revenue.parquet"
            if not rev_path.exists():
                continue
            df = pd.read_parquet(rev_path)
            if df.empty or "revenue" not in df.columns:
                continue
            df["date"] = pd.to_datetime(df["date"])
            # 40 天營收公布延遲（台灣月營收於次月 10 日前公布）
            usable_cutoff = as_of - pd.DateOffset(days=40)
            df = df[df["date"] <= usable_cutoff].sort_values("date")
            if len(df) < 12:
                continue

            revenues = df["revenue"].astype(float).values

            if len(revenues) < 12:
                continue
            rev_short = float(np.mean(revenues[-6:]))
            rev_long = float(np.mean(revenues[-12:]))
            if rev_long <= 0:
                continue
            results[sym] = float(rev_short / rev_long)

        except Exception:
            continue
    return results
