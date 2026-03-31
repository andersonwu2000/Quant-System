"""Notification system unit tests — Discord, LINE, Telegram providers & formatter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.notifications.discord import DiscordNotifier
from src.notifications.line import LineNotifier
from src.notifications.telegram import TelegramNotifier
from src.notifications.factory import create_notifier
from src.notifications.formatter import format_rebalance_notification


# ── Discord ──────────────────────────────────────────────


class TestDiscordNotifier:
    def test_not_configured_when_empty(self) -> None:
        assert DiscordNotifier().is_configured() is False

    def test_configured_when_url_set(self) -> None:
        assert DiscordNotifier(webhook_url="https://discord.com/api/webhooks/x/y").is_configured() is True

    async def test_send_not_configured_returns_false(self) -> None:
        result = await DiscordNotifier().send("title", "body")
        assert result is False

    async def test_send_success(self) -> None:
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/x/y")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await notifier.send("Test", "Body")

        assert result is True
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://discord.com/api/webhooks/x/y"
        embeds = call_args[1]["json"]["embeds"]
        assert embeds[0]["title"] == "Test"

    async def test_send_failure_returns_false(self) -> None:
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/x/y")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Network error"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await notifier.send("Title", "Body")

        assert result is False


# ── LINE ─────────────────────────────────────────────────


class TestLineNotifier:
    def test_not_configured_when_empty(self) -> None:
        assert LineNotifier().is_configured() is False

    def test_configured_when_token_set(self) -> None:
        assert LineNotifier(access_token="tok").is_configured() is True

    async def test_send_not_configured_returns_false(self) -> None:
        result = await LineNotifier().send("title", "body")
        assert result is False

    async def test_send_success(self) -> None:
        notifier = LineNotifier(access_token="fake-token")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await notifier.send("Test Title", "Test Body")

        assert result is True
        call_args = mock_client.post.call_args
        assert "notify-api.line.me" in call_args[0][0]
        assert "Bearer fake-token" in call_args[1]["headers"]["Authorization"]


# ── Telegram ─────────────────────────────────────────────


class TestTelegramNotifier:
    def test_not_configured_when_empty(self) -> None:
        assert TelegramNotifier().is_configured() is False

    def test_not_configured_missing_chat_id(self) -> None:
        assert TelegramNotifier(bot_token="tok").is_configured() is False

    def test_configured_when_both_set(self) -> None:
        assert TelegramNotifier(bot_token="tok", chat_id="123").is_configured() is True

    async def test_send_not_configured_returns_false(self) -> None:
        result = await TelegramNotifier().send("title", "body")
        assert result is False

    async def test_send_success(self) -> None:
        notifier = TelegramNotifier(bot_token="fake-token", chat_id="12345")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await notifier.send("Test Title", "Test Body")

        assert result is True
        call_args = mock_client.post.call_args
        assert "fake-token" in call_args[0][0]
        assert call_args[1]["json"]["chat_id"] == "12345"


# ── Factory ──────────────────────────────────────────────


class TestFactory:
    def test_explicit_discord(self) -> None:
        from src.core.config import TradingConfig

        cfg = TradingConfig(
            notify_provider="discord",
            discord_webhook_url="https://discord.com/api/webhooks/x/y",
        )
        n = create_notifier(cfg)
        assert isinstance(n, DiscordNotifier)
        assert n.is_configured() is True

    def test_explicit_line(self) -> None:
        from src.core.config import TradingConfig

        cfg = TradingConfig(
            notify_provider="line",
            line_notify_token="tok",
        )
        n = create_notifier(cfg)
        assert isinstance(n, LineNotifier)
        assert n.is_configured() is True

    def test_auto_detect_discord(self) -> None:
        from src.core.config import TradingConfig

        cfg = TradingConfig(discord_webhook_url="https://discord.com/api/webhooks/x/y")
        n = create_notifier(cfg)
        assert isinstance(n, DiscordNotifier)

    def test_auto_detect_line(self) -> None:
        from src.core.config import TradingConfig

        # Explicitly clear discord so line is auto-detected
        cfg = TradingConfig(
            line_notify_token="tok",
            discord_webhook_url="",
            notify_provider="",
        )
        n = create_notifier(cfg)
        assert isinstance(n, LineNotifier)

    def test_no_config_returns_null(self) -> None:
        from src.core.config import TradingConfig

        # Explicitly clear all notification providers
        cfg = TradingConfig(
            discord_webhook_url="",
            line_notify_token="",
            telegram_bot_token="",
            telegram_chat_id="",
            notify_provider="",
        )
        n = create_notifier(cfg)
        assert n.is_configured() is False


# ── Formatter ────────────────────────────────────────────


class TestFormatter:
    def test_buy_and_sell(self) -> None:
        trades = [
            {"symbol": "2330.TW", "side": "BUY", "quantity": 1000, "estimated_cost": 580000},
            {"symbol": "2317.TW", "side": "SELL", "quantity": 500, "estimated_cost": 52500},
        ]
        title, message = format_rebalance_notification(
            strategy_name="momentum",
            suggested_trades=trades,
            estimated_commission=900,
            estimated_tax=158,
        )
        assert "momentum" in title
        assert "2330.TW" in message
        assert "2317.TW" in message
        assert "580,000" in message
        assert "900" in message
        assert "買進" in message
        assert "賣出" in message

    def test_empty_trades(self) -> None:
        title, message = format_rebalance_notification(
            strategy_name="test_strat",
            suggested_trades=[],
            estimated_commission=0,
            estimated_tax=0,
        )
        assert "test_strat" in title
        assert "$0" in message
