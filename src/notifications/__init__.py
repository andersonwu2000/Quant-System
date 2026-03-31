"""Notification system — pluggable providers with severity levels.

Severity levels:
  P0 — CRITICAL: kill switch, position inconsistency → all channels immediately
  P1 — IMPORTANT: trade completion, QG failure, drift > 50bps → Discord
  P2 — INFO: heartbeat, daily summary, data refresh done → Discord
  P3 — DEBUG: factor evaluation, backtest details → log only (no Discord)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import IntEnum

logger = logging.getLogger(__name__)


class Severity(IntEnum):
    P0 = 0  # CRITICAL
    P1 = 1  # IMPORTANT
    P2 = 2  # INFO
    P3 = 3  # DEBUG


# Default: send P0-P2 to notification channels, P3 to log only
NOTIFY_THRESHOLD = Severity.P2


class NotificationProvider(ABC):
    """Base class for notification providers."""

    @abstractmethod
    async def send(self, title: str, message: str) -> bool:
        """Send a notification. Returns True if successful."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this provider has valid configuration."""


async def notify(
    notifier: NotificationProvider,
    severity: Severity | int,
    title: str,
    message: str = "",
) -> bool:
    """Send notification with severity filtering.

    P0-P2: send via notifier (Discord/LINE/Telegram)
    P3: log only, don't send
    """
    sev = Severity(severity) if isinstance(severity, int) else severity
    prefix = f"[{sev.name}] "

    if sev <= NOTIFY_THRESHOLD and notifier.is_configured():
        return await notifier.send(prefix + title, message)
    else:
        logger.info("Notify %s %s: %s", sev.name, title, message[:100])
        return False
