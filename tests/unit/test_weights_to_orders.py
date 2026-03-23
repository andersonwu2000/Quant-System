"""weights_to_orders 市場感知交易單位測試。"""

from decimal import Decimal

from src.domain.models import Instrument, Portfolio
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

    def test_tw_stock_rounds_to_1000(self):
        """Taiwan stock with market_lot_sizes should round to 1000 shares."""
        portfolio = Portfolio(cash=Decimal("10000000"))  # 1000萬
        target = {"2330.TW": 0.10}  # 10% = 1,000,000
        prices = {"2330.TW": Decimal("700")}
        market_lots = {".TW": 1000, ".TWO": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        assert len(orders) == 1
        order = orders[0]
        assert order.instrument.symbol == "2330.TW"
        # 1,000,000 / 700 = ~1428 shares → floor to 1000
        assert order.quantity == Decimal("1000")
        assert order.quantity % 1000 == 0

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
        # 50,000 / 180 = ~277 shares → floor to 277 (lot_size=1)
        assert order.quantity == Decimal("277")

    def test_japan_stock_rounds_to_100(self):
        """Japan stock (.T suffix) rounds to 100 shares."""
        portfolio = Portfolio(cash=Decimal("10000000"))
        target = {"7203.T": 0.05}  # 5% = 500,000
        prices = {"7203.T": Decimal("2500")}
        market_lots = {".TW": 1000, ".T": 100}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        assert len(orders) == 1
        order = orders[0]
        # 500,000 / 2500 = 200 shares → floor to 200 (lot_size=100)
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
        # 1,000,000 / 700 = ~1428 shares → floor to 1428 (lot_size=1)
        assert order.quantity == Decimal("1428")

    def test_small_portfolio_skips_expensive_stock(self):
        """
        小資金買不起一整張台積電 (700 × 1000 = 700K)。
        Portfolio 100萬, target 50% = 500K < 700K per lot → qty rounds to 0 → no order.
        """
        portfolio = Portfolio(cash=Decimal("1000000"))  # 100萬
        target = {"2330.TW": 0.50}  # 50% = 500,000
        prices = {"2330.TW": Decimal("700")}
        market_lots = {".TW": 1000}

        orders = weights_to_orders(
            target, portfolio, prices,
            market_lot_sizes=market_lots,
        )

        # 500,000 / 700 = ~714 shares → floor to 0 (lot_size=1000) → skipped
        assert len(orders) == 0

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

        assert len(orders) == 1
        order = orders[0]
        # 1,000,000 / 700 = ~1428 shares → floor to 1000 (lot_size=500 → 500*2)
        assert order.quantity == Decimal("1000")
        assert order.quantity % 500 == 0

    def test_without_market_lot_sizes_backward_compatible(self):
        """Without market_lot_sizes, behavior is unchanged (lot_size from instrument)."""
        portfolio = Portfolio(cash=Decimal("1000000"))
        target = {"AAPL": 0.05}
        prices = {"AAPL": Decimal("180")}

        orders = weights_to_orders(target, portfolio, prices)

        assert len(orders) == 1
        # Default instrument lot_size=1, so 50000/180 = 277
        assert orders[0].quantity == Decimal("277")

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

        orders_by_sym = {o.instrument.symbol: o for o in orders}
        assert len(orders_by_sym) == 2

        # TW stock rounds to 1000
        tw_order = orders_by_sym["2330.TW"]
        assert tw_order.quantity % 1000 == 0

        # US stock rounds to 1
        us_order = orders_by_sym["AAPL"]
        assert us_order.quantity == Decimal("2777")  # 500,000/180 = 2777
