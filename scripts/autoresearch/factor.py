"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Buying pressure ratio 60d: sum(close-low) / sum(high-low)."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 60: continue
            b60 = b.iloc[-60:]
            high = b60["high"].values
            low = b60["low"].values
            close = b60["close"].values
            hl = high - low
            mask = hl > 1e-8
            if mask.sum() < 20: continue
            results[sym] = float(np.sum((close[mask] - low[mask])) / np.sum(hl[mask]))
        except Exception: continue
    return results
