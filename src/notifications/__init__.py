"""Notification system — pluggable providers for trade alerts."""

from __future__ import annotations

from abc import ABC, abstractmethod


class NotificationProvider(ABC):
    """Base class for notification providers. Extensible for LINE, Slack, Email, etc."""

    @abstractmethod
    async def send(self, title: str, message: str) -> bool:
        """Send a notification. Returns True if successful."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this provider has valid configuration."""
