"""策略層測試。"""

from decimal import Decimal

import pandas as pd

from src.data.feed import HistoricalFeed
from src.core.models import Portfolio
from src.strategy.base import Context, Strategy
from src.strategy.engine import weights_to_orders
from src.strategy.optimizer import equal_weight, signal_weight, OptConstraints


# ─── Context 測試 ────────────────────────────────


class TestContext:
    def test_bars_truncated_by_current_time(self):
        """確保 Context 在回測時截斷未來數據。"""
        feed = HistoricalFeed()
        dates = pd.date_range("2020-01-01", periods=100, freq="B")
        df = pd.DataFrame(
            {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
            index=dates,
        )
        feed.load("A", df)

        # 設定在第 50 天
        mid_date = dates[49].to_pydatetime()
        ctx = Context(feed=feed, portfolio=Portfolio(), current_time=mid_date)

        bars = ctx.bars("A", lookback=1000)
        assert len(bars) == 50  # 只看到前 50 天

    def test_universe(self):
        feed = HistoricalFeed()
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        for sym in ["A", "B", "C"]:
            df = pd.DataFrame(
                {"open": 100, "high": 101, "low": 99, "close": 100, "volume": 1000},
                index=dates,
            )
            feed.load(sym, df)

        ctx = Context(feed=feed, portfolio=Portfolio())
        assert set(ctx.universe()) == {"A", "B", "C"}


# ─── Optimizer 測試 ───────────────────────────────


class TestOptimizer:
    def test_equal_weight(self):
        signals = {"A": 1.0, "B": 0.5, "C": -0.3}
        weights = equal_weight(signals, OptConstraints(max_weight=0.10, long_only=True))
        assert "C" not in weights  # 負信號被過濾
        assert len(weights) == 2
        assert all(w <= 0.10 for w in weights.values())

    def test_signal_weight(self):
        signals = {"A": 0.8, "B": 0.2}
        weights = signal_weight(signals, OptConstraints(max_weight=0.95))
        assert weights["A"] > weights["B"]  # A 信號更強，權重更大

    def test_empty_signals(self):
        assert equal_weight({}) == {}
        assert signal_weight({}) == {}


# ─── weights_to_orders 測試 ───────────────────────


class TestWeightsToOrders:
    def test_new_position(self):
        portfolio = Portfolio(cash=Decimal("1000000"))
        target = {"A": 0.05}  # 5% = 50000
        prices = {"A": Decimal("100")}
        orders = weights_to_orders(target, portfolio, prices)

        assert len(orders) == 1
        assert orders[0].instrument.symbol == "A"
        assert orders[0].side.value == "BUY"
        assert orders[0].quantity == Decimal("500")

    def test_close_position(self):
        from src.core.models import Instrument, Position

        portfolio = Portfolio(
            cash=Decimal("950000"),
            positions={
                "A": Position(
                    instrument=Instrument(symbol="A"),
                    quantity=Decimal("500"),
                    avg_cost=Decimal("100"),
                    market_price=Decimal("100"),
                ),
            },
        )
        # 目標不包含 A → 應該賣出
        target = {}
        prices = {"A": Decimal("100")}
        orders = weights_to_orders(target, portfolio, prices)

        assert len(orders) == 1
        assert orders[0].side.value == "SELL"

    def test_ignore_small_diff(self):
        """微小差異不應產生訂單。"""
        from src.core.models import Instrument, Position

        portfolio = Portfolio(
            cash=Decimal("950000"),
            positions={
                "A": Position(
                    instrument=Instrument(symbol="A"),
                    quantity=Decimal("500"),
                    avg_cost=Decimal("100"),
                    market_price=Decimal("100"),
                ),
            },
        )
        # 目標 5% ≈ 當前 5%
        target = {"A": 0.05}
        prices = {"A": Decimal("100")}
        orders = weights_to_orders(target, portfolio, prices)

        # 差異太小，不應有訂單
        assert len(orders) == 0


# ─── Strategy 子類測試 ────────────────────────────


class DummyStrategy(Strategy):
    def name(self) -> str:
        return "dummy"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        return {"A": 0.5, "B": 0.3}


class TestStrategyInterface:
    def test_name(self):
        s = DummyStrategy()
        assert s.name() == "dummy"

    def test_on_bar(self):
        s = DummyStrategy()
        feed = HistoricalFeed()
        ctx = Context(feed=feed, portfolio=Portfolio())
        weights = s.on_bar(ctx)
        assert weights == {"A": 0.5, "B": 0.3}

    def test_repr(self):
        s = DummyStrategy()
        assert "dummy" in repr(s)
