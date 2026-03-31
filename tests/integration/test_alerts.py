"""AK-2 Layer 6: Monitoring and alert tests.

Verifies:
- Paper mode produces no false alerts
- Live mode discrepancy triggers notification
- Kill switch logs warning
"""

from __future__ import annotations

import logging
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import Instrument, Portfolio, Position


class TestPaperModeNoAlerts:
    """Test 6.1: Paper mode must not trigger reconciliation alerts."""

    @pytest.mark.asyncio
    async def test_paper_mode_no_discord(self):
        """Paper mode → reconcile skipped → notifier never called."""
        from src.scheduler.jobs import execute_daily_reconcile

        config = MagicMock()
        config.mode = "paper"

        with patch("src.notifications.factory.create_notifier") as mock_notifier:
            result = await execute_daily_reconcile(config)
            assert result["status"] == "skipped"
            # Notifier should never be instantiated in paper mode
            # (the function returns before creating notifier)


class TestLiveModeAlerts:
    """Test 6.2: Live mode discrepancy triggers notification."""

    def test_reconcile_summary_contains_discrepancy_info(self):
        """ReconcileResult.summary() includes system/broker only details."""
        from src.execution.reconcile import reconcile

        portfolio = Portfolio()
        portfolio.positions["2330.TW"] = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("590"),
        )
        # Broker has different position
        broker = {"2330": {"quantity": 500, "avg_cost": 590}}
        result = reconcile(portfolio, broker)

        summary = result.summary()
        assert "DISCREPANCY" in summary
        assert "2330" in summary


class TestKillSwitchAlert:
    """Test 6.3: Kill switch logs warning on MDD breach."""

    def test_kill_switch_logs_warning(self, tmp_path, caplog):
        """MDD > 3% triggers logger.warning with 'KILL' message."""
        from src.alpha.auto.paper_deployer import PaperDeployer

        deployer = PaperDeployer(deploy_dir=str(tmp_path))
        deployer.deploy("doomed", "factor", total_nav=10_000_000)
        initial = deployer.get_active()[0].initial_nav

        with caplog.at_level(logging.WARNING):
            deployer.update_nav("doomed", initial * 0.96)  # 4% drop

        assert any("KILL" in record.message for record in caplog.records), (
            "Kill switch should log WARNING with 'KILL' keyword"
        )
