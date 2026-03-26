"""
Yahoo Finance 數據源 — 開發和研究用。
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal

import pandas as pd
import yfinance as yf
from cachetools import LRUCache

from src.data.feed import DataFeed
from src.data.quality import check_bars
from src.data.sources.parquet_cache import ParquetDiskCache

logger = logging.getLogger(__name__)

# 快取 TTL（秒），預設 24 小時
_CACHE_TTL = 86400


class YahooFeed(DataFeed):
    """
    從 Yahoo Finance 取得數據。

    注意：Yahoo Finance 有 rate limit，不適合高頻使用。
    適用於：開發測試、日線級別策略研究。
    """

    def __init__(
        self,
        universe: list[str] | None = None,
        cache_size: int | None = None,
    ):
        self._universe = universe or []
        if cache_size is None:
            from src.core.config import get_config
            cache_size = get_config().data_cache_size
        self._cache: LRUCache[str, pd.DataFrame] = LRUCache(maxsize=cache_size)
        self._disk_cache = ParquetDiskCache(prefix="")

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
        else:
            # Ensure cached data covers requested range; re-download if not
            cached = self._cache[cache_key]
            if not cached.empty:
                if start is not None and pd.Timestamp(start) < cached.index.min():
                    self._cache[cache_key] = self._download(symbol, start, end, freq)
                if end is not None and pd.Timestamp(end) > cached.index.max():
                    self._cache[cache_key] = self._download(symbol, start, end, freq)

        df: pd.DataFrame = self._cache[cache_key]

        # 確保 index 是 DatetimeIndex（parquet 快取載入後可能退化）
        if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

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
        """從 Yahoo Finance 下載數據（優先使用本地快取）。"""
        # 嘗試從快取讀取
        cached = self._disk_cache.load(symbol, freq)
        if cached is not None:
            logger.info("Cache hit for %s (freq=%s)", symbol, freq)
            return cached

        interval_map = {"1d": "1d", "1h": "1h", "5m": "5m", "1m": "1m"}
        interval = interval_map.get(freq, "1d")

        logger.info("Downloading %s from Yahoo Finance (freq=%s)", symbol, freq)

        import time

        max_retries = 3
        df = pd.DataFrame()
        for attempt in range(max_retries):
            try:
                # 全域速率限制：每次請求前等待，避免觸發 Yahoo 限流
                time.sleep(0.5)
                ticker = yf.Ticker(symbol)
                # auto_adjust=True: close 已含除權除息調整，回測用調整後價格
                start_str = start.strftime("%Y-%m-%d") if isinstance(start, datetime) else (str(start)[:10] if start else "2015-01-01")
                end_str = end.strftime("%Y-%m-%d") if isinstance(end, datetime) else (str(end)[:10] if end else None)
                df = ticker.history(
                    start=start_str,
                    end=end_str,
                    interval=interval,
                    auto_adjust=True,
                )
                if not df.empty:
                    break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning("Download %s failed (attempt %d/%d), retrying in %ds: %s",
                                   symbol, attempt + 1, max_retries, wait, e)
                    time.sleep(wait)
                else:
                    logger.error("Failed to download %s after %d attempts: %s", symbol, max_retries, e)
                    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if df.empty:
            logger.warning("No data returned for %s", symbol)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # 標準化欄位名
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].copy()

        # 統一為 tz-naive DatetimeIndex 避免比較問題
        dti = pd.DatetimeIndex(df.index)
        if dti.tz is not None:
            df.index = dti.tz_convert("UTC").tz_localize(None)
        else:
            df.index = dti  # 確保 index 始終是 DatetimeIndex

        df = df.sort_index()

        # 品質檢查
        result = check_bars(df, symbol)
        if not result.ok:
            logger.warning("Data quality issues for %s: %s", symbol, result.issues)

        # 去除 NaN 行
        df = df.dropna()

        # 寫入快取
        self._disk_cache.save(symbol, freq, df)

        result_df: pd.DataFrame = df
        return result_df

    def get_latest_price(self, symbol: str) -> Decimal:
        df = self.get_bars(symbol)
        if df.empty:
            return Decimal("0")
        return Decimal(str(round(df["close"].iloc[-1], 4)))

    def get_dividends(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> dict[str, float]:
        """取得股利數據。

        Args:
            symbol: 股票代碼
            start: 起始日期 (YYYY-MM-DD)
            end: 結束日期 (YYYY-MM-DD)

        Returns:
            dict mapping date string (YYYY-MM-DD) to dividend amount per share.
        """
        cache_key = f"{symbol}_dividends"

        if cache_key not in self._cache:
            self._cache[cache_key] = self._download_dividends(symbol, start, end)

        div_df = self._cache[cache_key]
        if div_df.empty:
            return {}

        # Extract dividend column if DataFrame
        series = div_df["dividend"] if "dividend" in div_df.columns else div_df.iloc[:, 0]

        # 確保 index 是 DatetimeIndex（快取反序列化後可能退化）
        if not series.empty and not isinstance(series.index, pd.DatetimeIndex):
            series.index = pd.to_datetime(series.index)

        # Filter to requested range
        mask = (series.index >= pd.Timestamp(start)) & (
            series.index <= pd.Timestamp(end)
        )
        filtered = series[mask]

        result: dict[str, float] = {}
        for ts, amount in filtered.items():
            date_str = ts.strftime("%Y-%m-%d")
            result[date_str] = float(amount)
        return result

    def _download_dividends(
        self,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """從 Yahoo Finance 下載股利數據（優先使用本地快取）。"""
        cached = self._disk_cache.load(symbol, "dividends")
        if cached is not None:
            logger.info("Dividend cache hit for %s", symbol)
            return cached

        logger.info("Downloading dividends for %s from Yahoo Finance", symbol)
        try:
            ticker = yf.Ticker(symbol)
            divs = ticker.dividends
        except Exception as e:
            logger.error("Failed to download dividends for %s: %s", symbol, e)
            return pd.DataFrame(columns=["dividend"])

        if divs is None or divs.empty:
            logger.debug("No dividend data for %s", symbol)
            return pd.DataFrame(columns=["dividend"])

        # Normalize to tz-naive
        if divs.index.tz is not None:
            divs.index = divs.index.tz_convert("UTC").tz_localize(None)

        divs = divs.sort_index()

        # Convert Series to DataFrame for parquet caching and consistent type
        div_df: pd.DataFrame = divs.to_frame(name="dividend")

        self._disk_cache.save(symbol, "dividends", div_df)
        return div_df

    def get_universe(self) -> list[str]:
        return list(self._universe)

    def set_universe(self, symbols: list[str]) -> None:
        self._universe = symbols
