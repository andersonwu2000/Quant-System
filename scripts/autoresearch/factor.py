"""Alpha factor definition — the ONLY file the agent may edit."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_factor(
    symbols: list[str],
    as_of: pd.Timestamp,
    data: dict,
) -> dict[str, float]:
    """Dual-window momentum Sharpe: average of 12-1 and 9-1 Sharpe ratios.
    9-month window may be more stable than 6-month (lower turnover).
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

            def _sharpe(seg):
                r = np.diff(seg) / seg[:-1]
                m = float(np.mean(r))
                s = float(np.std(r, ddof=1))
                return m / s if s > 0 else None

            # 12-0.75 Sharpe (skip 15d)
            s12 = _sharpe(close[-252:-15])
            # 8-0.75 Sharpe
            s6 = _sharpe(close[-168:-15])

            if s12 is None or s6 is None:
                continue

            results[sym] = (s12 + s6) / 2.0

        except Exception:
            continue

    return results
