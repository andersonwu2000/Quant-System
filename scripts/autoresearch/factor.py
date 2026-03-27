"""Alpha factor definition — the ONLY file the agent may edit."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_factor(
    symbols: list[str],
    as_of: pd.Timestamp,
    data: dict,
) -> dict[str, float]:
    """Momentum Sharpe: 12-1 daily return mean / std.
    Risk-adjusted momentum — Sharpe ratio of daily returns from day -252 to -21.
    More stable than raw momentum since it penalizes erratic price moves.
    """
    results: dict[str, float] = {}

    for sym in symbols:
        try:
            bars = data["bars"].get(sym)
            if bars is None or bars.empty:
                continue

            b = bars.loc[:as_of]
            if len(b) < 252:
                continue

            close = b["close"].values
            # Daily returns from -252 to -21 (skip recent month)
            segment = close[-252:-21]
            rets = np.diff(segment) / segment[:-1]

            mean_ret = float(np.mean(rets))
            std_ret = float(np.std(rets, ddof=1))
            if std_ret <= 0:
                continue

            results[sym] = mean_ret / std_ret

        except Exception:
            continue

    return results
