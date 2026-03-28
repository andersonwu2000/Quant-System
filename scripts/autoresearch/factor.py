"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Intraday close strength × new 20d high frequency."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 140: continue
            h = b["high"].values[-60:]
            l = b["low"].values[-60:]
            c = b["close"].values[-60:]
            rng = h - l
            valid = rng > 0
            if valid.sum() < 20: continue
            cs = np.mean((c[valid] - l[valid]) / rng[valid])
            # New high frequency over 120d
            close = b["close"].values
            c140 = close[-140:]
            count = sum(1 for i in range(20, 140) if c140[i] >= np.max(c140[i-20:i]))
            nhf = count / 120.0
            results[sym] = float(cs * nhf)
        except Exception: continue
    return results
