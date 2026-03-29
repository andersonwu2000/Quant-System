"""Alpha factor definition — the ONLY file the agent may edit.

This file defines compute_factor(), which takes market data and returns
a cross-sectional score for each symbol. Higher score = more desirable to hold.

The evaluate.py harness will:
1. Call compute_factor(symbols, as_of, data) for each evaluation date
2. Compute IC against forward returns (with 40-day revenue delay enforced)
3. Run 5-layer validation (L1-L5)
4. Output a composite score

Available data in the `data` dict:
    data["bars"][symbol]       — pd.DataFrame with columns: open, high, low, close, volume
    data["revenue"][symbol]    — pd.DataFrame with columns: date, revenue, yoy_growth
    data["institutional"][symbol] — pd.DataFrame with columns: date, trust_net, foreign_net, dealer_net
    data["pe"][symbol]         — float (latest PE ratio)
    data["pb"][symbol]         — float (latest PB ratio)
    data["roe"][symbol]        — float (latest ROE %)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_factor(
    symbols: list[str],
    as_of: pd.Timestamp,
    data: dict,
) -> dict[str, float]:
    """Compute alpha score for each symbol at the given date.

    Args:
        symbols: list of stock symbols to score
        as_of: evaluation date (revenue data already truncated by 40-day delay)
        data: dict with "bars", "revenue", "institutional", "pe", "pb", "roe"

    Returns:
        dict mapping symbol -> score (higher = more desirable)
        Missing symbols are excluded (return empty dict entry)
    """
    results: dict[str, float] = {}

    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty:
                continue

            # Slice to as_of — bars contains full history, use only up to current date
            close = bars.loc[:as_of, "close"]
            if len(close) < 252:
                continue

            # === Baseline: 12-1 Momentum ===
            # Skip most recent 21 days (short-term reversal)
            ret_12m = float(close.iloc[-22] / close.iloc[-252] - 1)
            results[sym] = ret_12m

        except Exception:
            continue

    return results
