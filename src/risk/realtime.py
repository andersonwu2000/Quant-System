"""
即時風控監控 — 基於 tick 資料的投資組合風險即時監控。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
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

    Thread-safe: on_price_update() can be called from Shioaji SDK thread.
    """

    def __init__(
        self,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        ws_manager: Any,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        execution_service: Any = None,
    ) -> None:
        self.portfolio = portfolio
        self.risk_engine = risk_engine
        self.ws_manager = ws_manager
        self.execution_service = execution_service  # for kill switch liquidation
        self._loop = loop
        # Price updates use portfolio.lock (shared with apply_trades) for thread safety
        self._nav_high: float = float(portfolio.nav)
        self._alerts_sent: set[str] = set()
        self._alerts_count: int = 0
        self._last_update: datetime | None = None
        self._last_reset_date: str = ""  # #17: auto reset tracking

    # ── Public API ────────────────────────────────────────

    def on_price_update(self, symbol: str, price: Decimal) -> None:
        """Called on each tick — update portfolio prices and check risk.

        Thread-safe: uses portfolio.lock to protect portfolio mutation.
        Portfolio.update_market_prices() also acquires portfolio.lock internally,
        but since threading.Lock is reentrant-safe within the same thread (we call
        update_market_prices while already holding the lock in this thread), we
        call it directly on the dict to avoid nested lock acquisition.
        No deadlock risk: Portfolio has a single threading.Lock and no other lock.
        """
        with self.portfolio.lock:
            # #4: 用台灣時間（UTC+8）判斷日期變更，避免 UTC midnight 提前 reset
            _tw_tz = timezone(timedelta(hours=8))
            now = datetime.now(_tw_tz)
            today_str = now.strftime("%Y-%m-%d")
            if self._last_reset_date and today_str != self._last_reset_date:
                self._nav_high = float(self.portfolio.nav)
                self._alerts_sent.clear()
                logger.info("RealtimeRiskMonitor auto-reset for new day %s", today_str)
            self._last_reset_date = today_str

            # 1. Update portfolio market price (direct dict mutation to avoid
            #    nested lock — update_market_prices() acquires portfolio.lock too)
            if symbol in self.portfolio.positions:
                self.portfolio.positions[symbol].market_price = price
            self._last_update = now

            # 2. Check intraday drawdown
            current_nav = float(self.portfolio.nav)
            self._nav_high = max(self._nav_high, current_nav)

        if self._nav_high == 0:
            return

        # Kill switch and alerts use current_nav snapshot taken inside lock — safe
        intraday_dd = (current_nav - self._nav_high) / self._nav_high

        # 3. Tiered alerts (outside lock to avoid blocking)
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
            # Trigger kill switch — schedule liquidation on event loop
            # (不在 Shioaji 線程中直接操作 portfolio，避免和 asyncio 側的
            #  mutation_lock 競爭。改為排程到 event loop 執行。)
            if self.risk_engine.kill_switch(self.portfolio):
                liq_orders = self.risk_engine.generate_liquidation_orders(self.portfolio)
                if liq_orders and self.execution_service is not None and self._loop is not None:
                    import asyncio

                    async def _execute_liquidation(orders: list[Any], svc: Any, pf: Any) -> None:
                        try:
                            trades = svc.submit_orders(orders, pf)
                            if trades:
                                from src.execution.oms import apply_trades
                                apply_trades(pf, trades)
                                logger.critical(
                                    "Kill switch (tick): %d liquidation trades, NAV=%s",
                                    len(trades), pf.nav,
                                )
                        except Exception:
                            logger.exception("Kill switch liquidation failed")

                    asyncio.run_coroutine_threadsafe(
                        _execute_liquidation(liq_orders, self.execution_service, self.portfolio),
                        self._loop,
                    )
                elif liq_orders:
                    logger.critical(
                        "Kill switch: %d liquidation orders but no ExecutionService/loop",
                        len(liq_orders),
                    )

    def poll_prices_from_feed(self, feed: Any) -> int:
        """Fallback price update when tick callbacks are unavailable.

        Returns number of successfully updated symbols.
        """
        updated = 0
        for symbol in list(self.portfolio.positions.keys()):
            try:
                price = feed.get_latest_price(symbol)
                if price and price > 0:
                    self.on_price_update(symbol, price)
                    updated += 1
            except Exception:
                logger.debug("Price poll failed for %s", symbol)
        if updated == 0 and self.portfolio.positions:
            logger.warning("Price poll: 0/%d symbols updated — feed may be broken",
                          len(self.portfolio.positions))
        return updated

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
