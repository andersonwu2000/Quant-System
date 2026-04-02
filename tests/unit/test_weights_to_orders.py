"""weights_to_orders 市場感知交易單位測試。"""

from decimal import Decimal

from src.core.models import Instrument, Portfolio
from src.strategy.engine import _get_lot_size, weights_to_orders


# ─── _get_lot_size 單元測試 ──────────────────────────


class TestGetLotSize:
    def test_tw_suffix_returns_1000(self):
        inst = Instrument(symbol="2330.TW")
        lot = _get_lot_size("2330.TW", inst, market_lot_sizes={".TW": 1000})
        assert lot == 1000

    def test_two_suffix_returns_1000(self):
        inst = Instrument(symbol="6547.TWO")
        lot = _get_lot_size("6547.TWO", inst, market_lot_sizes={".TW": 1000, ".TWO": 1000})
        assert lot == 1000

    def test_us_stock_no_suffix_returns_1(self):
        inst = Instrument(symbol="AAPL")
        lot = _get_lot_size("AAPL", inst, market_lot_sizes={".TW": 1000})
        assert lot == 1

    def test_japan_stock_returns_100(self):
        inst = Instrument(symbol="7203.T")
        lot = _get_lot_size("7203.T", inst, market_lot_sizes={".TW": 1000, ".T": 100})
        assert lot == 100

    def test_explicit_instrument_lot_size_overrides_market(self):
        """Instrument.lot_size > 1 takes priority over market suffix."""
        inst = Instrument(symbol="2330.TW", lot_size=500)
        lot = _get_lot_size("2330.TW", inst, market_lot_sizes={".TW": 1000})
        assert lot == 500

    def test_fractional_shares_always_returns_1(self):
        inst = Instrument(symbol="2330.TW", lot_size=1000)
        lot = _get_lot_size("2330.TW", inst, market_lot_sizes={".TW": 1000}, fractional_shares=True)
        assert lot == 1

    def test_no_market_lot_sizes_uses_instrument_default(self):
        inst = Instrument(symbol="AAPL")  # lot_size defaults to 1
        lot = _get_lot_size("AAPL", inst, market_lot_sizes=None)
        assert lot == 1

    def test_no_market_lot_sizes_with_instrument_override(self):
        inst = Instrument(symbol="2330.TW", lot_size=1000)
        lot = _get_lot_size("2330.TW", inst, market_lot_sizes=None)
        assert lot == 1000


# ─── weights_to_orders 整合測試 ──────────────────────


class TestWeightsToOrdersLotSize:
    """Test market-aware lot size in weights_to_orders."""

    def test_tw_stock_rounds_to_1000_with_odd_lot(self):
        """Taiwan stock: whole lot + odd lot order for remainder."""
        portfolio = Portfolio(cash=Decimal("10000000"))  # 1000萬
        target = {"2330.TW": 0.10}  # 10% = 1,000,000
        prices = {"2330.TW": Decimal("700")}
        market_lots = {".TW": 1000, ".TWO": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        # 1,000,000 / 700 = ~1428 → 1 whole lot (1000) + 428 odd lot
        assert len(orders) == 2
        whole = orders[0]
        odd = orders[1]
        assert whole.quantity == Decimal("1000")
        assert whole.quantity % 1000 == 0
        assert odd.quantity == Decimal("428")
        assert whole.quantity + odd.quantity == Decimal("1428")

    def test_us_stock_rounds_to_1(self):
        """US stock (no suffix match) should use lot_size=1."""
        portfolio = Portfolio(cash=Decimal("1000000"))
        target = {"AAPL": 0.05}  # 5% = 50,000
        prices = {"AAPL": Decimal("180")}
        market_lots = {".TW": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        assert len(orders) == 1
        order = orders[0]
        # 50,000 / 180 = ~277.7 → 278 (lot_size=1, rounded)
        assert order.quantity == Decimal("278")

    def test_japan_stock_rounds_to_100_with_odd_lot(self):
        """Japan stock (.T suffix) rounds to 100, remainder as odd lot."""
        portfolio = Portfolio(cash=Decimal("10000000"))
        target = {"7203.T": 0.05}  # 5% = 500,000
        prices = {"7203.T": Decimal("2500")}
        market_lots = {".TW": 1000, ".T": 100}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        # 500,000 / 2500 = 200 shares → exactly 2 lots, no remainder
        assert len(orders) == 1
        order = orders[0]
        assert order.quantity == Decimal("200")
        assert order.quantity % 100 == 0

    def test_fractional_override(self):
        """fractional_shares=True → lot_size=1 always, ignoring market."""
        portfolio = Portfolio(cash=Decimal("10000000"))
        target = {"2330.TW": 0.10}  # 10% = 1,000,000
        prices = {"2330.TW": Decimal("700")}
        market_lots = {".TW": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
            fractional_shares=True,
        )

        assert len(orders) == 1
        order = orders[0]
        # 1,000,000 / 700 = ~1428.57 → 1429 (lot_size=1, rounded)
        assert order.quantity == Decimal("1429")

    def test_small_portfolio_odd_lot_only(self):
        """
        小資金買不起一整張台積電 (700 × 1000 = 700K)。
        Portfolio 100萬, target 50% = 500K < 700K per lot →
        整張 qty=0, but odd lot = 714 shares generated.
        """
        portfolio = Portfolio(cash=Decimal("1000000"))  # 100萬
        target = {"2330.TW": 0.50}  # 50% = 500,000
        prices = {"2330.TW": Decimal("700")}
        market_lots = {".TW": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        # 500,000 / 700 = ~714 shares → 0 whole lots + 714 odd lot
        assert len(orders) == 1
        assert orders[0].quantity == Decimal("714")

    def test_explicit_instrument_lot_size_overrides_market(self):
        """Instrument with explicit lot_size > 1 overrides market suffix."""
        portfolio = Portfolio(cash=Decimal("10000000"))
        target = {"2330.TW": 0.10}  # 10% = 1,000,000
        prices = {"2330.TW": Decimal("700")}
        market_lots = {".TW": 1000}
        instruments = {"2330.TW": Instrument(symbol="2330.TW", lot_size=500)}

        orders = weights_to_orders(
            target, portfolio, prices,
            instruments=instruments,
            market_lot_sizes=market_lots,
        )

        # 1,000,000 / 700 = ~1428 → 2 whole lots of 500 (1000) + 428 odd lot
        assert len(orders) == 2
        assert orders[0].quantity == Decimal("1000")
        assert orders[0].quantity % 500 == 0
        assert orders[1].quantity == Decimal("428")

    def test_without_market_lot_sizes_backward_compatible(self):
        """Without market_lot_sizes, behavior is unchanged (lot_size from instrument)."""
        portfolio = Portfolio(cash=Decimal("1000000"))
        target = {"AAPL": 0.05}
        prices = {"AAPL": Decimal("180")}

        orders = weights_to_orders(target, portfolio, prices)

        assert len(orders) == 1
        # Default instrument lot_size=1, so 50000/180 = 278 (rounded)
        assert orders[0].quantity == Decimal("278")

    def test_mixed_markets(self):
        """Portfolio with both TW and US stocks in same call."""
        portfolio = Portfolio(cash=Decimal("10000000"))
        target = {"2330.TW": 0.10, "AAPL": 0.05}
        prices = {"2330.TW": Decimal("700"), "AAPL": Decimal("180")}
        market_lots = {".TW": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        # TW: 1 whole lot + 1 odd lot, US: 1 order
        tw_orders = [o for o in orders if o.instrument.symbol == "2330.TW"]
        us_orders = [o for o in orders if o.instrument.symbol == "AAPL"]

        assert len(tw_orders) == 2  # whole + odd
        assert tw_orders[0].quantity % 1000 == 0
        assert tw_orders[0].quantity + tw_orders[1].quantity == Decimal("1428")

        assert len(us_orders) == 1
        assert us_orders[0].quantity == Decimal("2778")  # 500,000/180 = 2777.7 → 2778

    def test_exact_lot_no_odd_order(self):
        """When qty divides evenly by lot_size, no odd lot order generated."""
        portfolio = Portfolio(cash=Decimal("10000000"))
        target = {"2330.TW": 0.07}  # 7% = 700,000
        prices = {"2330.TW": Decimal("700")}
        market_lots = {".TW": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        # 700,000 / 700 = 1000 shares → exactly 1 lot, no remainder
        assert len(orders) == 1
        assert orders[0].quantity == Decimal("1000")

    def test_sell_includes_odd_lot(self):
        """Selling position should also generate odd lot for remainder."""
        from src.core.models import Instrument as Inst, Position
        portfolio = Portfolio(cash=Decimal("600000"))
        portfolio.positions["2330.TW"] = Position(
            instrument=Inst(symbol="2330.TW", lot_size=1000, market="tw"),
            quantity=Decimal("2500"),
            avg_cost=Decimal("700"),
            market_price=Decimal("700"),
        )
        # NAV = cash + market_value = 600,000 + 2500*700 = 2,350,000

        target = {"2330.TW": 0.0}  # sell everything
        prices = {"2330.TW": Decimal("700")}
        market_lots = {".TW": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        # Selling 2500 shares → 2 whole lots (2000) + 500 odd lot
        from src.core.models import Side
        sell_orders = [o for o in orders if o.side == Side.SELL]
        total_sell = sum(o.quantity for o in sell_orders)
        assert total_sell == Decimal("2500")
        assert any(o.quantity == Decimal("2000") for o in sell_orders)
        assert any(o.quantity == Decimal("500") for o in sell_orders)
