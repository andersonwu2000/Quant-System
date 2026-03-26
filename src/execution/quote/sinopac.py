"""
永豐金 Shioaji 即時行情訂閱。

將 Shioaji tick/bidask callback 轉換為內部格式，
並透過 WebSocket broadcast 推送至前端。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickData:
    """標準化的 tick 行情資料。"""
    symbol: str
    price: Decimal
    volume: int
    bid_price: Decimal
    ask_price: Decimal
    timestamp: datetime
    total_volume: int = 0


@dataclass(frozen=True)
class BidAskData:
    """標準化的五檔報價資料。"""
    symbol: str
    bid_prices: tuple[Decimal, ...]
    bid_volumes: tuple[int, ...]
    ask_prices: tuple[Decimal, ...]
    ask_volumes: tuple[int, ...]
    timestamp: datetime


@dataclass
class QuoteSubscription:
    """行情訂閱管理。"""
    symbol: str
    quote_type: str = "tick"  # "tick" or "bidask"
    contract: Any = None


class SinopacQuoteManager:
    """管理 Shioaji 即時行情訂閱與回調轉發。

    Usage:
        manager = SinopacQuoteManager(shioaji_api)
        manager.on_tick = my_tick_handler
        manager.subscribe("2330")  # 台積電
    """

    def __init__(self, api: Any = None) -> None:
        self._api = api
        self._subscriptions: dict[str, QuoteSubscription] = {}
        self._tick_callbacks: list[Callable[[TickData], None]] = []
        self._bidask_callbacks: list[Callable[[BidAskData], None]] = []
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._latest_ticks: dict[str, TickData] = {}

    def set_api(self, api: Any) -> None:
        """設定或更新 Shioaji API 實例。"""
        self._api = api
        self._register_sdk_callbacks()

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """設定 asyncio event loop（用於跨執行緒回調）。"""
        self._event_loop = loop

    def set_broadcast_callback(
        self,
        callback: Callable[[TickData], Any],
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """註冊 WebSocket broadcast 回調（線程安全）。

        Tick callbacks come from Shioaji's background thread.  If *callback*
        is a coroutine function the caller must supply an *loop* so we can
        schedule it via ``run_coroutine_threadsafe``.  For plain sync
        callbacks *loop* is not required.

        Args:
            callback: A sync function ``(TickData) -> None`` **or** an async
                function whose coroutine will be scheduled on *loop*.
            loop: The running asyncio event loop (required for async
                callbacks).
        """
        if asyncio.iscoroutinefunction(callback):
            if loop is None:
                raise ValueError(
                    "An asyncio event loop is required for async broadcast callbacks"
                )

            def _threadsafe_wrapper(tick: TickData) -> None:
                asyncio.run_coroutine_threadsafe(callback(tick), loop)

            self._tick_callbacks.append(_threadsafe_wrapper)
        else:
            self._tick_callbacks.append(callback)

        if loop is not None:
            self._event_loop = loop
        logger.info("Broadcast callback registered")

    def on_tick(self, callback: Callable[[TickData], None]) -> None:
        """註冊 tick 回調。"""
        self._tick_callbacks.append(callback)

    def on_bidask(self, callback: Callable[[BidAskData], None]) -> None:
        """註冊五檔報價回調。"""
        self._bidask_callbacks.append(callback)

    def subscribe(self, symbol: str, quote_type: str = "tick") -> bool:
        """訂閱標的行情。

        Args:
            symbol: 股票代碼（如 "2330"）。
            quote_type: "tick" 或 "bidask"。

        Returns:
            是否訂閱成功。
        """
        if self._api is None:
            logger.warning("Cannot subscribe: API not connected")
            return False

        try:
            import shioaji as sj

            contract = self._api.Contracts.Stocks.get(symbol)
            if contract is None:
                logger.warning("Contract not found: %s", symbol)
                return False

            if quote_type == "tick":
                self._api.quote.subscribe(
                    contract, quote_type=sj.constant.QuoteType.Tick
                )
            elif quote_type == "bidask":
                self._api.quote.subscribe(
                    contract, quote_type=sj.constant.QuoteType.BidAsk
                )

            self._subscriptions[f"{symbol}:{quote_type}"] = QuoteSubscription(
                symbol=symbol, quote_type=quote_type, contract=contract
            )
            logger.info("Subscribed: %s (%s)", symbol, quote_type)
            return True

        except Exception:
            logger.exception("Subscribe failed: %s", symbol)
            return False

    def unsubscribe(self, symbol: str, quote_type: str = "tick") -> bool:
        """取消訂閱。"""
        if self._api is None:
            return False

        key = f"{symbol}:{quote_type}"
        sub = self._subscriptions.pop(key, None)
        if sub is None:
            return False

        try:
            import shioaji as sj

            qt = (
                sj.constant.QuoteType.Tick
                if quote_type == "tick"
                else sj.constant.QuoteType.BidAsk
            )
            self._api.quote.unsubscribe(sub.contract, quote_type=qt)
            logger.info("Unsubscribed: %s (%s)", symbol, quote_type)
            return True
        except Exception:
            logger.exception("Unsubscribe failed: %s", symbol)
            return False

    def unsubscribe_all(self) -> int:
        """取消所有訂閱。"""
        count = 0
        for key in list(self._subscriptions.keys()):
            symbol, qt = key.split(":", 1)
            if self.unsubscribe(symbol, qt):
                count += 1
        return count

    def get_latest_tick(self, symbol: str) -> TickData | None:
        """取得最新的 tick 資料。"""
        return self._latest_ticks.get(symbol)

    @property
    def subscribed_symbols(self) -> list[str]:
        return list({sub.symbol for sub in self._subscriptions.values()})

    # ── SDK Callbacks ─────────────────────────────────────

    def _register_sdk_callbacks(self) -> None:
        """註冊 Shioaji 的行情回調。

        Stock callbacks: set_on_tick_stk_v1_callback / set_on_bidask_stk_v1_callback
        Futures/Options: set_on_tick_fop_v1_callback / set_on_bidask_fop_v1_callback
        """
        if self._api is None:
            return

        try:
            self._api.quote.set_on_tick_stk_v1_callback(self._on_tick_v1)
            self._api.quote.set_on_bidask_stk_v1_callback(self._on_bidask_v1)
            logger.info("Shioaji stock quote callbacks registered")
        except Exception:
            logger.warning("Failed to register stock quote callbacks", exc_info=True)

        try:
            self._api.quote.set_on_tick_fop_v1_callback(self._on_tick_v1)
            self._api.quote.set_on_bidask_fop_v1_callback(self._on_bidask_v1)
            logger.info("Shioaji futures/options quote callbacks registered")
        except Exception:
            logger.warning("Failed to register fop quote callbacks", exc_info=True)

    def _on_tick_v1(self, exchange: Any, tick: Any) -> None:
        """Shioaji tick callback — 在 SDK 背景執行緒中調用。"""
        try:
            td = TickData(
                symbol=getattr(tick, "code", str(tick)),
                price=Decimal(str(getattr(tick, "close", 0))),
                volume=int(getattr(tick, "volume", 0)),
                bid_price=Decimal(str(getattr(tick, "bid_price", 0))),
                ask_price=Decimal(str(getattr(tick, "ask_price", 0))),
                timestamp=_parse_tick_ts(getattr(tick, "datetime", None)),
                total_volume=int(getattr(tick, "total_volume", 0)),
            )
            self._latest_ticks[td.symbol] = td

            for fn in self._tick_callbacks:
                try:
                    fn(td)
                except Exception:
                    logger.debug("Tick callback error", exc_info=True)

        except Exception:
            logger.debug("Error parsing tick data", exc_info=True)

    def _on_bidask_v1(self, exchange: Any, bidask: Any) -> None:
        """Shioaji bidask callback.

        bidask.bid_price / bid_volume / ask_price / ask_volume are List[Decimal].
        """
        try:
            bid_price_list = getattr(bidask, "bid_price", [])
            bid_volume_list = getattr(bidask, "bid_volume", [])
            ask_price_list = getattr(bidask, "ask_price", [])
            ask_volume_list = getattr(bidask, "ask_volume", [])

            bd = BidAskData(
                symbol=getattr(bidask, "code", str(bidask)),
                bid_prices=tuple(
                    Decimal(str(bid_price_list[i])) if i < len(bid_price_list) else Decimal("0")
                    for i in range(5)
                ),
                bid_volumes=tuple(
                    int(bid_volume_list[i]) if i < len(bid_volume_list) else 0
                    for i in range(5)
                ),
                ask_prices=tuple(
                    Decimal(str(ask_price_list[i])) if i < len(ask_price_list) else Decimal("0")
                    for i in range(5)
                ),
                ask_volumes=tuple(
                    int(ask_volume_list[i]) if i < len(ask_volume_list) else 0
                    for i in range(5)
                ),
                timestamp=_parse_tick_ts(getattr(bidask, "datetime", None)),
            )

            for fn in self._bidask_callbacks:
                try:
                    fn(bd)
                except Exception:
                    logger.debug("Bidask callback error", exc_info=True)

        except Exception:
            logger.debug("Error parsing bidask data", exc_info=True)

    def to_ws_payload(self, tick: TickData) -> dict[str, Any]:
        """將 TickData 轉換為 WebSocket 推送格式。"""
        return {
            "symbol": tick.symbol,
            "price": float(tick.price),
            "volume": tick.volume,
            "bid": float(tick.bid_price),
            "ask": float(tick.ask_price),
            "total_volume": tick.total_volume,
            "timestamp": tick.timestamp.isoformat(),
        }


def _parse_tick_ts(dt: Any) -> datetime:
    """解析 Shioaji 的 datetime 欄位。"""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    return datetime.now(timezone.utc)
