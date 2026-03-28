"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Rank-sum buying pressure 60d + new 20d high frequency 120d."""
    bp_s: dict[str, float] = {}
    nh_s: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 120: continue
            close = b["close"].values[-120:]
            high = b["high"].values[-60:]
            low = b["low"].values[-60:]
            cl60 = close[-60:]
            # Buying pressure
            hl = high - low
            mask = hl > 1e-8
            if mask.sum() < 20: continue
            bp_s[sym] = float(np.sum((cl60[mask] - low[mask])) / np.sum(hl[mask]))
            # New 20d high frequency
            rm = pd.Series(close).rolling(20).max().values
            nh_s[sym] = float(np.nansum(close[19:] >= rm[19:]) / 101)
        except Exception: continue
    common = set(bp_s) & set(nh_s)
    if len(common) < 10: return {}
    syms = sorted(common)
    def rank(d): a = np.array([d[s] for s in syms]); return a.argsort().argsort().astype(float)
    combo = rank(bp_s) + rank(nh_s)
    return {syms[i]: float(combo[i]) for i in range(len(syms))}
