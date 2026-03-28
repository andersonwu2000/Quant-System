"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Volume-confirmed momentum: 6-1 return × volume expansion ratio."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 126: continue
            close = b["close"].values
            vol = b["volume"].values
            mom = close[-1] / close[-126] - 1
            vol_ratio = np.mean(vol[-20:]) / np.mean(vol[-120:])
            results[sym] = mom * vol_ratio
        except Exception: continue
    return results
