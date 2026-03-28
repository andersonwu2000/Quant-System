"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Trend quality × new highs: R²×sign(slope) × new 20d high frequency."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 140: continue
            close = b["close"].values
            # R² × direction
            c120 = close[-120:]
            x = np.arange(120)
            coeffs = np.polyfit(x, c120, 1)
            fitted = np.polyval(coeffs, x)
            ss_res = np.sum((c120 - fitted) ** 2)
            ss_tot = np.sum((c120 - np.mean(c120)) ** 2)
            if ss_tot == 0: continue
            r2d = (1 - ss_res / ss_tot) * np.sign(coeffs[0])
            # New high frequency
            c140 = close[-140:]
            count = sum(1 for i in range(20, 140) if c140[i] >= np.max(c140[i-20:i]))
            nhf = count / 120.0
            results[sym] = float(r2d * nhf)
        except Exception: continue
    return results
