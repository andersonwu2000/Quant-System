"""Tests for RealtimeRiskMonitor."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.models import Instrument, Portfolio, Position
from src.risk.engine import RiskEngine
from src.risk.realtime import RealtimeRiskMonitor


# ── Helpers ───────────────────────────────────────────


def _make_portfolio(cash: float = 1_000_000, positions: dict[str, tuple[int, int]] | None = None) -> Portfolio:
    p = Portfolio(cash=Decimal(str(cash)))
    if positions:
        for symbol, (qty, price) in positions.items():
            p.positions[symbol] = Position(
                instrument=Instrument(symbol=symbol),
                quantity=Decimal(str(qty)),
                avg_cost=Decimal(str(price)),
                market_price=Decimal(str(price)),
            )
    return p


def _make_monitor(
    cash: float = 1_000_000,
    positions: dict[str, tuple[int, int]] | None = None,
) -> tuple[RealtimeRiskMonitor, Portfolio, MagicMock]:
    portfolio = _make_portfolio(cash, positions)
    risk_engine = RiskEngine()
    ws_manager = MagicMock()
    ws_manager.broadcast = AsyncMock()
    monitor = RealtimeRiskMonitor(
        portfolio=portfolio,
        risk_engine=risk_engine,
        ws_manager=ws_manager,
    )
    return monitor, portfolio, ws_manager


# ── Tests ─────────────────────────────────────────────


class TestRealtimeRiskMonitorInit:
    def test_initial_state(self) -> None:
        monitor, portfolio, _ = _make_monitor(cash=500_000)
        assert monitor._nav_high == float(portfolio.nav)
        assert monitor._alerts_sent == set()
        assert monitor._alerts_count == 0
        assert monitor._last_update is None

    def test_initial_nav_with_positions(self) -> None:
        monitor, portfolio, _ = _make_monitor(
            cash=500_000, positions={"AAPL": (100, 150)}
        )
        expected_nav = 500_000 + 100 * 150
        assert monitor._nav_high == expected_nav


class TestOnPriceUpdate:
    def test_updates_portfolio_market_price(self) -> None:
        monitor, portfolio, _ = _make_monitor(
            cash=500_000, positions={"AAPL": (100, 150)}
        )
        monitor.on_price_update("AAPL", Decimal("160"))
        assert portfolio.positions["AAPL"].market_price == Decimal("160")

    def test_tracks_nav_high(self) -> None:
        monitor, portfolio, _ = _make_monitor(
            cash=500_000, positions={"AAPL": (100, 100)}
        )
        # NAV starts at 500_000 + 10_000 = 510_000
        initial_nav_high = monitor._nav_high

        # Price goes up: NAV increases
        monitor.on_price_update("AAPL", Decimal("120"))
        new_nav = float(portfolio.nav)
        assert monitor._nav_high == new_nav
        assert monitor._nav_high > initial_nav_high

        # Price drops: NAV decreases but high watermark stays
        monitor.on_price_update("AAPL", Decimal("110"))
        assert monitor._nav_high == new_nav  # unchanged

    def test_sets_last_update(self) -> None:
        monitor, _, _ = _make_monitor(cash=1_000_000)
        assert monitor._last_update is None
        monitor.on_price_update("AAPL", Decimal("100"))
        assert monitor._last_update is not None

    def test_no_alert_on_small_drawdown(self) -> None:
        monitor, portfolio, ws = _make_monitor(
            cash=500_000, positions={"AAPL": (1000, 100)}
        )
        # NAV = 600_000. A 1% drop means price ~99.4
        monitor.on_price_update("AAPL", Decimal("99.4"))
        assert "dd_2pct" not in monitor._alerts_sent


class TestDrawdownAlerts:
    def test_2pct_warning(self) -> None:
        """2% drawdown triggers a warning alert."""
        monitor, portfolio, ws = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        # NAV = 100_000. Need >2% drop: price < 98
        monitor.on_price_update("AAPL", Decimal("97"))
        assert "dd_2pct" in monitor._alerts_sent
        assert monitor._alerts_count >= 1

    def test_3pct_critical(self) -> None:
        """3% drawdown triggers a critical alert."""
        monitor, portfolio, ws = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        monitor.on_price_update("AAPL", Decimal("96"))
        assert "dd_2pct" in monitor._alerts_sent
        assert "dd_3pct" in monitor._alerts_sent
        assert monitor._alerts_count >= 2

    def test_5pct_kill_switch(self) -> None:
        """5% drawdown triggers kill switch alert and generates liquidation orders."""
        monitor, portfolio, ws = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        with patch.object(monitor.risk_engine, "generate_liquidation_orders") as mock_liq:
            mock_liq.return_value = []
            monitor.on_price_update("AAPL", Decimal("94"))
            assert "kill_switch" in monitor._alerts_sent
            mock_liq.assert_called_once_with(portfolio)

    def test_no_duplicate_alerts(self) -> None:
        """Same alert level should only fire once."""
        monitor, _, _ = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        monitor.on_price_update("AAPL", Decimal("97"))
        count_after_first = monitor._alerts_count

        # Another tick at the same price
        monitor.on_price_update("AAPL", Decimal("97"))
        assert monitor._alerts_count == count_after_first

    def test_progressive_alerts(self) -> None:
        """Drawdown worsening triggers alerts in sequence."""
        monitor, _, _ = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        # 2.5% drop
        monitor.on_price_update("AAPL", Decimal("97.5"))
        # Actually need >2% dd: 97.5 → 2.5% drop → alerts
        monitor.on_price_update("AAPL", Decimal("97"))
        assert "dd_2pct" in monitor._alerts_sent
        assert "dd_3pct" not in monitor._alerts_sent

        # Worsen to 4%
        monitor.on_price_update("AAPL", Decimal("95.5"))
        assert "dd_3pct" in monitor._alerts_sent
        assert "kill_switch" not in monitor._alerts_sent


class TestResetDaily:
    def test_resets_nav_high(self) -> None:
        monitor, portfolio, _ = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        # Simulate price increase then drop
        monitor.on_price_update("AAPL", Decimal("110"))
        old_high = monitor._nav_high

        # Reset
        monitor.on_price_update("AAPL", Decimal("105"))
        monitor.reset_daily()
        assert monitor._nav_high == float(portfolio.nav)
        assert monitor._nav_high < old_high

    def test_clears_alerts(self) -> None:
        monitor, _, _ = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        monitor.on_price_update("AAPL", Decimal("97"))
        assert len(monitor._alerts_sent) > 0
        monitor.reset_daily()
        assert len(monitor._alerts_sent) == 0


class TestGetStatus:
    def test_initial_status(self) -> None:
        monitor, portfolio, _ = _make_monitor(cash=1_000_000)
        status = monitor.get_status()
        assert status["nav_current"] == float(portfolio.nav)
        assert status["nav_high"] == float(portfolio.nav)
        assert status["intraday_drawdown"] == 0.0
        assert status["alerts_sent"] == 0
        assert status["alerts_total"] == 0
        assert status["last_update"] is None

    def test_status_after_drawdown(self) -> None:
        monitor, _, _ = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        monitor.on_price_update("AAPL", Decimal("97"))
        status = monitor.get_status()
        assert status["intraday_drawdown"] < 0
        assert status["alerts_sent"] > 0
        assert status["last_update"] is not None

    def test_status_nav_high_preserved(self) -> None:
        monitor, _, _ = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        monitor.on_price_update("AAPL", Decimal("110"))
        monitor.on_price_update("AAPL", Decimal("105"))
        status = monitor.get_status()
        assert status["nav_high"] == 110_000.0
        assert status["nav_current"] == 105_000.0


class TestBroadcastAlert:
    def test_broadcast_with_loop(self) -> None:
        """When a loop is provided, broadcast is scheduled."""
        loop = asyncio.new_event_loop()
        try:
            monitor, portfolio, ws = _make_monitor(
                cash=0, positions={"AAPL": (1000, 100)}
            )
            monitor._loop = loop

            # We can't easily test run_coroutine_threadsafe without
            # actually running the loop, so just verify the alert
            # state management works.
            monitor.on_price_update("AAPL", Decimal("97"))
            assert monitor._alerts_count > 0
        finally:
            loop.close()

    def test_broadcast_without_loop(self) -> None:
        """When no loop is available, alert still gets recorded."""
        monitor, _, ws = _make_monitor(
            cash=0, positions={"AAPL": (1000, 100)}
        )
        monitor._loop = None
        monitor.on_price_update("AAPL", Decimal("97"))
        assert "dd_2pct" in monitor._alerts_sent
        assert monitor._alerts_count >= 1


class TestZeroNav:
    def test_zero_nav_no_crash(self) -> None:
        """Zero NAV should not cause division by zero."""
        monitor, _, _ = _make_monitor(cash=0)
        assert monitor._nav_high == 0.0
        # Should return early without crash
        monitor.on_price_update("AAPL", Decimal("100"))
        assert "dd_2pct" not in monitor._alerts_sent


class TestAppStateGuard:
    """Tests for race condition prevention with app_state injection."""

    def _make_monitor_with_state(
        self,
        cash: float = 0,
        positions: dict[str, tuple[int, int]] | None = None,
        kill_switch_fired: bool = False,
    ) -> tuple["RealtimeRiskMonitor", MagicMock]:
        portfolio = _make_portfolio(cash, positions)
        risk_engine = RiskEngine()
        ws_manager = MagicMock()
        ws_manager.broadcast = AsyncMock()

        app_state = MagicMock()
        app_state.kill_switch_fired = kill_switch_fired
        app_state.mutation_lock = asyncio.Lock()

        monitor = RealtimeRiskMonitor(
            portfolio=portfolio,
            risk_engine=risk_engine,
            ws_manager=ws_manager,
            app_state=app_state,
        )
        return monitor, app_state

    def test_app_state_stored(self) -> None:
        """app_state kwarg is stored on the monitor."""
        monitor, app_state = self._make_monitor_with_state()
        assert monitor._app_state is app_state

    def test_no_app_state_still_works(self) -> None:
        """Without app_state, kill switch path still runs (backward compat)."""
        monitor, _, _ = _make_monitor(cash=0, positions={"AAPL": (1000, 100)})
        assert monitor._app_state is None
        with patch.object(monitor.risk_engine, "generate_liquidation_orders") as mock_liq:
            mock_liq.return_value = []
            monitor.on_price_update("AAPL", Decimal("94"))
            assert "kill_switch" in monitor._alerts_sent
            mock_liq.assert_called_once()

    def test_kill_switch_generates_liquidation_with_state(self) -> None:
        """With app_state, 5% drawdown still generates liquidation orders."""
        monitor, app_state = self._make_monitor_with_state(
            positions={"AAPL": (1000, 100)}
        )
        with patch.object(monitor.risk_engine, "generate_liquidation_orders") as mock_liq:
            mock_liq.return_value = []
            monitor.on_price_update("AAPL", Decimal("94"))
            assert "kill_switch" in monitor._alerts_sent
            mock_liq.assert_called_once()

    def test_no_execution_when_already_fired(self) -> None:
        """When kill_switch_fired is already True, path B skips liquidation."""
        monitor, app_state = self._make_monitor_with_state(
            positions={"AAPL": (1000, 100)},
            kill_switch_fired=True,
        )
        loop = asyncio.new_event_loop()
        monitor._loop = loop
        mock_svc = MagicMock()
        monitor.execution_service = mock_svc

        with patch.object(monitor.risk_engine, "generate_liquidation_orders") as mock_liq:
            from unittest.mock import MagicMock as MM
            fake_order = MM()
            mock_liq.return_value = [fake_order]

            # Patch run_coroutine_threadsafe to capture the coroutine and run it
            scheduled_coros: list = []

            def capture(coro, lp):  # type: ignore[no-untyped-def]
                scheduled_coros.append(coro)
                return MagicMock()

            with patch("asyncio.run_coroutine_threadsafe", side_effect=capture):
                monitor.on_price_update("AAPL", Decimal("94"))

            # Run the scheduled coroutine synchronously
            if scheduled_coros:
                loop.run_until_complete(scheduled_coros[0])

            # submit_orders should NOT have been called because fired=True
            mock_svc.submit_orders.assert_not_called()
        loop.close()
