"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """New 10d high frequency: fraction of days making new 10d high over 60d."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 70: continue
            close = b["close"].values[-70:]
            count = 0
            for i in range(10, 70):
                if close[i] >= np.max(close[i-10:i]):
                    count += 1
            results[sym] = count / 60.0
        except Exception: continue
    return results
