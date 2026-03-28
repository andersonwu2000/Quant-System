"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Rank-sum of trend R² and new-high frequency (additive combo)."""
    r2_scores: dict[str, float] = {}
    nh_scores: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 120: continue
            close = b["close"].values[-120:]
            # Trend R² × direction
            x = np.arange(120, dtype=float)
            lc = np.log(close)
            coef = np.polyfit(x, lc, 1)
            ss_res = np.sum((lc - np.polyval(coef, x)) ** 2)
            ss_tot = np.sum((lc - lc.mean()) ** 2)
            if ss_tot < 1e-12: continue
            r2 = 1 - ss_res / ss_tot
            sign = 1.0 if coef[0] > 0 else -1.0
            r2_scores[sym] = r2 * sign
            # New 20d high frequency
            rolling_max = pd.Series(close).rolling(20).max().values
            nh_scores[sym] = float(np.nansum(close[19:] >= rolling_max[19:]) / 101)
        except Exception: continue
    common = set(r2_scores) & set(nh_scores)
    if len(common) < 10: return {}
    syms = sorted(common)
    r2_arr = np.array([r2_scores[s] for s in syms])
    nh_arr = np.array([nh_scores[s] for s in syms])
    r2_rank = r2_arr.argsort().argsort().astype(float)
    nh_rank = nh_arr.argsort().argsort().astype(float)
    combo = r2_rank + nh_rank
    return {syms[i]: float(combo[i]) for i in range(len(syms))}
