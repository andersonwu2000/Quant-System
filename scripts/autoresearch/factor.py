"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """High-low trend: close relative to 120d high-low range midpoint."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 120: continue
            high = np.max(b["high"].values[-120:])
            low = np.min(b["low"].values[-120:])
            if high == low: continue
            results[sym] = (b["close"].values[-1] - low) / (high - low)
        except Exception: continue
    return results
