"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Trend R² × direction: R² of 120d price regression × sign of slope."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 120: continue
            close = b["close"].values[-120:]
            x = np.arange(120)
            coeffs = np.polyfit(x, close, 1)
            fitted = np.polyval(coeffs, x)
            ss_res = np.sum((close - fitted) ** 2)
            ss_tot = np.sum((close - np.mean(close)) ** 2)
            if ss_tot == 0: continue
            r2 = 1 - ss_res / ss_tot
            results[sym] = float(r2 * np.sign(coeffs[0]))
        except Exception: continue
    return results
