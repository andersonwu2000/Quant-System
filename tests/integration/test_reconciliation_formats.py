"""AK-2 Layer 5: Reconciliation symbol format and mode guard tests.

Regression tests for 2026-03-31 bugs:
- System uses .TW suffix, broker uses bare symbols → matched: 0
- Paper mode false alerts (SimBroker ephemeral vs Portfolio persistent)
- API endpoints accessible in paper mode → misleading results
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.core.models import Instrument, Portfolio, Position
from src.execution.reconcile import reconcile


# ── Test 5.1: Mixed symbol format reconciliation ────────────────────


class TestMixedSymbolFormat:
    """Reconciliation must correctly handle .TW vs bare symbol formats."""

    def _make_portfolio(self, **positions: tuple[int, float]) -> Portfolio:
        p = Portfolio()
        for symbol, (qty, cost) in positions.items():
            p.positions[symbol] = Position(
                instrument=Instrument(symbol=symbol),
                quantity=Decimal(str(qty)),
                avg_cost=Decimal(str(cost)),
            )
        return p

    def test_system_tw_broker_bare_matched(self):
        """System .TW + Broker bare with same qty → matched."""
        portfolio = self._make_portfolio(**{"2330.TW": (1000, 590)})
        broker = {"2330": {"quantity": 1000, "avg_cost": 590}}
        result = reconcile(portfolio, broker)
        assert result.is_clean
        assert len(result.matched) == 1

    def test_system_tw_broker_bare_mismatched(self):
        """System .TW + Broker bare with different qty → mismatched."""
        portfolio = self._make_portfolio(**{"2330.TW": (1000, 590)})
        broker = {"2330": {"quantity": 500, "avg_cost": 590}}
        result = reconcile(portfolio, broker)
        assert not result.is_clean
        assert len(result.mismatched) == 1

    def test_system_tw_broker_bare_system_only(self):
        """Position in system (.TW) but not in broker → system_only."""
        portfolio = self._make_portfolio(
            **{"2330.TW": (1000, 590), "2451.TW": (100, 200)}
        )
        broker = {"2330": {"quantity": 1000, "avg_cost": 590}}
        result = reconcile(portfolio, broker)
        assert len(result.matched) == 1
        assert len(result.system_only) == 1
        assert result.system_only[0].symbol == "2451.TW"

    def test_system_tw_broker_bare_broker_only(self):
        """Position in broker (bare) but not in system → broker_only."""
        portfolio = self._make_portfolio(**{"2330.TW": (1000, 590)})
        broker = {
            "2330": {"quantity": 1000, "avg_cost": 590},
            "1312": {"quantity": 84, "avg_cost": 30},
        }
        result = reconcile(portfolio, broker)
        assert len(result.matched) == 1
        assert len(result.broker_only) == 1

    def test_both_bare_still_works(self):
        """Both sides bare → no normalization needed, still works."""
        portfolio = self._make_portfolio(**{"2330": (1000, 590)})
        broker = {"2330": {"quantity": 1000, "avg_cost": 590}}
        result = reconcile(portfolio, broker)
        assert result.is_clean

    def test_both_tw_still_works(self):
        """Both sides .TW → no normalization needed, still works."""
        portfolio = self._make_portfolio(**{"2330.TW": (1000, 590)})
        broker = {"2330.TW": {"quantity": 1000, "avg_cost": 590}}
        result = reconcile(portfolio, broker)
        assert result.is_clean

    def test_full_scenario_from_webhook(self):
        """Reproduce the exact 2026-03-31 Discord webhook scenario.

        System: 2406.TW(22), 2887.TW(37), 2451.TW(3)
        Broker: 2406(22), 2887(37), 1312(84)
        Expected: 2 matched, 1 system_only(2451), 1 broker_only(1312)
        """
        portfolio = self._make_portfolio(**{
            "2406.TW": (22, 100),
            "2887.TW": (37, 50),
            "2451.TW": (3, 200),
        })
        broker = {
            "2406": {"quantity": 22, "avg_cost": 100},
            "2887": {"quantity": 37, "avg_cost": 50},
            "1312": {"quantity": 84, "avg_cost": 30},
        }
        result = reconcile(portfolio, broker)
        assert len(result.matched) == 2
        assert len(result.system_only) == 1
        assert len(result.broker_only) == 1


# ── Test 5.2: Mode guard (scheduler) ───────────────────────────────


class TestReconcileSchedulerModeGuard:
    """execute_daily_reconcile must skip in non-live modes."""

    @pytest.mark.asyncio
    async def test_paper_mode_skips(self):
        """Paper mode (reconciliation disabled) → reconcile skipped."""
        from src.scheduler.jobs import execute_daily_reconcile

        config = MagicMock()
        config.mode = "paper"
        config.enable_reconciliation = False

        result = await execute_daily_reconcile(config)
        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_backtest_mode_skips(self):
        """Backtest mode (reconciliation disabled) → reconcile skipped."""
        from src.scheduler.jobs import execute_daily_reconcile

        config = MagicMock()
        config.mode = "backtest"
        config.enable_reconciliation = False

        result = await execute_daily_reconcile(config)
        assert result["status"] == "skipped"


# ── Test 5.3: API endpoint mode guard ──────────────────────────────


class TestReconcileApiModeGuard:
    """POST /execution/reconcile must reject in paper mode."""

    def test_reconcile_endpoint_checks_broker_type(self):
        """Verify reconcile endpoint source contains SinopacBroker check."""
        import inspect
        from src.api.routes.execution import run_reconciliation
        source = inspect.getsource(run_reconciliation)
        assert "SinopacBroker" in source, (
            "run_reconciliation must check for SinopacBroker"
        )

    def test_auto_correct_endpoint_checks_broker_type(self):
        """Verify auto-correct endpoint source contains SinopacBroker check."""
        import inspect
        from src.api.routes.execution import auto_correct_positions
        source = inspect.getsource(auto_correct_positions)
        assert "SinopacBroker" in source, (
            "auto_correct_positions must check for SinopacBroker"
        )
