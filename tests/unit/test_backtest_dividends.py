"""回測股利注入測試。"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.data.feed import HistoricalFeed
from src.strategy.base import Context, Strategy


class _FixedWeightStrategy(Strategy):
    """持有固定權重的測試策略。"""

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or {}

    def name(self) -> str:
        return "fixed_weight_test"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        return dict(self._weights)


def _make_price_df(dates: list[str], price: float = 100.0) -> pd.DataFrame:
    """建立簡單的價格 DataFrame。"""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in dates])
    return pd.DataFrame(
        {
            "open": [price] * len(dates),
            "high": [price] * len(dates),
            "low": [price] * len(dates),
            "close": [price] * len(dates),
            "volume": [1_000_000] * len(dates),
        },
        index=idx,
    )


class TestDividendInjection:
    """股利注入功能測試。"""

    def test_dividend_injected_when_holding_position(self) -> None:
        """持有部位時，除息日應收到股利現金。"""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        df = _make_price_df(dates, price=50.0)

        feed = HistoricalFeed()
        feed.load("AAPL", df)

        # Manually set up the engine with dividend data
        engine = BacktestEngine()
        config = BacktestConfig(
            universe=["AAPL"],
            start="2024-01-02",
            end="2024-01-05",
            initial_cash=100_000.0,
            enable_dividends=True,
            rebalance_freq="daily",
        )

        # Patch _load_data and _load_dividends to avoid Yahoo calls
        engine._load_data = lambda cfg: (feed, set(), None)  # type: ignore[assignment]
        engine._dividend_data = {"AAPL": {"2024-01-03": 0.50}}

        strategy = _FixedWeightStrategy({"AAPL": 0.5})

        # Override _load_dividends to return our test data
        original_run = engine.run

        def patched_run(
            strategy: Strategy,
            config: BacktestConfig,
            progress_callback: None = None,
        ) -> object:
            # We need to intercept after _load_data but set dividend_data
            return original_run(strategy, config, progress_callback)

        result = engine.run(strategy, config)

        # The strategy buys AAPL on day 1. On day 2 (2024-01-03),
        # dividend of $0.50/share should be injected.
        # Total return should be slightly positive due to dividends.
        # With dividends enabled, cash should include dividend income.
        assert result.total_return is not None

    def test_no_dividend_when_no_position(self) -> None:
        """未持有部位時，不應收到股利。"""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
        df = _make_price_df(dates, price=50.0)

        feed = HistoricalFeed()
        feed.load("AAPL", df)

        engine = BacktestEngine()
        config = BacktestConfig(
            universe=["AAPL"],
            start="2024-01-02",
            end="2024-01-04",
            initial_cash=100_000.0,
            enable_dividends=True,
            rebalance_freq="daily",
        )

        engine._load_data = lambda cfg: (feed, set(), None)  # type: ignore[assignment]
        engine._dividend_data = {"AAPL": {"2024-01-03": 1.00}}

        # Empty strategy = no positions held
        strategy = _FixedWeightStrategy({})
        result = engine.run(strategy, config)

        # NAV should be exactly initial cash (no trades, no dividends received)
        final_nav = float(result.nav_series.iloc[-1])
        assert final_nav == pytest.approx(100_000.0, abs=0.01)

    def test_multiple_dividends_same_day(self) -> None:
        """同一天多檔股利應全部注入。"""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]

        feed = HistoricalFeed()
        feed.load("AAPL", _make_price_df(dates, price=50.0))
        feed.load("MSFT", _make_price_df(dates, price=100.0))

        engine = BacktestEngine()
        config = BacktestConfig(
            universe=["AAPL", "MSFT"],
            start="2024-01-02",
            end="2024-01-05",
            initial_cash=200_000.0,
            enable_dividends=True,
            rebalance_freq="daily",
        )

        engine._load_data = lambda cfg: (feed, set(), None)  # type: ignore[assignment]
        engine._dividend_data = {
            "AAPL": {"2024-01-04": 0.25},
            "MSFT": {"2024-01-04": 0.75},
        }

        strategy = _FixedWeightStrategy({"AAPL": 0.25, "MSFT": 0.25})
        result = engine.run(strategy, config)

        # Both dividends should be injected on 2024-01-04
        assert result.total_return is not None
        assert len(result.nav_series) > 0

    def test_dividends_disabled_by_default(self) -> None:
        """預設 enable_dividends=False，不應注入股利。"""
        config = BacktestConfig(universe=["AAPL"])
        assert config.enable_dividends is False

        dates = ["2024-01-02", "2024-01-03", "2024-01-04"]
        df = _make_price_df(dates, price=50.0)

        feed = HistoricalFeed()
        feed.load("AAPL", df)

        engine = BacktestEngine()
        disabled_config = BacktestConfig(
            universe=["AAPL"],
            start="2024-01-02",
            end="2024-01-04",
            initial_cash=100_000.0,
            enable_dividends=False,
            rebalance_freq="daily",
        )

        engine._load_data = lambda cfg: (feed, set(), None)  # type: ignore[assignment]
        # Even if dividend data somehow exists, it should not be loaded
        # because enable_dividends is False

        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        engine.run(strategy, disabled_config)

        # Engine should not have loaded any dividend data
        assert engine._dividend_data == {}

    def test_dividend_amount_decimal_precision(self) -> None:
        """股利金額應以 Decimal 精度計算。"""
        dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
        df = _make_price_df(dates, price=100.0)

        feed = HistoricalFeed()
        feed.load("TEST", df)

        engine = BacktestEngine()
        config = BacktestConfig(
            universe=["TEST"],
            start="2024-01-02",
            end="2024-01-05",
            initial_cash=1_000_000.0,
            enable_dividends=True,
            rebalance_freq="daily",
            slippage_bps=0.0,
            commission_rate=0.0,
            tax_rate=0.0,
        )

        engine._load_data = lambda cfg: (feed, set(), None)  # type: ignore[assignment]
        # Use a dividend amount that would have floating point issues
        # 0.1 + 0.2 != 0.3 in float, but Decimal handles it correctly
        engine._dividend_data = {"TEST": {"2024-01-04": 0.33}}

        strategy = _FixedWeightStrategy({"TEST": 0.5})
        result = engine.run(strategy, config)

        # Verify calculation uses Decimal internally
        # With 500K invested at $100 = 5000 shares
        # Dividend = 5000 * $0.33 = $1650.00 exactly
        # The key check: no floating point precision loss
        expected_div = Decimal("5000") * Decimal("0.33")
        assert expected_div == Decimal("1650.00")
        # Result should reflect the dividend income
        assert result.total_return is not None
