"""
風控引擎 — 獨立於策略，擁有否決權。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from src.core.models import (
    Order,
    Portfolio,
    RiskAlert,
    RiskDecision,
    Severity,
    Side,
)
from src.risk.rules import MarketState, RiskRule, default_rules

logger = logging.getLogger(__name__)


class RiskEngine:
    """
    風控引擎：依序執行所有規則，第一個 REJECT 即終止。
    """

    def __init__(
        self,
        rules: list[RiskRule] | None = None,
        persist_fn: Callable[[RiskAlert], None] | None = None,
    ):
        self.rules = rules if rules is not None else default_rules()
        self._alerts: list[RiskAlert] = []
        self._persist_fn = persist_fn

    def check_order(
        self,
        order: Order,
        portfolio: Portfolio,
        market: MarketState | None = None,
    ) -> RiskDecision:
        """
        Pre-trade 風控檢查。

        逐一執行規則，第一個 REJECT 就擋下。
        """
        if market is None:
            logger.debug(
                "MarketState not provided — market-dependent rules "
                "(fat_finger, adv, circuit_breaker) will auto-approve"
            )
            market = MarketState(prices={}, daily_volumes={})

        for rule in self.rules:
            if not rule.enabled:
                continue

            decision = rule(order, portfolio, market)

            if not decision.approved:
                logger.warning(
                    "RISK REJECT [%s]: %s — %s",
                    rule.name,
                    order.instrument.symbol,
                    decision.reason,
                )
                self._record_alert(rule.name, decision.reason, Severity.WARNING)
                return decision

            if decision.modified_qty is not None:
                if decision.modified_qty <= 0:
                    logger.warning(
                        "RISK REJECT [%s]: %s — modified_qty %s <= 0",
                        rule.name, order.instrument.symbol, decision.modified_qty,
                    )
                    self._record_alert(rule.name, f"modified_qty {decision.modified_qty} <= 0", Severity.WARNING)
                    return RiskDecision(approved=False, reason=f"modified_qty {decision.modified_qty} invalid")
                if decision.modified_qty > order.quantity:
                    decision.modified_qty = order.quantity  # cap: never increase
                logger.info(
                    "RISK MODIFY [%s]: %s qty %s → %s",
                    rule.name,
                    order.instrument.symbol,
                    order.quantity,
                    decision.modified_qty,
                )
                order.quantity = decision.modified_qty

        return RiskDecision.APPROVE()

    def check_orders(
        self,
        orders: list[Order],
        portfolio: Portfolio,
        market: MarketState | None = None,
    ) -> list[Order]:
        """批次檢查訂單，返回通過的訂單。

        使用模擬的 projected portfolio 計算累積效應：
        前面通過的買單會增加 projected 持倉，影響後續訂單的權重計算。
        """
        from copy import deepcopy

        projected = deepcopy(portfolio)
        approved = []
        for order in orders:
            decision = self.check_order(order, projected, market)
            if decision.approved:
                approved.append(order)
                # 更新 projected portfolio 以反映累積效應
                sym = order.instrument.symbol
                # H5 fix: market order 可能 price=None，fallback 到 MarketState
                price = order.price
                if not price or price <= 0:
                    if market and sym in market.prices:
                        price = market.prices[sym]
                    else:
                        # H1: skip order with no price (was 0 → bypassed all limits)
                        logger.warning("Risk: skipping %s %s — no price available", order.side.value, sym)
                        continue
                notional = order.quantity * price
                if order.side == Side.BUY:
                    projected.cash -= notional
                    if sym in projected.positions:
                        projected.positions[sym].quantity += order.quantity
                        projected.positions[sym].market_price = price
                    else:
                        from src.core.models import Instrument, Position
                        projected.positions[sym] = Position(
                            instrument=Instrument(symbol=sym),
                            quantity=order.quantity,
                            avg_cost=price,
                            market_price=price,
                        )
                else:
                    projected.cash += notional
                    if sym in projected.positions:
                        projected.positions[sym].quantity -= order.quantity
                        if projected.positions[sym].quantity <= 0:
                            del projected.positions[sym]
        return approved

    def check_portfolio(self, portfolio: Portfolio) -> list[RiskAlert]:
        """
        Real-time 持倉檢查：回撤監控。
        返回告警列表。
        """
        alerts: list[RiskAlert] = []
        now = datetime.now(timezone.utc)

        # 日回撤檢查
        dd = float(portfolio.daily_drawdown)
        if dd > 0.02:  # > 2% warning
            severity = Severity.CRITICAL if dd > 0.03 else Severity.WARNING
            alert = RiskAlert(
                timestamp=now,
                rule_name="daily_drawdown",
                severity=severity,
                metric_value=dd,
                threshold=0.03,
                action_taken="alert",
                message=f"日回撤 {dd:.2%}",
            )
            alerts.append(alert)
            self._alerts.append(alert)

        return alerts

    def kill_switch(self, portfolio: Portfolio, threshold: float = 0.0) -> bool:
        """
        熔斷檢查：是否需要緊急停止。
        返回 True = 觸發熔斷。

        Args:
            threshold: Drawdown threshold to trigger (0.0 = use config default).
                       Caller should pass config.max_daily_drawdown_pct.

        注意：此方法只做判斷，不執行清倉。
        回測引擎用 _execute_kill_switch() 清倉。
        實盤管線需自行呼叫 liquidate_all() 或等效操作。
        """
        dd = float(portfolio.daily_drawdown)
        trigger = threshold if threshold > 0 else 0.05
        if dd > trigger:
            logger.critical("KILL SWITCH TRIGGERED: daily drawdown %.2f%% > %.1f%%",
                          dd * 100, trigger * 100)
            self._record_alert(
                "kill_switch", f"日回撤 {dd:.2%} 觸發熔斷（門檻 {trigger:.1%}）", Severity.EMERGENCY
            )
            return True
        return False

    def generate_liquidation_orders(self, portfolio: Portfolio) -> list[Order]:
        """產生清倉訂單（所有持倉全部賣出）。

        供實盤管線在 kill_switch 觸發後使用。
        回測引擎有自己的 _execute_kill_switch。
        """
        from src.core.models import Instrument, OrderType
        import uuid

        orders: list[Order] = []
        for symbol, pos in portfolio.positions.items():
            if pos.quantity > 0:
                orders.append(Order(
                    id=uuid.uuid4().hex[:12],
                    instrument=pos.instrument or Instrument(symbol=symbol),
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    quantity=pos.quantity,
                    price=pos.market_price,
                ))
        if orders:
            logger.critical("Generated %d liquidation orders for kill switch", len(orders))
        return orders

    def post_trade_check(self, portfolio: Portfolio) -> list[RiskAlert]:
        """Post-trade 持倉檢查：成交後驗證組合是否仍合規。

        檢查項目：
        1. 日回撤是否接近/超過限制
        2. 累計回撤是否超標
        3. 單一持倉是否因價格變動超過權重限制
        """
        alerts: list[RiskAlert] = []
        now = datetime.now(timezone.utc)

        # 日回撤
        dd = float(portfolio.daily_drawdown)
        if dd > 0.02:
            severity = Severity.CRITICAL if dd > 0.03 else Severity.WARNING
            alerts.append(RiskAlert(
                timestamp=now, rule_name="post_daily_drawdown",
                severity=severity, metric_value=dd, threshold=0.03,
                action_taken="alert", message=f"Post-trade 日回撤 {dd:.2%}",
            ))

        # 累計回撤
        if portfolio.initial_cash > 0:
            cum_dd = 1 - float(portfolio.nav / portfolio.initial_cash)
            if cum_dd > 0.15:
                severity = Severity.CRITICAL if cum_dd > 0.20 else Severity.WARNING
                alerts.append(RiskAlert(
                    timestamp=now, rule_name="post_cumulative_drawdown",
                    severity=severity, metric_value=cum_dd, threshold=0.20,
                    action_taken="alert", message=f"Post-trade 累計回撤 {cum_dd:.2%}",
                ))

        # 持倉集中度
        if portfolio.nav > 0:
            for sym, pos in portfolio.positions.items():
                weight = float(abs(pos.market_value) / portfolio.nav)
                if weight > 0.15:
                    alerts.append(RiskAlert(
                        timestamp=now, rule_name="post_position_concentration",
                        severity=Severity.WARNING, metric_value=weight, threshold=0.15,
                        action_taken="alert",
                        message=f"Post-trade {sym} 權重 {weight:.1%} > 15%",
                    ))

        for alert in alerts:
            self._alerts.append(alert)
            if self._persist_fn:
                try:
                    self._persist_fn(alert)
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)

        return alerts

    def get_alerts(self) -> list[RiskAlert]:
        """取得所有歷史告警。"""
        return list(self._alerts)

    def clear_alerts(self) -> None:
        self._alerts.clear()

    def reset_state(self) -> None:
        """重置所有有狀態的規則（回測間清除用）。"""
        for rule in self.rules:
            rule.reset()

    _MAX_ALERTS = 10000

    def _record_alert(self, rule: str, message: str, severity: Severity) -> None:
        if len(self._alerts) >= self._MAX_ALERTS:
            self._alerts = self._alerts[-self._MAX_ALERTS // 2 :]
        alert = RiskAlert(
            timestamp=datetime.now(timezone.utc),
            rule_name=rule,
            severity=severity,
            metric_value=0,
            threshold=0,
            action_taken="reject",
            message=message,
        )
        self._alerts.append(alert)
        if self._persist_fn:
            try:
                self._persist_fn(alert)
            except Exception:
                logger.debug("Failed to persist risk event", exc_info=True)
