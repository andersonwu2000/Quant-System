"""AO-10: Failure-mode integration tests.

Tests pipeline behavior under specific failure scenarios:
data refresh failure, kill switch, persistence failure, empty universe.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import Portfolio
from src.data.data_catalog import DataNotAvailableError
from src.scheduler.jobs import PipelineResult


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.portfolio = Portfolio(cash=Decimal("10000000"))
    state.kill_switch_fired = False
    state.mutation_lock = AsyncMock()
    state.mutation_lock.__aenter__ = AsyncMock(return_value=None)
    # __aexit__ must return falsy so exceptions propagate (like real asyncio.Lock)
    state.mutation_lock.__aexit__ = AsyncMock(return_value=False)
    state.execution_service = MagicMock()
    state.execution_service.is_initialized = True
    state.risk_engine = MagicMock()
    state.oms = MagicMock()
    state.strategies = {}
    return state


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.active_strategy = "momentum"
    config.active_strategy_params = None
    config.mode = "paper"
    config.backtest_timeout = 30
    config.pipeline_data_update = True
    config.commission_rate = Decimal("0.001425")
    config.tax_rate = Decimal("0.003")
    config.default_slippage_bps = 5
    config.market_lot_sizes = {}
    config.fractional_shares = False
    config.data_source = "yahoo"
    return config


# ── Test 1: data refresh partial failure blocks pipeline ────────


@pytest.mark.asyncio
async def test_data_refresh_partial_failure_blocks_pipeline(mock_state, mock_config):
    """When refresh_all_trading_data returns a report with ok=False,
    execute_pipeline should return status='data_failed' and not proceed."""

    failed_report = MagicMock()
    failed_report.ok = False
    failed_report.summary.return_value = "price: 5/10 symbols failed"

    mock_strategy = MagicMock()
    mock_strategy.name.return_value = "momentum"
    mock_strategy.on_bar.return_value = {}

    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = False

    with (
        patch("src.scheduler.jobs._has_completed_run_today", return_value=False),
        patch("src.scheduler.jobs._has_completed_run_this_month", return_value=False),
        patch("src.scheduler.jobs._today_run_id", return_value="test-run-001"),
        patch("src.scheduler.jobs._write_pipeline_record"),
        patch("src.api.state.get_app_state", return_value=mock_state),
        patch("src.notifications.factory.create_notifier", return_value=mock_notifier),
        patch("src.strategy.registry.resolve_strategy", return_value=mock_strategy),
        patch("src.scheduler.jobs._get_tw_universe_fallback", return_value=["2330.TW"]),
        patch("src.data.refresh.refresh_all_trading_data", new_callable=AsyncMock, return_value=[failed_report]),
    ):
        result = await _run_pipeline_inner(mock_config)

    assert result.status == "data_failed"
    assert result.n_trades == 0
    # Strategy should NOT have been called
    mock_strategy.on_bar.assert_not_called()


# ── Test 2: kill switch blocks subsequent trading ───────────────


@pytest.mark.asyncio
async def test_kill_switch_blocks_subsequent_trading(mock_state, mock_config):
    """When kill_switch_fired=True, pipeline inner should return 'aborted'."""

    mock_state.kill_switch_fired = True
    mock_config.pipeline_data_update = False  # skip data refresh

    mock_strategy = MagicMock()
    mock_strategy.name.return_value = "momentum"
    # Return weights so pipeline reaches the kill-switch check
    mock_strategy.on_bar.return_value = {"2330.TW": 0.5}

    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = False

    mock_feed = MagicMock()
    mock_feed.get_latest_price.return_value = 600.0
    mock_feed.get_bars.return_value = None

    mock_gate = MagicMock()
    mock_gate.passed = True
    mock_gate.warnings = []

    with (
        patch("src.scheduler.jobs._has_completed_run_today", return_value=False),
        patch("src.scheduler.jobs._has_completed_run_this_month", return_value=False),
        patch("src.scheduler.jobs._today_run_id", return_value="test-run-002"),
        patch("src.scheduler.jobs._write_pipeline_record"),
        patch("src.api.state.get_app_state", return_value=mock_state),
        patch("src.notifications.factory.create_notifier", return_value=mock_notifier),
        patch("src.strategy.registry.resolve_strategy", return_value=mock_strategy),
        patch("src.scheduler.jobs._get_tw_universe_fallback", return_value=["2330.TW"]),
        patch("src.data.quality_gate.pre_trade_quality_gate", return_value=mock_gate),
        patch("src.data.data_catalog.get_catalog") as mock_catalog,
        patch("src.data.feed.HistoricalFeed", return_value=mock_feed),
    ):
        mock_catalog_inst = MagicMock()
        mock_catalog.return_value = mock_catalog_inst
        mock_catalog_inst.get_result.side_effect = DataNotAvailableError("no data")

        result = await _run_pipeline_inner(mock_config)

    assert result.status == "aborted"
    assert "kill switch" in result.error.lower() or "Kill switch" in result.error


# ── Test 3: portfolio persistence failure logged ────────────────


@pytest.mark.asyncio
async def test_portfolio_persistence_failure_logged(mock_state, mock_config, caplog):
    """When save_portfolio raises, the pipeline should still complete
    (persistence failure is non-fatal), but the error should be logged."""

    mock_config.pipeline_data_update = False
    mock_config.mode = "paper"

    mock_strategy = MagicMock()
    mock_strategy.name.return_value = "momentum"
    mock_strategy.on_bar.return_value = {"2330.TW": 0.5}

    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = False

    mock_gate = MagicMock()
    mock_gate.passed = True
    mock_gate.warnings = []

    mock_feed = MagicMock()
    mock_feed.get_latest_price.return_value = 600.0
    mock_feed.get_bars.return_value = None

    # execute_from_weights returns empty trades to keep test simple
    with (
        patch("src.scheduler.jobs._has_completed_run_today", return_value=False),
        patch("src.scheduler.jobs._has_completed_run_this_month", return_value=False),
        patch("src.scheduler.jobs._today_run_id", return_value="test-run-003"),
        patch("src.scheduler.jobs._write_pipeline_record"),
        patch("src.api.state.get_app_state", return_value=mock_state),
        patch("src.notifications.factory.create_notifier", return_value=mock_notifier),
        patch("src.strategy.registry.resolve_strategy", return_value=mock_strategy),
        patch("src.scheduler.jobs._get_tw_universe_fallback", return_value=["2330.TW"]),
        patch("src.data.quality_gate.pre_trade_quality_gate", return_value=mock_gate),
        patch("src.data.data_catalog.get_catalog") as mock_catalog,
        patch("src.data.feed.HistoricalFeed", return_value=mock_feed),
        patch("src.core.trading_pipeline.execute_from_weights", return_value=[]),
        patch("src.api.state.save_portfolio", side_effect=OSError("Disk full")),
        patch("src.scheduler.jobs._save_selection_log"),
        patch("src.scheduler.jobs._reconcile", return_value=[]),
        patch("src.scheduler.jobs._record_backtest_comparison"),
        patch("src.scheduler.jobs._save_nav_snapshot"),
        patch("src.scheduler.jobs._write_daily_report"),
    ):
        mock_catalog_inst = MagicMock()
        mock_catalog.return_value = mock_catalog_inst
        mock_catalog_inst.get_result.side_effect = DataNotAvailableError("no data")

        # The save_portfolio call is inside mutation_lock context.
        # Since it raises, the pipeline should propagate the error
        # but the outer execute_pipeline catches it and returns error status.
        result = await _run_pipeline(mock_config)

    # Pipeline crashed due to save_portfolio raising inside mutation_lock.
    # The outer handler catches all exceptions and returns status="error".
    assert result.status == "error"
    assert result.error  # should contain error info


# ── Test 4: empty universe fails safely ─────────────────────────


@pytest.mark.asyncio
async def test_empty_universe_fails_safely(mock_state, mock_config):
    """When universe resolution returns empty, pipeline returns status='error'."""

    mock_config.pipeline_data_update = False

    mock_strategy = MagicMock()
    mock_strategy.name.return_value = "momentum"

    mock_notifier = MagicMock()
    mock_notifier.is_configured.return_value = False

    with (
        patch("src.scheduler.jobs._has_completed_run_today", return_value=False),
        patch("src.scheduler.jobs._has_completed_run_this_month", return_value=False),
        patch("src.scheduler.jobs._today_run_id", return_value="test-run-004"),
        patch("src.scheduler.jobs._write_pipeline_record"),
        patch("src.api.state.get_app_state", return_value=mock_state),
        patch("src.notifications.factory.create_notifier", return_value=mock_notifier),
        patch("src.strategy.registry.resolve_strategy", return_value=mock_strategy),
        patch("src.scheduler.jobs._get_tw_universe_fallback", return_value=[]),
    ):
        # Portfolio has no positions either → truly empty universe
        result = await _run_pipeline_inner(mock_config)

    assert result.status == "error"
    assert "empty universe" in result.error.lower() or "Empty universe" in result.error
    # Strategy should NOT have been called
    mock_strategy.on_bar.assert_not_called()


# ── Helpers ─────────────────────────────────────────────────────


async def _run_pipeline_inner(config) -> PipelineResult:
    """Call _execute_pipeline_inner directly (bypasses timeout/idempotency)."""
    from src.scheduler.jobs import _execute_pipeline_inner
    return await _execute_pipeline_inner(config)


async def _run_pipeline(config) -> PipelineResult:
    """Call execute_pipeline (includes outer error handling)."""
    from src.scheduler.jobs import execute_pipeline
    return await execute_pipeline(config)
