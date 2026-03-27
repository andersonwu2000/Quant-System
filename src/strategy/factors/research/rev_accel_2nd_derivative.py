"""Auto-generated research factor: rev_accel_2nd_derivative

營收加速度的二階導數（加速度的變化率）
Academic basis: Second-order momentum
Direction: revenue_acceleration_2nd_order
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_accel_2nd_derivative(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_accel_2nd_derivative for all symbols at as_of date."""
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

            # YoY for each month, then 2nd derivative (jerk)
            if len(revenues) < 24:
                continue
            yoy = []
            for i in range(12, len(revenues)):
                if revenues[i-12] > 0:
                    yoy.append(revenues[i] / revenues[i-12] - 1)
                else:
                    yoy.append(0)
            if len(yoy) < 3:
                continue
            # 2nd derivative: (yoy[-1]-yoy[-2]) - (yoy[-2]-yoy[-3])
            accel_now = yoy[-1] - yoy[-2]
            accel_prev = yoy[-2] - yoy[-3]
            results[sym] = float(accel_now - accel_prev)

        except Exception:
            continue
    return results
