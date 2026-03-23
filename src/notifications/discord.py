"""Discord Webhook notification provider."""

from __future__ import annotations

import logging

from src.notifications import NotificationProvider

logger = logging.getLogger(__name__)


class DiscordNotifier(NotificationProvider):
    """Send notifications via Discord Webhook."""

    def __init__(self, webhook_url: str = "") -> None:
        self._webhook_url = webhook_url

    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    async def send(self, title: str, message: str) -> bool:
        """Send message via Discord Webhook using httpx."""
        if not self.is_configured():
            logger.warning("Discord not configured, skipping notification")
            return False

        try:
            import httpx

            payload = {
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": 3447003,  # blue
                    }
                ],
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self._webhook_url, json=payload, timeout=10
                )
                resp.raise_for_status()
                return True
        except Exception:
            logger.exception("Failed to send Discord notification")
            return False
