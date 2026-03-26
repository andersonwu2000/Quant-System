"""
策略基類與上下文 — 整個策略層唯一需要繼承的介面。

設計決策：
- on_bar 返回目標權重 dict，不是訂單
- Context 保證時間因果性（回測時截斷未來數據）
- 回測與實盤共用同一個 Strategy 介面
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from decimal import Decimal

import pandas as pd

from src.data.feed import DataFeed
from src.data.fundamentals import FundamentalsProvider
from src.core.models import Portfolio

logger = logging.getLogger(__name__)


class Context:
    """
    策略的唯一數據入口。

    回測時：SimContext 會限制可見數據 ≤ current_date
    實盤時：LiveContext 提供即時數據
    """

    def __init__(
        self,
        feed: DataFeed,
        portfolio: Portfolio,
        current_time: datetime | None = None,
        fundamentals_provider: FundamentalsProvider | None = None,
    ):
        self._feed = feed
        self._portfolio = portfolio
        self._current_time = current_time
        self._fundamentals = fundamentals_provider
        self._logger = logging.getLogger("strategy")

    def bars(self, symbol: str, lookback: int = 252) -> pd.DataFrame:
        """
        取得歷史 K 線。

        回測時自動截斷到當前模擬時間，保證因果性。
        """
        df = self._feed.get_bars(symbol)
        if df.empty:
            return df

        # 確保 index 是 tz-naive DatetimeIndex，避免 numpy.ndarray vs Timestamp 比較錯誤
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)

        # 如果有 current_time，截斷未來數據
        if self._current_time is not None:
            df = df[df.index <= pd.Timestamp(self._current_time)]

        # 只返回最近 lookback 根 bar
        if len(df) > lookback:
            df = df.iloc[-lookback:]

        return df

    def universe(self) -> list[str]:
        """當前可交易標的清單。"""
        return self._feed.get_universe()

    def portfolio(self) -> Portfolio:
        """當前持倉快照。"""
        return self._portfolio

    def now(self) -> datetime:
        """當前時間。"""
        if self._current_time is not None:
            return self._current_time
        return datetime.now(timezone.utc)

    def log(self, msg: str, **kwargs: Any) -> None:
        """策略日誌。"""
        self._logger.info(msg, **kwargs)

    def latest_price(self, symbol: str) -> Decimal:
        """取得最新價格。"""
        return self._feed.get_latest_price(symbol)

    def fundamentals(self, symbol: str) -> dict[str, float]:
        """Get fundamental data for symbol. Returns {} if no provider."""
        if self._fundamentals is None:
            return {}
        try:
            date_str = (
                self._current_time.strftime("%Y-%m-%d")
                if self._current_time
                else None
            )
            return self._fundamentals.get_financials(symbol, date_str)
        except Exception:
            return {}

    def sector(self, symbol: str) -> str:
        """Get sector classification. Returns '' if no provider."""
        if self._fundamentals is None:
            return ""
        try:
            return self._fundamentals.get_sector(symbol)
        except Exception:
            return ""


class Strategy(ABC):
    """
    策略基類 — 唯一需要繼承的介面。

    使用方式：
        class MyStrategy(Strategy):
            def name(self) -> str:
                return "my_strategy"

            def on_bar(self, ctx: Context) -> dict[str, float]:
                # 返回目標權重
                return {"2330.TW": 0.05, "2317.TW": 0.03}

    策略只需關心「我想持有什麼、多少」。
    系統自動處理：當前持倉差異 → 風控檢查 → 生成訂單 → 執行。
    """

    @abstractmethod
    def name(self) -> str:
        """策略名稱（唯一識別碼）。"""

    @abstractmethod
    def on_bar(self, ctx: Context) -> dict[str, float]:
        """
        收到新 bar，返回目標持倉權重。

        Returns:
            {"symbol": weight, ...}
            weight = 佔 NAV 的比例，正=多頭，負=空頭
            不在 dict 中的標的 = 目標權重 0（平倉）
        """

    def on_start(self, ctx: Context) -> None:
        """策略啟動時呼叫（可選覆寫）。"""

    def on_stop(self) -> None:
        """策略停止時呼叫（可選覆寫）。"""

    def on_fill(self, symbol: str, side: str, qty: float, price: float) -> None:
        """成交回報（可選覆寫）。"""

    def __repr__(self) -> str:
        return f"Strategy({self.name()})"
