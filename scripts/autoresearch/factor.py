"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Rank-sum of monotonicity (Kendall) + new-high frequency 120d."""
    mono_s: dict[str, float] = {}
    nh_s: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 120: continue
            close = b["close"].values[-120:]
            # Monotonicity: sample every 5d
            s = close[::5]
            n = len(s)
            conc = sum(1 if s[j] > s[i] else -1 for i in range(n) for j in range(i+1, n))
            mono_s[sym] = float(conc / (n * (n - 1) / 2))
            # New 20d high frequency
            rm = pd.Series(close).rolling(20).max().values
            nh_s[sym] = float(np.nansum(close[19:] >= rm[19:]) / 101)
        except Exception: continue
    common = set(mono_s) & set(nh_s)
    if len(common) < 10: return {}
    syms = sorted(common)
    def rank(d): a = np.array([d[s] for s in syms]); return a.argsort().argsort().astype(float)
    combo = rank(mono_s) + rank(nh_s)
    return {syms[i]: float(combo[i]) for i in range(len(syms))}
