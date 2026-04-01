"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import pandas as pd
import numpy as np

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Revenue YoY growth divided by price volatility (growth confidence).

    Economic rationale: revenue growth signals business momentum, but
    high-volatility stocks with strong growth may be speculative or
    priced-in. Dividing by realized volatility (60d) rewards stocks
    where growth is more likely to be sustainably priced — high growth
    with low vol implies the market hasn't fully reacted yet.
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
            bdf = bdf[bdf.index <= as_of].sort_index().tail(60)
            if len(bdf) < 40:
                continue
            ret = bdf["close"].pct_change().dropna()
            vol = ret.std()
            if vol <= 0 or pd.isna(vol):
                continue
            results[sym] = float(yoy / vol)
        except Exception:
            continue
    return results
