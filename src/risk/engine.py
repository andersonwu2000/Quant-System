"""
風控引擎 — 獨立於策略，擁有否決權。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from src.domain.models import (
    Order,
    Portfolio,
    RiskAlert,
    RiskDecision,
    Severity,
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
        """批次檢查訂單，返回通過的訂單。"""
        approved = []
        for order in orders:
            decision = self.check_order(order, portfolio, market)
            if decision.approved:
                approved.append(order)
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

    def kill_switch(self, portfolio: Portfolio) -> bool:
        """
        熔斷檢查：是否需要緊急停止。
        返回 True = 觸發熔斷。
        """
        dd = float(portfolio.daily_drawdown)
        if dd > 0.05:  # 日回撤 > 5%
            logger.critical("KILL SWITCH TRIGGERED: daily drawdown %.2f%%", dd * 100)
            self._record_alert(
                "kill_switch", f"日回撤 {dd:.2%} 觸發熔斷", Severity.EMERGENCY
            )
            return True
        return False

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
