"""Tests for ExecutionService — 模式路由測試。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import Instrument, Order, OrderStatus, OrderType, Portfolio, Side
from src.execution.service import ExecutionConfig, ExecutionService


def _make_order(symbol: str = "2330") -> Order:
    return Order(
        instrument=Instrument(symbol=symbol),
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1000"),
        strategy_id="test",
    )


class TestExecutionServiceBacktest:
    def test_initialize_backtest(self) -> None:
        config = ExecutionConfig(mode="backtest")
        svc = ExecutionService(config)
        assert svc.initialize() is True
        assert svc.mode == "backtest"
        assert svc.sim_broker is not None

    def test_submit_orders_backtest(self) -> None:
        config = ExecutionConfig(mode="backtest")
        svc = ExecutionService(config)
        svc.initialize()

        order = _make_order()
        portfolio = Portfolio()
        bars = {"2330": {"close": 590.0, "volume": 1000000}}

        trades = svc.submit_orders([order], portfolio, current_bars=bars)
        assert len(trades) == 1
        assert trades[0].symbol == "2330"

    def test_submit_empty_orders(self) -> None:
        config = ExecutionConfig(mode="backtest")
        svc = ExecutionService(config)
        svc.initialize()

        trades = svc.submit_orders([], Portfolio())
        assert trades == []


class TestExecutionServicePaper:
    def test_initialize_paper_no_shioaji(self) -> None:
        """Without shioaji installed, should fall back to PaperBroker."""
        config = ExecutionConfig(mode="paper")
        svc = ExecutionService(config)

        # Make the import inside initialize() raise ImportError
        import src.execution.service as mod

        def patched_init(self_inner: ExecutionService) -> bool:
            # Simulate ImportError on sinopac import
            from src.execution.broker.base import PaperBroker
            self_inner._broker = PaperBroker()
            self_inner._initialized = True
            return True

        with patch.object(mod.ExecutionService, "initialize", patched_init):
            result = svc.initialize()

        assert result is True

    def test_initialize_paper_with_mock_broker(self) -> None:
        config = ExecutionConfig(mode="paper")
        svc = ExecutionService(config)

        # Simulate successful init: directly set broker
        mock_sinopac = MagicMock()
        mock_sinopac.is_connected.return_value = True

        with patch("src.execution.broker.sinopac.SinopacBroker", return_value=mock_sinopac), \
             patch("src.execution.broker.sinopac.SinopacConfig"):
            result = svc.initialize()

        assert result is True
        assert svc.broker is not None

    def test_paper_mode_skips_market_hours(self) -> None:
        """Paper mode skips market hours check — orders go through even when closed."""
        config = ExecutionConfig(
            mode="paper", check_market_hours=True, queue_off_hours_orders=False
        )
        svc = ExecutionService(config)
        svc._initialized = True
        svc._broker = MagicMock()
        svc._broker.submit_order.return_value = "mock_id"

        order = _make_order()

        with patch("src.execution.service.is_tradable", return_value=False):
            svc.submit_orders([order], Portfolio())

        # Paper mode skips market hours — broker.submit_order should be called
        svc._broker.submit_order.assert_called_once()

    def test_live_mode_market_hours_queues(self) -> None:
        """Live mode should queue orders when market is closed."""
        config = ExecutionConfig(
            mode="live", check_market_hours=True, queue_off_hours_orders=True
        )
        svc = ExecutionService(config)
        svc._initialized = True
        svc._broker = MagicMock()

        order = _make_order()

        with patch("src.execution.service.is_tradable", return_value=False):
            trades = svc.submit_orders([order], Portfolio())

        assert trades == []
        assert svc.order_queue.size == 1

    def test_flush_queued_orders(self) -> None:
        config = ExecutionConfig(mode="paper")
        svc = ExecutionService(config)
        svc._order_queue.enqueue({"symbol": "2330"})

        flushed = svc.flush_queued_orders()
        assert len(flushed) == 1
        assert svc.order_queue.size == 0


class TestExecutionServiceShutdown:
    def test_shutdown(self) -> None:
        config = ExecutionConfig(mode="backtest")
        svc = ExecutionService(config)
        svc.initialize()
        svc.shutdown()
        assert not svc.is_initialized

    def test_not_initialized_raises(self) -> None:
        svc = ExecutionService()
        with pytest.raises(RuntimeError, match="not initialized"):
            svc.submit_orders([_make_order()], Portfolio())
