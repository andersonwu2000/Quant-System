"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """High-low frequency spread: new 20d highs minus new 20d lows over 120d."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 140: continue
            close = b["close"].values[-140:]
            highs = lows = 0
            for i in range(20, 140):
                window = close[i-20:i]
                if close[i] >= np.max(window): highs += 1
                if close[i] <= np.min(window): lows += 1
            results[sym] = (highs - lows) / 120.0
        except Exception: continue
    return results
