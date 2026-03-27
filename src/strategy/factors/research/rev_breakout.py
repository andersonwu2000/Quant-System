"""Auto-generated research factor: rev_breakout

本月營收突破近 12 月最高值的幅度
Academic basis: 52-week high effect applied to revenue
Direction: earnings_surprise_proxy
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_breakout(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_breakout for all symbols at as_of date."""
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

            if len(revenues) < 12:
                continue
            recent_6 = revenues[-6:]
            # Linear trend: fit on indices 0..4, predict at index 5
            x = np.arange(len(recent_6))
            coeffs = np.polyfit(x, recent_6, 1)  # [slope, intercept]
            predicted_next = coeffs[0] * len(recent_6) + coeffs[1]
            actual = revenues[-1]
            if predicted_next > 0:
                results[sym] = float((actual - predicted_next) / predicted_next)

        except Exception:
            continue
    return results
