"""本地市場數據存儲 — Parquet 格式，永久保存。

所有市場數據下載後存到 data/market/，永不過期。
系統各處（回測、因子分析、實驗框架）統一從這裡讀取。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# 預設存放目錄
_DEFAULT_DIR = "data/market"


class LocalMarketData:
    """本地市場數據存儲。

    存放路徑: data/market/{symbol}_{freq}.parquet
    數據永不過期 — 本地有就用本地的，沒有才需要下載。
    """

    def __init__(self, data_dir: str = _DEFAULT_DIR, prefix: str = "", **_kwargs: object) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._prefix = prefix  # backward compat (finmind uses prefix="finmind_")

    def path(self, symbol: str, freq: str = "1d") -> Path:
        safe = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self._dir / f"{self._prefix}{safe}_{freq}.parquet"

    def exists(self, symbol: str, freq: str = "1d") -> bool:
        return self.path(symbol, freq).exists()

    def load(self, symbol: str, freq: str = "1d") -> pd.DataFrame | None:
        """讀取本地數據。不存在返回 None。"""
        p = self.path(symbol, freq)
        if not p.exists():
            return None
        try:
            df: pd.DataFrame = pd.read_parquet(p)
            if not df.empty and not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            # 統一為 tz-naive，避免與 tz-naive Timestamp 比較時報錯
            if not df.empty and isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
                df.index = df.index.tz_convert("UTC").tz_localize(None)
            return df
        except Exception:
            logger.debug("Failed to read %s", p)
            return None

    def save(self, symbol: str, freq: str, df: pd.DataFrame) -> None:
        """儲存數據到本地。"""
        if df.empty:
            return
        try:
            p = self.path(symbol, freq)
            df.to_parquet(p)
            logger.debug("Saved %s (%d rows) to %s", symbol, len(df), p)
        except Exception as e:
            logger.warning("Failed to save %s: %s", symbol, e)

    def list_symbols(self, freq: str = "1d") -> list[str]:
        """列出本地已有的所有 symbol。"""
        suffix = f"_{freq}.parquet"
        result = []
        for p in self._dir.glob(f"*{suffix}"):
            sym = p.stem.replace(suffix.replace(".parquet", ""), "")
            result.append(sym)
        return sorted(result)

    def covers_range(self, symbol: str, start: str, end: str, freq: str = "1d") -> bool:
        """檢查本地數據是否涵蓋指定日期範圍。"""
        df = self.load(symbol, freq)
        if df is None or df.empty:
            return False
        return bool(
            df.index.min() <= pd.Timestamp(start)
            and df.index.max() >= pd.Timestamp(end) - pd.Timedelta(days=5)
        )


# Backward compat alias
ParquetDiskCache = LocalMarketData


# 全局 singleton
_store: LocalMarketData | None = None


def get_market_data_store() -> LocalMarketData:
    global _store
    if _store is None:
        _store = LocalMarketData()
    return _store
