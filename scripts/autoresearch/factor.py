"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Baseline: 12-1 momentum (skip most recent month)."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 252: continue
            ret_12m = b["close"].iloc[-21] / b["close"].iloc[-252] - 1
            results[sym] = float(ret_12m)
        except Exception: continue
    return results
