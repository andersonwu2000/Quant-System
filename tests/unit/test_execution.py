"""執行層測試。"""

from decimal import Decimal


from src.core.models import Instrument, Order, OrderStatus, Portfolio, Position, Side
from src.execution.oms import OrderManager, apply_trades
from src.execution.broker.simulated import SimBroker, SimConfig
from src.core.models import Trade


class TestSimBroker:
    def test_basic_fill(self):
        broker = SimBroker(SimConfig(impact_model="fixed", slippage_bps=0, commission_rate=0, tax_rate=0))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("50"),
        )
        bars = {"A": {"close": 50.0, "volume": 1e6}}
        trades = broker.execute([order], bars)

        assert len(trades) == 1
        assert trades[0].symbol == "A"
        assert trades[0].quantity == Decimal("100")
        assert trades[0].price == Decimal("50")
        assert order.status == OrderStatus.FILLED

    def test_slippage_applied(self):
        broker = SimBroker(SimConfig(impact_model="fixed", slippage_bps=10, commission_rate=0, tax_rate=0))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("100"),
        )
        bars = {"A": {"close": 100.0, "volume": 1e6}}
        trades = broker.execute([order], bars)

        # 10 bps = 0.1%, 100 * 0.001 = 0.1, fill at 100.10
        assert trades[0].price == Decimal("100.10")

    def test_sell_slippage(self):
        broker = SimBroker(SimConfig(impact_model="fixed", slippage_bps=10, commission_rate=0, tax_rate=0))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.SELL,
            quantity=Decimal("100"),
            price=Decimal("100"),
        )
        bars = {"A": {"close": 100.0, "volume": 1e6}}
        trades = broker.execute([order], bars)

        # 賣出滑價向下
        assert trades[0].price == Decimal("99.90")

    def test_commission(self):
        broker = SimBroker(SimConfig(impact_model="fixed", slippage_bps=0, commission_rate=0.001, tax_rate=0))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("1000"),
            price=Decimal("100"),
        )
        bars = {"A": {"close": 100.0, "volume": 1e8}}
        trades = broker.execute([order], bars)

        # commission = 1000 * 100 * 0.001 = 100
        assert trades[0].commission == Decimal("100")

    def test_sell_tax(self):
        broker = SimBroker(SimConfig(impact_model="fixed", slippage_bps=0, commission_rate=0.001, tax_rate=0.003))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.SELL,
            quantity=Decimal("1000"),
            price=Decimal("100"),
        )
        bars = {"A": {"close": 100.0, "volume": 1e8}}
        trades = broker.execute([order], bars)

        # commission = 100K * 0.001 + 100K * 0.003 = 100 + 300 = 400
        assert trades[0].commission == Decimal("400")

    def test_no_data_rejected(self):
        broker = SimBroker()
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
        )
        trades = broker.execute([order], {})
        assert len(trades) == 0
        assert order.status == OrderStatus.REJECTED


class TestApplyTrades:
    def test_buy_creates_position(self):
        portfolio = Portfolio(cash=Decimal("100000"))
        trade = Trade(
            timestamp=portfolio.as_of,
            symbol="A",
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("50"),
            commission=Decimal("7"),
            slippage_bps=Decimal("0"),
        )
        portfolio = apply_trades(portfolio, [trade])

        assert "A" in portfolio.positions
        assert portfolio.positions["A"].quantity == Decimal("100")
        assert portfolio.positions["A"].avg_cost == Decimal("50")
        assert portfolio.cash == Decimal("100000") - Decimal("5000") - Decimal("7")

    def test_sell_removes_position(self):
        portfolio = Portfolio(
            cash=Decimal("95000"),
            positions={
                "A": Position(
                    instrument=Instrument(symbol="A"),
                    quantity=Decimal("100"),
                    avg_cost=Decimal("50"),
                    market_price=Decimal("60"),
                ),
            },
        )
        trade = Trade(
            timestamp=portfolio.as_of,
            symbol="A",
            side=Side.SELL,
            quantity=Decimal("100"),
            price=Decimal("60"),
            commission=Decimal("10"),
            slippage_bps=Decimal("0"),
        )
        portfolio = apply_trades(portfolio, [trade])

        assert "A" not in portfolio.positions
        assert portfolio.cash == Decimal("95000") + Decimal("6000") - Decimal("10")


class TestOrderManager:
    def test_submit_and_get(self):
        oms = OrderManager()
        order = Order(id="test-1", instrument=Instrument(symbol="A"))
        oms.submit(order)
        assert oms.get_order("test-1") is not None
        assert oms.get_order("test-1").status == OrderStatus.SUBMITTED

    def test_cancel_all(self):
        oms = OrderManager()
        o1 = Order(id="1", instrument=Instrument(symbol="A"))
        o2 = Order(id="2", instrument=Instrument(symbol="B"))
        oms.submit(o1)
        oms.submit(o2)
        cancelled = oms.cancel_all()
        assert cancelled == 2
        assert o1.status == OrderStatus.CANCELLED
