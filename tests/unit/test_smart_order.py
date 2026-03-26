"""Tests for TWAP smart order splitter."""

from datetime import datetime, timedelta
from decimal import Decimal

from src.core.models import Instrument, Order, OrderType, Side
from src.execution.smart_order import TWAPConfig, TWAPSplitter


def _make_instrument(symbol: str = "2330.TW") -> Instrument:
    return Instrument(symbol)


def _make_order(
    quantity: int = 1000,
    price: Decimal | None = None,
    side: Side = Side.BUY,
    order_type: OrderType = OrderType.MARKET,
) -> Order:
    return Order(
        instrument=_make_instrument(),
        side=side,
        order_type=order_type,
        quantity=Decimal(str(quantity)),
        price=price,
    )


class TestShouldSplit:
    """should_split 判斷邏輯。"""

    def test_large_order_should_split(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(min_order_value=Decimal("50000")))
        order = _make_order(quantity=100)
        # 100 shares * 600 = 60,000 >= 50,000
        assert splitter.should_split(order, Decimal("600")) is True

    def test_small_order_should_not_split(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(min_order_value=Decimal("50000")))
        order = _make_order(quantity=10)
        # 10 shares * 100 = 1,000 < 50,000
        assert splitter.should_split(order, Decimal("100")) is False

    def test_exact_threshold_should_split(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(min_order_value=Decimal("50000")))
        order = _make_order(quantity=100)
        # 100 * 500 = 50,000 == 50,000
        assert splitter.should_split(order, Decimal("500")) is True

    def test_just_below_threshold(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(min_order_value=Decimal("50000")))
        order = _make_order(quantity=100)
        # 100 * 499 = 49,900 < 50,000
        assert splitter.should_split(order, Decimal("499")) is False


class TestSplit:
    """split 拆單邏輯。"""

    def test_correct_number_of_children(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(n_slices=5))
        order = _make_order(quantity=1000)
        children = splitter.split(order)
        assert len(children) == 5

    def test_total_quantity_equals_parent(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(n_slices=5))
        order = _make_order(quantity=1000)
        children = splitter.split(order)
        total = sum(c.quantity for c in children)
        assert total == Decimal("1000")

    def test_remainder_goes_to_last_child(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(n_slices=3))
        order = _make_order(quantity=100)
        children = splitter.split(order)
        # 100 // 3 = 33, remainder = 1
        assert children[0].quantity == Decimal("33")
        assert children[1].quantity == Decimal("33")
        assert children[2].quantity == Decimal("34")  # 33 + 1

    def test_even_split_no_remainder(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(n_slices=4))
        order = _make_order(quantity=100)
        children = splitter.split(order)
        for child in children:
            assert child.quantity == Decimal("25")

    def test_scheduled_times_spaced_correctly(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(n_slices=3, interval_minutes=30))
        start = datetime(2026, 3, 26, 9, 0, 0)
        order = _make_order(quantity=300)
        children = splitter.split(order, start_time=start)

        assert children[0].scheduled_time == start
        assert children[1].scheduled_time == start + timedelta(minutes=30)
        assert children[2].scheduled_time == start + timedelta(minutes=60)

    def test_single_slice_returns_one_child(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(n_slices=1))
        order = _make_order(quantity=500)
        children = splitter.split(order)
        assert len(children) == 1
        assert children[0].quantity == Decimal("500")

    def test_child_fields_populated(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(n_slices=2, interval_minutes=15))
        order = _make_order(
            quantity=200, price=Decimal("100"), side=Side.SELL, order_type=OrderType.LIMIT
        )
        start = datetime(2026, 1, 1, 10, 0, 0)
        children = splitter.split(order, start_time=start)

        child = children[0]
        assert child.parent_id == order.id
        assert child.instrument.symbol == "2330.TW"
        assert child.side == Side.SELL
        assert child.price == Decimal("100")
        assert child.order_type == OrderType.LIMIT
        assert child.slice_index == 0
        assert child.total_slices == 2
        assert child.scheduled_time == start

        child2 = children[1]
        assert child2.slice_index == 1
        assert child2.scheduled_time == start + timedelta(minutes=15)

    def test_parent_id_matches_order_id(self) -> None:
        splitter = TWAPSplitter(TWAPConfig(n_slices=3))
        order = _make_order(quantity=300)
        children = splitter.split(order)
        for child in children:
            assert child.parent_id == order.id


class TestTWAPConfig:
    """TWAPConfig 預設值。"""

    def test_defaults(self) -> None:
        cfg = TWAPConfig()
        assert cfg.n_slices == 5
        assert cfg.interval_minutes == 30
        assert cfg.min_order_value == Decimal("50000")

    def test_custom_config(self) -> None:
        cfg = TWAPConfig(n_slices=10, interval_minutes=15, min_order_value=Decimal("100000"))
        splitter = TWAPSplitter(cfg)
        assert splitter.config.n_slices == 10
        assert splitter.config.interval_minutes == 15
