"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """New 20d low avoidance: negative fraction of days making new 20d low."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 140: continue
            close = b["close"].values[-140:]
            count = 0
            for i in range(20, 140):
                if close[i] <= np.min(close[i-20:i]):
                    count += 1
            results[sym] = -count / 120.0
        except Exception: continue
    return results
