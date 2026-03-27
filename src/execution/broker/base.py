"""
券商介面 — 統一的交易通道抽象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from typing import Any

from src.core.models import Order


class BrokerAdapter(ABC):
    """券商統一介面。"""

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """提交訂單，返回券商端 order_id。"""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤單，返回是否成功。"""

    @abstractmethod
    def query_positions(self) -> dict[str, dict[str, Any]]:
        """查詢券商端持倉。返回 {symbol: {qty, avg_cost, ...}}"""

    @abstractmethod
    def query_account(self) -> dict[str, Any]:
        """查詢帳戶信息 (餘額、購買力等)。"""

    @abstractmethod
    def is_connected(self) -> bool:
        """連線狀態。"""


class PaperBroker(BrokerAdapter):
    """
    紙上交易券商 — 用最新收盤價模擬即時成交。

    用於模擬盤測試，不實際下單。訂單提交後立即以 order.price 成交。
    """

    def __init__(self) -> None:
        self._connected = True
        self._positions: dict[str, dict[str, Any]] = {}
        self._cash = Decimal("10000000")

    def submit_order(self, order: Order) -> str:
        """紙上交易直接以委託價成交，使用與 SimBroker 一致的成本模型。"""
        from src.core.models import OrderStatus, Side

        order.filled_qty = order.quantity
        order.filled_avg_price = order.price or Decimal("0")
        order.status = OrderStatus.FILLED

        # 成本模型：手續費 0.1425% + 賣出交易稅 0.3%（與 SimBroker 一致）
        notional = order.quantity * (order.price or Decimal("0"))
        commission = notional * Decimal("0.001425")
        # 台灣券商最低手續費 20 元
        if commission < Decimal("20"):
            commission = Decimal("20")
        tax = notional * Decimal("0.003") if order.side == Side.SELL else Decimal("0")
        order.commission = commission + tax
        return order.id

    def cancel_order(self, order_id: str) -> bool:
        return True

    def query_positions(self) -> dict[str, dict[str, Any]]:
        return dict(self._positions)

    def query_account(self) -> dict[str, Any]:
        return {"cash": float(self._cash), "status": "active"}

    def is_connected(self) -> bool:
        return self._connected
