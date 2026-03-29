"""
策略引擎 — 管理策略的生命週期，將目標權重轉換為訂單。
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal

from src.core.models import (
    Instrument,
    Order,
    OrderType,
    Portfolio,
    Side,
)

logger = logging.getLogger(__name__)


def _get_lot_size(
    symbol: str,
    instrument: Instrument,
    market_lot_sizes: dict[str, int] | None = None,
    fractional_shares: bool = False,
) -> int:
    """
    Determine lot size based on market. Extensible for any market.

    Priority:
    1. fractional_shares=True → always 1 (零股模式)
    2. instrument.lot_size > 1 → explicit instrument override
    3. market_lot_sizes suffix match → market-level default
    4. fallback → 1 (US-style, single share)
    """
    if fractional_shares:
        return 1
    if instrument.lot_size > 1:
        return instrument.lot_size
    if market_lot_sizes:
        for suffix, lot_size in market_lot_sizes.items():
            if symbol.endswith(suffix):
                return lot_size
    return 1  # Default: 1 share (US, etc.)


def weights_to_orders(
    target_weights: dict[str, float],
    portfolio: Portfolio,
    prices: dict[str, Decimal],
    instruments: dict[str, Instrument] | None = None,
    available_cash: Decimal | None = None,
    market_lot_sizes: dict[str, int] | None = None,
    fractional_shares: bool = False,
    volumes: dict[str, Decimal] | None = None,
) -> list[Order]:
    """
    將目標權重轉換為訂單列表。

    計算差異：target_weight - current_weight → 需要買賣多少。

    Args:
        available_cash: If provided, cap buy orders so total notional does not
                        exceed this amount. Used by T+N settlement to prevent
                        spending unsettled funds.
        market_lot_sizes: Mapping of symbol suffix to lot size,
                          e.g. {".TW": 1000, ".T": 100}. Used to determine
                          trading units per market. Instrument-level lot_size
                          takes priority if > 1.
        fractional_shares: If True, always use lot_size=1 (零股模式).
        volumes: {symbol: Decimal} 20-day average daily volume. If provided,
                 order quantity is capped at 10% of ADV to avoid excessive
                 market impact.
    """
    if portfolio.nav <= 0:
        return []

    # Filter NaN/inf/None weights (keep 0.0 — it means close position)
    import math
    target_weights = {
        k: v for k, v in target_weights.items()
        if v is not None and isinstance(v, (int, float)) and math.isfinite(v)
    }
    # Don't early-return on empty target — existing positions need to be closed

    # 驗證總權重不超過合理上限。
    # Threshold = 1.5: allows up to 50% gross leverage (e.g. 130/30 strategy)
    # while catching clearly erroneous inputs (un-normalized scores, double-counting).
    # Weights between 1.0 and 1.5 pass through unchanged to support leveraged strategies.
    total_weight = sum(target_weights.values())
    if total_weight > 1.5:
        logger.warning(
            "Total target weight %.2f exceeds 1.5 — possible leverage or bug. "
            "Capping to normalized weights.",
            total_weight,
        )
        target_weights = {k: v / total_weight for k, v in target_weights.items()}

    orders: list[Order] = []
    nav = portfolio.nav

    # 收集所有涉及的標的（持倉中的 + 目標中的），排序確保確定性分配
    all_symbols = sorted(set(target_weights.keys()) | set(portfolio.positions.keys()))

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
        inst = (instruments or {}).get(symbol, Instrument(symbol=symbol))
        multiplier = inst.multiplier if inst.multiplier > 0 else Decimal("1")
        target_value = Decimal(str(diff_w)) * nav
        # 考慮合約乘數：每口合約的名義價值 = price × multiplier
        notional_per_unit = price * multiplier
        qty = abs(target_value / notional_per_unit)

        # 取整到 lot_size（市場感知）
        lot_size = _get_lot_size(symbol, inst, market_lot_sizes, fractional_shares)
        if lot_size > 0:
            qty = (qty // Decimal(str(lot_size))) * Decimal(str(lot_size))

        # Volume cap: max 10% of 20-day ADV to limit market impact
        if volumes and symbol in volumes:
            adv = volumes[symbol]
            if adv > 0:
                max_qty = Decimal(str(int(float(adv) * 0.10)))
                if lot_size > 0:
                    max_qty = (max_qty // Decimal(str(lot_size))) * Decimal(str(lot_size))
                if qty > max_qty and max_qty > 0:
                    qty = max_qty

        if qty <= 0:
            continue

        side = Side.BUY if diff_w > 0 else Side.SELL

        # Cap buy orders to available cash when settlement constraint is active
        if side == Side.BUY and available_cash is not None:
            max_buy_value = max(available_cash, Decimal("0"))
            max_buy_qty = max_buy_value / notional_per_unit if notional_per_unit > 0 else Decimal("0")
            if lot_size > 0:
                max_buy_qty = (max_buy_qty // Decimal(str(lot_size))) * Decimal(str(lot_size))
            if qty > max_buy_qty:
                qty = max_buy_qty
            if qty <= 0:
                continue
            # Reduce remaining available cash for subsequent buy orders
            available_cash -= qty * notional_per_unit

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
