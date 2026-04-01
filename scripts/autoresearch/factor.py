"""Alpha factor definition — the ONLY file the agent may edit."""
from __future__ import annotations
import pandas as pd
import numpy as np

def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:
    """PER mean reversion (current PER vs 2-year average, inverted).

    Economic rationale: when a stock's PER is below its own 2-year
    average, it may be temporarily undervalued relative to its normal
    earnings multiple. This captures mean-reversion in valuations —
    stocks that have de-rated tend to re-rate back toward their
    historical norm. Negative z-score = cheap = buy signal.
    """
    results: dict[str, float] = {}
    for sym in symbols:
        try:
            per = data["per_history"].get(sym)
            if per is None or per.empty:
                continue
            pdf = per.copy()
            pdf["date"] = pd.to_datetime(pdf["date"])
            pdf = pdf[pdf["date"] <= as_of].sort_values("date")
            if len(pdf) < 250:
                continue
            # Use last 500 trading days (~2 years)
            window = pdf["PER"].iloc[-500:] if len(pdf) >= 500 else pdf["PER"]
            window = window.dropna()
            if len(window) < 200:
                continue
            mu = window.mean()
            sigma = window.std()
            if sigma <= 0 or pd.isna(sigma):
                continue
            current = pdf["PER"].iloc[-1]
            if pd.isna(current) or current <= 0:
                continue
            # Negative z-score = cheap = high signal
            z = (current - mu) / sigma
            results[sym] = float(-z)
        except Exception:
            continue
    return results
