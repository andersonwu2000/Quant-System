"""Forward-fill limit tests for BacktestEngine._build_matrices()."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.data.feed import HistoricalFeed


def _make_feed_with_gap(
    symbol: str,
    dates: list[str],
    prices: list[float | None],
) -> HistoricalFeed:
    """Build a HistoricalFeed with specific price data (None = missing row)."""
    rows = [
        (d, p) for d, p in zip(dates, prices) if p is not None
    ]
    index = pd.DatetimeIndex([r[0] for r in rows])
    df = pd.DataFrame(
        {
            "open": [r[1] for r in rows],
            "high": [r[1] for r in rows],
            "low": [r[1] for r in rows],
            "close": [r[1] for r in rows],
            "volume": [1000.0] * len(rows),
        },
        index=index,
    )
    feed = HistoricalFeed()
    feed.load(symbol, df)
    return feed


class TestFfillWithinLimit:
    """Prices missing within the limit are forward-filled."""

    def test_within_limit_filled(self) -> None:
        dates = [
            "2024-01-01",
            "2024-01-02",
            "2024-01-03",  # gap starts
            "2024-01-04",
            "2024-01-05",
            "2024-01-06",
            "2024-01-07",
            "2024-01-08",
        ]
        # Provide price on day 1-2, gap for 3 days (within default limit=5), resume day 6
        prices: list[float | None] = [100.0, 101.0, None, None, None, 105.0, 106.0, 107.0]

        feed = _make_feed_with_gap("TEST", dates, prices)

        config = BacktestConfig(universe=["TEST"], max_ffill_days=5)
        engine = BacktestEngine()
        engine._config = config
        engine._build_matrices(feed, ["TEST"])

        matrix = engine._price_matrix
        # Days 3-5 should be forward-filled with 101.0
        for d in ["2024-01-03", "2024-01-04", "2024-01-05"]:
            ts = pd.Timestamp(d)
            if ts in matrix.index:
                assert matrix.loc[ts, "TEST"] == 101.0, (
                    f"Expected 101.0 on {d} (ffill), got {matrix.loc[ts, 'TEST']}"
                )


class TestFfillBeyondLimit:
    """Prices beyond the forward-fill limit become NaN (symbol skipped)."""

    def test_beyond_limit_becomes_nan(self) -> None:
        # Create a feed with a gap of 7 days, exceeding default limit of 5
        all_dates = [f"2024-01-{d:02d}" for d in range(1, 15)]
        prices: list[float | None] = [100.0, 101.0]
        # 7-day gap (days 3-9 missing)
        prices += [None] * 7
        # Resume on day 10
        prices += [110.0, 111.0, 112.0, 113.0, 114.0]

        feed = _make_feed_with_gap("TEST", all_dates, prices)

        config = BacktestConfig(universe=["TEST"], max_ffill_days=5)
        engine = BacktestEngine()
        engine._config = config
        engine._build_matrices(feed, ["TEST"])

        matrix = engine._price_matrix
        # Days within limit (3-7) should be filled
        for d in ["2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07"]:
            ts = pd.Timestamp(d)
            if ts in matrix.index:
                assert not np.isnan(matrix.loc[ts, "TEST"]), f"Day {d} should be filled"

        # Days beyond limit (8-9) should be NaN
        for d in ["2024-01-08", "2024-01-09"]:
            ts = pd.Timestamp(d)
            if ts in matrix.index:
                assert np.isnan(matrix.loc[ts, "TEST"]), (
                    f"Day {d} should be NaN (beyond ffill limit)"
                )


class TestFfillCustomLimit:
    """Custom max_ffill_days value is respected."""

    def test_custom_limit_of_2(self) -> None:
        all_dates = [f"2024-01-{d:02d}" for d in range(1, 10)]
        # Price on day 1, then 4-day gap, then resume
        prices: list[float | None] = [100.0, None, None, None, None, 106.0, 107.0, 108.0, 109.0]

        feed = _make_feed_with_gap("TEST", all_dates, prices)

        config = BacktestConfig(universe=["TEST"], max_ffill_days=2)
        engine = BacktestEngine()
        engine._config = config
        engine._build_matrices(feed, ["TEST"])

        matrix = engine._price_matrix
        # Days 2-3 (within limit=2) should be filled
        for d in ["2024-01-02", "2024-01-03"]:
            ts = pd.Timestamp(d)
            if ts in matrix.index:
                assert matrix.loc[ts, "TEST"] == 100.0, f"Day {d} should be filled to 100.0"

        # Days 4-5 (beyond limit=2) should be NaN
        for d in ["2024-01-04", "2024-01-05"]:
            ts = pd.Timestamp(d)
            if ts in matrix.index:
                assert np.isnan(matrix.loc[ts, "TEST"]), (
                    f"Day {d} should be NaN (beyond custom limit=2)"
                )
