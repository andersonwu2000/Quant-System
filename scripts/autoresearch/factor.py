"""Alpha factor definition — the ONLY file the agent may edit."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import linregress


def compute_factor(
    symbols: list[str],
    as_of: pd.Timestamp,
    data: dict,
) -> dict[str, float]:
    """OBV slope: t-stat of linear regression on On-Balance Volume (60d).
    OBV accumulates volume on up days and subtracts on down days.
    Rising OBV with positive slope = sustained buying pressure.
    """
    results: dict[str, float] = {}

    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty:
                continue

            b = bars.loc[:as_of]
            if len(b) < 63:
                continue

            close = b["close"].values[-63:]
            volume = b["volume"].values[-63:]

            # OBV calculation
            price_change = np.diff(close)
            obv_changes = np.where(price_change > 0, volume[1:],
                          np.where(price_change < 0, -volume[1:], 0))
            obv = np.cumsum(obv_changes)

            # T-stat of OBV slope
            x = np.arange(len(obv), dtype=float)
            slope, intercept, r, p, se = linregress(x, obv.astype(float))
            if se > 0:
                results[sym] = slope / se

        except Exception:
            continue

    return results
