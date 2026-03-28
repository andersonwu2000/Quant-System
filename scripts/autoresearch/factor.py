"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """52-week high proximity: close / 252-day high."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 252: continue
            close = b["close"].values[-252:]
            high = b["high"].values[-252:]
            max_high = high.max()
            if max_high > 0:
                results[sym] = close[-1] / max_high
        except Exception: continue
    return results
