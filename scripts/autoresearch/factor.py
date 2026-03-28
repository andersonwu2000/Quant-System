"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Rank-sum of drawdown proximity + new-high frequency."""
    dd_scores: dict[str, float] = {}
    nh_scores: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 252: continue
            close = b["close"].values[-252:]
            # Drawdown proximity: close / 252d peak
            peak = np.max(close)
            if peak < 1e-8: continue
            dd_scores[sym] = float(close[-1] / peak)
            # New 20d high frequency over 120d
            c120 = close[-120:]
            rm = pd.Series(c120).rolling(20).max().values
            nh_scores[sym] = float(np.nansum(c120[19:] >= rm[19:]) / 101)
        except Exception: continue
    common = set(dd_scores) & set(nh_scores)
    if len(common) < 10: return {}
    syms = sorted(common)
    dd_arr = np.array([dd_scores[s] for s in syms])
    nh_arr = np.array([nh_scores[s] for s in syms])
    dd_rank = dd_arr.argsort().argsort().astype(float)
    nh_rank = nh_arr.argsort().argsort().astype(float)
    combo = dd_rank + nh_rank
    return {syms[i]: float(combo[i]) for i in range(len(syms))}
