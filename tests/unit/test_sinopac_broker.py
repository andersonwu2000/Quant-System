"""Tests for SinopacBroker — 使用 mock SDK 的完整單元測試。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.core.models import Instrument, Order, OrderStatus, OrderType, Side
from src.execution.broker.sinopac import (
    SinopacBroker,
    SinopacConfig,
    SinopacOrderType,
)


# ── Mock Helpers ──────────────────────────────────────────


def _make_mock_api(simulation: bool = True) -> MagicMock:
    """建立 mock Shioaji API。"""
    api = MagicMock()
    api.simulation = simulation

    # Contracts
    contract = MagicMock()
    contract.code = "2330"
    api.Contracts.Stocks.__getitem__ = MagicMock(return_value=contract)
    api.Contracts.Stocks.get = MagicMock(return_value=contract)
    api.Contracts.Futures.get = MagicMock(return_value=None)

    # Order result
    trade = MagicMock()
    trade.order.id = "ORD001"
    api.place_order.return_value = trade

    # Account
    margin = MagicMock()
    margin.acc_balance = 1000000
    margin.available_margin = 800000
    api.account_balance.return_value = margin

    # Positions
    pos = MagicMock()
    pos.code = "2330"
    pos.quantity = 5000  # 5000 shares
    pos.price = 590.0
    pos.pnl = 1000.0
    pos.last_price = 600.0
    api.list_positions.return_value = [pos]
    api.stock_account = MagicMock()

    return api


def _make_order(symbol: str = "2330", side: Side = Side.BUY, qty: int = 1000) -> Order:
    return Order(
        instrument=Instrument(symbol=symbol),
        side=side,
        order_type=OrderType.LIMIT,
        quantity=Decimal(str(qty)),
        price=Decimal("590"),
        strategy_id="test",
    )


# ── Tests ─────────────────────────────────────────────────


class TestSinopacBrokerInit:
    def test_default_config(self) -> None:
        broker = SinopacBroker()
        assert broker.simulation is True
        assert not broker.is_connected()

    def test_custom_config(self) -> None:
        config = SinopacConfig(simulation=False, default_order_type=SinopacOrderType.IOC)
        broker = SinopacBroker(config)
        assert broker.simulation is False


class TestSinopacBrokerConnect:
    def test_connect_requires_shioaji(self) -> None:
        broker = SinopacBroker()
        # Without shioaji installed, connect should raise ImportError
        with patch.dict("sys.modules", {"shioaji": None}):
            with pytest.raises(ImportError, match="shioaji is not installed"):
                broker.connect("my_api_key", "my_secret_key")

    def test_connect_success(self) -> None:
        broker = SinopacBroker()
        mock_api = _make_mock_api()

        mock_sj = MagicMock()
        mock_sj.Shioaji.return_value = mock_api

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            result = broker.connect("my_api_key", "my_secret_key")

        assert result is True
        assert broker.is_connected()

    def test_connect_failure(self) -> None:
        broker = SinopacBroker()
        mock_sj = MagicMock()
        mock_sj.Shioaji.return_value.login.side_effect = Exception("Login failed")

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            result = broker.connect("bad_key", "bad_secret")

        assert result is False
        assert not broker.is_connected()

    def test_disconnect(self) -> None:
        broker = SinopacBroker()
        broker._connected = True
        broker._api = MagicMock()
        broker.disconnect()
        assert not broker.is_connected()
        assert broker._api is None


class TestSinopacBrokerSubmitOrder:
    def _setup_connected_broker(self) -> SinopacBroker:
        broker = SinopacBroker()
        broker._api = _make_mock_api()
        broker._connected = True
        return broker

    def test_submit_buy_order(self) -> None:
        broker = self._setup_connected_broker()
        order = _make_order()

        mock_sj = MagicMock()
        mock_sj.constant.Action.Buy = "Buy"
        mock_sj.constant.StockPriceType.LMT = "LMT"
        mock_sj.constant.OrderType.ROD = "ROD"

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            broker_id = broker.submit_order(order)

        assert broker_id == "ORD001"
        assert order.status == OrderStatus.SUBMITTED
        broker._api.place_order.assert_called_once()

    def test_submit_sell_order(self) -> None:
        broker = self._setup_connected_broker()
        order = _make_order(side=Side.SELL)

        mock_sj = MagicMock()
        mock_sj.constant.Action.Sell = "Sell"
        mock_sj.constant.StockPriceType.LMT = "LMT"
        mock_sj.constant.OrderType.ROD = "ROD"

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            broker_id = broker.submit_order(order)

        assert broker_id == "ORD001"

    def test_submit_market_order(self) -> None:
        broker = self._setup_connected_broker()
        order = _make_order()
        order.order_type = OrderType.MARKET
        order.price = None

        mock_sj = MagicMock()
        mock_sj.constant.Action.Buy = "Buy"
        mock_sj.constant.StockPriceType.MKT = "MKT"
        mock_sj.constant.OrderType.ROD = "ROD"

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            broker_id = broker.submit_order(order)

        assert broker_id == "ORD001"

    def test_submit_contract_not_found(self) -> None:
        broker = self._setup_connected_broker()
        broker._api.Contracts.Stocks.get.return_value = None
        broker._api.Contracts.Futures.get.return_value = None
        order = _make_order(symbol="INVALID")

        mock_sj = MagicMock()
        mock_sj.constant.Action.Buy = "Buy"
        mock_sj.constant.StockPriceType.LMT = "LMT"
        mock_sj.constant.OrderType.ROD = "ROD"

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            broker_id = broker.submit_order(order)
        assert broker_id == ""
        assert order.status == OrderStatus.REJECTED

    def test_submit_api_error(self) -> None:
        broker = self._setup_connected_broker()
        broker._api.place_order.side_effect = Exception("API Error")
        order = _make_order()

        mock_sj = MagicMock()
        mock_sj.constant.Action.Buy = "Buy"
        mock_sj.constant.StockPriceType.LMT = "LMT"
        mock_sj.constant.OrderType.ROD = "ROD"

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            broker_id = broker.submit_order(order)

        assert broker_id == ""
        assert order.status == OrderStatus.REJECTED

    def test_submit_not_connected_raises(self) -> None:
        broker = SinopacBroker()
        order = _make_order()
        with pytest.raises(ConnectionError):
            broker.submit_order(order)


class TestSinopacBrokerCancel:
    def test_cancel_existing_order(self) -> None:
        broker = SinopacBroker()
        broker._api = _make_mock_api()
        broker._connected = True
        trade = MagicMock()
        broker._trades["ORD001"] = trade

        result = broker.cancel_order("ORD001")
        assert result is True
        broker._api.cancel_order.assert_called_once_with(trade)

    def test_cancel_unknown_order(self) -> None:
        broker = SinopacBroker()
        broker._api = _make_mock_api()
        broker._connected = True

        result = broker.cancel_order("UNKNOWN")
        assert result is False


class TestSinopacBrokerQuery:
    def test_query_positions(self) -> None:
        broker = SinopacBroker()
        broker._api = _make_mock_api()
        broker._connected = True

        positions = broker.query_positions()
        assert "2330" in positions
        assert positions["2330"]["quantity"] == 5000  # 5 張 × 1000

    def test_query_account(self) -> None:
        broker = SinopacBroker()
        broker._api = _make_mock_api()
        broker._connected = True

        account = broker.query_account()
        assert account["balance"] == 1000000
        assert account["simulation"] is True


class TestSinopacBrokerCallback:
    def test_fill_callback(self) -> None:
        broker = SinopacBroker()
        order = _make_order(qty=1000)
        order.status = OrderStatus.SUBMITTED
        broker._order_map["ORD001"] = order

        callback_called = []
        broker.register_callback(lambda o: callback_called.append(o))

        # StockDeal callback: stat.name == "StockDeal", msg has code/price/quantity
        stat = MagicMock()
        stat.name = "StockDeal"
        broker._on_order_callback(
            stat,
            {"code": "2330", "quantity": 1000, "price": 595.0},
        )

        assert order.status == OrderStatus.FILLED
        assert order.filled_avg_price == Decimal("595.0")
        assert len(callback_called) == 1

    def test_cancel_callback(self) -> None:
        broker = SinopacBroker()
        order = _make_order()
        order.status = OrderStatus.SUBMITTED
        broker._order_map["ORD001"] = order

        stat = MagicMock()
        stat.name = "StockOrder"
        broker._on_order_callback(
            stat,
            {"order": {"id": "ORD001"}, "operation": {"op_code": "Cancel"}},
        )
        assert order.status == OrderStatus.CANCELLED

    def test_reject_callback(self) -> None:
        broker = SinopacBroker()
        order = _make_order()
        order.status = OrderStatus.SUBMITTED
        broker._order_map["ORD001"] = order

        stat = MagicMock()
        stat.name = "StockOrder"
        broker._on_order_callback(
            stat,
            {
                "order": {"id": "ORD001"},
                "operation": {"op_code": "Reject", "op_msg": "Insufficient balance"},
            },
        )
        assert order.status == OrderStatus.REJECTED
        assert "Insufficient" in order.reject_reason

    def test_unknown_order_callback(self) -> None:
        broker = SinopacBroker()
        stat = MagicMock()
        stat.name = "StockDeal"
        # Should not raise — no matching order
        broker._on_order_callback(stat, {"code": "UNKNOWN", "quantity": 1, "price": 100})


class TestSinopacBrokerNonBlocking:
    def _setup_connected_broker(self, non_blocking: bool = True) -> SinopacBroker:
        config = SinopacConfig(non_blocking=non_blocking)
        broker = SinopacBroker(config)
        broker._api = _make_mock_api()
        broker._connected = True
        return broker

    def test_non_blocking_passes_timeout_zero(self) -> None:
        broker = self._setup_connected_broker(non_blocking=True)
        order = _make_order()

        mock_sj = MagicMock()
        mock_sj.constant.Action.Buy = "Buy"
        mock_sj.constant.StockPriceType.LMT = "LMT"
        mock_sj.constant.OrderType.ROD = "ROD"

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            broker.submit_order(order)

        # Verify timeout=0 was passed
        broker._api.place_order.assert_called_once()
        _, kwargs = broker._api.place_order.call_args
        assert kwargs.get("timeout") == 0

    def test_blocking_does_not_pass_timeout(self) -> None:
        broker = self._setup_connected_broker(non_blocking=False)
        order = _make_order()

        mock_sj = MagicMock()
        mock_sj.constant.Action.Buy = "Buy"
        mock_sj.constant.StockPriceType.LMT = "LMT"
        mock_sj.constant.OrderType.ROD = "ROD"

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            broker.submit_order(order)

        broker._api.place_order.assert_called_once()
        _, kwargs = broker._api.place_order.call_args
        assert "timeout" not in kwargs


class TestSinopacBrokerTradingLimits:
    def _setup_connected_broker(self) -> SinopacBroker:
        broker = SinopacBroker()
        broker._api = _make_mock_api()
        broker._connected = True
        return broker

    def test_query_trading_limits(self) -> None:
        broker = self._setup_connected_broker()
        limits_mock = MagicMock()
        limits_mock.trading_limit = 5000000
        limits_mock.trading_used = 1000000
        limits_mock.trading_available = 4000000
        limits_mock.margin_limit = 3000000
        limits_mock.margin_used = 500000
        limits_mock.margin_available = 2500000
        limits_mock.short_limit = 1000000
        limits_mock.short_used = 0
        limits_mock.short_available = 1000000
        broker._api.trading_limits.return_value = limits_mock

        result = broker.query_trading_limits()
        assert result["trading_limit"] == 5000000
        assert result["trading_used"] == 1000000
        assert result["trading_available"] == 4000000
        assert result["margin_limit"] == 3000000
        assert result["margin_available"] == 2500000
        assert result["short_available"] == 1000000
        broker._api.trading_limits.assert_called_once_with(broker._api.stock_account)

    def test_query_trading_limits_error(self) -> None:
        broker = self._setup_connected_broker()
        broker._api.trading_limits.side_effect = Exception("API Error")
        result = broker.query_trading_limits()
        assert result == {}

    def test_query_trading_limits_not_connected(self) -> None:
        broker = SinopacBroker()
        with pytest.raises(ConnectionError):
            broker.query_trading_limits()

    def test_query_settlements(self) -> None:
        broker = self._setup_connected_broker()
        s1 = MagicMock()
        s1.date = "2026-03-26"
        s1.amount = -50000
        s2 = MagicMock()
        s2.date = "2026-03-27"
        s2.amount = 120000
        broker._api.settlements.return_value = [s1, s2]

        result = broker.query_settlements()
        assert len(result) == 2
        assert result[0]["date"] == "2026-03-26"
        assert result[0]["amount"] == -50000
        assert result[1]["date"] == "2026-03-27"
        assert result[1]["amount"] == 120000
        broker._api.settlements.assert_called_once_with(broker._api.stock_account)

    def test_query_settlements_error(self) -> None:
        broker = self._setup_connected_broker()
        broker._api.settlements.side_effect = Exception("API Error")
        result = broker.query_settlements()
        assert result == []

    def test_query_settlements_not_connected(self) -> None:
        broker = SinopacBroker()
        with pytest.raises(ConnectionError):
            broker.query_settlements()

    def test_check_dispositions(self) -> None:
        broker = self._setup_connected_broker()
        punish_mock = MagicMock()
        punish_mock.code = ["2330", "2317", "3008"]
        broker._api.punish.return_value = punish_mock

        result = broker.check_dispositions()
        assert result == {"2330", "2317", "3008"}
        broker._api.punish.assert_called_once()

    def test_check_dispositions_empty(self) -> None:
        broker = self._setup_connected_broker()
        punish_mock = MagicMock()
        punish_mock.code = []
        broker._api.punish.return_value = punish_mock

        result = broker.check_dispositions()
        assert result == set()

    def test_check_dispositions_error(self) -> None:
        broker = self._setup_connected_broker()
        broker._api.punish.side_effect = Exception("API Error")
        result = broker.check_dispositions()
        assert result == set()

    def test_check_dispositions_not_connected(self) -> None:
        broker = SinopacBroker()
        with pytest.raises(ConnectionError):
            broker.check_dispositions()


class TestSinopacBrokerUpdateOrder:
    def test_update_price(self) -> None:
        broker = SinopacBroker()
        broker._api = _make_mock_api()
        broker._connected = True
        trade = MagicMock()
        trade.order.price = 590
        trade.order.quantity = 1
        broker._trades["ORD001"] = trade

        result = broker.update_order("ORD001", price=Decimal("595"))
        assert result is True
        broker._api.update_order.assert_called_once()

    def test_update_unknown_order(self) -> None:
        broker = SinopacBroker()
        broker._api = _make_mock_api()
        broker._connected = True

        result = broker.update_order("UNKNOWN", price=Decimal("595"))
        assert result is False
