"""CatalogFeed — DataFeed backed by DataCatalog.

Reads data through the unified DataCatalog layer instead of directly
from Yahoo/FinMind APIs. Uses local parquet files (same as other feeds),
but goes through a single consistent interface.

Usage:
    feed = CatalogFeed(universe=["2330.TW", "2317.TW"])
    df = feed.get_bars("2330.TW", start="2025-01-01", end="2026-03-27")
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

import pandas as pd

from src.data.data_catalog import DataCatalog
from src.data.feed import DataFeed

logger = logging.getLogger(__name__)


class CatalogFeed(DataFeed):
    """DataFeed that reads from the local DataCatalog (parquet files)."""

    def __init__(self, universe: list[str], base_dir: str = "data"):
        self._universe = list(universe)
        self._catalog = DataCatalog(base_dir)

    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        freq: str = "1d",
    ) -> pd.DataFrame:
        """Get OHLCV bars from local parquet via DataCatalog."""
        start_date = _to_date(start) if start else None
        end_date = _to_date(end) if end else None

        df = self._catalog.get("price", symbol, start=start_date, end=end_date)
        if df.empty:
            return df

        # Ensure standard OHLCV columns
        expected = {"open", "high", "low", "close", "volume"}
        available = expected & set(df.columns)
        if len(available) < 5:
            logger.debug("Incomplete OHLCV for %s: %s", symbol, df.columns.tolist())

        return df

    def get_latest_price(self, symbol: str) -> Decimal:
        """Get the most recent close price."""
        df = self._catalog.get("price", symbol)
        if df.empty or "close" not in df.columns:
            return Decimal("0")
        last_close = df["close"].iloc[-1]
        return Decimal(str(last_close))

    def get_universe(self) -> list[str]:
        """Return the configured universe."""
        return list(self._universe)


def _to_date(val: datetime | str | None) -> date | None:
    """Convert various date types to date."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        return date.fromisoformat(val[:10])
    return None
