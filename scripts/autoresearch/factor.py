"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import pandas as pd

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """Revenue growth + value composite (YoY growth / PBR).

    Economic rationale: stocks with strong revenue growth AND
    reasonable valuation (low PBR) offer the best risk-reward.
    High growth justifies a premium, but overpaying erodes returns.
    Dividing YoY growth by PBR rewards growth-at-a-reasonable-price.
    """
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            rev = data["revenue"].get(sym)
            per = data["per_history"].get(sym)
            if rev is None or rev.empty or per is None or per.empty:
                continue
            # Revenue YoY
            rdf = rev.copy()
            rdf["date"] = pd.to_datetime(rdf["date"])
            rdf = rdf[rdf["date"] <= as_of].sort_values("date")
            if len(rdf) < 3: continue
            yoy = rdf["yoy_growth"].iloc[-1]
            if pd.isna(yoy): continue
            # PBR
            pdf = per.copy()
            pdf["date"] = pd.to_datetime(pdf["date"])
            pdf = pdf[pdf["date"] <= as_of].sort_values("date")
            if len(pdf) < 5: continue
            pbr = pdf["PBR"].iloc[-1]
            if pd.isna(pbr) or pbr <= 0: continue
            results[sym] = float(yoy / pbr)
        except Exception:
            continue
    return results
