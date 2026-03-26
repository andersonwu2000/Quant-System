"""Strategy scheduler — periodic rebalance trigger."""

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
        """Start the scheduler with jobs from config."""
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

        # Parse cron expression from config
        # Default: "0 9 1 * *" = 1st of every month at 09:00
        trigger = CronTrigger.from_crontab(config.rebalance_cron)

        self._scheduler.add_job(  # type: ignore[union-attr]
            self._rebalance_job,
            trigger=trigger,
            id="rebalance",
            kwargs={"config": config},
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
        # This will be wired up to the rebalance-preview logic from Phase 3-2
        # and the notification system from Phase 3-3

        try:
            from src.scheduler.jobs import execute_rebalance

            await execute_rebalance(config)
        except Exception:
            logger.exception("Scheduled rebalance failed")
