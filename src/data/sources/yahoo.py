"""
Yahoo Finance 數據源 — 開發和研究用。
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
import yfinance as yf

from src.data.feed import DataFeed
from src.data.quality import check_bars

logger = logging.getLogger(__name__)

# 快取 TTL（秒），預設 24 小時
_CACHE_TTL = 86400


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
        else:
            # Ensure cached data covers requested range; re-download if not
            cached = self._cache[cache_key]
            if not cached.empty:
                if start is not None and pd.Timestamp(start) < cached.index.min():
                    self._cache[cache_key] = self._download(symbol, start, end, freq)
                if end is not None and pd.Timestamp(end) > cached.index.max():
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
        """從 Yahoo Finance 下載數據（優先使用本地快取）。"""
        # 嘗試從快取讀取
        cached = self._load_cache(symbol, freq)
        if cached is not None:
            logger.info("Cache hit for %s (freq=%s)", symbol, freq)
            return cached

        interval_map = {"1d": "1d", "1h": "1h", "5m": "5m", "1m": "1m"}
        interval = interval_map.get(freq, "1d")

        logger.info("Downloading %s from Yahoo Finance (freq=%s)", symbol, freq)

        try:
            ticker = yf.Ticker(symbol)
            # auto_adjust=True: close 已含除權除息調整，回測用調整後價格
            df = ticker.history(
                start=str(start) if start else "2015-01-01",
                end=str(end) if end else None,
                interval=interval,
                auto_adjust=True,
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

        # 寫入快取
        self._save_cache(symbol, freq, df)

        result_df: pd.DataFrame = df
        return result_df

    def _cache_path(self, symbol: str, freq: str) -> Path:
        from src.config import get_config
        cache_dir = Path(get_config().data_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize symbol to prevent path traversal
        safe_symbol = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
        path = (cache_dir / f"{safe_symbol}_{freq}.parquet").resolve()
        if not str(path).startswith(str(cache_dir.resolve())):
            raise ValueError(f"Invalid symbol for cache path: {symbol}")
        return path

    def _load_cache(self, symbol: str, freq: str) -> pd.DataFrame | None:
        path = self._cache_path(symbol, freq)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > _CACHE_TTL:
            return None
        try:
            return pd.read_parquet(path)
        except Exception:
            return None

    def _save_cache(self, symbol: str, freq: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        try:
            path = self._cache_path(symbol, freq)
            df.to_parquet(path)
        except Exception as e:
            logger.debug("Failed to cache %s: %s", symbol, e)

    def get_latest_price(self, symbol: str) -> Decimal:
        df = self.get_bars(symbol)
        if df.empty:
            return Decimal("0")
        return Decimal(str(round(df["close"].iloc[-1], 4)))

    def get_universe(self) -> list[str]:
        return list(self._universe)

    def set_universe(self, symbols: list[str]) -> None:
        self._universe = symbols
