"""Scheduler — daily operations orchestrator.

Single daily_ops entry point replaces scattered cron jobs.
execute_pipeline is called by daily_ops, not separately scheduled.

Flow: daily_ops (07:50) → [trading day?] → TWSE snapshot → execute_pipeline → heartbeat
      eod_ops  (13:30) → reconcile → backtest reconcile → daily summary → heartbeat
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import TradingConfig

logger = logging.getLogger(__name__)

# R10.3: 全局執行鎖 — 防止多條路徑併發操作同一個 Portfolio
_pipeline_lock = asyncio.Lock()


class SchedulerService:
    """Manages daily trading operations via APScheduler.

    Two jobs:
      1. daily_ops (07:50 weekdays) — pre-market + trading + heartbeat
      2. eod_ops  (13:30 weekdays) — reconciliation + daily summary
    """

    def __init__(self) -> None:
        self._scheduler: object | None = None
        self._running = False

    def start(self, config: TradingConfig) -> None:
        """Start the scheduler with daily_ops + eod_ops."""
        if not config.scheduler_enabled:
            logger.info("Scheduler disabled, skipping")
            return

        # Crash recovery: check for pipeline runs that never finished
        from src.scheduler.jobs import check_crashed_runs
        crashed = check_crashed_runs()
        for run in crashed:
            logger.warning(
                "Detected crashed pipeline run: run_id=%s, strategy=%s",
                run.get("run_id", "?"), run.get("strategy", "?"),
            )

        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            logger.warning("apscheduler not installed, scheduler disabled")
            return

        self._scheduler = AsyncIOScheduler()

        # ── daily_ops: 07:50 weekdays ────────────────────────────────
        # Trading day check is inside daily_ops, not in cron filter.
        # This ensures heartbeat "休市" message is sent on holidays.
        self._scheduler.add_job(
            self._run_daily_ops,
            trigger=CronTrigger(hour=7, minute=50, day_of_week="mon-fri"),
            id="daily_ops",
            kwargs={"config": config},
        )

        # ── eod_ops: 13:30 weekdays ─────────────────────────────────
        self._scheduler.add_job(
            self._run_eod_ops,
            trigger=CronTrigger(hour=13, minute=30, day_of_week="mon-fri"),
            id="eod_ops",
            kwargs={"config": config},
        )

        self._scheduler.start()
        self._running = True
        logger.info(
            "Scheduler started: strategy=%s, daily_ops=07:50, eod_ops=13:30",
            config.active_strategy,
        )

    def stop(self) -> None:
        if self._scheduler and self._running:
            self._scheduler.shutdown()  # type: ignore[attr-defined]
            self._running = False
            logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _run_daily_ops(self, config: TradingConfig) -> None:
        """Pre-market + trading. Acquires pipeline lock."""
        if _pipeline_lock.locked():
            logger.warning("Pipeline lock held, skipping daily_ops")
            return
        async with _pipeline_lock:
            try:
                from src.scheduler.ops import daily_ops
                result = await daily_ops(config)
                logger.info("daily_ops result: %s", result.get("status", "unknown"))
            except Exception:
                logger.exception("daily_ops failed")

    async def _run_eod_ops(self, config: TradingConfig) -> None:
        """Post-market reconciliation + summary."""
        # EOD doesn't need pipeline lock (no portfolio mutation)
        try:
            from src.scheduler.ops import eod_ops
            result = await eod_ops(config)
            logger.info("eod_ops result: %s", result)
        except Exception:
            logger.exception("eod_ops failed")
