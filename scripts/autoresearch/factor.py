"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Trend strength: close / 200-day SMA - 1."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 200: continue
            close = b["close"].values[-200:]
            sma200 = close.mean()
            if sma200 > 0:
                results[sym] = close[-1] / sma200 - 1
        except Exception: continue
    return results
