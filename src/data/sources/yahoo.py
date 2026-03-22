"""
Yahoo Finance 數據源 — 開發和研究用。
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

import pandas as pd
import yfinance as yf

from src.data.feed import DataFeed
from src.data.quality import check_bars

logger = logging.getLogger(__name__)


class YahooFeed(DataFeed):
    """
    從 Yahoo Finance 取得數據。

    注意：Yahoo Finance 有 rate limit，不適合高頻使用。
    適用於：開發測試、日線級別策略研究。
    """

    def __init__(self, universe: list[str] | None = None):
        self._universe = universe or []
        self._cache: dict[str, pd.DataFrame] = {}

    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        freq: str = "1d",
    ) -> pd.DataFrame:
        cache_key = f"{symbol}_{freq}"

        if cache_key not in self._cache:
            self._cache[cache_key] = self._download(symbol, start, end, freq)

        df = self._cache[cache_key]

        if start is not None:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]

        return df

    def _download(
        self,
        symbol: str,
        start: datetime | str | None,
        end: datetime | str | None,
        freq: str,
    ) -> pd.DataFrame:
        """從 Yahoo Finance 下載數據。"""
        interval_map = {"1d": "1d", "1h": "1h", "5m": "5m", "1m": "1m"}
        interval = interval_map.get(freq, "1d")

        logger.info("Downloading %s from Yahoo Finance (freq=%s)", symbol, freq)

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=str(start) if start else "2015-01-01",
                end=str(end) if end else None,
                interval=interval,
            )
        except Exception as e:
            logger.error("Failed to download %s: %s", symbol, e)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if df.empty:
            logger.warning("No data returned for %s", symbol)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # 標準化欄位名
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].copy()

        # 統一為 tz-naive 避免比較問題
        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)

        df = df.sort_index()

        # 品質檢查
        result = check_bars(df, symbol)
        if not result.ok:
            logger.warning("Data quality issues for %s: %s", symbol, result.issues)

        # 去除 NaN 行
        df = df.dropna()

        return df

    def get_latest_price(self, symbol: str) -> Decimal:
        df = self.get_bars(symbol)
        if df.empty:
            return Decimal("0")
        return Decimal(str(round(df["close"].iloc[-1], 4)))

    def get_universe(self) -> list[str]:
        return list(self._universe)

    def set_universe(self, symbols: list[str]) -> None:
        self._universe = symbols
