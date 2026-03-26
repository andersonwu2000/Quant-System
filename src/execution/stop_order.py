"""
停損/停利委託管理 — 純 Python 實作，不依賴 Shioaji。

StopOrderManager 監控即時價格，當觸發條件滿足時
返回待提交的 Order 列表，由上層整合至 tick callback。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from src.core.models import Order


@dataclass
class StopOrder:
    """停損/停利委託。"""
    symbol: str
    stop_price: Decimal               # 觸發價格
    order: Order                       # 觸發後要執行的委託
    direction: str = "below"           # "below" = 價格 <= stop_price 時觸發
    executed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class StopOrderManager:
    """管理一組停損/停利委託，根據即時報價觸發。

    使用方式:
        manager = StopOrderManager()
        manager.add("2330", Decimal("580"), sell_order, direction="below")
        # 每次收到 tick 時:
        triggered = manager.on_tick("2330", Decimal("575"))
        for order in triggered:
            broker.submit_order(order)
    """

    def __init__(self) -> None:
        self._stops: list[StopOrder] = []

    def add(
        self,
        symbol: str,
        stop_price: Decimal,
        order: Order,
        direction: str = "below",
    ) -> StopOrder:
        """註冊一筆停損/停利委託。

        Args:
            symbol: 監控標的代碼。
            stop_price: 觸發價格。
            order: 觸發後要提交的委託。
            direction: "below" — 價格 <= stop_price 時觸發（停損賣出）；
                       "above" — 價格 >= stop_price 時觸發（停利買入）。

        Returns:
            建立的 StopOrder。
        """
        if direction not in ("below", "above"):
            raise ValueError(f"direction must be 'below' or 'above', got '{direction}'")

        stop = StopOrder(
            symbol=symbol,
            stop_price=stop_price,
            order=order,
            direction=direction,
        )
        self._stops.append(stop)
        return stop

    def on_tick(self, symbol: str, price: Decimal) -> list[Order]:
        """檢查是否有停損/停利委託被觸發。

        Args:
            symbol: 標的代碼。
            price: 最新價格。

        Returns:
            被觸發的 Order 列表（可直接提交至券商）。
        """
        triggered: list[Order] = []
        for stop in self._stops:
            if stop.executed or stop.symbol != symbol:
                continue
            if self._is_triggered(stop, price):
                stop.executed = True
                triggered.append(stop.order)
        return triggered

    def cancel(self, symbol: str) -> int:
        """取消指定標的的所有未觸發停損委託。

        Returns:
            取消的數量。
        """
        removed = 0
        remaining: list[StopOrder] = []
        for stop in self._stops:
            if stop.symbol == symbol and not stop.executed:
                removed += 1
            else:
                remaining.append(stop)
        self._stops = remaining
        return removed

    def cancel_all(self) -> int:
        """取消所有未觸發停損委託。

        Returns:
            取消的數量。
        """
        removed = sum(1 for s in self._stops if not s.executed)
        self._stops = [s for s in self._stops if s.executed]
        return removed

    def get_pending(self) -> list[StopOrder]:
        """取得所有未觸發的停損委託。"""
        return [s for s in self._stops if not s.executed]

    def get_executed(self) -> list[StopOrder]:
        """取得所有已觸發的停損委託。"""
        return [s for s in self._stops if s.executed]

    # ── 內部 ──────────────────────────────────────────────

    @staticmethod
    def _is_triggered(stop: StopOrder, price: Decimal) -> bool:
        if stop.direction == "below":
            return price <= stop.stop_price
        return price >= stop.stop_price
