"""SafetyChecker — drawdown circuit breaker and consecutive-loss detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

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
    momentum_crash_detected: bool = False


@dataclass
class RecoveryResult:
    """Result of a kill switch recovery check."""

    can_resume: bool
    position_scale: float  # 0.0 to 1.0
    reason: str


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

    def check(
        self,
        portfolio_nav: float,
        initial_nav: float,
        peak_nav: float | None = None,
    ) -> SafetyResult:
        """Run all safety checks and return aggregated result.

        Parameters
        ----------
        portfolio_nav:
            Current portfolio net asset value.
        initial_nav:
            Starting portfolio net asset value (fallback if peak_nav not provided).
        peak_nav:
            High-water-mark NAV. If provided, drawdown is computed from peak
            (standard definition). Falls back to ``initial_nav`` for backward
            compatibility.

        Returns
        -------
        SafetyResult with ``should_pause=True`` when emergency stop is triggered.
        """
        result = SafetyResult()

        # 1. Drawdown from peak NAV (standard definition); fall back to initial NAV
        baseline = peak_nav if peak_nav is not None and peak_nav > 0 else initial_nav
        if baseline > 0:
            result.drawdown = (baseline - portfolio_nav) / baseline
        else:
            # Fail-closed: no valid baseline → assume worst-case
            result.drawdown = 1.0
            result.should_pause = True
            result.alerts.append(AlphaAlert(
                timestamp=datetime.now(),
                level="critical",
                category="safety",
                message="Baseline NAV is zero or negative — emergency pause",
            ))

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

    def check_recovery(self, days_since_pause: int) -> RecoveryResult:
        """Check if system can resume after kill switch.

        Returns RecoveryResult with:
        - can_resume: bool -- True if cooldown period has passed
        - position_scale: float -- 0.5 to 1.0 based on ramp schedule
        - reason: str
        """
        cfg = self._config

        if days_since_pause < cfg.kill_switch_cooldown_days:
            return RecoveryResult(
                can_resume=False,
                position_scale=0.0,
                reason=f"Cooldown: {days_since_pause}/{cfg.kill_switch_cooldown_days} days",
            )

        # Ramp: days 0..ramp_days maps to recovery_pct..1.0
        days_in_ramp = days_since_pause - cfg.kill_switch_cooldown_days
        if days_in_ramp >= cfg.kill_switch_recovery_ramp_days:
            scale = 1.0
        else:
            start_pct = cfg.kill_switch_recovery_position_pct
            scale = start_pct + (1.0 - start_pct) * (
                days_in_ramp / cfg.kill_switch_recovery_ramp_days
            )

        return RecoveryResult(
            can_resume=True,
            position_scale=scale,
            reason=f"Ramping: {scale:.0%}",
        )

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


def check_momentum_crash(
    market_returns: pd.Series,
    market_threshold: float = -0.20,
    vol_multiplier: float = 2.0,
    lookback_return: int = 252,
    lookback_vol: int = 20,
    long_vol: int = 252,
) -> bool:
    """Detect momentum crash conditions (Daniel & Moskowitz 2016).

    Returns True if BOTH conditions are met:
    1. Trailing ``lookback_return``-day cumulative market return < ``market_threshold``
       (e.g., -20%).
    2. Recent ``lookback_vol``-day realized volatility > ``vol_multiplier`` times the
       long-term (``long_vol``-day) realized volatility.

    Parameters
    ----------
    market_returns:
        Daily market returns series (e.g., index or broad ETF).
    market_threshold:
        Cumulative return threshold (negative, e.g. -0.20 for -20%).
    vol_multiplier:
        How many times recent vol must exceed long-term vol.
    lookback_return:
        Number of trading days for trailing return calculation.
    lookback_vol:
        Number of trading days for recent volatility.
    long_vol:
        Number of trading days for long-term volatility.
    """
    if len(market_returns) < max(lookback_return, long_vol):
        return False

    # Condition 1: trailing cumulative return
    cum_product: float = (1 + market_returns.iloc[-lookback_return:]).prod()  # type: ignore[assignment]
    trailing_cum = cum_product - 1
    condition_return = trailing_cum < market_threshold

    # Condition 2: recent vol >> long-term vol
    recent_vol = float(market_returns.iloc[-lookback_vol:].std() * np.sqrt(252))
    longterm_vol = float(market_returns.iloc[-long_vol:].std() * np.sqrt(252))

    if longterm_vol <= 0:
        return False

    condition_vol = recent_vol > vol_multiplier * longterm_vol

    return bool(condition_return and condition_vol)
