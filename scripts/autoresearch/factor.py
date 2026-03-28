"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Drawdown proximity: 1 - drawdown from 252d peak (close to peak = good)."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 252: continue
            close = b["close"].values[-252:]
            peak = np.max(close)
            if peak <= 0: continue
            results[sym] = close[-1] / peak
        except Exception: continue
    return results
