"""Auto-generated research factor: rev_consecutive_beat

連續 N 月營收超越去年同月的月數
Academic basis: Earnings consistency premium
Direction: revenue_acceleration_2nd_order
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_consecutive_beat(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_consecutive_beat for all symbols at as_of date."""
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
            # 40 天營收公布延遲
            usable_cutoff = as_of - pd.DateOffset(days=40)
            df = df[df["date"] <= usable_cutoff].sort_values("date")
            if len(df) < 12:
                continue

            revenues = df["revenue"].astype(float).values

            if len(revenues) < 24:
                continue
            count = 0
            for i in range(max(len(revenues)-12, 12), len(revenues)):
                if revenues[i-12] > 0 and revenues[i] > revenues[i-12]:
                    count += 1
            results[sym] = float(count)

        except Exception:
            continue
    return results
