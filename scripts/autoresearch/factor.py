"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Volatility-adjusted 6-1 momentum: momentum / realized vol."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty: continue
            b = bars.loc[:as_of]
            if len(b) < 126: continue
            close = b["close"].values
            mom = close[-21] / close[-126] - 1
            rets = np.diff(np.log(close[-126:]))
            vol = np.std(rets)
            if vol > 0 and np.isfinite(mom):
                results[sym] = mom / vol
        except Exception: continue
    return results
