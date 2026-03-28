"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Volume-at-high: volume weighted by how close the close is to the high."""
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
            v = b["volume"].values[-60:]
            rng = h - l
            valid = rng > 0
            if valid.sum() < 20: continue
            # Close position in range, weighted by volume
            pos = (c[valid] - l[valid]) / rng[valid]
            vol = v[valid].astype(float)
            total_vol = vol.sum()
            if total_vol <= 0: continue
            results[sym] = float(np.sum(pos * vol) / total_vol)
        except Exception: continue
    return results
