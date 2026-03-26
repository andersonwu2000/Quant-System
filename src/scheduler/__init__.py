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

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import TradingConfig

logger = logging.getLogger(__name__)

# R10.3: 全局執行鎖 — 防止多條路徑併發操作同一個 Portfolio
_pipeline_lock = asyncio.Lock()


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

        # ── Phase S: 統一交易管線（取代舊的 2-3 個 job） ──
        pipeline_cron = config.trading_pipeline_cron
        trigger = CronTrigger.from_crontab(pipeline_cron)
        self._scheduler.add_job(  # type: ignore[union-attr]
            self._run_pipeline,
            trigger=trigger,
            id="trading_pipeline",
            kwargs={"config": config},
        )

        self._scheduler.start()  # type: ignore[union-attr]
        self._running = True
        logger.info(
            "Scheduler started: strategy=%s, cron=%s",
            config.active_strategy, pipeline_cron,
        )

    def stop(self) -> None:
        if self._scheduler and self._running:
            self._scheduler.shutdown()  # type: ignore[attr-defined]
            self._running = False
            logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _run_pipeline(self, config: TradingConfig) -> None:
        """Phase S: 統一交易管線。"""
        if _pipeline_lock.locked():
            logger.warning("Pipeline lock held, skipping")
            return
        async with _pipeline_lock:
            try:
                from src.scheduler.jobs import execute_pipeline

                result = await execute_pipeline(config)
                logger.info("Pipeline result: %s (%d trades)", result.status, result.n_trades)
            except Exception:
                logger.exception("Pipeline failed")

    # ── Deprecated methods (kept for backward compat) ──

    async def _rebalance_job(self, config: TradingConfig) -> None:
        """[deprecated] Use _run_pipeline instead."""
        await self._run_pipeline(config)

    async def _revenue_update_then_rebalance(self, config: TradingConfig) -> None:
        """Monthly revenue: update data → rebalance (chained, R10.1).

        If update fails after retry, rebalance is skipped and alert is sent.
        Uses pipeline lock to prevent concurrent execution (R10.3).
        """
        if _pipeline_lock.locked():
            logger.warning("Pipeline lock held, skipping revenue pipeline")
            return
        async with _pipeline_lock:
            logger.info("Revenue pipeline started at %s", datetime.now())

            # Step 1: Update data
            from src.scheduler.jobs import monthly_revenue_update, monthly_revenue_rebalance

            update_ok = await monthly_revenue_update(max_retries=1)

            if not update_ok:
                # R10.6: update 失敗 → 通知 + 跳過 rebalance
                logger.error("Revenue update failed — skipping rebalance")
                try:
                    from src.notifications.factory import create_notifier
                    notifier = create_notifier(config)
                    if notifier.is_configured():
                        await notifier.send(
                            "Revenue Update FAILED",
                            "Monthly revenue data update failed after retry. "
                            "Rebalance skipped. Check logs.",
                        )
                except Exception:
                    logger.debug("Failed to send update-failure notification", exc_info=True)
                return

            # Step 2: Rebalance (only if update succeeded)
            logger.info("Revenue update OK — proceeding to rebalance")
            try:
                await monthly_revenue_rebalance(config)
            except Exception:
                logger.exception("Revenue rebalance failed after successful update")
