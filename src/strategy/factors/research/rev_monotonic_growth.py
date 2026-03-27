"""Auto-generated research factor: rev_monotonic_growth

近 6 個月營收是否單調遞增（Kendall tau with time）
Academic basis: Trend consistency / monotonicity
Direction: multi_period_momentum
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_monotonic_growth(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_monotonic_growth for all symbols at as_of date."""
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

            from scipy.stats import kendalltau
            if len(revenues) < 6:
                continue
            recent = revenues[-6:]
            tau, _ = kendalltau(range(len(recent)), recent)
            if np.isnan(tau):
                continue
            results[sym] = float(tau)

        except Exception:
            continue
    return results
