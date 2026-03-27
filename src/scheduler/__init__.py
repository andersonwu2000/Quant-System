"""Strategy scheduler — Phase S 統一交易管線。

一條 Trading Pipeline（由 QUANT_ACTIVE_STRATEGY + QUANT_TRADING_PIPELINE_CRON 控制）。
Auto-Alpha Research Pipeline 獨立運行（不操作 Portfolio），由 ``POST /auto-alpha/start`` 觸發。

流程：cron → execute_pipeline(config)
  → 數據更新（營收策略自動下載 FinMind）
  → strategy.on_bar() → weights_to_orders()
  → RiskEngine → ExecutionService → apply_trades()
  → 持久化 + 通知
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
    """Manages scheduled strategy runs using APScheduler."""

    def __init__(self) -> None:
        self._scheduler: object | None = None
        self._running = False

    def start(self, config: TradingConfig) -> None:
        """Start the scheduler with the unified trading pipeline.

        Registers one job: ``trading_pipeline`` (cron from ``config.trading_pipeline_cron``).
        Strategy is determined by ``config.active_strategy``.
        """
        if not config.scheduler_enabled:
            logger.info("Scheduler disabled, skipping")
            return

        # Crash recovery: check for pipeline runs that never finished
        from src.scheduler.jobs import check_crashed_runs

        crashed = check_crashed_runs()
        for run in crashed:
            logger.warning(
                "Detected crashed pipeline run: run_id=%s, strategy=%s, started_at=%s",
                run.get("run_id", "?"),
                run.get("strategy", "?"),
                run.get("started_at", "?"),
            )

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
        """Phase S: 統一交易管線。

        Note: The locked() check + acquire is technically TOCTOU, but acceptable
        because asyncio.Lock is single-threaded — no preemption between check and
        acquire within the same coroutine execution slice.
        """
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

    # Deprecated methods removed in Phase S cleanup.
    # Git history preserves them (commit fc5eab4).
