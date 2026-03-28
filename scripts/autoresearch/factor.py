"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Close vs open-to-close range: directional conviction 60d."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 60: continue
            b60 = b.iloc[-60:]
            opn = b60["open"].values
            close = b60["close"].values
            high = b60["high"].values
            low = b60["low"].values
            hl = high - low
            mask = hl > 1e-8
            if mask.sum() < 20: continue
            # Direction: (close - open) / (high - low)
            direction = (close[mask] - opn[mask]) / hl[mask]
            results[sym] = float(np.mean(direction))
        except Exception: continue
    return results
