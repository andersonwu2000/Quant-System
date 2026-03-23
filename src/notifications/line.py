"""LINE Notify notification provider."""

from __future__ import annotations

import logging

from src.notifications import NotificationProvider

logger = logging.getLogger(__name__)


class LineNotifier(NotificationProvider):
    """Send notifications via LINE Notify API.

    Setup: https://notify-bot.line.me/ → generate personal access token.
    """

    def __init__(self, access_token: str = "") -> None:
        self._access_token = access_token

    def is_configured(self) -> bool:
        return bool(self._access_token)

    async def send(self, title: str, message: str) -> bool:
        """Send message via LINE Notify API using httpx."""
        if not self.is_configured():
            logger.warning("LINE Notify not configured, skipping notification")
            return False

        try:
            import httpx

            url = "https://notify-api.line.me/api/notify"
            headers = {"Authorization": f"Bearer {self._access_token}"}
            data = {"message": f"\n{title}\n\n{message}"}
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url, headers=headers, data=data, timeout=10
                )
                resp.raise_for_status()
                return True
        except Exception:
            logger.exception("Failed to send LINE notification")
            return False
