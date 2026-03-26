"""Strategy scheduler — periodic rebalance trigger.

Three mutually exclusive execution paths are managed here:

1. **General rebalance** — runs whichever strategy is currently "active"
   (configurable cron, default 1st of month 09:00).
2. **Auto-Alpha** — daily factor pipeline, started separately via
   ``POST /api/v1/auto-alpha/start``; has its own APScheduler instance
   inside ``AlphaScheduler``.
3. **Monthly revenue** — fixed ``revenue_momentum_hedged`` strategy,
   triggered on the 11th of each month (data update 08:30, rebalance 09:05).

These three paths should NOT run simultaneously. The general rebalance
and monthly revenue jobs are registered here; Auto-Alpha is managed by
``src/alpha/auto/scheduler.py``. Operators should ensure only one path
is active at a time by configuring ``scheduler_enabled``,
``revenue_scheduler_enabled``, and the Auto-Alpha /start endpoint
accordingly.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import TradingConfig

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages scheduled strategy runs using APScheduler."""

    def __init__(self) -> None:
        self._scheduler: object | None = None
        self._running = False

    def start(self, config: TradingConfig) -> None:
        """Start the scheduler with jobs from config.

        Registers up to three jobs depending on configuration:

        - **rebalance** (always): general strategy rebalance
          (cron from ``config.rebalance_cron``).
        - **revenue_update** (if ``revenue_scheduler_enabled``):
          monthly revenue data download (cron from ``config.revenue_update_cron``).
        - **revenue_rebalance** (if ``revenue_scheduler_enabled``):
          monthly revenue_momentum_hedged rebalance
          (cron from ``config.revenue_rebalance_cron``).
        """
        if not config.scheduler_enabled:
            logger.info("Scheduler disabled, skipping")
            return

        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            logger.warning("apscheduler not installed, scheduler disabled")
            return

        self._scheduler = AsyncIOScheduler()

        # ── Job 1: General rebalance ──────────────────────────────
        trigger = CronTrigger.from_crontab(config.rebalance_cron)
        self._scheduler.add_job(  # type: ignore[union-attr]
            self._rebalance_job,
            trigger=trigger,
            id="rebalance",
            kwargs={"config": config},
        )

        # ── Jobs 2 & 3: Monthly revenue (gated by revenue_scheduler_enabled) ──
        if config.revenue_scheduler_enabled:
            revenue_update_trigger = CronTrigger.from_crontab(config.revenue_update_cron)
            self._scheduler.add_job(  # type: ignore[union-attr]
                self._revenue_update_job,
                trigger=revenue_update_trigger,
                id="revenue_update",
            )

            revenue_rebalance_trigger = CronTrigger.from_crontab(config.revenue_rebalance_cron)
            self._scheduler.add_job(  # type: ignore[union-attr]
                self._revenue_rebalance_job,
                trigger=revenue_rebalance_trigger,
                id="revenue_rebalance",
                kwargs={"config": config},
            )
            logger.info(
                "Revenue jobs registered — update: %s, rebalance: %s",
                config.revenue_update_cron,
                config.revenue_rebalance_cron,
            )

        self._scheduler.start()  # type: ignore[union-attr]
        self._running = True
        logger.info("Scheduler started with cron: %s", config.rebalance_cron)

    def stop(self) -> None:
        if self._scheduler and self._running:
            self._scheduler.shutdown()  # type: ignore[attr-defined]
            self._running = False
            logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _rebalance_job(self, config: TradingConfig) -> None:
        """Execute rebalance: run strategy -> generate suggestions -> notify."""
        logger.info("Scheduled rebalance triggered at %s", datetime.now())

        try:
            from src.scheduler.jobs import execute_rebalance

            await execute_rebalance(config)
        except Exception:
            logger.exception("Scheduled rebalance failed")

    async def _revenue_update_job(self) -> None:
        """Monthly revenue data update (11th of month, 08:30)."""
        logger.info("Scheduled revenue update triggered at %s", datetime.now())

        try:
            from src.scheduler.jobs import monthly_revenue_update

            await monthly_revenue_update()
        except Exception:
            logger.exception("Scheduled revenue update failed")

    async def _revenue_rebalance_job(self, config: TradingConfig) -> None:
        """Monthly revenue rebalance (11th of month, 09:05)."""
        logger.info("Scheduled revenue rebalance triggered at %s", datetime.now())

        try:
            from src.scheduler.jobs import monthly_revenue_rebalance

            await monthly_revenue_rebalance(config)
        except Exception:
            logger.exception("Scheduled revenue rebalance failed")
