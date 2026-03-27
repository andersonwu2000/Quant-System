"""Auto-generated research factor: rev_rank_change

近 3 月 vs 近 6 月營收動量比（短期加速度代理）
Academic basis: Cross-sectional momentum (Jegadeesh-Titman)
Direction: revenue_breadth
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_rank_change(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_rank_change for all symbols at as_of date."""
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

            revenues = np.asarray(df["revenue"].astype(float))
            rev_3m = float(np.mean(revenues[-3:]))
            rev_6m = float(np.mean(revenues[-6:]))
            if rev_6m <= 0:
                continue
            results[sym] = float(rev_3m / rev_6m - 1)

        except Exception:
            continue
    return results
