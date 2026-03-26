"""Auto-generated research factor: rev_accel_2nd_derivative

營收加速度的二階導數（加速度的變化率）
Academic basis: Second-order momentum
Direction: revenue_acceleration_2nd_order
"""

from __future__ import annotations
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
            df = df[df["date"] <= as_of].sort_values("date")
            if len(df) < 12:
                continue

            revenues = df["revenue"].astype(float).values

            # YoY for each month
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
            # Acceleration = latest YoY - previous YoY
            results[sym] = float(yoy[-1] - yoy[-2])

        except Exception:
            continue
    return results
