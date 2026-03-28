"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Intraday close strength: avg (close-low)/(high-low) over 60d."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 60: continue
            h = b["high"].values[-60:]
            l = b["low"].values[-60:]
            c = b["close"].values[-60:]
            rng = h - l
            mask = rng > 0
            if mask.sum() < 30: continue
            results[sym] = float(np.mean((c[mask] - l[mask]) / rng[mask]))
        except Exception: continue
    return results
