"""Tests for auto-alpha WebSocket integration (F3b)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.alpha.auto.config import AutoAlphaConfig, FactorScore, ResearchSnapshot
from src.alpha.auto.decision import AlphaDecisionEngine, DecisionResult
from src.alpha.auto.executor import AlphaExecutor, ExecutionResult
from src.alpha.auto.scheduler import AlphaScheduler, _broadcast_event
from src.alpha.auto.universe import UniverseResult, UniverseSelector
from src.alpha.regime import MarketRegime
from src.core.models import Portfolio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    result: dict[str, pd.DataFrame] = {}
    for sym in ["AAPL", "MSFT"]:
        df = pd.DataFrame(
            {
                "open": 100.0,
                "high": 105.0,
                "low": 95.0,
                "close": 102.0,
                "volume": 1_000_000,
            },
            index=dates,
        )
        result[sym] = df
    return result


def _good_score(name: str) -> FactorScore:
    return FactorScore(
        name=name,
        ic=0.04,
        icir=0.6,
        hit_rate=0.58,
        decay_half_life=5,
        turnover=0.1,
        cost_drag_bps=80.0,
        long_short_sharpe=1.2,
        eligible=True,
    )


def _build_scheduler_with_mocks(
    *,
    universe_symbols: list[str] | None = None,
    researcher: MagicMock | None = None,
    decision_result: DecisionResult | None = None,
    execution_result: ExecutionResult | None = None,
) -> AlphaScheduler:
    """Build an AlphaScheduler with fully mocked sub-components."""
    cfg = AutoAlphaConfig()

    universe_selector = MagicMock(spec=UniverseSelector)
    symbols = universe_symbols if universe_symbols is not None else ["AAPL", "MSFT"]
    universe_selector.select.return_value = UniverseResult(
        symbols=symbols,
        total_candidates=5,
    )

    if researcher is None:
        researcher = MagicMock()
        snapshot = ResearchSnapshot(
            regime=MarketRegime.BULL,
            universe=["AAPL", "MSFT"],
            factor_scores={"momentum": _good_score("momentum")},
        )
        researcher.run.return_value = snapshot

    decision_engine = MagicMock(spec=AlphaDecisionEngine)
    if decision_result is None:
        decision_result = DecisionResult(
            selected_factors=["momentum"],
            factor_weights={"momentum": 1.0},
            regime=MarketRegime.BULL,
            reason="test",
        )
    decision_engine.decide.return_value = decision_result

    executor = MagicMock(spec=AlphaExecutor)
    if execution_result is None:
        execution_result = ExecutionResult(
            trades_count=2,
            turnover=0.05,
            orders_submitted=2,
            orders_rejected=0,
        )
    executor.execute.return_value = execution_result

    return AlphaScheduler(
        cfg,
        universe_selector=universe_selector,
        researcher=researcher,
        decision_engine=decision_engine,
        executor=executor,
    )


# ---------------------------------------------------------------------------
# Tests for _broadcast_event
# ---------------------------------------------------------------------------


class TestBroadcastEvent:
    """Tests for the _broadcast_event helper function."""

    def test_no_crash_when_no_event_loop(self) -> None:
        """_broadcast_event should not raise even when there is no event loop."""
        # In environments without a running loop, this should silently pass
        _broadcast_event("test_event", {"key": "value"})

    def test_broadcast_with_mock_ws_manager(self) -> None:
        """_broadcast_event calls ws_manager.broadcast with correct args when a loop is running."""
        mock_manager = MagicMock()
        mock_manager.broadcast = AsyncMock()

        async def _run() -> None:
            with patch("src.api.ws.ws_manager", mock_manager):
                _broadcast_event("stage_started", {"stage": "universe"})
            # Let the scheduled coroutine execute
            await asyncio.sleep(0)

        asyncio.run(_run())

        mock_manager.broadcast.assert_called_once_with(
            "auto-alpha",
            {"type": "stage_started", "stage": "universe"},
        )

    def test_broadcast_swallows_exceptions(self) -> None:
        """_broadcast_event should not propagate exceptions."""
        with patch(
            "src.api.ws.ws_manager",
            new_callable=lambda: MagicMock,
        ) as mock_mgr:
            mock_mgr.broadcast = MagicMock(side_effect=RuntimeError("send failed"))
            # Should not raise — exceptions are swallowed
            _broadcast_event("error", {"message": "something broke"})


# ---------------------------------------------------------------------------
# Tests for stage events in run_full_cycle
# ---------------------------------------------------------------------------


class TestRunFullCycleWsEvents:
    """Test that run_full_cycle emits WebSocket events at each stage."""

    @patch("src.alpha.auto.backtest_gate.BacktestEngine")
    @patch("src.alpha.auto.scheduler._broadcast_event")
    def test_full_cycle_emits_all_stage_events(
        self, mock_broadcast: MagicMock, mock_engine_cls: MagicMock,
    ) -> None:
        """Full cycle should broadcast events for all 5 stages (incl. backtest gate)."""
        from src.backtest.analytics import BacktestResult

        mock_engine = MagicMock()
        mock_engine.run.return_value = BacktestResult(
            strategy_name="test", start_date="2024-01-01", end_date="2024-06-01",
            initial_cash=10_000_000.0, total_return=0.05, annual_return=0.10,
            sharpe=0.8, sortino=1.0, calmar=0.5, max_drawdown=0.03,
            max_drawdown_duration=10, volatility=0.15, downside_vol=0.10,
            total_trades=20, win_rate=0.55, avg_trade_return=0.005,
            total_commission=10_000.0, turnover=0.1,
        )
        mock_engine_cls.return_value = mock_engine

        scheduler = _build_scheduler_with_mocks()

        scheduler.run_full_cycle(
            data=_make_data(),
            portfolio=Portfolio(),
            execution_service=MagicMock(),
            risk_engine=MagicMock(),
        )

        # Collect all event types
        event_types = [call.args[0] for call in mock_broadcast.call_args_list]

        # Verify stage_started events for all 5 stages (incl. backtest_gate)
        assert event_types.count("stage_started") == 5
        assert "stage_completed" in event_types
        assert "decision" in event_types
        assert "execution" in event_types

        # Verify stage ordering: universe → research → decision → backtest_gate → execution
        stage_started_calls = [
            call.args[1]["stage"]
            for call in mock_broadcast.call_args_list
            if call.args[0] == "stage_started"
        ]
        assert stage_started_calls == [
            "universe", "research", "decision", "backtest_gate", "execution",
        ]

    @patch("src.alpha.auto.scheduler._broadcast_event")
    def test_error_event_on_exception(self, mock_broadcast: MagicMock) -> None:
        """run_full_cycle should broadcast an error event when an exception occurs."""
        cfg = AutoAlphaConfig()
        universe_selector = MagicMock(spec=UniverseSelector)
        universe_selector.select.side_effect = RuntimeError("boom")

        scheduler = AlphaScheduler(cfg, universe_selector=universe_selector)

        with pytest.raises(RuntimeError, match="boom"):
            scheduler.run_full_cycle(
                data=_make_data(),
                portfolio=Portfolio(),
                execution_service=MagicMock(),
                risk_engine=MagicMock(),
            )

        # Verify error event was broadcast
        error_calls = [
            call for call in mock_broadcast.call_args_list if call.args[0] == "error"
        ]
        assert len(error_calls) == 1
        assert "boom" in error_calls[0].args[1]["message"]
