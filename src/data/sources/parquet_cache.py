"""Shared Parquet disk cache for data feeds."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Default TTL: 24 hours
_DEFAULT_TTL = 86400


class ParquetDiskCache:
    """Parquet-based disk cache with TTL for DataFeed implementations.

    Provides _cache_path, _load_cache, _save_cache with consistent
    path sanitization, TTL checking, and error handling.
    """

    def __init__(self, prefix: str = "", ttl: int = _DEFAULT_TTL):
        self._prefix = prefix
        self._ttl = ttl

    def cache_path(self, symbol: str, freq: str) -> Path:
        from src.core.config import get_config

        cache_dir = Path(get_config().data_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        safe_symbol = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
        filename = f"{self._prefix}{safe_symbol}_{freq}.parquet"
        path = (cache_dir / filename).resolve()
        if not str(path).startswith(str(cache_dir.resolve())):
            raise ValueError(f"Invalid symbol for cache path: {symbol}")
        return path

    def load(self, symbol: str, freq: str) -> pd.DataFrame | None:
        path = self.cache_path(symbol, freq)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self._ttl:
            return None
        try:
            df: pd.DataFrame = pd.read_parquet(path)
            # 確保 index 是 DatetimeIndex（parquet 反序列化後可能退化為 numpy array）
            if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            return df
        except Exception:
            return None

    def save(self, symbol: str, freq: str, df: pd.DataFrame) -> None:
        if df.empty:
            return
        try:
            path = self.cache_path(symbol, freq)
            df.to_parquet(path)
        except Exception as e:
            logger.debug("Failed to cache %s: %s", symbol, e)
