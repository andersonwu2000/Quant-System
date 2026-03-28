"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """4-way rank: vol-adj-mom + close-str + new-high + monotonicity."""
    mom_s: dict[str, float] = {}
    cs_s: dict[str, float] = {}
    nh_s: dict[str, float] = {}
    r2_s: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 130: continue
            close = b["close"].values
            c120 = close[-120:]
            # Vol-adj 6-1 momentum
            ret = close[-21] / close[-130] - 1.0
            vol = np.std(np.diff(np.log(close[-130:-20])))
            if vol < 1e-8: continue
            mom_s[sym] = float(ret / vol)
            # Intraday close strength
            h60, l60 = b["high"].values[-60:], b["low"].values[-60:]
            hl = h60 - l60; mask = hl > 1e-8
            if mask.sum() < 20: continue
            cs_s[sym] = float(np.mean((close[-60:][mask] - l60[mask]) / hl[mask]))
            # New 20d high frequency
            rm = pd.Series(c120).rolling(20).max().values
            nh_s[sym] = float(np.nansum(c120[19:] >= rm[19:]) / 101)
            # Monotonicity (Kendall tau proxy on sampled 120d)
            s = c120[::5]  # ~24 points
            n = len(s)
            conc = sum(1 if s[j] > s[i] else -1 for i in range(n) for j in range(i+1, n))
            r2_s[sym] = float(conc / (n * (n - 1) / 2))
        except Exception: continue
    common = set(mom_s) & set(cs_s) & set(nh_s) & set(r2_s)
    if len(common) < 10: return {}
    syms = sorted(common)
    def rank(d): a = np.array([d[s] for s in syms]); return a.argsort().argsort().astype(float)
    combo = rank(mom_s) + rank(cs_s) + rank(nh_s) + rank(r2_s)
    return {syms[i]: float(combo[i]) for i in range(len(syms))}
