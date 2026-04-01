"""
訂單管理系統 (OMS) — 管理訂單生命週期。
"""

from __future__ import annotations

import logging
from decimal import Decimal

from src.core.models import Order, OrderStatus, Portfolio, Side, Trade, TradingInvariantError

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


def apply_trades(portfolio: Portfolio, trades: list[Trade], *, check_invariants: bool = False) -> Portfolio:
    """
    將成交記錄應用到投資組合，更新持倉和現金。

    注意：此函式直接 mutate portfolio 物件並回傳它（非純函式）。
    Thread-safe: 使用 portfolio.lock 防止和 update_market_prices 的 race condition。
    """
    from src.core.models import Instrument, Position

    with portfolio.lock:
        for trade in trades:
            symbol = trade.symbol

            # C4 fix: check position exists BEFORE updating cash for SELL
            effective_qty = trade.quantity
            if trade.side == Side.SELL:
                if symbol not in portfolio.positions:
                    logger.critical(
                        "SELL for %s but no position exists — trade SKIPPED (no cash change).",
                        symbol,
                    )
                    continue
                pos_qty = portfolio.positions[symbol].quantity
                if trade.quantity > pos_qty:
                    logger.warning(
                        "SELL qty %s > position %s for %s — capping",
                        trade.quantity, pos_qty, symbol,
                    )
                    effective_qty = pos_qty

            # 更新現金
            notional = effective_qty * trade.price
            if trade.side == Side.BUY:
                portfolio.cash -= notional + trade.commission
            else:
                portfolio.cash += notional - trade.commission

            # 更新持倉
            if symbol in portfolio.positions:
                pos = portfolio.positions[symbol]
                if trade.side == Side.BUY:
                    total_cost = pos.avg_cost * pos.quantity + trade.price * effective_qty
                    new_qty = pos.quantity + effective_qty
                    pos.avg_cost = total_cost / new_qty if new_qty > 0 else Decimal("0")
                    pos.quantity = new_qty
                else:
                    pos.quantity -= effective_qty

                pos.market_price = trade.price

                if pos.quantity <= 0:
                    del portfolio.positions[symbol]
            else:
                if trade.side == Side.BUY:
                    _is_tw = symbol.endswith(".TW") or symbol.endswith(".TWO")
                    portfolio.positions[symbol] = Position(
                        instrument=Instrument(symbol=symbol, lot_size=1000 if _is_tw else 1, market="tw" if _is_tw else "us"),
                        quantity=effective_qty,
                        avg_cost=trade.price,
                        market_price=trade.price,
                    )
                # SELL without position: already caught above (continue), should never reach here

        portfolio.as_of = trades[-1].timestamp if trades else portfolio.as_of

        # Log fills to append-only ledger (crash recovery for live mode)
        try:
            from src.execution.trade_ledger import log_fill
            for trade in trades:
                log_fill(
                    symbol=trade.symbol,
                    side=str(trade.side),
                    quantity=float(trade.quantity),
                    fill_price=float(trade.price),
                    commission=float(trade.commission),
                )
        except Exception:
            logger.warning("Trade ledger write failed", exc_info=True)

        # Persist portfolio state for crash recovery (paper/live mode)
        # Inside lock to prevent concurrent reads seeing partial state
        try:
            from src.core.config import get_config
            if get_config().mode in ("paper", "live"):
                from src.api.state import save_portfolio
                save_portfolio(portfolio)
        except Exception as _pe:
            logger.error("Portfolio persistence failed: %s", _pe)  # H4: was silent

        # AL-1: Portfolio invariant check after every trade application (paper/live only)
        # Backtest mode allows slight rounding issues (e.g. cash going slightly negative from order sizing)
        if check_invariants:
            try:
                portfolio._check_invariants()
            except TradingInvariantError:
                logger.critical("INVARIANT VIOLATION after apply_trades — raising to caller")
                raise

    return portfolio
