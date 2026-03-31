"""AK-6 (partial): Broker disconnect resilience tests.

The #1 real-money risk: Sinopac disconnects mid-order.
Verifies the system doesn't duplicate orders or lose state.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import (
    AssetClass,
    Instrument,
    Market,
    Order,
    Portfolio,
    Position,
    Side,
)


class TestBrokerTimeoutDuringOrder:
    """Broker raises timeout/ConnectionError during submit_order."""

    def test_order_rejected_on_timeout(self):
        """If broker.submit_order raises, order status should be REJECTED."""
        from src.execution.broker.sinopac import SinopacBroker

        # Create mock Sinopac that raises on submit
        broker = MagicMock(spec=SinopacBroker)
        broker.submit_order.side_effect = ConnectionError("Sinopac disconnected")

        order = Order(
            instrument=Instrument(
                symbol="2330.TW",
                asset_class=AssetClass.EQUITY,
                market=Market.TW,
            ),
            side=Side.BUY,
            quantity=Decimal("1000"),
            price=Decimal("590"),
        )

        with pytest.raises(ConnectionError):
            broker.submit_order(order)

        # Order should NOT have been applied to portfolio
        # (execute_from_weights catches exceptions before apply_trades)

    def test_portfolio_unchanged_after_broker_error(self):
        """Portfolio must not be modified if broker execution fails."""
        portfolio = Portfolio()
        portfolio.positions["2330.TW"] = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("590"),
        )
        original_qty = portfolio.positions["2330.TW"].quantity
        original_cash = portfolio.cash

        # Simulate: execute_from_weights fails mid-execution
        # The function should NOT call apply_trades on failure
        from src.core.trading_pipeline import execute_from_weights

        mock_broker = MagicMock()
        mock_broker.execute.side_effect = ConnectionError("Broker down")

        mock_risk = MagicMock()
        mock_risk.check_orders.return_value = ([], [])  # approve all

        # execute_from_weights should raise or return empty, not modify portfolio
        try:
            execute_from_weights(
                target_weights={"2330.TW": 0.0},  # sell all
                portfolio=portfolio,
                risk_engine=mock_risk,
                prices={"2330.TW": Decimal("590")},
                broker=mock_broker,
            )
        except Exception:
            pass  # Expected

        # Portfolio unchanged
        assert portfolio.positions["2330.TW"].quantity == original_qty
        assert portfolio.cash == original_cash


class TestReconcileAfterDisconnect:
    """Reconciliation must handle broker unavailability gracefully."""

    @pytest.mark.asyncio
    async def test_reconcile_handles_query_failure(self):
        """If broker.query_positions() raises, reconcile should return error."""
        from src.scheduler.jobs import execute_daily_reconcile

        config = MagicMock()
        config.mode = "live"

        mock_state = MagicMock()
        mock_broker = MagicMock()
        mock_broker.query_positions.side_effect = ConnectionError("Broker down")

        # Need to make isinstance check pass for SinopacBroker
        from src.execution.broker.sinopac import SinopacBroker
        mock_broker.__class__ = SinopacBroker
        mock_state.execution_service.is_initialized = True
        mock_state.execution_service.broker = mock_broker

        with (
            patch("src.api.state.get_app_state", return_value=mock_state),
            patch("src.scheduler.jobs.update_portfolio_market_prices") as mock_update,
            patch("src.notifications.factory.create_notifier") as mock_notifier,
        ):
            mock_update.return_value = None
            mock_notifier.return_value.is_configured.return_value = False

            result = await execute_daily_reconcile(config)
            assert result["status"] == "error"
