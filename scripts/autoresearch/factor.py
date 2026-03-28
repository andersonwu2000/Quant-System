"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Regime-conditional momentum: 6-1 return when above SMA200, else 0."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 252: continue
            close = b["close"].values
            sma200 = np.mean(close[-200:])
            mom = close[-1] / close[-126] - 1
            results[sym] = mom if close[-1] > sma200 else 0.0
        except Exception: continue
    return results
