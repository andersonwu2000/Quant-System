"""Composite growth-value factor: revenue_acceleration × per_value.

Economic rationale: stocks with accelerating revenue growth AND low PER
represent undervalued growth — the market hasn't priced in the acceleration.
Equal-weight rank combination of two L5-validated single factors.

IS ICIR(20d)=+0.364, IS ICIR(60d)=+0.453, OOS ICIR=+0.571 (2026-04-01 test)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Rank-composite of revenue acceleration + PER value."""
    # Factor 1: revenue acceleration (recent 3m YoY growth - prior 3m)
    ra = {}
    for sym in symbols:
        rev = data["revenue"].get(sym)
        if rev is None or "yoy_growth" not in rev.columns:
            continue
        r = rev[rev["date"] <= as_of].dropna(subset=["yoy_growth"])
        if len(r) < 6:
            continue
        recent = r["yoy_growth"].iloc[-3:].mean()
        older = r["yoy_growth"].iloc[-6:-3].mean()
        v = recent - older
        if np.isfinite(v):
            ra[sym] = float(v)

    # Factor 2: negative PER (low PER = high score)
    pv = {}
    for sym in symbols:
        per = data["per_history"].get(sym)
        if per is None or "PER" not in per.columns:
            continue
        d = per[per["date"] <= as_of]
        if len(d) < 1:
            continue
        v = d["PER"].iloc[-1]
        if v > 0:
            pv[sym] = -float(v)

    # Combine: equal-weight rank
    common = sorted(set(ra) & set(pv))
    if len(common) < 10:
        return {}

    ra_sorted = sorted(common, key=lambda s: ra[s])
    pv_sorted = sorted(common, key=lambda s: pv[s])
    ra_rank = {s: i for i, s in enumerate(ra_sorted)}
    pv_rank = {s: i for i, s in enumerate(pv_sorted)}

    return {s: (ra_rank[s] + pv_rank[s]) / 2 for s in common}
