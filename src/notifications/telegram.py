"""Telegram Bot notification provider."""

from __future__ import annotations

import logging

from src.notifications import NotificationProvider

logger = logging.getLogger(__name__)


class TelegramNotifier(NotificationProvider):
    """Send notifications via Telegram Bot API."""

    def __init__(self, bot_token: str = "", chat_id: str = "") -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    def is_configured(self) -> bool:
        return bool(self._bot_token and self._chat_id)

    async def send(self, title: str, message: str) -> bool:
        """Send message via Telegram Bot API using httpx (no heavy dependency)."""
        if not self.is_configured():
            logger.warning("Telegram not configured, skipping notification")
            return False

        try:
            import httpx

            url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"
            payload = {
                "chat_id": self._chat_id,
                "text": f"*{title}*\n\n{message}",
                "parse_mode": "Markdown",
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10)
                resp.raise_for_status()
                return True
        except Exception:
            logger.exception("Failed to send Telegram notification")
            return False
