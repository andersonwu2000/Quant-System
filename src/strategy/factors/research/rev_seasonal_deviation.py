"""Auto-generated research factor: rev_seasonal_deviation

實際營收 vs 同行業歷史同月平均的偏離
Academic basis: Seasonal anomalies in earnings
Direction: seasonal_revenue_patterns
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_seasonal_deviation(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_seasonal_deviation for all symbols at as_of date."""
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
            df = df[df["date"] <= as_of].sort_values("date")
            if len(df) < 12:
                continue

            revenues = df["revenue"].astype(float).values

            if len(revenues) < 36:
                continue
            # Current month revenue vs same month average of past 3 years
            current = revenues[-1]
            month_idx = len(revenues) - 1
            same_month = [revenues[month_idx - 12*k] for k in range(1, 4) if month_idx - 12*k >= 0]
            if not same_month or np.mean(same_month) <= 0:
                continue
            results[sym] = float(current / np.mean(same_month) - 1)

        except Exception:
            continue
    return results
