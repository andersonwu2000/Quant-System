"""SimBroker tests — slippage models, zero volume, price limits, rejected order logging."""

from decimal import Decimal

from src.domain.models import Instrument, Order, OrderStatus, Side
from src.execution.sim import SimBroker, SimConfig


class TestFixedSlippageModel:
    def test_fixed_slippage_model(self):
        """Fixed slippage should apply a flat bps rate regardless of order size."""
        broker = SimBroker(SimConfig(
            impact_model="fixed",
            slippage_bps=10.0,
            commission_rate=0,
            tax_rate=0,
        ))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("100"),
        )
        bars = {"A": {"close": 100.0, "volume": 1e6}}
        trades = broker.execute([order], bars)

        assert len(trades) == 1
        # 10 bps on 100 = 0.10
        assert trades[0].price == Decimal("100") + Decimal("100") * Decimal("10") / Decimal("10000")


class TestSqrtSlippageModel:
    def test_sqrt_slippage_small_order(self):
        """A small order (low participation) should have slippage near base_bps."""
        broker = SimBroker(SimConfig(
            impact_model="sqrt",
            base_slippage_bps=2.0,
            impact_coeff=50.0,
            commission_rate=0,
            tax_rate=0,
        ))
        # 10 shares out of 1,000,000 ADV => participation = 0.00001
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("10"),
            price=Decimal("100"),
        )
        bars = {"A": {"close": 100.0, "volume": 1_000_000}}
        trades = broker.execute([order], bars)

        assert len(trades) == 1
        fill_price = trades[0].price
        # With tiny participation, impact should be very close to base (2 bps)
        slippage_bps = float((fill_price - Decimal("100")) / Decimal("100") * Decimal("10000"))
        assert 2.0 <= slippage_bps < 3.0, f"Expected near 2 bps, got {slippage_bps:.4f}"

    def test_sqrt_slippage_large_order(self):
        """A large order (high participation) should have significantly higher slippage."""
        broker = SimBroker(SimConfig(
            impact_model="sqrt",
            base_slippage_bps=2.0,
            impact_coeff=50.0,
            commission_rate=0,
            tax_rate=0,
        ))
        # 100,000 shares out of 1,000,000 ADV => participation = 0.10
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100000"),
            price=Decimal("100"),
        )
        bars = {"A": {"close": 100.0, "volume": 1_000_000}}
        trades = broker.execute([order], bars)

        assert len(trades) == 1
        fill_price = trades[0].price
        # sqrt(0.1) ~= 0.316, impact = 2 + 50 * 0.316 ~= 17.8 bps
        slippage_bps = float((fill_price - Decimal("100")) / Decimal("100") * Decimal("10000"))
        assert slippage_bps > 10.0, f"Expected >10 bps for large order, got {slippage_bps:.4f}"
        # Should be significantly more than the base 2 bps
        assert slippage_bps > 5 * 2.0  # at least 5x the base


class TestZeroVolumeRejected:
    def test_zero_volume_rejected(self):
        """Orders should be rejected when volume is zero (market halted)."""
        broker = SimBroker(SimConfig(commission_rate=0, tax_rate=0))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("50"),
        )
        bars = {"A": {"close": 50.0, "volume": 0}}
        trades = broker.execute([order], bars)

        assert len(trades) == 0
        assert order.status == OrderStatus.REJECTED
        assert "Zero volume" in order.reject_reason

    def test_negative_volume_rejected(self):
        """Negative volume should also be rejected."""
        broker = SimBroker(SimConfig(commission_rate=0, tax_rate=0))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("50"),
        )
        bars = {"A": {"close": 50.0, "volume": -100}}
        trades = broker.execute([order], bars)

        assert len(trades) == 0
        assert order.status == OrderStatus.REJECTED


class TestPriceLimits:
    def test_price_limit_rejects_beyond_limit(self):
        """Fill price exceeding price limit should be rejected."""
        broker = SimBroker(SimConfig(
            impact_model="fixed",
            slippage_bps=0,
            commission_rate=0,
            tax_rate=0,
            price_limit_pct=0.10,  # +/-10%
        ))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("120"),
        )
        # Current close = 120, prev_close = 100 => 120 exceeds 100*1.10 = 110
        bars = {"A": {"close": 120.0, "volume": 1e6, "prev_close": 100.0}}
        trades = broker.execute([order], bars)

        assert len(trades) == 0
        assert order.status == OrderStatus.REJECTED
        assert "exceeds limit" in order.reject_reason

    def test_price_limit_allows_within_limit(self):
        """Fill price within price limit should execute normally."""
        broker = SimBroker(SimConfig(
            impact_model="fixed",
            slippage_bps=0,
            commission_rate=0,
            tax_rate=0,
            price_limit_pct=0.10,  # +/-10%
        ))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("105"),
        )
        # Current close = 105, prev_close = 100 => within [90, 110]
        bars = {"A": {"close": 105.0, "volume": 1e6, "prev_close": 100.0}}
        trades = broker.execute([order], bars)

        assert len(trades) == 1
        assert order.status == OrderStatus.FILLED

    def test_price_limit_sell_below_lower_bound(self):
        """Sell fill price below lower limit should be rejected."""
        broker = SimBroker(SimConfig(
            impact_model="fixed",
            slippage_bps=0,
            commission_rate=0,
            tax_rate=0,
            price_limit_pct=0.10,
        ))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.SELL,
            quantity=Decimal("100"),
            price=Decimal("80"),
        )
        # Current close = 80, prev_close = 100 => 80 < 100*0.90 = 90
        bars = {"A": {"close": 80.0, "volume": 1e6, "prev_close": 100.0}}
        trades = broker.execute([order], bars)

        assert len(trades) == 0
        assert order.status == OrderStatus.REJECTED
        assert "exceeds limit" in order.reject_reason

    def test_no_price_limit_when_disabled(self):
        """With price_limit_pct=0 (disabled), any price should be accepted."""
        broker = SimBroker(SimConfig(
            impact_model="fixed",
            slippage_bps=0,
            commission_rate=0,
            tax_rate=0,
            price_limit_pct=0.0,
        ))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("200"),
        )
        bars = {"A": {"close": 200.0, "volume": 1e6, "prev_close": 100.0}}
        trades = broker.execute([order], bars)

        assert len(trades) == 1
        assert order.status == OrderStatus.FILLED

    def test_price_limit_no_prev_close(self):
        """Without prev_close in bars, price limit check is skipped."""
        broker = SimBroker(SimConfig(
            impact_model="fixed",
            slippage_bps=0,
            commission_rate=0,
            tax_rate=0,
            price_limit_pct=0.10,
        ))
        order = Order(
            instrument=Instrument(symbol="A"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("200"),
        )
        # No prev_close key — limit check should be skipped
        bars = {"A": {"close": 200.0, "volume": 1e6}}
        trades = broker.execute([order], bars)

        assert len(trades) == 1
        assert order.status == OrderStatus.FILLED


class TestRejectedOrdersLogged:
    def test_rejected_orders_logged(self):
        """Rejected orders should appear in the rejected_log."""
        broker = SimBroker(SimConfig(commission_rate=0, tax_rate=0))

        # Order with no market data
        order1 = Order(
            instrument=Instrument(symbol="MISSING"),
            side=Side.BUY,
            quantity=Decimal("100"),
        )
        # Order with zero volume
        order2 = Order(
            instrument=Instrument(symbol="HALTED"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("50"),
        )
        # Valid order
        order3 = Order(
            instrument=Instrument(symbol="OK"),
            side=Side.BUY,
            quantity=Decimal("100"),
            price=Decimal("50"),
        )

        bars = {
            "HALTED": {"close": 50.0, "volume": 0},
            "OK": {"close": 50.0, "volume": 1e6},
        }
        trades = broker.execute([order1, order2, order3], bars)

        # Only the valid order should execute
        assert len(trades) == 1
        assert trades[0].symbol == "OK"

        # Two rejected orders should be logged
        assert len(broker.rejected_log) == 2
        rejected_symbols = {o.instrument.symbol for o in broker.rejected_log}
        assert rejected_symbols == {"MISSING", "HALTED"}

    def test_reset_clears_rejected_log(self):
        """reset() should clear both trade_log and rejected_log."""
        broker = SimBroker(SimConfig(commission_rate=0, tax_rate=0))
        order = Order(
            instrument=Instrument(symbol="X"),
            side=Side.BUY,
            quantity=Decimal("100"),
        )
        broker.execute([order], {})  # Will be rejected (no data)
        assert len(broker.rejected_log) == 1

        broker.reset()
        assert len(broker.rejected_log) == 0
        assert len(broker.trade_log) == 0
