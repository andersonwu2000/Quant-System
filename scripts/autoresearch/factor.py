"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import numpy as np
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """ROE quality: higher ROE = better."""
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            roe = data["roe"].get(sym)
            if roe is None or np.isnan(roe): continue
            results[sym] = float(roe)
        except Exception: continue
    return results
