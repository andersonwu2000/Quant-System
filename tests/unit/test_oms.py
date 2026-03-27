"""
Tests for src/execution/oms.py — Order Management System.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.core.models import (
    Instrument,
    Order,
    OrderStatus,
    Portfolio,
    Position,
    Side,
    Trade,
)
from src.execution.oms import OrderManager, apply_trades


# ─── Fixtures ─────────────────────────────────────────────


@pytest.fixture
def oms() -> OrderManager:
    return OrderManager()


@pytest.fixture
def instrument() -> Instrument:
    return Instrument(symbol="2330.TW")


@pytest.fixture
def make_order(instrument: Instrument):
    """Factory to create orders with sensible defaults."""
    def _make(
        side: Side = Side.BUY,
        quantity: Decimal = Decimal("100"),
        price: Decimal = Decimal("500"),
        order_id: str | None = None,
    ) -> Order:
        order = Order(
            instrument=instrument,
            side=side,
            quantity=quantity,
            price=price,
        )
        if order_id:
            order.id = order_id
        return order
    return _make


@pytest.fixture
def make_trade():
    """Factory to create Trade objects."""
    def _make(
        symbol: str = "2330.TW",
        side: Side = Side.BUY,
        quantity: Decimal = Decimal("100"),
        price: Decimal = Decimal("500"),
        commission: Decimal = Decimal("71"),
    ) -> Trade:
        return Trade(
            timestamp=datetime.now(timezone.utc),
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            commission=commission,
            slippage_bps=Decimal("0"),
            order_id="ord-001",
        )
    return _make


# ─── OrderManager: submit ─────────────────────────────────


class TestSubmit:
    def test_submit_sets_status_to_submitted(self, oms, make_order):
        order = make_order()
        assert order.status == OrderStatus.PENDING
        oms.submit(order)
        assert order.status == OrderStatus.SUBMITTED

    def test_submit_buy_order(self, oms, make_order):
        order = make_order(side=Side.BUY)
        oms.submit(order)
        retrieved = oms.get_order(order.id)
        assert retrieved is order
        assert retrieved.side == Side.BUY

    def test_submit_sell_order(self, oms, make_order):
        order = make_order(side=Side.SELL)
        oms.submit(order)
        retrieved = oms.get_order(order.id)
        assert retrieved.side == Side.SELL

    def test_submit_multiple_orders(self, oms, make_order):
        o1 = make_order(order_id="a1")
        o2 = make_order(order_id="a2")
        o3 = make_order(order_id="a3")
        oms.submit(o1)
        oms.submit(o2)
        oms.submit(o3)
        assert len(oms.get_all_orders()) == 3

    def test_submit_overwrites_same_id(self, oms, make_order):
        """Submitting with duplicate ID replaces the old order."""
        o1 = make_order(order_id="dup", price=Decimal("500"))
        o2 = make_order(order_id="dup", price=Decimal("600"))
        oms.submit(o1)
        oms.submit(o2)
        assert len(oms.get_all_orders()) == 1
        assert oms.get_order("dup").price == Decimal("600")


# ─── OrderManager: get_order ──────────────────────────────


class TestGetOrder:
    def test_get_existing_order(self, oms, make_order):
        order = make_order(order_id="x1")
        oms.submit(order)
        assert oms.get_order("x1") is order

    def test_get_nonexistent_order_returns_none(self, oms):
        assert oms.get_order("nonexistent") is None


# ─── OrderManager: open orders ────────────────────────────


class TestGetOpenOrders:
    def test_submitted_orders_are_open(self, oms, make_order):
        o = make_order()
        oms.submit(o)
        assert o in oms.get_open_orders()

    def test_filled_orders_not_open(self, oms, make_order):
        o = make_order()
        oms.submit(o)
        o.status = OrderStatus.FILLED
        assert o not in oms.get_open_orders()

    def test_cancelled_orders_not_open(self, oms, make_order):
        o = make_order()
        oms.submit(o)
        o.status = OrderStatus.CANCELLED
        assert o not in oms.get_open_orders()

    def test_rejected_orders_not_open(self, oms, make_order):
        o = make_order()
        oms.submit(o)
        o.status = OrderStatus.REJECTED
        assert o not in oms.get_open_orders()

    def test_partial_orders_are_open(self, oms, make_order):
        o = make_order()
        oms.submit(o)
        o.status = OrderStatus.PARTIAL
        assert o in oms.get_open_orders()


# ─── OrderManager: cancel_all ─────────────────────────────


class TestCancelAll:
    def test_cancel_all_returns_count(self, oms, make_order):
        oms.submit(make_order(order_id="c1"))
        oms.submit(make_order(order_id="c2"))
        assert oms.cancel_all() == 2

    def test_cancel_all_sets_status(self, oms, make_order):
        o = make_order()
        oms.submit(o)
        oms.cancel_all()
        assert o.status == OrderStatus.CANCELLED

    def test_cancel_all_skips_terminal(self, oms, make_order):
        o1 = make_order(order_id="t1")
        o2 = make_order(order_id="t2")
        oms.submit(o1)
        oms.submit(o2)
        o1.status = OrderStatus.FILLED
        count = oms.cancel_all()
        assert count == 1
        assert o1.status == OrderStatus.FILLED
        assert o2.status == OrderStatus.CANCELLED

    def test_cancel_all_empty(self, oms):
        assert oms.cancel_all() == 0

    def test_cancel_all_all_terminal(self, oms, make_order):
        o = make_order()
        oms.submit(o)
        o.status = OrderStatus.REJECTED
        assert oms.cancel_all() == 0


# ─── OrderManager: on_fill / get_trades ───────────────────


class TestOnFill:
    def test_on_fill_records_trade(self, oms, make_trade):
        t = make_trade()
        oms.on_fill(t)
        assert oms.get_trades() == [t]

    def test_multiple_fills(self, oms, make_trade):
        t1 = make_trade(symbol="2330.TW")
        t2 = make_trade(symbol="2317.TW")
        oms.on_fill(t1)
        oms.on_fill(t2)
        assert len(oms.get_trades()) == 2

    def test_get_trades_returns_copy(self, oms, make_trade):
        oms.on_fill(make_trade())
        trades = oms.get_trades()
        trades.clear()
        assert len(oms.get_trades()) == 1


# ─── apply_trades ─────────────────────────────────────────


class TestApplyTrades:
    """Test apply_trades with mocked config to avoid persistence side effects."""

    @pytest.fixture(autouse=True)
    def _mock_config(self):
        """Mock get_config so apply_trades doesn't try to persist."""
        mock_cfg = type("Cfg", (), {"mode": "backtest"})()
        with patch("src.core.config.get_config", return_value=mock_cfg):
            yield

    def test_buy_reduces_cash(self, make_trade):
        portfolio = Portfolio(cash=Decimal("1000000"))
        trade = make_trade(
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("500"),
            commission=Decimal("71"),
        )
        apply_trades(portfolio, [trade])
        # cash = 1000000 - (100*500) - 71 = 949929
        assert portfolio.cash == Decimal("949929")

    def test_sell_increases_cash(self, make_trade):
        portfolio = Portfolio(
            cash=Decimal("500000"),
            positions={
                "2330.TW": Position(
                    instrument=Instrument(symbol="2330.TW"),
                    quantity=Decimal("200"),
                    avg_cost=Decimal("450"),
                )
            },
        )
        trade = make_trade(
            side=Side.SELL,
            quantity=Decimal("100"),
            price=Decimal("500"),
            commission=Decimal("150"),
        )
        apply_trades(portfolio, [trade])
        # cash = 500000 + (100*500) - 150 = 549850
        assert portfolio.cash == Decimal("549850")

    def test_buy_creates_new_position(self, make_trade):
        portfolio = Portfolio(cash=Decimal("1000000"))
        trade = make_trade(side=Side.BUY, quantity=Decimal("50"), price=Decimal("600"))
        apply_trades(portfolio, [trade])
        assert "2330.TW" in portfolio.positions
        pos = portfolio.positions["2330.TW"]
        assert pos.quantity == Decimal("50")
        assert pos.avg_cost == Decimal("600")

    def test_buy_updates_existing_position(self, make_trade):
        portfolio = Portfolio(
            cash=Decimal("1000000"),
            positions={
                "2330.TW": Position(
                    instrument=Instrument(symbol="2330.TW"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("500"),
                    market_price=Decimal("500"),
                )
            },
        )
        trade = make_trade(side=Side.BUY, quantity=Decimal("100"), price=Decimal("600"))
        apply_trades(portfolio, [trade])
        pos = portfolio.positions["2330.TW"]
        assert pos.quantity == Decimal("200")
        # avg_cost = (100*500 + 100*600) / 200 = 550
        assert pos.avg_cost == Decimal("550")

    def test_sell_removes_position_when_fully_sold(self, make_trade):
        portfolio = Portfolio(
            cash=Decimal("500000"),
            positions={
                "2330.TW": Position(
                    instrument=Instrument(symbol="2330.TW"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("500"),
                )
            },
        )
        trade = make_trade(side=Side.SELL, quantity=Decimal("100"), price=Decimal("550"))
        apply_trades(portfolio, [trade])
        assert "2330.TW" not in portfolio.positions

    def test_sell_partial_position(self, make_trade):
        portfolio = Portfolio(
            cash=Decimal("500000"),
            positions={
                "2330.TW": Position(
                    instrument=Instrument(symbol="2330.TW"),
                    quantity=Decimal("200"),
                    avg_cost=Decimal("500"),
                )
            },
        )
        trade = make_trade(side=Side.SELL, quantity=Decimal("50"), price=Decimal("550"))
        apply_trades(portfolio, [trade])
        pos = portfolio.positions["2330.TW"]
        assert pos.quantity == Decimal("150")

    def test_sell_more_than_position_caps(self, make_trade):
        """Selling more than held caps to position size."""
        portfolio = Portfolio(
            cash=Decimal("500000"),
            positions={
                "2330.TW": Position(
                    instrument=Instrument(symbol="2330.TW"),
                    quantity=Decimal("50"),
                    avg_cost=Decimal("500"),
                )
            },
        )
        trade = make_trade(side=Side.SELL, quantity=Decimal("100"), price=Decimal("500"))
        apply_trades(portfolio, [trade])
        # Position should be removed (qty capped to 50, then 50-50=0)
        assert "2330.TW" not in portfolio.positions

    def test_sell_nonexistent_position_ignored(self, make_trade):
        """Selling a symbol with no position does not create one."""
        portfolio = Portfolio(cash=Decimal("500000"))
        trade = make_trade(symbol="9999.TW", side=Side.SELL, quantity=Decimal("10"), price=Decimal("100"))
        apply_trades(portfolio, [trade])
        assert "9999.TW" not in portfolio.positions

    def test_as_of_updated(self, make_trade):
        portfolio = Portfolio(cash=Decimal("1000000"))
        trade = make_trade()
        apply_trades(portfolio, [trade])
        assert portfolio.as_of == trade.timestamp

    def test_multiple_trades(self, make_trade):
        portfolio = Portfolio(cash=Decimal("1000000"))
        t1 = make_trade(symbol="2330.TW", side=Side.BUY, quantity=Decimal("10"), price=Decimal("500"), commission=Decimal("0"))
        t2 = make_trade(symbol="2317.TW", side=Side.BUY, quantity=Decimal("20"), price=Decimal("100"), commission=Decimal("0"))
        apply_trades(portfolio, [t1, t2])
        # cash = 1000000 - 5000 - 2000 = 993000
        assert portfolio.cash == Decimal("993000")
        assert "2330.TW" in portfolio.positions
        assert "2317.TW" in portfolio.positions

    def test_empty_trades_list(self):
        portfolio = Portfolio(cash=Decimal("1000000"))
        original_as_of = portfolio.as_of
        with patch("src.core.config.get_config", return_value=type("C", (), {"mode": "backtest"})()):
            apply_trades(portfolio, [])
        assert portfolio.cash == Decimal("1000000")
        assert portfolio.as_of == original_as_of

    def test_market_price_updated(self, make_trade):
        portfolio = Portfolio(
            cash=Decimal("1000000"),
            positions={
                "2330.TW": Position(
                    instrument=Instrument(symbol="2330.TW"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("500"),
                    market_price=Decimal("500"),
                )
            },
        )
        trade = make_trade(side=Side.BUY, quantity=Decimal("10"), price=Decimal("550"))
        apply_trades(portfolio, [trade])
        assert portfolio.positions["2330.TW"].market_price == Decimal("550")
