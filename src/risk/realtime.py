"""
即時風控監控 — 基於 tick 資料的投資組合風險即時監控。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.core.models import Portfolio
from src.risk.engine import RiskEngine

logger = logging.getLogger(__name__)


class RealtimeRiskMonitor:
    """Monitors portfolio risk metrics in real-time using tick data.

    Tracks intraday NAV high-water mark and broadcasts tiered drawdown
    alerts via WebSocket.  When drawdown exceeds the kill-switch
    threshold the ``RiskEngine.kill_switch`` is invoked automatically.
    """

    def __init__(
        self,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        ws_manager: Any,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self.portfolio = portfolio
        self.risk_engine = risk_engine
        self.ws_manager = ws_manager
        self._loop = loop
        self._nav_high: float = float(portfolio.nav)
        self._alerts_sent: set[str] = set()
        self._alerts_count: int = 0
        self._last_update: datetime | None = None

    # ── Public API ────────────────────────────────────────

    def on_price_update(self, symbol: str, price: Decimal) -> None:
        """Called on each tick — update portfolio prices and check risk.

        This method is safe to call from *any* thread (e.g. the Shioaji
        SDK background thread).
        """
        # 1. Update portfolio market price
        self.portfolio.update_market_prices({symbol: price})
        self._last_update = datetime.now(timezone.utc)

        # 2. Check intraday drawdown
        current_nav = float(self.portfolio.nav)
        self._nav_high = max(self._nav_high, current_nav)

        if self._nav_high == 0:
            return

        intraday_dd = (current_nav - self._nav_high) / self._nav_high

        # 3. Tiered alerts
        if intraday_dd < -0.02 and "dd_2pct" not in self._alerts_sent:
            self._broadcast_alert(
                "warning",
                f"Intraday drawdown {intraday_dd:.1%}",
            )
            self._alerts_sent.add("dd_2pct")

        if intraday_dd < -0.03 and "dd_3pct" not in self._alerts_sent:
            self._broadcast_alert(
                "critical",
                f"Intraday drawdown {intraday_dd:.1%} — approaching kill switch",
            )
            self._alerts_sent.add("dd_3pct")

        if intraday_dd < -0.05 and "kill_switch" not in self._alerts_sent:
            self._broadcast_alert(
                "emergency",
                f"KILL SWITCH: drawdown {intraday_dd:.1%}",
            )
            self._alerts_sent.add("kill_switch")
            # Trigger kill switch
            self.risk_engine.kill_switch(self.portfolio)

    def reset_daily(self) -> None:
        """Call at market open to reset intraday tracking."""
        self._nav_high = float(self.portfolio.nav)
        self._alerts_sent.clear()

    def get_status(self) -> dict[str, Any]:
        """Return current realtime risk status for the API."""
        current_nav = float(self.portfolio.nav)
        if self._nav_high > 0:
            intraday_dd = (current_nav - self._nav_high) / self._nav_high
        else:
            intraday_dd = 0.0

        return {
            "nav_current": current_nav,
            "nav_high": self._nav_high,
            "intraday_drawdown": round(intraday_dd, 6),
            "alerts_sent": len(self._alerts_sent),
            "alerts_total": self._alerts_count,
            "last_update": (
                self._last_update.isoformat() if self._last_update else None
            ),
        }

    # ── Internal ──────────────────────────────────────────

    def _broadcast_alert(self, level: str, message: str) -> None:
        """Fire-and-forget WS broadcast to the alerts channel."""
        self._alerts_count += 1
        payload: dict[str, Any] = {
            "type": "realtime_risk",
            "level": level,
            "message": message,
            "nav": float(self.portfolio.nav),
            "nav_high": self._nav_high,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.warning("Realtime risk alert [%s]: %s", level, message)

        loop = self._loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.ws_manager.broadcast("alerts", payload),
                loop,
            )
        else:
            # Best-effort: try to get the current running event loop
            try:
                current_loop = asyncio.get_running_loop()
                asyncio.run_coroutine_threadsafe(
                    self.ws_manager.broadcast("alerts", payload),
                    current_loop,
                )
            except RuntimeError:
                logger.debug("No running event loop available for broadcast")
