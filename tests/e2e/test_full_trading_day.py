"""AK-3 E2E-1: Full trading day simulation.

Simulates 07:50 daily_ops → pipeline → deployed strategies → 13:30 eod_ops.
Uses mocked data feeds and SimBroker — no network, no real broker.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest



def _make_trading_config(mode="paper", strategy="revenue_momentum_hedged"):
    config = MagicMock()
    config.mode = mode
    config.active_strategy = strategy
    config.active_strategy_params = None
    config.rebalance_frequency = "monthly"
    config.trading_pipeline_cron = "3 9 11 * *"
    config.backtest_timeout = 300
    config.initial_cash = 10_000_000
    return config


class TestFullTradingDay:
    """Simulate a complete trading day in paper mode."""

    @pytest.mark.asyncio
    async def test_daily_ops_non_rebalance_day(self):
        """Non-rebalance day: TWSE snapshot + Yahoo refresh, skip pipeline."""
        from src.scheduler.ops import daily_ops

        config = _make_trading_config()

        with (
            patch("src.core.calendar.get_tw_calendar") as mock_cal,
            patch("src.scheduler.ops._fetch_twse_snapshot", new_callable=AsyncMock, return_value="OHLCV: 100"),
            patch("src.scheduler.ops._yahoo_daily_refresh", new_callable=AsyncMock, return_value="Yahoo: 50 updated"),
            patch("src.scheduler.ops._is_rebalance_day", return_value=False),
            patch("src.alpha.auto.paper_deployer.PaperDeployer.get_instance") as mock_deployer,
            patch("src.alpha.auto.deployed_executor.process_deploy_queue", return_value=[]),
            patch("src.alpha.auto.deployed_executor.execute_deployed_strategies", return_value={}),
            patch("src.scheduler.heartbeat.heartbeat", new_callable=AsyncMock),
        ):
            mock_cal.return_value.is_trading_day.return_value = True
            mock_deployer.return_value = MagicMock()

            result = await daily_ops(config)

            assert result["status"] == "completed"
            assert result["pipeline"] == "skipped"

    @pytest.mark.asyncio
    async def test_daily_ops_holiday_skips(self):
        """Holiday: skip everything."""
        from src.scheduler.ops import daily_ops

        config = _make_trading_config()

        with (
            patch("src.core.calendar.get_tw_calendar") as mock_cal,
            patch("src.scheduler.heartbeat.heartbeat", new_callable=AsyncMock) as mock_hb,
        ):
            mock_cal.return_value.is_trading_day.return_value = False
            result = await daily_ops(config)

            assert result["status"] == "holiday"
            mock_hb.assert_called_once()

    @pytest.mark.asyncio
    async def test_eod_ops_paper_mode_skips_reconcile(self):
        """EOD in paper mode: reconcile skipped, summary produced."""
        from src.scheduler.ops import eod_ops

        config = _make_trading_config(mode="paper")

        with (
            patch("src.scheduler.jobs.execute_daily_reconcile", new_callable=AsyncMock) as mock_recon,
            patch("src.scheduler.jobs.execute_backtest_reconcile", new_callable=AsyncMock, return_value={"status": "ok"}),
            patch("src.scheduler.ops._generate_daily_summary", new_callable=AsyncMock, return_value="NAV=10,000,000"),
            patch("src.scheduler.heartbeat.heartbeat", new_callable=AsyncMock),
        ):
            mock_recon.return_value = {"status": "skipped", "reason": "not live mode"}
            result = await eod_ops(config)
            assert result["reconcile"]["status"] == "skipped"


class TestAutoresearchCycle:
    """E2E-3: Autoresearch factor → deploy queue → executor cycle."""

    def test_deploy_queue_to_execution(self, tmp_path):
        """Factor in deploy_queue → process_deploy_queue → execute_deployed_strategies."""
        import json
        from src.alpha.auto.paper_deployer import PaperDeployer
        from src.alpha.auto.deployed_executor import process_deploy_queue

        # Setup: create a deploy queue marker
        queue_dir = tmp_path / "deploy_queue"
        queue_dir.mkdir()
        factor_code = '''
def compute_factor(symbols, as_of, data):
    return {s: 1.0 for s in symbols[:15]}
'''
        marker = {
            "factor_code": factor_code,
            "code_hash": "test123",
            "timestamp": "20260401_test",
        }
        (queue_dir / "test.json").write_text(json.dumps(marker))

        deployer = PaperDeployer(deploy_dir=str(tmp_path / "deploy"))

        with patch("src.alpha.auto.deployed_executor.DEPLOY_QUEUE_DIR", queue_dir):
            with patch("src.api.state.get_app_state") as mock_state:
                mock_state.return_value.portfolio.nav = 10_000_000
                names = process_deploy_queue(deployer)

        assert len(names) >= 1 or len(list(queue_dir.glob("*.json"))) == 0, \
            "Marker should be processed (deployed or moved to failed)"

    def test_deployed_strategy_monthly_rebalance(self, tmp_path):
        """Deployed strategy rebalances on first run, skips same month."""
        import json
        from datetime import datetime
        from src.alpha.auto.deployed_executor import _should_rebalance, PAPER_TRADE_DIR

        with patch("src.alpha.auto.deployed_executor.PAPER_TRADE_DIR", tmp_path):
            # First run: should rebalance
            assert _should_rebalance("test_strat") is True

            # Record a trade
            trade_dir = tmp_path / "test_strat"
            trade_dir.mkdir()
            today = datetime.now().strftime("%Y-%m-%d")
            (trade_dir / f"{today}.json").write_text(json.dumps({
                "date": today, "weights": {"2330.TW": 0.063}, "nav": 500000,
            }))

            # Same month: skip
            assert _should_rebalance("test_strat") is False


class TestPaperToLiveSwitch:
    """E2E-2: Verify mode switch changes reconciliation behavior."""

    @pytest.mark.asyncio
    async def test_paper_skips_live_runs(self):
        """Paper mode → skipped, live mode → would attempt (but no broker)."""
        from src.scheduler.jobs import execute_daily_reconcile

        # Paper → skip
        paper_config = _make_trading_config(mode="paper")
        result = await execute_daily_reconcile(paper_config)
        assert result["status"] == "skipped"

        # Live → attempts (but no broker initialized → also skips with different reason)
        live_config = _make_trading_config(mode="live")
        with patch("src.scheduler.jobs.update_portfolio_market_prices", new_callable=AsyncMock):
            with patch("src.api.state.get_app_state") as mock_state:
                mock_state.return_value.execution_service.is_initialized = False
                mock_state.return_value.execution_service.broker = None
                result = await execute_daily_reconcile(live_config)
                assert result["status"] == "skipped"
                assert "broker" in result["reason"]
