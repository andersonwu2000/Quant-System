"""領域模型測試。"""

from decimal import Decimal

import pytest

from src.domain.models import (
    Instrument,
    Order,
    OrderStatus,
    Portfolio,
    Position,
    RiskDecision,
    Side,
)


class TestPosition:
    def test_market_value(self):
        pos = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("500"),
            market_price=Decimal("600"),
        )
        assert pos.market_value == Decimal("600000")

    def test_unrealized_pnl(self):
        pos = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("500"),
            market_price=Decimal("600"),
        )
        assert pos.unrealized_pnl == Decimal("100000")

    def test_short_position(self):
        pos = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("-500"),
            avg_cost=Decimal("600"),
            market_price=Decimal("550"),
        )
        # 空頭：(550-600) * (-500) = 25000 (盈利)
        assert pos.unrealized_pnl == Decimal("25000")


class TestPortfolio:
    def test_nav(self):
        portfolio = Portfolio(
            positions={
                "A": Position(
                    instrument=Instrument(symbol="A"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("10"),
                    market_price=Decimal("12"),
                ),
            },
            cash=Decimal("5000"),
        )
        # NAV = 5000 + 100*12 = 6200
        assert portfolio.nav == Decimal("6200")

    def test_gross_exposure(self):
        portfolio = Portfolio(
            positions={
                "A": Position(
                    instrument=Instrument(symbol="A"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("10"),
                    market_price=Decimal("10"),
                ),
                "B": Position(
                    instrument=Instrument(symbol="B"),
                    quantity=Decimal("-50"),
                    avg_cost=Decimal("20"),
                    market_price=Decimal("20"),
                ),
            },
            cash=Decimal("5000"),
        )
        # gross = |100*10| + |-50*20| = 1000 + 1000 = 2000
        assert portfolio.gross_exposure == Decimal("2000")

    def test_position_weight(self):
        portfolio = Portfolio(
            positions={
                "A": Position(
                    instrument=Instrument(symbol="A"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("10"),
                    market_price=Decimal("10"),
                ),
            },
            cash=Decimal("9000"),
        )
        # weight = 1000 / 10000 = 0.1
        assert portfolio.get_position_weight("A") == Decimal("0.1")
        assert portfolio.get_position_weight("B") == Decimal("0")

    def test_update_market_prices(self):
        portfolio = Portfolio(
            positions={
                "A": Position(
                    instrument=Instrument(symbol="A"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("10"),
                    market_price=Decimal("10"),
                ),
            },
            cash=Decimal("5000"),
        )
        portfolio.update_market_prices({"A": Decimal("15")})
        assert portfolio.positions["A"].market_price == Decimal("15")
        assert portfolio.nav == Decimal("6500")


class TestOrder:
    def test_is_terminal(self):
        order = Order(status=OrderStatus.FILLED)
        assert order.is_terminal is True

        order2 = Order(status=OrderStatus.SUBMITTED)
        assert order2.is_terminal is False

    def test_cancelled_is_terminal(self):
        order = Order(status=OrderStatus.CANCELLED)
        assert order.is_terminal is True


class TestRiskDecision:
    def test_approve(self):
        d = RiskDecision.APPROVE()
        assert d.approved is True

    def test_reject(self):
        d = RiskDecision.REJECT("too risky")
        assert d.approved is False
        assert d.reason == "too risky"

    def test_modify(self):
        d = RiskDecision.MODIFY(Decimal("50"), "reduced")
        assert d.approved is True
        assert d.modified_qty == Decimal("50")
