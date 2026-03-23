"""Notification provider factory — create the right notifier from config."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.notifications import NotificationProvider

if TYPE_CHECKING:
    from src.config import TradingConfig

logger = logging.getLogger(__name__)


class _NullNotifier(NotificationProvider):
    """No-op notifier when nothing is configured."""

    def is_configured(self) -> bool:
        return False

    async def send(self, title: str, message: str) -> bool:
        logger.debug("No notification provider configured, message discarded")
        return False


def create_notifier(config: TradingConfig) -> NotificationProvider:
    """Create a notification provider based on config.notify_provider.

    Falls back to auto-detection if notify_provider is empty:
    checks discord → line → telegram in order.
    """
    provider = config.notify_provider

    # Auto-detect if not explicitly set
    if not provider:
        if config.discord_webhook_url:
            provider = "discord"
        elif config.line_notify_token:
            provider = "line"
        elif config.telegram_bot_token and config.telegram_chat_id:
            provider = "telegram"

    if provider == "discord":
        from src.notifications.discord import DiscordNotifier
        return DiscordNotifier(webhook_url=config.discord_webhook_url)

    if provider == "line":
        from src.notifications.line import LineNotifier
        return LineNotifier(access_token=config.line_notify_token)

    if provider == "telegram":
        from src.notifications.telegram import TelegramNotifier
        return TelegramNotifier(
            bot_token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
        )

    return _NullNotifier()
