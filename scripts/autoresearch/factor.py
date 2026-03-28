"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """3-factor rank-sum: trend R² + new-high freq + drawdown proximity."""
    r2s: dict[str, float] = {}
    nhs: dict[str, float] = {}
    dds: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 252: continue
            close = b["close"].values[-252:]
            c120 = close[-120:]
            # Trend R² × direction
            x = np.arange(120, dtype=float)
            lc = np.log(c120)
            coef = np.polyfit(x, lc, 1)
            resid = lc - np.polyval(coef, x)
            ss_tot = np.sum((lc - lc.mean()) ** 2)
            if ss_tot < 1e-12: continue
            r2 = 1 - np.sum(resid ** 2) / ss_tot
            r2s[sym] = r2 * (1.0 if coef[0] > 0 else -1.0)
            # New 20d high frequency
            rm = pd.Series(c120).rolling(20).max().values
            nhs[sym] = float(np.nansum(c120[19:] >= rm[19:]) / 101)
            # Drawdown proximity
            dds[sym] = float(close[-1] / np.max(close))
        except Exception: continue
    common = set(r2s) & set(nhs) & set(dds)
    if len(common) < 10: return {}
    syms = sorted(common)
    def rank(d): a = np.array([d[s] for s in syms]); return a.argsort().argsort().astype(float)
    combo = rank(r2s) + rank(nhs) + rank(dds)
    return {syms[i]: float(combo[i]) for i in range(len(syms))}
