"""
即時監控 — 持續監控投資組合狀態並產生告警。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from src.core.models import Portfolio, RiskAlert, Severity

logger = logging.getLogger(__name__)


@dataclass
class MonitorConfig:
    """監控閾值配置。"""
    drawdown_warning_pct: float = 0.02
    drawdown_critical_pct: float = 0.03
    drawdown_emergency_pct: float = 0.05
    concentration_warning_pct: float = 0.15     # 前 3 大持倉佔比 > 15%
    exposure_warning_pct: float = 1.05          # 總曝險 > 105% NAV


class RiskMonitor:
    """即時風控監控器。"""

    def __init__(self, config: MonitorConfig | None = None):
        self.config = config or MonitorConfig()
        self._last_alerts: dict[str, datetime] = {}  # 避免重複告警
        self._cooldown_seconds = 300  # 5 分鐘冷卻

    def check(self, portfolio: Portfolio) -> list[RiskAlert]:
        """執行所有監控檢查，返回告警列表。"""
        alerts: list[RiskAlert] = []
        now = datetime.now(timezone.utc)

        # 1. 回撤監控
        dd = float(portfolio.daily_drawdown)
        if dd > self.config.drawdown_emergency_pct:
            alerts.append(self._alert(now, "drawdown", Severity.EMERGENCY, dd,
                                       self.config.drawdown_emergency_pct,
                                       "flatten_all",
                                       f"日回撤 {dd:.2%} — 觸發熔斷"))
        elif dd > self.config.drawdown_critical_pct:
            alerts.append(self._alert(now, "drawdown", Severity.CRITICAL, dd,
                                       self.config.drawdown_critical_pct,
                                       "reduce_exposure",
                                       f"日回撤 {dd:.2%} — 建議減倉"))
        elif dd > self.config.drawdown_warning_pct:
            alerts.append(self._alert(now, "drawdown", Severity.WARNING, dd,
                                       self.config.drawdown_warning_pct,
                                       "alert",
                                       f"日回撤 {dd:.2%} — 接近閾值"))

        # 2. 集中度監控
        if portfolio.positions:
            weights = sorted(
                [abs(float(portfolio.get_position_weight(s)))
                 for s in portfolio.positions],
                reverse=True,
            )
            top3 = sum(weights[:3]) if len(weights) >= 3 else sum(weights)
            if top3 > self.config.concentration_warning_pct:
                alerts.append(self._alert(
                    now, "concentration", Severity.WARNING, top3,
                    self.config.concentration_warning_pct, "alert",
                    f"前3大持倉佔比 {top3:.1%}",
                ))

        # 3. 曝險監控
        if portfolio.nav > 0:
            exposure_ratio = float(portfolio.gross_exposure / portfolio.nav)
            if exposure_ratio > self.config.exposure_warning_pct:
                alerts.append(self._alert(
                    now, "exposure", Severity.WARNING, exposure_ratio,
                    self.config.exposure_warning_pct, "alert",
                    f"總曝險 {exposure_ratio:.1%} NAV",
                ))

        # 過濾冷卻中的告警
        filtered = []
        for alert in alerts:
            last = self._last_alerts.get(alert.rule_name)
            if last is None or (now - last).total_seconds() > self._cooldown_seconds:
                filtered.append(alert)
                self._last_alerts[alert.rule_name] = now

        return filtered

    def _alert(
        self,
        ts: datetime,
        rule: str,
        severity: Severity,
        value: float,
        threshold: float,
        action: str,
        message: str,
    ) -> RiskAlert:
        return RiskAlert(
            timestamp=ts,
            rule_name=rule,
            severity=severity,
            metric_value=value,
            threshold=threshold,
            action_taken=action,
            message=message,
        )
