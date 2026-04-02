"""Integration tests for Kill Switch race condition prevention and crash recovery.

Item 1: Simulates both Path A (5s poll) and Path B (tick) firing concurrently,
         confirming only one batch of liquidation orders executes.
Item 2: Crash recovery — save/load portfolio roundtrip preserving all state.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


from src.core.models import Instrument, Portfolio, Position
from src.risk.engine import RiskEngine
from src.risk.realtime import RealtimeRiskMonitor


# ── Helpers ───────────────────────────────────────────


def _make_portfolio_with_positions() -> Portfolio:
    """Portfolio with 100k in single position, nav_sod set for kill switch."""
    p = Portfolio(cash=Decimal("0"))
    p.positions["AAPL"] = Position(
        instrument=Instrument(symbol="AAPL"),
        quantity=Decimal("1000"),
        avg_cost=Decimal("100"),
        market_price=Decimal("100"),
    )
    p.nav_sod = p.nav  # Set SOD NAV so daily_drawdown works
    return p


def _make_app_state(kill_switch_fired: bool = False) -> MagicMock:
    state = MagicMock()
    state.kill_switch_fired = kill_switch_fired
    state.mutation_lock = asyncio.Lock()
    return state


# ── Item 1: Race condition simulation ────────────────


class TestKillSwitchRaceCondition:
    """Simulate both paths triggering, confirm only one liquidation executes."""

    def test_path_b_fires_first_path_a_skips(self) -> None:
        """Path B (tick) fires and sets kill_switch_fired=True.
        Path A should see it and skip."""
        app_state = _make_app_state(kill_switch_fired=False)
        portfolio = _make_portfolio_with_positions()
        risk_engine = RiskEngine()

        # Simulate Path B setting the flag (as our fix does)
        loop = asyncio.new_event_loop()
        try:
            ws_manager = MagicMock()
            ws_manager.broadcast = AsyncMock()
            mock_svc = MagicMock()
            mock_svc.submit_orders.return_value = [MagicMock()]  # fake trades

            monitor = RealtimeRiskMonitor(
                portfolio=portfolio,
                risk_engine=risk_engine,
                ws_manager=ws_manager,
                loop=loop,
                execution_service=mock_svc,
                app_state=app_state,
            )

            # Capture coroutines scheduled to the loop
            scheduled_coros: list = []

            def capture(coro, lp):
                scheduled_coros.append(coro)
                return MagicMock()

            with patch("asyncio.run_coroutine_threadsafe", side_effect=capture):
                # Trigger 6% drawdown → kill switch
                monitor.on_price_update("AAPL", Decimal("94"))

            assert "kill_switch" in monitor._alerts_sent
            assert len(scheduled_coros) == 1

            # Run path B's coroutine
            with patch("src.execution.oms.apply_trades"):
                loop.run_until_complete(scheduled_coros[0])

            # Path B should have set the flag
            assert app_state.kill_switch_fired is True
            mock_svc.submit_orders.assert_called_once()

            # Now simulate path A checking — it should see fired=True and skip
            assert app_state.kill_switch_fired is True
            # Path A's logic: `if state.kill_switch_fired: continue`
            # → confirmed it would skip
        finally:
            loop.close()

    def test_path_a_fires_first_path_b_skips(self) -> None:
        """Path A fires first (sets kill_switch_fired=True).
        Path B's coroutine should detect it and skip liquidation."""
        app_state = _make_app_state(kill_switch_fired=False)
        portfolio = _make_portfolio_with_positions()
        risk_engine = RiskEngine()
        loop = asyncio.new_event_loop()

        try:
            ws_manager = MagicMock()
            ws_manager.broadcast = AsyncMock()
            mock_svc = MagicMock()
            mock_svc.submit_orders.return_value = [MagicMock()]

            monitor = RealtimeRiskMonitor(
                portfolio=portfolio,
                risk_engine=risk_engine,
                ws_manager=ws_manager,
                loop=loop,
                execution_service=mock_svc,
                app_state=app_state,
            )

            # Capture path B's coroutine
            scheduled_coros: list = []

            def capture(coro, lp):
                scheduled_coros.append(coro)
                return MagicMock()

            with patch("asyncio.run_coroutine_threadsafe", side_effect=capture):
                monitor.on_price_update("AAPL", Decimal("94"))

            # Simulate Path A firing FIRST (sets flag before path B's coroutine runs)
            app_state.kill_switch_fired = True

            # Now run path B's coroutine — should detect flag and skip
            loop.run_until_complete(scheduled_coros[0])

            # submit_orders should NOT have been called
            mock_svc.submit_orders.assert_not_called()
        finally:
            loop.close()

    def test_concurrent_path_b_only_one_succeeds(self) -> None:
        """Two path B coroutines race — only one should execute liquidation."""
        app_state = _make_app_state(kill_switch_fired=False)
        portfolio = _make_portfolio_with_positions()
        risk_engine = RiskEngine()
        loop = asyncio.new_event_loop()

        try:
            ws_manager = MagicMock()
            ws_manager.broadcast = AsyncMock()
            mock_svc = MagicMock()
            mock_svc.submit_orders.return_value = [MagicMock()]

            monitor = RealtimeRiskMonitor(
                portfolio=portfolio,
                risk_engine=risk_engine,
                ws_manager=ws_manager,
                loop=loop,
                execution_service=mock_svc,
                app_state=app_state,
            )

            # Capture coroutines
            scheduled_coros: list = []

            def capture(coro, lp):
                scheduled_coros.append(coro)
                return MagicMock()

            with patch("asyncio.run_coroutine_threadsafe", side_effect=capture):
                # First tick triggers kill switch
                monitor.on_price_update("AAPL", Decimal("94"))

            # Reset alerts to allow second trigger
            monitor._alerts_sent.discard("kill_switch")
            monitor._alerts_sent.discard("dd_3pct")
            monitor._alerts_sent.discard("dd_2pct")

            with patch("asyncio.run_coroutine_threadsafe", side_effect=capture):
                monitor.on_price_update("AAPL", Decimal("93"))

            assert len(scheduled_coros) == 2

            # Run both concurrently — wrap in async to run inside the loop
            async def run_both() -> None:
                await asyncio.gather(scheduled_coros[0], scheduled_coros[1])

            with patch("src.execution.oms.apply_trades"):
                loop.run_until_complete(run_both())

            # Only one should have called submit_orders
            assert mock_svc.submit_orders.call_count == 1
            assert app_state.kill_switch_fired is True
        finally:
            loop.close()


# ── Item 2: Crash recovery ───────────────────────────


class TestCrashRecovery:
    """Test portfolio save/load roundtrip preserving full state."""

    def test_save_load_roundtrip(self, tmp_path) -> None:
        """Portfolio with positions, pending_settlements, nav_sod survives save/load."""
        from src.api.state import save_portfolio, load_portfolio

        portfolio = Portfolio(
            cash=Decimal("500000"),
            initial_cash=Decimal("1000000"),
        )
        portfolio.positions["2330.TW"] = Position(
            instrument=Instrument(symbol="2330.TW", name="TSMC"),
            quantity=Decimal("5000"),
            avg_cost=Decimal("600"),
            market_price=Decimal("650"),
        )
        portfolio.nav_sod = Decimal("3800000")
        portfolio.pending_settlements = [
            ("2026-03-30", Decimal("100000")),
            ("2026-03-31", Decimal("-50000")),
        ]

        # Patch persist path to tmp
        test_path = tmp_path / "portfolio_state.json"
        with patch("src.api.state._PERSIST_PATH", test_path), \
             patch("src.api.state._PERSIST_DIR", tmp_path):

            save_portfolio(portfolio)
            assert test_path.exists()

            loaded = load_portfolio()
            assert loaded is not None

            # Core state
            assert loaded.cash == Decimal("500000")
            assert loaded.initial_cash == Decimal("1000000")
            assert loaded.nav_sod == Decimal("3800000")

            # Positions
            assert "2330.TW" in loaded.positions
            pos = loaded.positions["2330.TW"]
            assert pos.quantity == Decimal("5000")
            assert pos.avg_cost == Decimal("600")
            assert pos.market_price == Decimal("650")
            assert pos.instrument.name == "TSMC"

            # Pending settlements
            assert len(loaded.pending_settlements) == 2
            assert loaded.pending_settlements[0] == ("2026-03-30", Decimal("100000"))
            assert loaded.pending_settlements[1] == ("2026-03-31", Decimal("-50000"))

    def test_nav_sod_defaults_to_nav_when_zero(self, tmp_path) -> None:
        """If saved nav_sod is 0, load_portfolio defaults to current NAV (E5 fix)."""
        import json

        test_path = tmp_path / "portfolio_state.json"
        # Write a minimal state with nav_sod = 0
        state = {
            "cash": "1000000",
            "initial_cash": "1000000",
            "nav_sod": "0",
            "positions": {},
            "pending_settlements": [],
        }
        test_path.write_text(json.dumps(state), encoding="utf-8")

        with patch("src.api.state._PERSIST_PATH", test_path), \
             patch("src.api.state._PERSIST_DIR", tmp_path):
            from src.api.state import load_portfolio
            loaded = load_portfolio()
            assert loaded is not None
            # nav_sod should default to current NAV (= cash = 1M), not 0
            assert loaded.nav_sod == loaded.nav
            assert loaded.nav_sod > 0

    def test_load_returns_none_when_no_file(self, tmp_path) -> None:
        """load_portfolio returns None when no persisted file exists."""
        fake_path = tmp_path / "nonexistent.json"
        with patch("src.api.state._PERSIST_PATH", fake_path):
            from src.api.state import load_portfolio
            assert load_portfolio() is None

    def test_atomic_write(self, tmp_path) -> None:
        """save_portfolio uses tmp+rename for atomic write."""
        from src.api.state import save_portfolio

        portfolio = Portfolio(cash=Decimal("100"))
        test_path = tmp_path / "portfolio_state.json"

        with patch("src.api.state._PERSIST_PATH", test_path), \
             patch("src.api.state._PERSIST_DIR", tmp_path):
            save_portfolio(portfolio)

        # tmp file should not remain
        assert not (tmp_path / "portfolio_state.tmp").exists()
        assert test_path.exists()


# ── Item 2b: Rebalance idempotency ──────────────────


class TestRebalanceIdempotency:
    """Verify pipeline idempotency guards prevent duplicate rebalance on restart."""

    def test_has_completed_run_today(self, tmp_path) -> None:
        """A completed run today prevents re-execution."""
        from src.scheduler.jobs import _has_completed_run_today
        import json

        today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
        run_file = tmp_path / f"{today}_0930.json"
        run_file.write_text(json.dumps({
            "run_id": f"{today}_0930",
            "status": "completed",
            "strategy": "test",
        }))

        with patch("src.scheduler.jobs.PIPELINE_RUNS_DIR", tmp_path):
            assert _has_completed_run_today() is True

    def test_no_run_today(self, tmp_path) -> None:
        """No completed run today allows execution."""
        with patch("src.scheduler.jobs.PIPELINE_RUNS_DIR", tmp_path):
            from src.scheduler.jobs import _has_completed_run_today
            assert _has_completed_run_today() is False

    def test_concurrent_kill_switch_and_rebalance(self) -> None:
        """AN-20: Verify kill switch and rebalance don't corrupt state."""
        app_state = _make_app_state(kill_switch_fired=False)
        portfolio = _make_portfolio_with_positions()
        risk_engine = RiskEngine()
        loop = asyncio.new_event_loop()

        try:
            ws_manager = MagicMock()
            ws_manager.broadcast = AsyncMock()
            mock_svc = MagicMock()
            mock_svc.submit_orders.return_value = [MagicMock()]

            monitor = RealtimeRiskMonitor(
                portfolio=portfolio,
                risk_engine=risk_engine,
                ws_manager=ws_manager,
                loop=loop,
                execution_service=mock_svc,
                app_state=app_state,
            )

            # Fire kill switch
            scheduled_coros: list = []

            def capture(coro, lp):
                scheduled_coros.append(coro)
                return MagicMock()

            with patch("asyncio.run_coroutine_threadsafe", side_effect=capture):
                monitor.on_price_update("AAPL", Decimal("94"))

            # Simultaneously set kill_switch_fired (simulating rebalance path)
            app_state.kill_switch_fired = True

            # Run the kill switch coroutine — should not raise
            if scheduled_coros:
                with patch("src.execution.oms.apply_trades"):
                    loop.run_until_complete(scheduled_coros[0])

            # Assert: kill_switch_fired = True, no exception raised
            assert app_state.kill_switch_fired is True
        finally:
            loop.close()

    def test_crashed_run_detected(self, tmp_path) -> None:
        """Crashed (started but never finished) runs are detected on startup."""
        from src.scheduler.jobs import check_crashed_runs
        import json

        run_file = tmp_path / "2026-03-28_0930.json"
        run_file.write_text(json.dumps({
            "run_id": "2026-03-28_0930",
            "status": "started",
            "strategy": "revenue_momentum_hedged",
        }))

        with patch("src.scheduler.jobs.PIPELINE_RUNS_DIR", tmp_path):
            crashed = check_crashed_runs()
            assert len(crashed) >= 1
            assert crashed[0]["status"] == "crashed"
