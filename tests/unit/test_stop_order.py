"""Tests for StopOrderManager — 停損/停利委託管理的完整單元測試。"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.core.models import Instrument, Order, OrderType, Side
from src.execution.stop_order import StopOrderManager


# ── Helpers ──────────────────────────────────────────────


def _make_order(symbol: str = "2330", side: Side = Side.SELL) -> Order:
    return Order(
        instrument=Instrument(symbol=symbol),
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal("1000"),
        strategy_id="stop_test",
    )


# ── Tests ────────────────────────────────────────────────


class TestStopOrderAdd:
    def test_add_stop_order(self) -> None:
        mgr = StopOrderManager()
        order = _make_order()
        stop = mgr.add("2330", Decimal("580"), order, direction="below")

        assert stop.symbol == "2330"
        assert stop.stop_price == Decimal("580")
        assert stop.direction == "below"
        assert stop.executed is False
        assert stop.order is order
        assert len(mgr.get_pending()) == 1

    def test_add_above_direction(self) -> None:
        mgr = StopOrderManager()
        order = _make_order(side=Side.BUY)
        stop = mgr.add("2330", Decimal("620"), order, direction="above")

        assert stop.direction == "above"
        assert len(mgr.get_pending()) == 1

    def test_add_invalid_direction_raises(self) -> None:
        mgr = StopOrderManager()
        order = _make_order()
        with pytest.raises(ValueError, match="direction must be"):
            mgr.add("2330", Decimal("580"), order, direction="sideways")

    def test_stop_order_has_id_and_timestamp(self) -> None:
        mgr = StopOrderManager()
        order = _make_order()
        stop = mgr.add("2330", Decimal("580"), order)
        assert len(stop.id) == 12
        assert stop.created_at is not None


class TestStopOrderTriggerBelow:
    def test_trigger_when_price_at_stop(self) -> None:
        mgr = StopOrderManager()
        order = _make_order()
        mgr.add("2330", Decimal("580"), order, direction="below")

        triggered = mgr.on_tick("2330", Decimal("580"))
        assert len(triggered) == 1
        assert triggered[0] is order

    def test_trigger_when_price_below_stop(self) -> None:
        mgr = StopOrderManager()
        order = _make_order()
        mgr.add("2330", Decimal("580"), order, direction="below")

        triggered = mgr.on_tick("2330", Decimal("575"))
        assert len(triggered) == 1
        assert triggered[0] is order

    def test_not_triggered_when_price_above_stop(self) -> None:
        mgr = StopOrderManager()
        order = _make_order()
        mgr.add("2330", Decimal("580"), order, direction="below")

        triggered = mgr.on_tick("2330", Decimal("590"))
        assert len(triggered) == 0
        assert len(mgr.get_pending()) == 1


class TestStopOrderTriggerAbove:
    def test_trigger_when_price_at_stop(self) -> None:
        mgr = StopOrderManager()
        order = _make_order(side=Side.BUY)
        mgr.add("2330", Decimal("620"), order, direction="above")

        triggered = mgr.on_tick("2330", Decimal("620"))
        assert len(triggered) == 1
        assert triggered[0] is order

    def test_trigger_when_price_above_stop(self) -> None:
        mgr = StopOrderManager()
        order = _make_order(side=Side.BUY)
        mgr.add("2330", Decimal("620"), order, direction="above")

        triggered = mgr.on_tick("2330", Decimal("625"))
        assert len(triggered) == 1

    def test_not_triggered_when_price_below_stop(self) -> None:
        mgr = StopOrderManager()
        order = _make_order(side=Side.BUY)
        mgr.add("2330", Decimal("620"), order, direction="above")

        triggered = mgr.on_tick("2330", Decimal("615"))
        assert len(triggered) == 0


class TestStopOrderExecutedNotRetriggered:
    def test_executed_stop_not_retriggered(self) -> None:
        mgr = StopOrderManager()
        order = _make_order()
        mgr.add("2330", Decimal("580"), order, direction="below")

        # First tick triggers
        triggered1 = mgr.on_tick("2330", Decimal("575"))
        assert len(triggered1) == 1

        # Second tick should NOT re-trigger
        triggered2 = mgr.on_tick("2330", Decimal("570"))
        assert len(triggered2) == 0

        assert len(mgr.get_executed()) == 1
        assert len(mgr.get_pending()) == 0


class TestStopOrderMultipleStops:
    def test_multiple_stops_same_symbol(self) -> None:
        mgr = StopOrderManager()
        order1 = _make_order()
        order2 = _make_order()
        mgr.add("2330", Decimal("580"), order1, direction="below")
        mgr.add("2330", Decimal("570"), order2, direction="below")

        # Price hits first stop but not second
        triggered = mgr.on_tick("2330", Decimal("578"))
        assert len(triggered) == 1
        assert triggered[0] is order1

        # Price hits second stop
        triggered2 = mgr.on_tick("2330", Decimal("568"))
        assert len(triggered2) == 1
        assert triggered2[0] is order2

    def test_different_symbols_independent(self) -> None:
        mgr = StopOrderManager()
        order1 = _make_order(symbol="2330")
        order2 = _make_order(symbol="2317")
        mgr.add("2330", Decimal("580"), order1, direction="below")
        mgr.add("2317", Decimal("100"), order2, direction="below")

        # Tick for 2330 only
        triggered = mgr.on_tick("2330", Decimal("575"))
        assert len(triggered) == 1
        assert triggered[0] is order1
        assert len(mgr.get_pending()) == 1  # 2317 still pending

    def test_both_directions_triggered(self) -> None:
        mgr = StopOrderManager()
        sell_order = _make_order(side=Side.SELL)
        buy_order = _make_order(side=Side.BUY)
        mgr.add("2330", Decimal("580"), sell_order, direction="below")
        mgr.add("2330", Decimal("620"), buy_order, direction="above")

        # Price drops — only below triggered
        triggered = mgr.on_tick("2330", Decimal("575"))
        assert len(triggered) == 1
        assert triggered[0] is sell_order


class TestStopOrderCancel:
    def test_cancel_by_symbol(self) -> None:
        mgr = StopOrderManager()
        mgr.add("2330", Decimal("580"), _make_order(), direction="below")
        mgr.add("2330", Decimal("570"), _make_order(), direction="below")
        mgr.add("2317", Decimal("100"), _make_order(symbol="2317"), direction="below")

        removed = mgr.cancel("2330")
        assert removed == 2
        assert len(mgr.get_pending()) == 1  # 2317 remains

    def test_cancel_does_not_remove_executed(self) -> None:
        mgr = StopOrderManager()
        mgr.add("2330", Decimal("580"), _make_order(), direction="below")

        # Trigger first
        mgr.on_tick("2330", Decimal("575"))
        assert len(mgr.get_executed()) == 1

        # Cancel should not remove executed
        removed = mgr.cancel("2330")
        assert removed == 0
        assert len(mgr.get_executed()) == 1

    def test_cancel_all(self) -> None:
        mgr = StopOrderManager()
        mgr.add("2330", Decimal("580"), _make_order(), direction="below")
        mgr.add("2317", Decimal("100"), _make_order(symbol="2317"), direction="below")

        removed = mgr.cancel_all()
        assert removed == 2
        assert len(mgr.get_pending()) == 0

    def test_cancel_all_preserves_executed(self) -> None:
        mgr = StopOrderManager()
        mgr.add("2330", Decimal("580"), _make_order(), direction="below")
        mgr.add("2317", Decimal("100"), _make_order(symbol="2317"), direction="below")

        # Trigger one
        mgr.on_tick("2330", Decimal("575"))

        removed = mgr.cancel_all()
        assert removed == 1  # only the 2317 pending one
        assert len(mgr.get_executed()) == 1


class TestStopOrderGetters:
    def test_get_pending_and_executed(self) -> None:
        mgr = StopOrderManager()
        mgr.add("2330", Decimal("580"), _make_order(), direction="below")
        mgr.add("2317", Decimal("100"), _make_order(symbol="2317"), direction="below")

        assert len(mgr.get_pending()) == 2
        assert len(mgr.get_executed()) == 0

        mgr.on_tick("2330", Decimal("575"))

        assert len(mgr.get_pending()) == 1
        assert len(mgr.get_executed()) == 1
        assert mgr.get_executed()[0].symbol == "2330"
        assert mgr.get_pending()[0].symbol == "2317"
