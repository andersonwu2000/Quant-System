"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import pandas as pd
import numpy as np

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Revenue YoY growth / long-term volatility (120d).

    Economic rationale: revenue growth signals business momentum.
    Dividing by 120d realized volatility (more stable than 60d)
    rewards stocks with strong growth and steady price behavior —
    implying the growth is real and sustainable, not driven by
    speculation. Longer vol window reduces estimation noise.
    """
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            rev = data["revenue"].get(sym)
            bars = data["bars"].get(sym)
            if rev is None or rev.empty or bars is None or bars.empty:
                continue
            rdf = rev.copy()
            rdf["date"] = pd.to_datetime(rdf["date"])
            rdf = rdf[rdf["date"] <= as_of].sort_values("date")
            if len(rdf) < 3:
                continue
            yoy = rdf["yoy_growth"].iloc[-1]
            if pd.isna(yoy):
                continue
            bdf = bars.copy()
            bdf.index = pd.to_datetime(bdf.index)
            bdf = bdf[bdf.index <= as_of].sort_index().tail(120)
            if len(bdf) < 80:
                continue
            ret = bdf["close"].pct_change().dropna()
            vol = ret.std()
            if vol <= 0 or pd.isna(vol):
                continue
            results[sym] = float(yoy / vol)
        except Exception:
            continue
    return results
