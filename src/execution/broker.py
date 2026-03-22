"""
券商介面 — 統一的交易通道抽象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from src.domain.models import Order, Portfolio


class BrokerAdapter(ABC):
    """券商統一介面。"""

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """提交訂單，返回券商端 order_id。"""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """撤單，返回是否成功。"""

    @abstractmethod
    def query_positions(self) -> dict[str, dict]:
        """查詢券商端持倉。返回 {symbol: {qty, avg_cost, ...}}"""

    @abstractmethod
    def query_account(self) -> dict:
        """查詢帳戶信息 (餘額、購買力等)。"""

    @abstractmethod
    def is_connected(self) -> bool:
        """連線狀態。"""


class PaperBroker(BrokerAdapter):
    """
    紙上交易券商 — 用即時行情模擬成交。

    用於模擬盤測試，不實際下單。
    """

    def __init__(self):
        self._connected = True
        self._positions: dict[str, dict] = {}
        self._cash = Decimal("10000000")

    def submit_order(self, order: Order) -> str:
        """紙上交易直接成交。"""
        return order.id

    def cancel_order(self, order_id: str) -> bool:
        return True

    def query_positions(self) -> dict[str, dict]:
        return dict(self._positions)

    def query_account(self) -> dict:
        return {"cash": float(self._cash), "status": "active"}

    def is_connected(self) -> bool:
        return self._connected
