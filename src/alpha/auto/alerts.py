"""AlertManager — rule-based alert generation for the automated alpha system."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from src.alpha.auto.config import ALERT_RULES, AlphaAlert, FactorScore
from src.alpha.auto.store import AlphaStore
from src.alpha.regime import MarketRegime

logger = logging.getLogger(__name__)


class AlertManager:
    """Generate and dispatch alerts based on research state changes.

    Each ``check_*`` method inspects a specific condition and returns
    an :class:`AlphaAlert` (or list thereof) when the condition fires,
    or ``None`` / empty list when everything is normal.
    """

    def __init__(self, store: AlphaStore) -> None:
        self._store = store

    # ------------------------------------------------------------------
    # Regime
    # ------------------------------------------------------------------

    def check_regime_change(
        self,
        prev_regime: MarketRegime | None,
        current_regime: MarketRegime,
    ) -> AlphaAlert | None:
        """Return alert if regime changed, None otherwise."""
        if prev_regime is None or prev_regime == current_regime:
            return None
        msg = ALERT_RULES["regime_change"].format(
            old=prev_regime.value, new=current_regime.value
        )
        alert = AlphaAlert(
            timestamp=datetime.now(),
            level="warning",
            category="regime",
            message=msg,
            details={"old": prev_regime.value, "new": current_regime.value},
        )
        self._store.save_alert(alert)
        return alert

    # ------------------------------------------------------------------
    # Factor degradation
    # ------------------------------------------------------------------

    def check_factor_degradation(
        self,
        prev_scores: dict[str, FactorScore],
        current_scores: dict[str, FactorScore],
        threshold: float = 0.2,
    ) -> list[AlphaAlert]:
        """Return alerts for factors whose ICIR dropped by more than *threshold*."""
        alerts: list[AlphaAlert] = []
        for name, cur in current_scores.items():
            prev = prev_scores.get(name)
            if prev is None:
                continue
            drop = prev.icir - cur.icir
            if drop > threshold:
                msg = ALERT_RULES["factor_degraded"].format(
                    name=name, old=prev.icir, new=cur.icir
                )
                alert = AlphaAlert(
                    timestamp=datetime.now(),
                    level="warning",
                    category="factor",
                    message=msg,
                    details={
                        "factor": name,
                        "old_icir": prev.icir,
                        "new_icir": cur.icir,
                        "drop": drop,
                    },
                )
                self._store.save_alert(alert)
                alerts.append(alert)
        return alerts

    # ------------------------------------------------------------------
    # IC reversal
    # ------------------------------------------------------------------

    def check_ic_reversal(
        self,
        store: AlphaStore,
        factor_name: str,
        days: int = 10,
    ) -> AlphaAlert | None:
        """Check if *factor_name* had negative IC for *days* consecutive days.

        Reads recent snapshots from the store. Returns alert if the factor
        had ``ic < 0`` for at least *days* consecutive most-recent snapshots.
        """
        snapshots = store.list_snapshots(limit=days)
        if len(snapshots) < days:
            return None

        consecutive_neg = 0
        for snap in snapshots:
            score = snap.factor_scores.get(factor_name)
            if score is None or score.ic >= 0:
                break
            consecutive_neg += 1

        if consecutive_neg >= days:
            msg = ALERT_RULES["ic_reversal"].format(
                name=factor_name, days=consecutive_neg
            )
            alert = AlphaAlert(
                timestamp=datetime.now(),
                level="warning",
                category="factor",
                message=msg,
                details={
                    "factor": factor_name,
                    "consecutive_negative_days": consecutive_neg,
                },
            )
            self._store.save_alert(alert)
            return alert
        return None

    # ------------------------------------------------------------------
    # No eligible factors
    # ------------------------------------------------------------------

    def check_no_eligible_factors(
        self,
        selected: list[str],
    ) -> AlphaAlert | None:
        """Return alert if no factors passed selection."""
        if selected:
            return None
        msg = ALERT_RULES["no_eligible_factors"]
        alert = AlphaAlert(
            timestamp=datetime.now(),
            level="critical",
            category="factor",
            message=msg,
            details={"selected_count": 0},
        )
        self._store.save_alert(alert)
        return alert

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def send_alerts(
        self,
        alerts: list[AlphaAlert],
        notifier: Any | None = None,
    ) -> None:
        """Log all alerts and optionally send via *notifier*.

        ``notifier``, if provided, should have a ``send(message: str)`` method
        (e.g. a :class:`NotificationProvider`).
        """
        for alert in alerts:
            log_fn = {
                "info": logger.info,
                "warning": logger.warning,
                "critical": logger.critical,
            }.get(alert.level, logger.info)
            log_fn("[%s] %s: %s", alert.level.upper(), alert.category, alert.message)

            if notifier is not None:
                try:
                    notifier.send(
                        f"[{alert.level.upper()}] {alert.category}: {alert.message}"
                    )
                except Exception:
                    logger.exception("Failed to send alert via notifier")
