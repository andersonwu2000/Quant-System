"""
FinMind 台股 OHLCV 數據源。

免費額度 600 req/hr。支援 .TW/.TWO 後綴自動轉換。
FinMind import 使用 lazy loading，測試可 mock 且未安裝時可 graceful degrade。
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from cachetools import LRUCache

from src.data.feed import DataFeed
from src.data.quality import check_bars
from src.data.sources.finmind_common import ensure_tw_suffix, get_dataloader, strip_tw_suffix
from src.data.sources.parquet_cache import ParquetDiskCache

logger = logging.getLogger(__name__)

# 快取 TTL（秒），預設 24 小時
_CACHE_TTL = 86400


class FinMindFeed(DataFeed):
    """
    FinMind 台股資料源。

    免費 600 req/hr。支援 bare stock ID（"2330"）和 suffixed（"2330.TW"）。
    """

    def __init__(
        self,
        universe: list[str] | None = None,
        token: str = "",
        cache_size: int | None = None,
    ):
        self._token = token
        # Normalize universe: ensure .TW suffix for internal tracking
        self._universe = [ensure_tw_suffix(s) for s in (universe or [])]
        if cache_size is None:
            from src.core.config import get_config

            cache_size = get_config().data_cache_size
        self._cache: LRUCache[str, pd.DataFrame] = LRUCache(maxsize=cache_size)
        self._disk_cache = ParquetDiskCache(prefix="finmind_")

    def _get_dataloader(self) -> Any:
        """Get cached FinMind DataLoader instance."""
        return get_dataloader(self._token)

    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        freq: str = "1d",
    ) -> pd.DataFrame:
        symbol = ensure_tw_suffix(symbol)
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

        # 確保 index 是 DatetimeIndex（快取反序列化後可能退化）
        if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
            self._cache[cache_key] = df

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
        """從 FinMind 下載數據（優先使用本地 Parquet 快取）。"""
        # 嘗試從磁碟快取讀取
        cached = self._disk_cache.load(symbol, freq)
        if cached is not None:
            logger.info("Cache hit for %s (freq=%s)", symbol, freq)
            return cached

        bare_id = strip_tw_suffix(symbol)
        start_str = str(start) if start else "2015-01-01"
        end_str = str(end) if end else None

        logger.info("Downloading %s from FinMind (freq=%s)", symbol, freq)

        try:
            dl = self._get_dataloader()
            kwargs: dict[str, str] = {
                "stock_id": bare_id,
                "start_date": start_str,
            }
            if end_str:
                kwargs["end_date"] = end_str
            raw = dl.taiwan_stock_daily(**kwargs)
        except Exception as e:
            logger.error("Failed to download %s from FinMind: %s", symbol, e)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if raw is None or raw.empty:
            logger.warning("No data returned for %s from FinMind", symbol)
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # Column mapping: FinMind -> standard OHLCV
        df = pd.DataFrame(
            {
                "open": raw["open"],
                "high": raw["max"],
                "low": raw["min"],
                "close": raw["close"],
                "volume": raw["Trading_Volume"],
            }
        )

        # Set date as DatetimeIndex
        df.index = pd.to_datetime(raw["date"])
        df.index.name = None

        # Normalize to tz-naive (consistent with YahooFeed)
        idx = df.index
        if hasattr(idx, "tz") and idx.tz is not None:
            df.index = idx.tz_convert("UTC").tz_localize(None)  # type: ignore[attr-defined]

        df = df.sort_index()

        # 品質檢查
        result = check_bars(df, symbol)
        if not result.ok:
            logger.warning("Data quality issues for %s: %s", symbol, result.issues)

        # 去除 NaN 行
        df = df.dropna()

        # 寫入磁碟快取
        self._disk_cache.save(symbol, freq, df)

        return df

    def get_latest_price(self, symbol: str) -> Decimal:
        symbol = ensure_tw_suffix(symbol)
        df = self.get_bars(symbol)
        if df.empty:
            return Decimal("0")
        return Decimal(str(round(df["close"].iloc[-1], 4)))

    def get_universe(self) -> list[str]:
        return list(self._universe)

    def set_universe(self, symbols: list[str]) -> None:
        self._universe = [ensure_tw_suffix(s) for s in symbols]
