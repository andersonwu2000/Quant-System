"""
策略引擎 — 管理策略的生命週期，將目標權重轉換為訂單。
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from src.domain.models import (
    Instrument,
    Order,
    OrderType,
    Portfolio,
    Side,
)
from src.strategy.base import Strategy

logger = logging.getLogger(__name__)


def weights_to_orders(
    target_weights: dict[str, float],
    portfolio: Portfolio,
    prices: dict[str, Decimal],
    instruments: dict[str, Instrument] | None = None,
) -> list[Order]:
    """
    將目標權重轉換為訂單列表。

    計算差異：target_weight - current_weight → 需要買賣多少。
    """
    if portfolio.nav <= 0:
        return []

    orders: list[Order] = []
    nav = portfolio.nav

    # 收集所有涉及的標的（持倉中的 + 目標中的）
    all_symbols = set(target_weights.keys()) | set(portfolio.positions.keys())

    for symbol in all_symbols:
        target_w = target_weights.get(symbol, 0.0)
        current_w = float(portfolio.get_position_weight(symbol))
        diff_w = target_w - current_w

        # 忽略微小差異（避免過度交易）
        if abs(diff_w) < 0.001:
            continue

        price = prices.get(symbol, Decimal("0"))
        if price <= 0:
            continue

        # 計算需要交易的數量
        target_value = Decimal(str(diff_w)) * nav
        qty = abs(target_value / price)

        # 取整到 lot_size
        inst = (instruments or {}).get(symbol, Instrument(symbol=symbol))
        lot_size = inst.lot_size
        if lot_size > 0:
            qty = Decimal(str(int(qty / lot_size) * lot_size))

        if qty <= 0:
            continue

        side = Side.BUY if diff_w > 0 else Side.SELL

        order = Order(
            id=uuid.uuid4().hex[:12],
            instrument=inst,
            side=side,
            order_type=OrderType.MARKET,
            quantity=qty,
            price=price,  # 用於風控計算，實際用市價成交
            strategy_id="",
        )
        orders.append(order)

    return orders
