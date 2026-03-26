"""Tests for SinopacQuoteManager — 即時行情管理。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.execution.quote.sinopac import (
    BidAskData,
    SinopacQuoteManager,
    TickData,
)


class TestTickData:
    def test_creation(self) -> None:
        td = TickData(
            symbol="2330",
            price=Decimal("590"),
            volume=100,
            bid_price=Decimal("589"),
            ask_price=Decimal("591"),
            timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc),
            total_volume=50000,
        )
        assert td.symbol == "2330"
        assert td.price == Decimal("590")


class TestBidAskData:
    def test_creation(self) -> None:
        bd = BidAskData(
            symbol="2330",
            bid_prices=(Decimal("589"), Decimal("588"), Decimal("587"), Decimal("586"), Decimal("585")),
            bid_volumes=(100, 200, 150, 300, 250),
            ask_prices=(Decimal("590"), Decimal("591"), Decimal("592"), Decimal("593"), Decimal("594")),
            ask_volumes=(50, 80, 120, 200, 100),
            timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc),
        )
        assert len(bd.bid_prices) == 5
        assert len(bd.ask_volumes) == 5


class TestQuoteManager:
    def test_no_api_subscribe_fails(self) -> None:
        mgr = SinopacQuoteManager()
        result = mgr.subscribe("2330")
        assert result is False

    def test_subscribe_with_mock_api(self) -> None:
        mock_api = MagicMock()
        mock_contract = MagicMock()
        mock_api.Contracts.Stocks.get.return_value = mock_contract

        mock_sj = MagicMock()
        mock_sj.constant.QuoteType.Tick = "Tick"

        mgr = SinopacQuoteManager(api=mock_api)

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            result = mgr.subscribe("2330", "tick")

        assert result is True
        assert "2330" in mgr.subscribed_symbols

    def test_subscribe_contract_not_found(self) -> None:
        mock_api = MagicMock()
        mock_api.Contracts.Stocks.get.return_value = None

        mock_sj = MagicMock()

        mgr = SinopacQuoteManager(api=mock_api)

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            result = mgr.subscribe("INVALID")

        assert result is False

    def test_unsubscribe(self) -> None:
        mock_api = MagicMock()
        mock_contract = MagicMock()
        mock_api.Contracts.Stocks.get.return_value = mock_contract

        mock_sj = MagicMock()
        mock_sj.constant.QuoteType.Tick = "Tick"

        mgr = SinopacQuoteManager(api=mock_api)

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            mgr.subscribe("2330", "tick")
            result = mgr.unsubscribe("2330", "tick")

        assert result is True
        assert "2330" not in mgr.subscribed_symbols

    def test_tick_callback(self) -> None:
        mgr = SinopacQuoteManager()
        received: list[TickData] = []
        mgr.on_tick(lambda td: received.append(td))

        # Simulate SDK tick callback
        mock_tick = MagicMock()
        mock_tick.code = "2330"
        mock_tick.close = 590.0
        mock_tick.volume = 100
        mock_tick.bid_price = 589.0
        mock_tick.ask_price = 591.0
        mock_tick.datetime = datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc)
        mock_tick.total_volume = 50000

        mgr._on_tick_v1(MagicMock(), mock_tick)

        assert len(received) == 1
        assert received[0].symbol == "2330"
        assert received[0].price == Decimal("590.0")

    def test_bidask_callback(self) -> None:
        mgr = SinopacQuoteManager()
        received: list[BidAskData] = []
        mgr.on_bidask(lambda bd: received.append(bd))

        mock_bidask = MagicMock()
        mock_bidask.code = "2330"
        mock_bidask.datetime = datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc)
        # Shioaji SDK: bid_price/bid_volume/ask_price/ask_volume are lists
        mock_bidask.bid_price = [589, 588, 587, 586, 585]
        mock_bidask.bid_volume = [100, 200, 150, 300, 250]
        mock_bidask.ask_price = [590, 591, 592, 593, 594]
        mock_bidask.ask_volume = [50, 80, 120, 200, 100]

        mgr._on_bidask_v1(MagicMock(), mock_bidask)

        assert len(received) == 1
        assert received[0].symbol == "2330"
        assert received[0].bid_prices[0] == Decimal("589")
        assert received[0].ask_prices[0] == Decimal("590")

    def test_latest_tick(self) -> None:
        mgr = SinopacQuoteManager()
        mock_tick = MagicMock()
        mock_tick.code = "2330"
        mock_tick.close = 590.0
        mock_tick.volume = 100
        mock_tick.bid_price = 589.0
        mock_tick.ask_price = 591.0
        mock_tick.datetime = datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc)
        mock_tick.total_volume = 50000

        mgr._on_tick_v1(MagicMock(), mock_tick)

        latest = mgr.get_latest_tick("2330")
        assert latest is not None
        assert latest.price == Decimal("590.0")

        assert mgr.get_latest_tick("9999") is None

    def test_to_ws_payload(self) -> None:
        mgr = SinopacQuoteManager()
        td = TickData(
            symbol="2330", price=Decimal("590"), volume=100,
            bid_price=Decimal("589"), ask_price=Decimal("591"),
            timestamp=datetime(2026, 3, 25, 10, 0, tzinfo=timezone.utc),
        )
        payload = mgr.to_ws_payload(td)
        assert payload["symbol"] == "2330"
        assert payload["price"] == 590.0
        assert "timestamp" in payload

    def test_unsubscribe_all(self) -> None:
        mock_api = MagicMock()
        mock_contract = MagicMock()
        mock_api.Contracts.Stocks.get.return_value = mock_contract

        mock_sj = MagicMock()
        mock_sj.constant.QuoteType.Tick = "Tick"
        mock_sj.constant.QuoteType.BidAsk = "BidAsk"

        mgr = SinopacQuoteManager(api=mock_api)

        with patch.dict("sys.modules", {"shioaji": mock_sj}):
            mgr.subscribe("2330", "tick")
            mgr.subscribe("2317", "tick")
            count = mgr.unsubscribe_all()

        assert count == 2
        assert len(mgr.subscribed_symbols) == 0
