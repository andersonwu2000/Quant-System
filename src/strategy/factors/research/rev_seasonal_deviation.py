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
            # 40 天營收公布延遲（台灣月營收於次月 10 日前公布）
            usable_cutoff = as_of - pd.DateOffset(days=40)
            df = df[df["date"] <= usable_cutoff].sort_values("date")
            if len(df) < 12:
                continue

            revenues = df["revenue"].astype(float).values

            if len(revenues) < 36:
                continue
            # 用日期欄位的月份匹配（不依賴 index 位置，避免缺月錯位）
            dates = df["date"].values
            current_month = pd.Timestamp(dates[-1]).month
            current_rev = float(df.iloc[-1]["revenue"])
            same_month_revs = []
            for j in range(len(df) - 1):
                if pd.Timestamp(dates[j]).month == current_month:
                    v = float(df.iloc[j]["revenue"])
                    if v > 0:
                        same_month_revs.append(v)
            # 只取最近 3 年同月
            same_month_revs = same_month_revs[-3:]
            if not same_month_revs or np.mean(same_month_revs) <= 0:
                continue
            results[sym] = float(current_rev / np.mean(same_month_revs) - 1)

        except Exception:
            continue
    return results
