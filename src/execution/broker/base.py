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
    """紙上交易券商 — 模擬即時成交，含滑價和成本。

    #2: 加入 sqrt 滑價模型（和 SimBroker 一致）
    #3: 從 config 讀取費率
    #14: 追蹤內部持倉
    """

    def __init__(
        self,
        commission_rate: float = 0.001425,
        tax_rate: float = 0.003,
        slippage_bps: float = 5.0,
        min_commission: float = 20.0,
    ) -> None:
        self._connected = True
        self._positions: dict[str, dict[str, Any]] = {}
        self._cash = Decimal("10000000")
        self._commission_rate = Decimal(str(commission_rate))
        self._tax_rate = Decimal(str(tax_rate))
        self._slippage_bps = Decimal(str(slippage_bps))
        self._min_commission = Decimal(str(min_commission))

    def submit_order(self, order: Order) -> str:
        """紙上交易成交，含滑價 + 佣金 + 稅。"""
        from src.core.models import OrderStatus, Side
        import logging
        _logger = logging.getLogger(__name__)

        price = order.price or Decimal("0")
        if price <= 0:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "No price available"
            return order.id

        # #2: 滑價（固定 bps，和 SimBroker base_slippage 一致）
        slippage = price * self._slippage_bps / Decimal("10000")
        if order.side == Side.BUY:
            fill_price = price + slippage
        else:
            fill_price = max(price - slippage, Decimal("0.01"))

        order.filled_qty = order.quantity
        order.filled_avg_price = fill_price
        order.status = OrderStatus.FILLED

        # #3: 成本模型（從 config 讀取，不再硬編碼）
        notional = order.quantity * fill_price
        commission = notional * self._commission_rate
        if commission < self._min_commission:
            commission = self._min_commission
        tax = notional * self._tax_rate if order.side == Side.SELL else Decimal("0")
        order.commission = commission + tax

        # #14: 追蹤內部持倉
        sym = order.instrument.symbol
        if order.side == Side.BUY:
            if sym in self._positions:
                self._positions[sym]["qty"] = float(Decimal(str(self._positions[sym]["qty"])) + order.quantity)
            else:
                self._positions[sym] = {"qty": float(order.quantity), "avg_cost": float(fill_price)}
            self._cash -= notional + commission + tax
        else:
            if sym in self._positions:
                self._positions[sym]["qty"] = float(Decimal(str(self._positions[sym]["qty"])) - order.quantity)
                if self._positions[sym]["qty"] <= 0:
                    del self._positions[sym]
            self._cash += notional - commission - tax

        return order.id

    def cancel_order(self, order_id: str) -> bool:
        return True

    def query_positions(self) -> dict[str, dict[str, Any]]:
        return dict(self._positions)

    def query_account(self) -> dict[str, Any]:
        return {"cash": float(self._cash), "status": "active"}

    def is_connected(self) -> bool:
        return self._connected
