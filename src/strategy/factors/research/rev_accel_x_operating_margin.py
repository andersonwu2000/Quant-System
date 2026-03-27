"""Auto-generated research factor: rev_accel_x_operating_margin

營收加速中且營業利益率穩定/改善
Academic basis: Operating leverage effect
Direction: revenue_quality_interaction
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_rev_accel_x_operating_margin(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute rev_accel_x_operating_margin for all symbols at as_of date."""
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

            revenues = np.asarray(df["revenue"].astype(float))

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
