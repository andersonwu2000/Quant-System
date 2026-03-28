"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Price efficiency ratio 120d: net displacement / total path length (signed)."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 120: continue
            close = b["close"].values[-120:]
            net = close[-1] - close[0]
            total = np.sum(np.abs(np.diff(close)))
            if total < 1e-8: continue
            results[sym] = float(net / total)
        except Exception: continue
    return results
