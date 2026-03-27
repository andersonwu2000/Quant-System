"""Auto-generated research factor: rev_yoy_x_gross_margin_chg

近 3 月 vs 近 12 月營收加速比（毛利率交互待財報資料）
Academic basis: Novy-Marx (2013) gross profitability + revenue momentum
Direction: revenue_quality_interaction
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_yoy_x_gross_margin_chg(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_yoy_x_gross_margin_chg for all symbols at as_of date."""
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

            # Revenue acceleration as proxy for interaction factors
            # (true interaction needs financial_statement data not yet available)
            if len(revenues) < 12 or revenues[-12] <= 0:
                continue
            rev_3m = float(revenues[-3:].mean()) if len(revenues) >= 3 else 0
            rev_12m = float(revenues[-12:].mean()) if len(revenues) >= 12 else 0
            if rev_12m <= 0:
                continue
            results[sym] = float(rev_3m / rev_12m)

        except Exception:
            continue
    return results
