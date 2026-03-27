"""
訂單管理系統 (OMS) — 管理訂單生命週期。
"""

from __future__ import annotations

import logging
from decimal import Decimal

from src.core.models import Order, OrderStatus, Portfolio, Side, Trade

logger = logging.getLogger(__name__)


class OrderManager:
    """訂單管理：追蹤所有訂單狀態。"""

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        self._trade_history: list[Trade] = []

    def submit(self, order: Order) -> None:
        """提交訂單。"""
        self._orders[order.id] = order
        order.status = OrderStatus.SUBMITTED
        logger.info("ORDER SUBMITTED: %s %s %s @ %s",
                     order.side.value, order.quantity,
                     order.instrument.symbol, order.price)

    def on_fill(self, trade: Trade) -> None:
        """處理成交回報。"""
        self._trade_history.append(trade)

    def get_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def get_open_orders(self) -> list[Order]:
        return [o for o in self._orders.values() if not o.is_terminal]

    def get_all_orders(self) -> list[Order]:
        return list(self._orders.values())

    def get_trades(self) -> list[Trade]:
        return list(self._trade_history)

    def cancel_all(self) -> int:
        """撤銷所有未完成訂單，返回撤銷筆數。"""
        count = 0
        for order in self._orders.values():
            if not order.is_terminal:
                order.status = OrderStatus.CANCELLED
                count += 1
        if count > 0:
            logger.warning("CANCELLED %d open orders", count)
        return count


def apply_trades(portfolio: Portfolio, trades: list[Trade]) -> Portfolio:
    """
    將成交記錄應用到投資組合，更新持倉和現金。

    注意：此函式直接 mutate portfolio 物件並回傳它（非純函式）。
    Thread-safe: 使用 portfolio.lock 防止和 update_market_prices 的 race condition。
    """
    from src.core.models import Instrument, Position

    with portfolio.lock:
        for trade in trades:
            symbol = trade.symbol

            # SELL 溢出防護：先 cap 數量再計算現金
            if trade.side == Side.SELL and symbol in portfolio.positions:
                pos_qty = portfolio.positions[symbol].quantity
                if trade.quantity > pos_qty:
                    logger.warning(
                        "SELL qty %s > position %s for %s — capping",
                        trade.quantity, pos_qty, symbol,
                    )
                    trade.quantity = pos_qty

            # 更新現金（用 capped 後的數量）
            notional = trade.quantity * trade.price
            if trade.side == Side.BUY:
                portfolio.cash -= notional + trade.commission
            else:
                portfolio.cash += notional - trade.commission

            # 更新持倉
            if symbol in portfolio.positions:
                pos = portfolio.positions[symbol]
                if trade.side == Side.BUY:
                    total_cost = pos.avg_cost * pos.quantity + trade.price * trade.quantity
                    new_qty = pos.quantity + trade.quantity
                    pos.avg_cost = total_cost / new_qty if new_qty > 0 else Decimal("0")
                    pos.quantity = new_qty
                else:
                    pos.quantity -= trade.quantity

                pos.market_price = trade.price

                if pos.quantity <= 0:
                    del portfolio.positions[symbol]
            else:
                if trade.side == Side.BUY:
                    portfolio.positions[symbol] = Position(
                        instrument=Instrument(symbol=symbol),
                        quantity=trade.quantity,
                        avg_cost=trade.price,
                        market_price=trade.price,
                    )

        portfolio.as_of = trades[-1].timestamp if trades else portfolio.as_of

    # Persist portfolio state for crash recovery (paper/live mode)
    try:
        from src.core.config import get_config
        if get_config().mode in ("paper", "live"):
            from src.api.state import save_portfolio
            save_portfolio(portfolio)
    except Exception:
        pass  # backtest mode or missing API dependencies — skip persistence

    return portfolio
