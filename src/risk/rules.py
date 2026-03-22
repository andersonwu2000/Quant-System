"""
風控規則 — 聲明式，純函式，不需要繼承。

每個規則是一個函式工廠，返回 RiskRule。
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from src.domain.models import Order, Portfolio, RiskDecision


@dataclass
class MarketState:
    """市場狀態快照，供風控規則使用。"""
    prices: dict[str, Decimal]
    daily_volumes: dict[str, Decimal]   # ADV (平均日成交量)


@dataclass
class RiskRule:
    """風控規則。"""
    name: str
    check: Callable[[Order, Portfolio, MarketState], RiskDecision]
    enabled: bool = True

    def __call__(self, order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        if not self.enabled:
            return RiskDecision.APPROVE()
        return self.check(order, portfolio, market)


# ─── 規則工廠 ────────────────────────────────────────


def max_position_weight(threshold: float = 0.05) -> RiskRule:
    """單一標的權重上限。"""
    def check(order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        if portfolio.nav <= 0:
            return RiskDecision.APPROVE()

        symbol = order.instrument.symbol
        current_mv = Decimal("0")
        if symbol in portfolio.positions:
            current_mv = portfolio.positions[symbol].market_value

        # 預估下單後的市值
        order_value = order.quantity * (order.price or Decimal("0"))
        if order.side.value == "BUY":
            projected_mv = current_mv + order_value
        else:
            projected_mv = current_mv - order_value

        projected_weight = float(abs(projected_mv) / portfolio.nav)

        if projected_weight > threshold:
            return RiskDecision.REJECT(
                f"[{symbol}] 預估權重 {projected_weight:.1%} 超過上限 {threshold:.1%}"
            )
        return RiskDecision.APPROVE()

    return RiskRule(f"max_position_weight_{threshold}", check)


def max_order_notional(threshold_pct: float = 0.02) -> RiskRule:
    """單筆訂單金額上限（佔 NAV 比例）。"""
    def check(order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        if portfolio.nav <= 0:
            return RiskDecision.APPROVE()

        notional = order.quantity * (order.price or Decimal("0"))
        pct = float(notional / portfolio.nav)

        if pct > threshold_pct:
            return RiskDecision.REJECT(
                f"單筆金額 {pct:.1%} 超過上限 {threshold_pct:.1%}"
            )
        return RiskDecision.APPROVE()

    return RiskRule(f"max_order_notional_{threshold_pct}", check)


def daily_drawdown_limit(threshold: float = 0.03) -> RiskRule:
    """日回撤上限。"""
    def check(order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        dd = float(portfolio.daily_drawdown)
        if dd > threshold:
            return RiskDecision.REJECT(
                f"日回撤 {dd:.1%} 已超過 {threshold:.1%}，禁止新下單"
            )
        return RiskDecision.APPROVE()

    return RiskRule(f"daily_drawdown_{threshold}", check)


def fat_finger_check(threshold: float = 0.05) -> RiskRule:
    """胖手指檢查：訂單價格偏離市價過大。"""
    def check(order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        if order.price is None:
            return RiskDecision.APPROVE()  # 市價單不檢查

        symbol = order.instrument.symbol
        mkt_price = market.prices.get(symbol)
        if mkt_price is None or mkt_price <= 0:
            return RiskDecision.APPROVE()

        deviation = abs(float(order.price / mkt_price) - 1)
        if deviation > threshold:
            return RiskDecision.REJECT(
                f"[{symbol}] 價格 {order.price} 偏離市價 {mkt_price} 達 {deviation:.1%}"
            )
        return RiskDecision.APPROVE()

    return RiskRule(f"fat_finger_{threshold}", check)


def max_daily_trades(limit: int = 100) -> RiskRule:
    """每日交易次數上限。"""
    trade_count: dict[str, int] = {}  # date_str → count

    def check(order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        today = portfolio.as_of.strftime("%Y-%m-%d")
        count = trade_count.get(today, 0)
        if count >= limit:
            return RiskDecision.REJECT(f"今日交易次數已達上限 {limit}")
        trade_count[today] = count + 1
        return RiskDecision.APPROVE()

    return RiskRule(f"max_daily_trades_{limit}", check)


def max_order_vs_adv(threshold: float = 0.10) -> RiskRule:
    """單筆訂單不超過 ADV 的一定比例。"""
    def check(order: Order, portfolio: Portfolio, market: MarketState) -> RiskDecision:
        symbol = order.instrument.symbol
        adv = market.daily_volumes.get(symbol)
        if adv is None or adv <= 0:
            return RiskDecision.APPROVE()  # 沒有 ADV 資料，放行

        ratio = float(order.quantity / adv)
        if ratio > threshold:
            return RiskDecision.REJECT(
                f"[{symbol}] 下單量 {order.quantity} 佔 ADV {adv} 的 {ratio:.1%}"
            )
        return RiskDecision.APPROVE()

    return RiskRule(f"max_order_vs_adv_{threshold}", check)


# ─── 預設規則集 ─────────────────────────────────────

def default_rules() -> list[RiskRule]:
    """回傳預設風控規則集。"""
    return [
        max_position_weight(0.10),
        max_order_notional(0.10),
        daily_drawdown_limit(0.03),
        fat_finger_check(0.05),
        max_daily_trades(100),
        max_order_vs_adv(0.10),
    ]
