"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """High-volume accumulation: rank(vol-weighted close position) × rank(new high freq)."""
    results: dict[str, float] = {}
    raw_cs = {}
    raw_nhf = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 140: continue
            h = b["high"].values[-60:]
            l = b["low"].values[-60:]
            c = b["close"].values[-60:]
            v = b["volume"].values[-60:]
            rng = h - l
            valid = rng > 0
            if valid.sum() < 20: continue
            pos = (c[valid] - l[valid]) / rng[valid]
            vol = v[valid].astype(float)
            tv = vol.sum()
            if tv <= 0: continue
            raw_cs[sym] = np.sum(pos * vol) / tv
            # New high frequency
            close = b["close"].values
            c140 = close[-140:]
            cnt = sum(1 for i in range(20, 140) if c140[i] >= np.max(c140[i-20:i]))
            raw_nhf[sym] = cnt / 120.0
        except Exception: continue
    common = set(raw_cs) & set(raw_nhf)
    if len(common) < 10: return results
    for sym in common:
        results[sym] = float(raw_cs[sym] * raw_nhf[sym])
    return results
