"""Scheduler API routes — view and manage scheduled jobs."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.api.auth import verify_api_key, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class JobInfo(BaseModel):
    name: str
    schedule: str
    enabled: bool
    last_run: str | None = None
    next_run: str | None = None

@router.get("/jobs", response_model=list[JobInfo])
async def list_scheduled_jobs(
    api_key: str = Depends(verify_api_key),
) -> list[JobInfo]:
    """List all scheduled jobs."""
    from src.core.config import get_config
    config = get_config()

    jobs = []
    if config.scheduler_enabled:
        jobs.append(JobInfo(
            name="daily_snapshot",
            schedule="0 14 * * 1-5",
            enabled=True,
        ))
        if config.rebalance_cron:
            jobs.append(JobInfo(
                name="rebalance",
                schedule=config.rebalance_cron,
                enabled=True,
            ))

    return jobs


class NotificationRequest(BaseModel):
    message: str
    channels: list[str] = ["all"]  # "discord" | "line" | "telegram" | "all"

class NotificationResponse(BaseModel):
    sent: list[str]
    failed: list[str]

@router.post("/notify", response_model=NotificationResponse)
async def send_notification(
    req: NotificationRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> NotificationResponse:
    """Send a manual notification to configured channels."""
    sent = []
    failed = []

    try:
        from src.core.config import get_config
        config = get_config()

        channels = req.channels if "all" not in req.channels else ["discord", "line", "telegram"]

        for ch in channels:
            try:
                if ch == "discord" and config.discord_webhook_url:
                    from src.notifications.discord import DiscordNotifier
                    discord_notifier = DiscordNotifier(webhook_url=config.discord_webhook_url)
                    await discord_notifier.send("Notification", req.message)
                    sent.append("discord")
                elif ch == "line" and config.line_notify_token:
                    from src.notifications.line import LineNotifier
                    line_notifier = LineNotifier(access_token=config.line_notify_token)
                    await line_notifier.send("Notification", req.message)
                    sent.append("line")
                elif ch == "telegram" and config.telegram_bot_token:
                    from src.notifications.telegram import TelegramNotifier
                    telegram_notifier = TelegramNotifier(bot_token=config.telegram_bot_token, chat_id=config.telegram_chat_id)
                    await telegram_notifier.send("Notification", req.message)
                    sent.append("telegram")
                else:
                    failed.append(f"{ch}: not configured")
            except Exception as e:
                failed.append(f"{ch}: {str(e)}")
    except Exception as e:
        failed.append(f"config error: {str(e)}")

    return NotificationResponse(sent=sent, failed=failed)


# ── Manual Job Triggers ────────────────────────────────────────


class JobTriggerResponse(BaseModel):
    job: str
    status: str
    message: str


@router.post("/trigger/{job_name}", response_model=JobTriggerResponse)
async def trigger_job(
    job_name: str,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> JobTriggerResponse:
    """Manually trigger a scheduled job."""
    if job_name == "revenue_update":
        try:
            from src.scheduler.jobs import monthly_revenue_update
            await monthly_revenue_update()
            return JobTriggerResponse(job=job_name, status="completed", message="Revenue data updated")
        except Exception as e:
            return JobTriggerResponse(job=job_name, status="failed", message=str(e))

    elif job_name in ("revenue_rebalance", "pipeline"):
        try:
            from src.core.config import get_config
            from src.scheduler.jobs import execute_pipeline
            config = get_config()
            result = await execute_pipeline(config)
            return JobTriggerResponse(job="pipeline", status=result.status,
                                     message=f"Pipeline executed: {result.n_trades} trades")
        except Exception as e:
            return JobTriggerResponse(job="pipeline", status="failed", message=str(e))

    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_name}. Available: revenue_update, pipeline")
