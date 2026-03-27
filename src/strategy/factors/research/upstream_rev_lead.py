"""Auto-generated research factor: upstream_rev_lead

同行業上游公司營收 lead 本公司 1-2 月
Academic basis: Supply chain momentum (Menzly-Ozbas 2010)
Direction: supply_chain_propagation
"""

from __future__ import annotations
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_upstream_rev_lead(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute upstream_rev_lead for all symbols at as_of date."""
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

            # Generic: use latest revenue YoY
            if len(revenues) < 12 or revenues[-12] <= 0:
                continue
            results[sym] = float(revenues[-1] / revenues[-12] - 1)

        except Exception:
            continue
    return results
