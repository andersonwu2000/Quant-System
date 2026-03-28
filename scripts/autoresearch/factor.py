"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """52-week high proximity × new 20d high frequency."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 252: continue
            close = b["close"].values
            # 52-week high proximity
            high_52w = np.max(close[-252:])
            if high_52w <= 0: continue
            proximity = close[-1] / high_52w
            # New high frequency over 120d
            c140 = close[-140:]
            count = sum(1 for i in range(20, 140) if c140[i] >= np.max(c140[i-20:i]))
            nhf = count / 120.0
            results[sym] = float(proximity * nhf)
        except Exception: continue
    return results
