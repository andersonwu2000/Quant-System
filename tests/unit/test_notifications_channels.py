"""Tests for src/notifications/ — Factory, channels, formatter.

Covers:
- NotificationFactory (create_notifier) with auto-detection and explicit provider
- NullNotifier behavior
- DiscordNotifier: is_configured, send (mocked HTTP)
- LineNotifier: is_configured, send (mocked HTTP)
- TelegramNotifier: is_configured, send (mocked HTTP)
- Message formatting (format_rebalance_notification)
- Error handling for failed sends
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.notifications import NotificationProvider
from src.notifications.discord import DiscordNotifier
from src.notifications.factory import _NullNotifier, create_notifier
from src.notifications.formatter import format_rebalance_notification
from src.notifications.line import LineNotifier
from src.notifications.telegram import TelegramNotifier


# ── Helpers ──────────────────────────────────────────────────


def _make_config(**overrides) -> MagicMock:
    """Create a mock TradingConfig with notification fields."""
    cfg = MagicMock()
    cfg.notify_provider = overrides.get("notify_provider", "")
    cfg.discord_webhook_url = overrides.get("discord_webhook_url", "")
    cfg.line_notify_token = overrides.get("line_notify_token", "")
    cfg.telegram_bot_token = overrides.get("telegram_bot_token", "")
    cfg.telegram_chat_id = overrides.get("telegram_chat_id", "")
    return cfg


# ── Factory (create_notifier) ────────────────────────────────


class TestCreateNotifier:
    def test_null_notifier_when_nothing_configured(self) -> None:
        cfg = _make_config()
        notifier = create_notifier(cfg)
        assert isinstance(notifier, _NullNotifier)
        assert notifier.is_configured() is False

    def test_explicit_discord(self) -> None:
        cfg = _make_config(
            notify_provider="discord",
            discord_webhook_url="https://discord.com/api/webhooks/test",
        )
        notifier = create_notifier(cfg)
        assert isinstance(notifier, DiscordNotifier)

    def test_explicit_line(self) -> None:
        cfg = _make_config(
            notify_provider="line",
            line_notify_token="test_token",
        )
        notifier = create_notifier(cfg)
        assert isinstance(notifier, LineNotifier)

    def test_explicit_telegram(self) -> None:
        cfg = _make_config(
            notify_provider="telegram",
            telegram_bot_token="bot123",
            telegram_chat_id="chat456",
        )
        notifier = create_notifier(cfg)
        assert isinstance(notifier, TelegramNotifier)

    def test_auto_detect_discord(self) -> None:
        cfg = _make_config(discord_webhook_url="https://discord.com/api/webhooks/auto")
        notifier = create_notifier(cfg)
        assert isinstance(notifier, DiscordNotifier)

    def test_auto_detect_line(self) -> None:
        cfg = _make_config(line_notify_token="auto_token")
        notifier = create_notifier(cfg)
        assert isinstance(notifier, LineNotifier)

    def test_auto_detect_telegram(self) -> None:
        cfg = _make_config(telegram_bot_token="auto_bot", telegram_chat_id="auto_chat")
        notifier = create_notifier(cfg)
        assert isinstance(notifier, TelegramNotifier)

    def test_auto_detect_priority_discord_first(self) -> None:
        """When multiple providers are configured, discord takes priority."""
        cfg = _make_config(
            discord_webhook_url="https://discord.com/api/webhooks/x",
            line_notify_token="token",
            telegram_bot_token="bot",
            telegram_chat_id="chat",
        )
        notifier = create_notifier(cfg)
        assert isinstance(notifier, DiscordNotifier)

    def test_auto_detect_line_before_telegram(self) -> None:
        """When line and telegram are both configured, line takes priority."""
        cfg = _make_config(
            line_notify_token="token",
            telegram_bot_token="bot",
            telegram_chat_id="chat",
        )
        notifier = create_notifier(cfg)
        assert isinstance(notifier, LineNotifier)

    def test_unknown_provider_returns_null(self) -> None:
        cfg = _make_config(notify_provider="slack")
        notifier = create_notifier(cfg)
        assert isinstance(notifier, _NullNotifier)


# ── NullNotifier ─────────────────────────────────────────────


class TestNullNotifier:
    def test_is_configured(self) -> None:
        n = _NullNotifier()
        assert n.is_configured() is False

    @pytest.mark.asyncio
    async def test_send_returns_false(self) -> None:
        n = _NullNotifier()
        result = await n.send("Title", "Body")
        assert result is False

    def test_is_notification_provider(self) -> None:
        n = _NullNotifier()
        assert isinstance(n, NotificationProvider)


# ── DiscordNotifier ──────────────────────────────────────────


class TestDiscordNotifier:
    def test_not_configured_empty_url(self) -> None:
        d = DiscordNotifier(webhook_url="")
        assert d.is_configured() is False

    def test_configured_with_url(self) -> None:
        d = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")
        assert d.is_configured() is True

    @pytest.mark.asyncio
    async def test_send_not_configured(self) -> None:
        d = DiscordNotifier(webhook_url="")
        result = await d.send("Title", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        d = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await d.send("Test Title", "Test Message")

        assert result is True
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "embeds" in payload
        assert payload["embeds"][0]["title"] == "Test Title"
        assert payload["embeds"][0]["description"] == "Test Message"

    @pytest.mark.asyncio
    async def test_send_http_error(self) -> None:
        d = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("HTTP 500"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await d.send("Title", "Body")

        assert result is False


# ── LineNotifier ─────────────────────────────────────────────


class TestLineNotifier:
    def test_not_configured_empty_token(self) -> None:
        ln = LineNotifier(access_token="")
        assert ln.is_configured() is False

    def test_configured_with_token(self) -> None:
        ln = LineNotifier(access_token="test_token_123")
        assert ln.is_configured() is True

    @pytest.mark.asyncio
    async def test_send_not_configured(self) -> None:
        ln = LineNotifier(access_token="")
        result = await ln.send("Title", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        ln = LineNotifier(access_token="test_token")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await ln.send("Test Title", "Test Message")

        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        # LINE uses form data, not json
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers")
        assert "Bearer test_token" in headers["Authorization"]

    @pytest.mark.asyncio
    async def test_send_http_error(self) -> None:
        ln = LineNotifier(access_token="test_token")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await ln.send("Title", "Body")

        assert result is False


# ── TelegramNotifier ─────────────────────────────────────────


class TestTelegramNotifier:
    def test_not_configured_empty(self) -> None:
        t = TelegramNotifier(bot_token="", chat_id="")
        assert t.is_configured() is False

    def test_not_configured_missing_chat_id(self) -> None:
        t = TelegramNotifier(bot_token="bot123", chat_id="")
        assert t.is_configured() is False

    def test_not_configured_missing_bot_token(self) -> None:
        t = TelegramNotifier(bot_token="", chat_id="chat456")
        assert t.is_configured() is False

    def test_configured_both_set(self) -> None:
        t = TelegramNotifier(bot_token="bot123", chat_id="chat456")
        assert t.is_configured() is True

    @pytest.mark.asyncio
    async def test_send_not_configured(self) -> None:
        t = TelegramNotifier(bot_token="", chat_id="")
        result = await t.send("Title", "Body")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        t = TelegramNotifier(bot_token="bot123", chat_id="chat456")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await t.send("Test Title", "Test Message")

        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        # Verify URL contains bot token
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
        assert "bot123" in url
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["chat_id"] == "chat456"
        assert "Test Title" in payload["text"]
        assert payload["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_send_http_error(self) -> None:
        t = TelegramNotifier(bot_token="bot123", chat_id="chat456")

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await t.send("Title", "Body")

        assert result is False


# ── Formatter ────────────────────────────────────────────────


class TestFormatter:
    def test_format_rebalance_basic(self) -> None:
        trades = [
            {"symbol": "2330.TW", "side": "BUY", "quantity": 1000, "estimated_cost": 600000},
            {"symbol": "2317.TW", "side": "SELL", "quantity": 500, "estimated_cost": -60000},
        ]
        title, body = format_rebalance_notification(
            strategy_name="momentum",
            suggested_trades=trades,
            estimated_commission=855,
            estimated_tax=180,
        )
        assert "momentum" in title
        assert "2330.TW" in body
        assert "2317.TW" in body
        assert "855" in body
        assert "180" in body

    def test_format_empty_trades(self) -> None:
        title, body = format_rebalance_notification(
            strategy_name="test",
            suggested_trades=[],
            estimated_commission=0,
            estimated_tax=0,
        )
        assert "test" in title
        assert "$0" in body

    def test_format_buy_emoji(self) -> None:
        trades = [{"symbol": "X", "side": "BUY", "quantity": 100, "estimated_cost": 1000}]
        _, body = format_rebalance_notification("s", trades, 0, 0)
        assert "\U0001f7e2" in body  # green circle for BUY

    def test_format_sell_emoji(self) -> None:
        trades = [{"symbol": "X", "side": "SELL", "quantity": 100, "estimated_cost": -1000}]
        _, body = format_rebalance_notification("s", trades, 0, 0)
        assert "\U0001f534" in body  # red circle for SELL

    def test_format_returns_tuple(self) -> None:
        result = format_rebalance_notification("s", [], 0, 0)
        assert isinstance(result, tuple)
        assert len(result) == 2
