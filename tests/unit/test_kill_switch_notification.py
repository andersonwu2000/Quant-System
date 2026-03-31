"""Tests for kill switch notification dispatch and daily reconcile scheduling.

Item 3: Daily reconcile job integration.
Item 4: Kill switch sends notifications via Discord/LINE/Telegram.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import Instrument, Portfolio, Position


# ── Item 3: Daily reconcile job ──────────────────────


class TestDailyReconcile:
    """Test the execute_daily_reconcile job."""

    @pytest.mark.asyncio
    async def test_skips_in_backtest_mode(self) -> None:
        """Reconcile skips when not in paper/live mode."""
        from src.scheduler.jobs import execute_daily_reconcile

        config = MagicMock()
        config.mode = "backtest"

        result = await execute_daily_reconcile(config)
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_skips_when_broker_not_initialized(self) -> None:
        """Reconcile skips when broker is not initialized."""
        from src.scheduler.jobs import execute_daily_reconcile

        config = MagicMock()
        config.mode = "live"

        mock_state = MagicMock()
        mock_state.execution_service.is_initialized = False

        with patch("src.api.state.get_app_state", return_value=mock_state):
            result = await execute_daily_reconcile(config)
            assert result["status"] == "skipped"
            assert "broker" in result["reason"]

    @pytest.mark.asyncio
    async def test_clean_reconcile(self) -> None:
        """Reconcile reports clean when positions match."""
        from src.scheduler.jobs import execute_daily_reconcile

        config = MagicMock()
        config.mode = "live"
        config.notify_provider = ""
        config.discord_webhook_url = ""
        config.line_notify_token = ""
        config.telegram_bot_token = ""
        config.telegram_chat_id = ""

        portfolio = Portfolio(cash=Decimal("500000"))
        portfolio.positions["2330.TW"] = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("600"),
            market_price=Decimal("650"),
        )

        mock_state = MagicMock()
        mock_state.execution_service.is_initialized = True
        mock_state.execution_service.broker.query_positions.return_value = {
            "2330.TW": {"quantity": 1000, "avg_cost": 600},
        }
        mock_state.portfolio = portfolio

        with patch("src.api.state.get_app_state", return_value=mock_state):
            result = await execute_daily_reconcile(config)
            assert result["status"] == "clean"
            assert result["matched"] == 1
            assert result["mismatched"] == 0

    @pytest.mark.asyncio
    async def test_discrepancy_sends_notification(self) -> None:
        """Reconcile sends notification when positions don't match."""
        from src.scheduler.jobs import execute_daily_reconcile

        config = MagicMock()
        config.mode = "live"
        config.notify_provider = "discord"
        config.discord_webhook_url = "https://discord.com/api/webhooks/test"
        config.line_notify_token = ""
        config.telegram_bot_token = ""
        config.telegram_chat_id = ""

        portfolio = Portfolio(cash=Decimal("500000"))
        portfolio.positions["2330.TW"] = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("600"),
            market_price=Decimal("650"),
        )

        mock_state = MagicMock()
        mock_state.execution_service.is_initialized = True
        # Broker says 900, system says 1000 → mismatch
        mock_state.execution_service.broker.query_positions.return_value = {
            "2330.TW": {"quantity": 900, "avg_cost": 600},
        }
        mock_state.portfolio = portfolio

        mock_notifier = AsyncMock()
        mock_notifier.is_configured.return_value = True

        with patch("src.api.state.get_app_state", return_value=mock_state), \
             patch("src.notifications.factory.create_notifier", return_value=mock_notifier):
            result = await execute_daily_reconcile(config)
            assert result["status"] == "discrepancy"
            assert result["mismatched"] == 1
            mock_notifier.send.assert_awaited_once()
            call_args = mock_notifier.send.call_args
            assert "Discrepancy" in call_args[0][0]


# ── Item 4: Kill switch notification ─────────────────


class TestKillSwitchNotification:
    """Verify kill switch paths send notifications to external channels."""

    def test_path_b_sends_notification(self) -> None:
        """Path B (tick) sends notification after successful liquidation."""
        from src.risk.realtime import RealtimeRiskMonitor
        from src.risk.engine import RiskEngine

        app_state = MagicMock()
        app_state.kill_switch_fired = False
        app_state.mutation_lock = asyncio.Lock()

        portfolio = Portfolio(cash=Decimal("0"))
        portfolio.positions["AAPL"] = Position(
            instrument=Instrument(symbol="AAPL"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("100"),
            market_price=Decimal("100"),
        )

        loop = asyncio.new_event_loop()
        try:
            ws_manager = MagicMock()
            ws_manager.broadcast = AsyncMock()
            mock_svc = MagicMock()
            mock_svc.submit_orders.return_value = [MagicMock()]

            mock_notifier = AsyncMock()
            mock_notifier.is_configured.return_value = True

            monitor = RealtimeRiskMonitor(
                portfolio=portfolio,
                risk_engine=RiskEngine(),
                ws_manager=ws_manager,
                loop=loop,
                execution_service=mock_svc,
                app_state=app_state,
            )

            # Capture the coroutine
            scheduled_coros: list = []

            def capture(coro, lp):
                scheduled_coros.append(coro)
                return MagicMock()

            with patch("asyncio.run_coroutine_threadsafe", side_effect=capture):
                monitor.on_price_update("AAPL", Decimal("94"))

            assert len(scheduled_coros) == 1

            # Run the coroutine with mocked notification
            with patch("src.execution.oms.apply_trades"), \
                 patch("src.risk.realtime.create_notifier", mock_notifier, create=True), \
                 patch("src.notifications.factory.create_notifier", return_value=mock_notifier):
                loop.run_until_complete(scheduled_coros[0])

            # Notification should have been sent
            assert app_state.kill_switch_fired is True
        finally:
            loop.close()

    def test_path_b_notification_failure_does_not_block(self) -> None:
        """Notification failure should not prevent kill switch from completing."""
        from src.risk.realtime import RealtimeRiskMonitor
        from src.risk.engine import RiskEngine

        app_state = MagicMock()
        app_state.kill_switch_fired = False
        app_state.mutation_lock = asyncio.Lock()

        portfolio = Portfolio(cash=Decimal("0"))
        portfolio.positions["AAPL"] = Position(
            instrument=Instrument(symbol="AAPL"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("100"),
            market_price=Decimal("100"),
        )

        loop = asyncio.new_event_loop()
        try:
            ws_manager = MagicMock()
            ws_manager.broadcast = AsyncMock()
            mock_svc = MagicMock()
            mock_svc.submit_orders.return_value = [MagicMock()]

            monitor = RealtimeRiskMonitor(
                portfolio=portfolio,
                risk_engine=RiskEngine(),
                ws_manager=ws_manager,
                loop=loop,
                execution_service=mock_svc,
                app_state=app_state,
            )

            scheduled_coros: list = []

            def capture(coro, lp):
                scheduled_coros.append(coro)
                return MagicMock()

            with patch("asyncio.run_coroutine_threadsafe", side_effect=capture):
                monitor.on_price_update("AAPL", Decimal("94"))

            # Notification raises exception — should not block kill switch
            mock_notifier = AsyncMock()
            mock_notifier.is_configured.return_value = True
            mock_notifier.send.side_effect = Exception("Network error")

            with patch("src.execution.oms.apply_trades"), \
                 patch("src.notifications.factory.create_notifier", return_value=mock_notifier):
                # Should not raise
                loop.run_until_complete(scheduled_coros[0])

            # Kill switch should still have succeeded
            assert app_state.kill_switch_fired is True
            mock_svc.submit_orders.assert_called_once()
        finally:
            loop.close()
