"""
券商介面 — 統一的交易通道抽象。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from src.core.models import Order, Trade


@runtime_checkable
class OrderExecutor(Protocol):
    """統一執行介面 — SimBroker 和 ExecutionService 都滿足此 protocol。

    U1: 讓 execute_one_bar 接受任何實作 execute() 的物件，
    回測用 SimBroker，Paper/Live 用 ExecutionService。
    """

    def execute(
        self,
        orders: list[Order],
        current_bars: dict[str, dict[str, Any]] | None = None,
        timestamp: datetime | None = None,
    ) -> list[Trade]: ...


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
    """紙上交易券商 — 模擬即時成交，使用統一 CostModel。"""

    def __init__(
        self,
        cost_model: Any | None = None,
        # 向後相容：舊的 keyword args 仍可用
        commission_rate: float = 0.001425,
        tax_rate: float = 0.003,
        slippage_bps: float = 5.0,
        min_commission: float = 20.0,
    ) -> None:
        self._connected = True
        self._positions: dict[str, dict[str, Any]] = {}
        self._cash = Decimal("10000000")

        if cost_model is not None:
            self._cost = cost_model
        else:
            from src.execution.cost_model import CostModel
            self._cost = CostModel(
                commission_rate=Decimal(str(commission_rate)),
                tax_rate=Decimal(str(tax_rate)),
                slippage_bps=Decimal(str(slippage_bps)),
                min_commission=Decimal(str(min_commission)),
            )

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

        # 使用統一 CostModel
        is_buy = order.side == Side.BUY
        fill_price = self._cost.compute_slippage(price, is_buy)

        order.filled_qty = order.quantity
        order.filled_avg_price = fill_price
        order.status = OrderStatus.FILLED

        notional = order.quantity * fill_price
        order.commission = self._cost.total_cost(notional, is_sell=(not is_buy))

        # #14: 追蹤內部持倉
        sym = order.instrument.symbol
        if order.side == Side.BUY:
            if sym in self._positions:
                self._positions[sym]["qty"] = float(Decimal(str(self._positions[sym]["qty"])) + order.quantity)
            else:
                self._positions[sym] = {"qty": float(order.quantity), "avg_cost": float(fill_price)}
            self._cash -= notional + order.commission
        else:
            if sym in self._positions:
                self._positions[sym]["qty"] = float(Decimal(str(self._positions[sym]["qty"])) - order.quantity)
                if self._positions[sym]["qty"] <= 0:
                    del self._positions[sym]
            self._cash += notional - order.commission

        return order.id

    def cancel_order(self, order_id: str) -> bool:
        return True

    def query_positions(self) -> dict[str, dict[str, Any]]:
        return dict(self._positions)

    def query_account(self) -> dict[str, Any]:
        return {"cash": float(self._cash), "status": "active"}

    def is_connected(self) -> bool:
        return self._connected
