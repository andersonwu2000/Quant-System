"""Tests for src/execution/service.py — ExecutionService.

Covers:
- ExecutionConfig creation
- ExecutionService initialization (backtest/paper/live modes)
- Mode switching
- Order routing (backtest via SimBroker, paper/live via BrokerAdapter)
- Market hours: queueing vs rejection
- Connection status and fallback
- Queue flush
- Shutdown
- Error handling
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import (
    Instrument,
    Order,
    OrderStatus,
    OrderType,
    Portfolio,
    Side,
    Trade,
)
from src.execution.broker.base import PaperBroker
from src.execution.service import ExecutionConfig, ExecutionService


# ── Helpers ──────────────────────────────────────────────────


def _make_instrument(symbol: str = "2330.TW") -> Instrument:
    return Instrument(symbol=symbol, name="TSMC")


def _make_order(
    symbol: str = "2330.TW",
    side: Side = Side.BUY,
    qty: int = 1000,
    price: float | None = 600.0,
) -> Order:
    return Order(
        instrument=_make_instrument(symbol),
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal(str(qty)),
        price=Decimal(str(price)) if price is not None else None,
        strategy_id="test_strategy",
    )


def _make_bars(*symbols: str) -> dict[str, dict[str, object]]:
    """Make simple bar data for given symbols."""
    bars: dict[str, dict[str, object]] = {}
    for sym in symbols:
        bars[sym] = {"open": 598, "high": 605, "low": 595, "close": 600, "volume": 50000}
    return bars


# ── ExecutionConfig ──────────────────────────────────────────


class TestExecutionConfig:
    def test_defaults(self) -> None:
        cfg = ExecutionConfig()
        assert cfg.mode == "backtest"
        assert cfg.check_market_hours is True
        assert cfg.queue_off_hours_orders is True
        assert cfg.smart_order_enabled is False
        assert cfg.sinopac_api_key == ""
        assert cfg.sinopac_simulation is True

    def test_paper_mode(self) -> None:
        cfg = ExecutionConfig(mode="paper")
        assert cfg.mode == "paper"

    def test_live_mode(self) -> None:
        cfg = ExecutionConfig(mode="live")
        assert cfg.mode == "live"

    def test_sinopac_fields(self) -> None:
        cfg = ExecutionConfig(
            sinopac_api_key="key123",
            sinopac_secret_key="secret456",
            sinopac_ca_path="/path/ca",
            sinopac_ca_password="pw",
            sinopac_simulation=False,
        )
        assert cfg.sinopac_api_key == "key123"
        assert cfg.sinopac_secret_key == "secret456"
        assert cfg.sinopac_ca_path == "/path/ca"
        assert cfg.sinopac_ca_password == "pw"
        assert cfg.sinopac_simulation is False

    def test_smart_order_fields(self) -> None:
        cfg = ExecutionConfig(
            smart_order_enabled=True,
            smart_order_slices=10,
            smart_order_interval_minutes=15,
            smart_order_min_value=100000,
        )
        assert cfg.smart_order_enabled is True
        assert cfg.smart_order_slices == 10
        assert cfg.smart_order_interval_minutes == 15
        assert cfg.smart_order_min_value == 100000


# ── Initialization ───────────────────────────────────────────


class TestInitialization:
    def test_not_initialized_by_default(self) -> None:
        svc = ExecutionService()
        assert svc.is_initialized is False
        assert svc.broker is None
        assert svc.sim_broker is None

    def test_default_config_when_none(self) -> None:
        svc = ExecutionService(None)
        assert svc.mode == "backtest"

    def test_initialize_backtest(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="backtest"))
        result = svc.initialize()
        assert result is True
        assert svc.is_initialized is True
        assert svc.sim_broker is not None
        assert svc.broker is None
        assert svc.fallback_mode is False

    def test_initialize_paper_fallback_import_error(self) -> None:
        """When shioaji is not importable, paper mode falls back to PaperBroker."""
        cfg = ExecutionConfig(mode="paper")
        svc = ExecutionService(cfg)
        result = svc.initialize()
        assert result is True
        assert svc.is_initialized is True
        # Without shioaji package, should be in fallback mode
        if svc.fallback_mode:
            assert isinstance(svc.broker, PaperBroker)

    def test_initialize_live_no_api_key_fails(self) -> None:
        """Live mode without API key refuses to start (LT-6)."""
        cfg = ExecutionConfig(mode="live")
        svc = ExecutionService(cfg)
        result = svc.initialize()
        assert result is False
        assert svc.is_initialized is False

    def test_twap_created_when_enabled(self) -> None:
        cfg = ExecutionConfig(smart_order_enabled=True, smart_order_slices=3)
        svc = ExecutionService(cfg)
        assert svc._twap is not None

    def test_twap_not_created_when_disabled(self) -> None:
        cfg = ExecutionConfig(smart_order_enabled=False)
        svc = ExecutionService(cfg)
        assert svc._twap is None


# ── Mode switching ───────────────────────────────────────────


class TestModeSwitching:
    def test_backtest_uses_sim_broker(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="backtest"))
        svc.initialize()
        assert svc.sim_broker is not None
        assert svc.broker is None

    def test_paper_uses_broker(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="paper"))
        svc.initialize()
        assert svc.broker is not None

    def test_mode_property(self) -> None:
        for mode in ("backtest", "paper", "live"):
            svc = ExecutionService(ExecutionConfig(mode=mode))  # type: ignore[arg-type]
            assert svc.mode == mode


# ── Order routing (backtest) ─────────────────────────────────


class TestBacktestOrderRouting:
    def test_submit_empty_returns_empty(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="backtest"))
        svc.initialize()
        assert svc.submit_orders([], Portfolio()) == []

    def test_submit_single_order(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="backtest"))
        svc.initialize()

        order = _make_order(symbol="2330.TW")
        bars = _make_bars("2330.TW")
        trades = svc.submit_orders([order], Portfolio(), current_bars=bars)

        assert len(trades) == 1
        assert isinstance(trades[0], Trade)
        assert trades[0].symbol == "2330.TW"

    def test_submit_multiple_orders(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="backtest"))
        svc.initialize()

        orders = [
            _make_order(symbol="2330.TW"),
            _make_order(symbol="2317.TW"),
        ]
        bars = _make_bars("2330.TW", "2317.TW")
        trades = svc.submit_orders(orders, Portfolio(), current_bars=bars)
        assert len(trades) == 2

    def test_submit_sell_order(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="backtest"))
        svc.initialize()

        order = _make_order(symbol="2330.TW", side=Side.SELL)
        bars = _make_bars("2330.TW")
        trades = svc.submit_orders([order], Portfolio(), current_bars=bars)
        assert len(trades) == 1
        assert trades[0].side == Side.SELL


# ── Order routing (paper/live with mock broker) ──────────────


class TestPaperLiveOrderRouting:
    def _make_svc_with_mock_broker(
        self, mode: str = "paper", check_hours: bool = False,
    ) -> tuple[ExecutionService, MagicMock]:
        cfg = ExecutionConfig(mode=mode, check_market_hours=check_hours)  # type: ignore[arg-type]
        svc = ExecutionService(cfg)
        mock_broker = MagicMock()
        mock_broker.submit_order.return_value = "order_123"
        svc._broker = mock_broker
        svc._initialized = True
        return svc, mock_broker

    def test_paper_mode_skips_market_hours(self) -> None:
        """Paper mode skips market hours check, orders go through."""
        svc, mock_broker = self._make_svc_with_mock_broker(
            mode="paper", check_hours=True,
        )
        order = _make_order()
        with patch("src.execution.service.is_tradable", return_value=False):
            svc.submit_orders([order], Portfolio())
        mock_broker.submit_order.assert_called_once()

    def test_live_mode_market_closed_queues(self) -> None:
        """Live mode queues orders when market is closed."""
        cfg = ExecutionConfig(
            mode="live", check_market_hours=True, queue_off_hours_orders=True,
        )
        svc = ExecutionService(cfg)
        svc._broker = MagicMock()
        svc._initialized = True

        order = _make_order()
        with patch("src.execution.service.is_tradable", return_value=False):
            trades = svc.submit_orders([order], Portfolio())

        assert trades == []
        assert svc.order_queue.size == 1

    def test_live_mode_market_closed_rejects(self) -> None:
        """Live mode rejects orders when market closed and queueing disabled."""
        cfg = ExecutionConfig(
            mode="live", check_market_hours=True, queue_off_hours_orders=False,
        )
        svc = ExecutionService(cfg)
        svc._broker = MagicMock()
        svc._initialized = True

        order = _make_order()
        from src.execution.market_hours import TradingSession
        with patch("src.execution.service.is_tradable", return_value=False), \
             patch("src.execution.service.get_current_session", return_value=TradingSession.AFTER_HOURS):
            trades = svc.submit_orders([order], Portfolio())

        assert trades == []
        assert order.status == OrderStatus.REJECTED
        assert "Market closed" in order.reject_reason

    def test_live_mode_multiple_orders_rejected(self) -> None:
        """All orders get rejected when market closed and queueing disabled."""
        cfg = ExecutionConfig(
            mode="live", check_market_hours=True, queue_off_hours_orders=False,
        )
        svc = ExecutionService(cfg)
        svc._broker = MagicMock()
        svc._initialized = True

        orders = [_make_order(symbol="2330.TW"), _make_order(symbol="2317.TW")]
        from src.execution.market_hours import TradingSession
        with patch("src.execution.service.is_tradable", return_value=False), \
             patch("src.execution.service.get_current_session", return_value=TradingSession.WEEKEND):
            trades = svc.submit_orders(orders, Portfolio())

        assert trades == []
        for o in orders:
            assert o.status == OrderStatus.REJECTED

    def test_broker_filled_order_produces_trade(self) -> None:
        """When broker fills an order, a Trade should be created."""
        svc, mock_broker = self._make_svc_with_mock_broker(mode="paper")

        order = _make_order()

        def fill_order(o: Order) -> str:
            o.status = OrderStatus.FILLED
            o.filled_qty = o.quantity
            o.filled_avg_price = Decimal("600")
            o.commission = Decimal("85")
            return "order_123"

        mock_broker.submit_order.side_effect = fill_order

        trades = svc.submit_orders([order], Portfolio())
        assert len(trades) == 1
        assert trades[0].symbol == "2330.TW"
        assert trades[0].price == Decimal("600")

    def test_broker_unfilled_order_no_trade(self) -> None:
        """When broker does NOT fill, no Trade should be created."""
        svc, mock_broker = self._make_svc_with_mock_broker(mode="paper")
        order = _make_order()
        # Default: order stays PENDING after submit_order mock
        mock_broker.submit_order.return_value = "order_123"

        trades = svc.submit_orders([order], Portfolio())
        assert trades == []


# ── Connection & Fallback ────────────────────────────────────


class TestConnectionFallback:
    def test_fallback_mode_default_false(self) -> None:
        svc = ExecutionService()
        assert svc.fallback_mode is False

    def test_paper_broker_connected(self) -> None:
        broker = PaperBroker()
        assert broker.is_connected() is True

    def test_paper_broker_query_account(self) -> None:
        broker = PaperBroker()
        acct = broker.query_account()
        assert "cash" in acct
        assert acct["cash"] > 0


# ── Queue operations ─────────────────────────────────────────


class TestQueueOperations:
    def test_flush_empty_queue(self) -> None:
        svc = ExecutionService()
        svc.initialize()
        assert svc.flush_queued_orders() == []

    def test_flush_after_queueing(self) -> None:
        cfg = ExecutionConfig(mode="live", check_market_hours=True, queue_off_hours_orders=True)
        svc = ExecutionService(cfg)
        svc._broker = MagicMock()
        svc._initialized = True

        order = _make_order()
        with patch("src.execution.service.is_tradable", return_value=False):
            svc.submit_orders([order], Portfolio())

        queued = svc.flush_queued_orders()
        assert len(queued) == 1
        assert svc.order_queue.size == 0

    def test_multiple_queue_drain(self) -> None:
        """Multiple orders queued, all drained at once."""
        cfg = ExecutionConfig(mode="live", check_market_hours=True, queue_off_hours_orders=True)
        svc = ExecutionService(cfg)
        svc._broker = MagicMock()
        svc._initialized = True

        orders = [_make_order(symbol=f"S{i}") for i in range(5)]
        with patch("src.execution.service.is_tradable", return_value=False):
            svc.submit_orders(orders, Portfolio())

        assert svc.order_queue.size == 5
        drained = svc.flush_queued_orders()
        assert len(drained) == 5
        assert svc.order_queue.size == 0


# ── Shutdown ─────────────────────────────────────────────────


class TestShutdown:
    def test_shutdown_backtest(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="backtest"))
        svc.initialize()
        assert svc.is_initialized is True
        svc.shutdown()
        assert svc.is_initialized is False

    def test_shutdown_paper(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="paper"))
        svc.initialize()
        svc.shutdown()
        assert svc.is_initialized is False

    def test_shutdown_not_initialized(self) -> None:
        svc = ExecutionService()
        svc.shutdown()  # should not raise
        assert svc.is_initialized is False

    def test_shutdown_idempotent(self) -> None:
        svc = ExecutionService(ExecutionConfig(mode="backtest"))
        svc.initialize()
        svc.shutdown()
        svc.shutdown()  # second call should not raise
        assert svc.is_initialized is False


# ── Error handling ───────────────────────────────────────────


class TestErrorHandling:
    def test_submit_without_init_raises(self) -> None:
        svc = ExecutionService()
        with pytest.raises(RuntimeError, match="not initialized"):
            svc.submit_orders([_make_order()], Portfolio())

    def test_oms_property_always_available(self) -> None:
        svc = ExecutionService()
        assert svc.oms is not None

    def test_order_queue_property_always_available(self) -> None:
        svc = ExecutionService()
        assert svc.order_queue is not None
        assert svc.order_queue.size == 0


# ── Safety Gates ──────────────────────────────────────────────


class TestEmergencyHaltFile:
    """Gate 1: file-based kill switch."""

    def test_halt_file_rejects_all_orders(self, tmp_path: "Path") -> None:
        halt_file = tmp_path / "halt.flag"
        halt_file.touch()

        svc = ExecutionService(ExecutionConfig(mode="paper"))
        svc._initialized = True
        svc._emergency_halt_file = str(halt_file)
        svc._startup_warmup_seconds = 0
        svc._startup_time = 0

        orders = [_make_order()]
        trades = svc._check_safety_gates(orders)
        assert trades is True  # rejected
        assert orders[0].status == OrderStatus.REJECTED
        assert "Emergency halt" in orders[0].reject_reason

    def test_no_halt_file_allows_orders(self, tmp_path: "Path") -> None:
        svc = ExecutionService(ExecutionConfig(mode="paper"))
        svc._initialized = True
        svc._emergency_halt_file = str(tmp_path / "nonexistent.flag")
        svc._startup_warmup_seconds = 0
        svc._startup_time = 0

        orders = [_make_order()]
        rejected = svc._check_safety_gates(orders)
        assert rejected is False


class TestStartupWarmup:
    """Gate 2: startup cooldown period."""

    def test_warmup_rejects_during_cooldown(self) -> None:
        import time
        svc = ExecutionService(ExecutionConfig(mode="paper"))
        svc._initialized = True
        svc._startup_time = time.monotonic()  # just started
        svc._emergency_halt_file = "nonexistent_path"
        svc._startup_warmup_seconds = 300

        orders = [_make_order()]
        rejected = svc._check_safety_gates(orders)
        assert rejected is True
        assert orders[0].status == OrderStatus.REJECTED
        assert "warmup" in orders[0].reject_reason.lower()

    def test_warmup_allows_after_cooldown(self) -> None:
        import time
        svc = ExecutionService(ExecutionConfig(mode="paper"))
        svc._initialized = True
        svc._startup_time = time.monotonic() - 600
        svc._emergency_halt_file = "nonexistent_path"
        svc._startup_warmup_seconds = 120

        orders = [_make_order()]
        rejected = svc._check_safety_gates(orders)
        assert rejected is False


class TestOrderRateLimit:
    """Gate 3: per-minute order throttling."""

    def test_rate_limit_rejects_burst(self) -> None:
        import time
        svc = ExecutionService(ExecutionConfig(mode="paper"))
        svc._initialized = True
        svc._startup_time = time.monotonic() - 9999
        svc._emergency_halt_file = "nonexistent_path"
        svc._startup_warmup_seconds = 0
        svc._max_orders_per_minute = 5

        # Submit 5 orders (should pass gate)
        batch1 = [_make_order(symbol=f"{i}.TW") for i in range(5)]
        rejected1 = svc._check_safety_gates(batch1)
        assert rejected1 is False

        # Submit 1 more (should be rejected — 6 > 5/min)
        batch2 = [_make_order(symbol="9999.TW")]
        rejected2 = svc._check_safety_gates(batch2)
        assert rejected2 is True
        assert batch2[0].status == OrderStatus.REJECTED
        assert "Rate limit" in batch2[0].reject_reason
