"""
台灣股市交易時段管理。

驗證委託是否在有效交易時段內，並提供盤外委託佇列。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timezone, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

# 台灣時區 UTC+8
TW_TZ = timezone(timedelta(hours=8))


class TradingSession(Enum):
    """交易時段。"""
    PRE_MARKET = "pre_market"       # 08:30–09:00 盤前試撮
    REGULAR = "regular"             # 09:00–13:25 盤中交易
    ODD_LOT = "odd_lot"             # 09:10–13:30 盤中零股
    CLOSING_AUCTION = "closing"     # 13:40–14:30 收盤定價
    AFTER_HOURS = "after_hours"     # 14:30–隔日 08:30
    WEEKEND = "weekend"


@dataclass(frozen=True)
class SessionWindow:
    """交易時段的起止時間。"""
    start: time
    end: time
    session: TradingSession


# 台股交易時段定義
TW_SESSIONS: list[SessionWindow] = [
    SessionWindow(time(8, 30), time(9, 0), TradingSession.PRE_MARKET),
    SessionWindow(time(9, 0), time(13, 25), TradingSession.REGULAR),
    SessionWindow(time(9, 10), time(13, 30), TradingSession.ODD_LOT),
    SessionWindow(time(13, 40), time(14, 30), TradingSession.CLOSING_AUCTION),
]


def get_current_session(
    now: datetime | None = None,
) -> TradingSession:
    """判斷當前屬於哪個交易時段。

    Args:
        now: 當前時間。None = 使用系統時間。

    Returns:
        當前交易時段。
    """
    if now is None:
        now = datetime.now(TW_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=TW_TZ)
    else:
        now = now.astimezone(TW_TZ)

    # 週末
    if now.weekday() >= 5:
        return TradingSession.WEEKEND

    current_time = now.time()

    # 檢查是否在任何交易時段內（優先匹配整股）
    if _in_window(current_time, time(9, 0), time(13, 25)):
        return TradingSession.REGULAR
    if _in_window(current_time, time(8, 30), time(9, 0)):
        return TradingSession.PRE_MARKET
    if _in_window(current_time, time(13, 40), time(14, 30)):
        return TradingSession.CLOSING_AUCTION

    return TradingSession.AFTER_HOURS


def is_tradable(
    now: datetime | None = None,
    allow_pre_market: bool = True,
) -> bool:
    """當前是否可下單。

    Args:
        now: 當前時間。
        allow_pre_market: 是否允許盤前下單。

    Returns:
        True 表示可以下單。
    """
    from src.core.calendar import get_tw_calendar

    # 先取得台灣時區的當前時間（用於日曆檢查）
    if now is None:
        now_tw = datetime.now(TW_TZ)
    elif now.tzinfo is None:
        now_tw = now.replace(tzinfo=TW_TZ)
    else:
        now_tw = now.astimezone(TW_TZ)

    # 檢查是否為交易日（排除國定假日）
    cal = get_tw_calendar()
    if not cal.is_trading_day(now_tw.date()):
        return False

    session = get_current_session(now)
    if session == TradingSession.REGULAR:
        return True
    if session == TradingSession.CLOSING_AUCTION:
        return True
    if session == TradingSession.PRE_MARKET and allow_pre_market:
        return True
    return False


def is_odd_lot_session(now: datetime | None = None) -> bool:
    """當前是否在零股交易時段。"""
    if now is None:
        now = datetime.now(TW_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=TW_TZ)
    else:
        now = now.astimezone(TW_TZ)

    if now.weekday() >= 5:
        return False

    return _in_window(now.time(), time(9, 10), time(13, 30))


def next_open(now: datetime | None = None) -> datetime:
    """計算下一個開盤時間。

    Returns:
        下一個交易日 09:00 (TW time)。
    """
    if now is None:
        now = datetime.now(TW_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=TW_TZ)
    else:
        now = now.astimezone(TW_TZ)

    candidate = now.replace(hour=9, minute=0, second=0, microsecond=0)

    # 如果今天已過開盤或是週末，推到下一個工作日
    if now.time() >= time(9, 0) or now.weekday() >= 5:
        candidate += timedelta(days=1)

    # 跳過週末
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)

    return candidate


def _in_window(current: time, start: time, end: time) -> bool:
    """判斷 current 是否在 [start, end) 區間內。"""
    return start <= current < end


@dataclass
class OrderQueue:
    """盤外委託佇列 — 暫存非交易時段的委託，開盤時送出。"""

    _queue: list[dict] = field(default_factory=list)  # type: ignore[type-arg]

    def enqueue(self, order_data: dict) -> int:  # type: ignore[type-arg]
        """加入佇列，返回佇列位置。"""
        self._queue.append(order_data)
        logger.info(
            "Order queued for next session: %s (queue size: %d)",
            order_data.get("symbol", "?"),
            len(self._queue),
        )
        return len(self._queue) - 1

    def drain(self) -> list[dict]:  # type: ignore[type-arg]
        """取出所有佇列中的委託並清空。"""
        orders = list(self._queue)
        self._queue.clear()
        if orders:
            logger.info("Drained %d queued orders", len(orders))
        return orders

    @property
    def size(self) -> int:
        return len(self._queue)

    @property
    def pending_orders(self) -> list[dict]:  # type: ignore[type-arg]
        return list(self._queue)
