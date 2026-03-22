"""
DataFeed — 即時行情與歷史數據的統一介面。

回測時用 HistoricalFeed，實盤時用 LiveFeed，策略代碼不變。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal

import pandas as pd

logger = logging.getLogger(__name__)


class DataFeed(ABC):
    """數據源統一介面。"""

    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        freq: str = "1d",
    ) -> pd.DataFrame:
        """
        取得 K 線數據。

        Returns:
            DataFrame with columns: [open, high, low, close, volume]
            index: DatetimeIndex (UTC)
        """

    @abstractmethod
    def get_latest_price(self, symbol: str) -> Decimal:
        """取得最新價格。"""

    @abstractmethod
    def get_universe(self) -> list[str]:
        """取得可交易標的清單。"""


class HistoricalFeed(DataFeed):
    """
    歷史數據 Feed — 用於回測。

    從預載入的 DataFrame dict 提供數據，
    SimContext 負責按時間截斷以保證因果性。
    """

    def __init__(self, data: dict[str, pd.DataFrame] | None = None):
        self._data: dict[str, pd.DataFrame] = data or {}
        self._current_date: datetime | None = None

    def load(self, symbol: str, df: pd.DataFrame) -> None:
        """載入一個標的的歷史數據。"""
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        # 統一為 tz-naive (UTC) 以避免比較問題
        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)
        df = df.sort_index()
        # 確保欄位名稱統一為小寫
        df.columns = [c.lower() for c in df.columns]
        self._data[symbol] = df

    def set_current_date(self, dt: datetime) -> None:
        """回測引擎在每個 bar 前呼叫，限制可見數據。"""
        self._current_date = dt

    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        freq: str = "1d",
    ) -> pd.DataFrame:
        if symbol not in self._data:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        df = self._data[symbol]

        # 因果性保證：截斷到 current_date
        if self._current_date is not None:
            df = df[df.index <= pd.Timestamp(self._current_date)]

        if start is not None:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]

        return df

    def get_latest_price(self, symbol: str) -> Decimal:
        df = self.get_bars(symbol)
        if df.empty:
            return Decimal("0")
        return Decimal(str(df["close"].iloc[-1]))

    def get_universe(self) -> list[str]:
        return list(self._data.keys())
