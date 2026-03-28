"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """5-way rank: vol-adj-mom + close-str + new-high + monotonicity + trend-R²."""
    mom_s: dict[str, float] = {}
    cs_s: dict[str, float] = {}
    nh_s: dict[str, float] = {}
    mn_s: dict[str, float] = {}
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
            # Monotonicity
            s = c120[::5]
            n = len(s)
            conc = sum(1 if s[j] > s[i] else -1 for i in range(n) for j in range(i+1, n))
            mn_s[sym] = float(conc / (n * (n - 1) / 2))
            # Trend R²
            x = np.arange(120, dtype=float); lc = np.log(c120)
            coef = np.polyfit(x, lc, 1)
            ss_tot = np.sum((lc - lc.mean()) ** 2)
            if ss_tot < 1e-12: continue
            r2 = 1 - np.sum((lc - np.polyval(coef, x)) ** 2) / ss_tot
            r2_s[sym] = r2 * (1.0 if coef[0] > 0 else -1.0)
        except Exception: continue
    common = set(mom_s) & set(cs_s) & set(nh_s) & set(mn_s) & set(r2_s)
    if len(common) < 10: return {}
    syms = sorted(common)
    def rank(d): a = np.array([d[s] for s in syms]); return a.argsort().argsort().astype(float)
    combo = rank(mom_s) + rank(cs_s) + rank(nh_s) + rank(mn_s) + rank(r2_s)
    return {syms[i]: float(combo[i]) for i in range(len(syms))}
