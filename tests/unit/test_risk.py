"""風控規則測試。"""

from decimal import Decimal


from src.core.models import Instrument, Order, Portfolio, Position, Side
from src.risk.engine import RiskEngine
from src.risk.rules import (
    MarketState,
    fat_finger_check,
    max_order_notional,
    max_position_weight,
)


def _make_portfolio(cash: float = 1_000_000, positions: dict | None = None) -> Portfolio:
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


def _make_order(symbol: str = "TEST", qty: float = 100, price: float = 100) -> Order:
    return Order(
        instrument=Instrument(symbol=symbol),
        side=Side.BUY,
        quantity=Decimal(str(qty)),
        price=Decimal(str(price)),
    )


class TestMaxPositionWeight:
    def test_approve_within_limit(self):
        rule = max_position_weight(0.10)
        portfolio = _make_portfolio(1_000_000)
        order = _make_order("A", qty=500, price=100)  # 50K / 1M = 5%
        market = MarketState(prices={}, daily_volumes={})
        result = rule(order, portfolio, market)
        assert result.approved

    def test_reject_over_limit(self):
        rule = max_position_weight(0.05)
        portfolio = _make_portfolio(1_000_000)
        order = _make_order("A", qty=1000, price=100)  # 100K / 1M = 10%
        market = MarketState(prices={}, daily_volumes={})
        result = rule(order, portfolio, market)
        assert not result.approved
        assert "權重" in result.reason


class TestMaxOrderNotional:
    def test_approve(self):
        rule = max_order_notional(0.05)
        portfolio = _make_portfolio(1_000_000)
        order = _make_order("A", qty=100, price=100)  # 10K / 1M = 1%
        market = MarketState(prices={}, daily_volumes={})
        result = rule(order, portfolio, market)
        assert result.approved

    def test_reject(self):
        rule = max_order_notional(0.01)
        portfolio = _make_portfolio(1_000_000)
        order = _make_order("A", qty=500, price=100)  # 50K / 1M = 5%
        market = MarketState(prices={}, daily_volumes={})
        result = rule(order, portfolio, market)
        assert not result.approved


class TestFatFingerCheck:
    def test_approve_normal_price(self):
        rule = fat_finger_check(0.05)
        order = _make_order("A", qty=100, price=100)
        portfolio = _make_portfolio()
        market = MarketState(prices={"A": Decimal("100")}, daily_volumes={})
        result = rule(order, portfolio, market)
        assert result.approved

    def test_reject_wild_price(self):
        rule = fat_finger_check(0.05)
        order = _make_order("A", qty=100, price=200)  # 100% 偏離
        portfolio = _make_portfolio()
        market = MarketState(prices={"A": Decimal("100")}, daily_volumes={})
        result = rule(order, portfolio, market)
        assert not result.approved

    def test_market_order_passes(self):
        rule = fat_finger_check(0.05)
        order = _make_order("A", qty=100, price=100)
        order.price = None  # 市價單
        portfolio = _make_portfolio()
        market = MarketState(prices={"A": Decimal("100")}, daily_volumes={})
        result = rule(order, portfolio, market)
        assert result.approved


class TestRiskEngine:
    def test_all_rules_pass(self):
        engine = RiskEngine(rules=[
            max_position_weight(0.10),
            max_order_notional(0.05),
        ])
        portfolio = _make_portfolio(1_000_000)
        order = _make_order("A", qty=100, price=100)
        result = engine.check_order(order, portfolio)
        assert result.approved

    def test_first_reject_stops(self):
        engine = RiskEngine(rules=[
            max_position_weight(0.01),  # 會擋
            max_order_notional(0.10),   # 不會到這
        ])
        portfolio = _make_portfolio(1_000_000)
        order = _make_order("A", qty=500, price=100)
        result = engine.check_order(order, portfolio)
        assert not result.approved

    def test_check_orders_filters(self):
        engine = RiskEngine(rules=[max_position_weight(0.05)])
        portfolio = _make_portfolio(1_000_000)
        orders = [
            _make_order("A", qty=100, price=100),   # 1% → pass
            _make_order("B", qty=1000, price=100),   # 10% → fail
            _make_order("C", qty=200, price=100),    # 2% → pass
        ]
        approved = engine.check_orders(orders, portfolio)
        assert len(approved) == 2
        symbols = [o.instrument.symbol for o in approved]
        assert "A" in symbols
        assert "C" in symbols
        assert "B" not in symbols
