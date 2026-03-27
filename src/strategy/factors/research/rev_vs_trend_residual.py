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


def compute_rev_vs_trend_residual(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_vs_trend_residual for all symbols at as_of date."""
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
