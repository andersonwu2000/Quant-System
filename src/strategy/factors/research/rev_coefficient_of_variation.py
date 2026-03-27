"""Auto-generated research factor: rev_coefficient_of_variation

近 12 月營收變異係數的倒數（穩定成長優於暴漲暴跌）
Academic basis: Earnings quality / persistence literature
Direction: revenue_stability
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_coefficient_of_variation(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_coefficient_of_variation for all symbols at as_of date."""
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
            recent = revenues[-12:]
            std = float(np.std(recent))
            mean = float(np.mean(recent))
            if std <= 0 or mean <= 0:
                continue
            # Inverse CV: higher = more stable growth (lower relative volatility)
            results[sym] = float(mean / std)

        except Exception:
            continue
    return results
