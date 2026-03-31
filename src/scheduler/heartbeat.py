"""Heartbeat monitor — Discord ping at key daily milestones.

Events:
  "start"  — 07:50 system startup
  "trade"  — post-pipeline execution
  "skip"   — non-rebalance day
  "eod"    — post-market reconciliation done
  "rest"   — holiday, no action today
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


async def heartbeat(event: str, message: str = "") -> None:
    """Send heartbeat notification via configured notifier.

    Uses P2 level (informational). Only sends if notifier is configured.
    """
    from src.core.config import get_config
    from src.notifications.factory import create_notifier

    config = get_config()
    notifier = create_notifier(config)

    if not notifier.is_configured():
        logger.debug("Heartbeat [%s]: %s (notifier not configured)", event, message)
        return

    timestamp = datetime.now().strftime("%H:%M")
    prefix = {
        "start": "[HB] Pre-Market",
        "trade": "[HB] Trade Done",
        "skip": "[HB] No Trade",
        "eod": "[HB] EOD",
        "rest": "[HB] Holiday",
    }.get(event, f"[HB] {event}")

    full_message = f"{prefix} ({timestamp}): {message}" if message else f"{prefix} ({timestamp})"

    try:
        await notifier.send("Heartbeat", full_message)
        logger.info("Heartbeat [%s]: %s", event, message)
    except Exception:
        logger.warning("Heartbeat send failed for event=%s", event)
