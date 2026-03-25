"""SafetyChecker — drawdown circuit breaker and consecutive-loss detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.alpha.auto.config import AlphaAlert, AutoAlphaConfig
from src.alpha.auto.store import AlphaStore

logger = logging.getLogger(__name__)


@dataclass
class SafetyResult:
    """Result of a safety check."""

    should_pause: bool = False
    alerts: list[AlphaAlert] = field(default_factory=list)
    drawdown: float = 0.0
    consecutive_losses: int = 0


class SafetyChecker:
    """Multi-layer safety checks: drawdown circuit breaker + loss streak detection.

    Parameters
    ----------
    config:
        Auto-alpha config with ``emergency_stop_drawdown`` and
        ``max_consecutive_losses`` thresholds.
    store:
        Alpha store for reading historical snapshots.
    """

    def __init__(self, config: AutoAlphaConfig, store: AlphaStore) -> None:
        self._config = config
        self._store = store

    def check(self, portfolio_nav: float, initial_nav: float) -> SafetyResult:
        """Run all safety checks and return aggregated result.

        Parameters
        ----------
        portfolio_nav:
            Current portfolio net asset value.
        initial_nav:
            Starting portfolio net asset value (baseline for drawdown).

        Returns
        -------
        SafetyResult with ``should_pause=True`` when emergency stop is triggered.
        """
        result = SafetyResult()

        # 1. Drawdown from initial NAV
        if initial_nav > 0:
            result.drawdown = (initial_nav - portfolio_nav) / initial_nav
        else:
            result.drawdown = 0.0

        # 2. Consecutive loss days from snapshots
        result.consecutive_losses = self._count_consecutive_losses()

        # 3. Emergency stop — drawdown exceeds threshold
        if result.drawdown >= self._config.emergency_stop_drawdown:
            alert = AlphaAlert(
                timestamp=datetime.now(),
                level="critical",
                category="drawdown",
                message=(
                    f"Drawdown reached {result.drawdown:.1%}, "
                    f"triggering emergency stop "
                    f"(threshold: {self._config.emergency_stop_drawdown:.1%})"
                ),
                details={
                    "drawdown": result.drawdown,
                    "threshold": self._config.emergency_stop_drawdown,
                    "portfolio_nav": portfolio_nav,
                    "initial_nav": initial_nav,
                },
            )
            result.alerts.append(alert)
            result.should_pause = True
            logger.critical(
                "EMERGENCY STOP: drawdown %.1f%% >= threshold %.1f%%",
                result.drawdown * 100,
                self._config.emergency_stop_drawdown * 100,
            )

        # 4. Consecutive loss warning
        if result.consecutive_losses >= self._config.max_consecutive_losses:
            alert = AlphaAlert(
                timestamp=datetime.now(),
                level="warning",
                category="execution",
                message=(
                    f"{result.consecutive_losses} consecutive loss days "
                    f"(threshold: {self._config.max_consecutive_losses})"
                ),
                details={
                    "consecutive_losses": result.consecutive_losses,
                    "threshold": self._config.max_consecutive_losses,
                },
            )
            result.alerts.append(alert)
            logger.warning(
                "Consecutive loss days: %d (threshold %d)",
                result.consecutive_losses,
                self._config.max_consecutive_losses,
            )

        return result

    def _count_consecutive_losses(self) -> int:
        """Count consecutive loss days from most-recent snapshots."""
        snapshots = self._store.list_snapshots(limit=30)
        count = 0
        for snap in snapshots:
            if snap.daily_pnl is not None and snap.daily_pnl < 0:
                count += 1
            else:
                break
        return count
