"""Tests for backtest defense mechanisms (G8): survivorship bias, short borrow cost, price outliers."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import numpy as np
import pandas as pd

from src.backtest.validation import detect_price_outliers, detect_survivorship_bias
from src.core.models import Instrument, Order, Side
from src.execution.broker.simulated import SimBroker, SimConfig


# ─── Survivorship Bias (G8a) ─────────────────────────────


class TestSurvivorshipBias:
    def test_detect_late_listing(self) -> None:
        """Symbol with data starting much later than backtest start."""
        dates_full = pd.date_range("2020-01-01", "2024-12-31", freq="B")
        dates_late = pd.date_range("2022-06-01", "2024-12-31", freq="B")
        data = {
            "AAPL": pd.DataFrame({"close": 100.0}, index=dates_full),
            "NEWCO": pd.DataFrame({"close": 50.0}, index=dates_late),
        }
        warnings = detect_survivorship_bias(data, "2020-01-01", "2024-12-31")
        assert len(warnings) >= 1
        assert any("NEWCO" in w and "late listing" in w for w in warnings)

    def test_detect_delisting(self) -> None:
        """Symbol with data ending much earlier than backtest end."""
        dates_full = pd.date_range("2020-01-01", "2024-12-31", freq="B")
        dates_early = pd.date_range("2020-01-01", "2022-06-01", freq="B")
        data = {
            "AAPL": pd.DataFrame({"close": 100.0}, index=dates_full),
            "DEAD": pd.DataFrame({"close": 50.0}, index=dates_early),
        }
        warnings = detect_survivorship_bias(data, "2020-01-01", "2024-12-31")
        assert len(warnings) >= 1
        assert any("DEAD" in w and "delisting" in w for w in warnings)

    def test_no_warnings_when_full_data(self) -> None:
        """No warnings when all symbols have full data coverage."""
        dates = pd.date_range("2020-01-01", "2024-12-31", freq="B")
        data = {
            "AAPL": pd.DataFrame({"close": 100.0}, index=dates),
            "MSFT": pd.DataFrame({"close": 200.0}, index=dates),
        }
        warnings = detect_survivorship_bias(data, "2020-01-01", "2024-12-31")
        assert len(warnings) == 0

    def test_empty_dataframe_warning(self) -> None:
        """Empty DataFrame should produce a delisted stock warning."""
        data = {
            "GONE": pd.DataFrame(),
        }
        warnings = detect_survivorship_bias(data, "2020-01-01", "2024-12-31")
        assert len(warnings) == 1
        assert "delisted" in warnings[0].lower()


# ─── Short Borrow Cost (G8b) ─────────────────────────────


class TestShortBorrowCost:
    def _make_sell_order(self, symbol: str = "AAPL", qty: int = 100) -> Order:
        return Order(
            id="test-001",
            instrument=Instrument(symbol=symbol),
            side=Side.SELL,
            quantity=Decimal(str(qty)),
            price=Decimal("100"),
        )

    def _make_bars(self, symbol: str = "AAPL") -> dict[str, dict]:
        return {
            symbol: {
                "close": 100.0,
                "volume": 1_000_000.0,
                "prev_close": 99.0,
            }
        }

    def test_borrow_cost_applied(self) -> None:
        """Short borrow cost should increase commission on sell orders."""
        config_no_borrow = SimConfig(
            slippage_bps=0.0,
            commission_rate=0.001,
            tax_rate=0.003,
            impact_model="fixed",
            short_borrow_rate=0.0,
        )
        config_with_borrow = SimConfig(
            slippage_bps=0.0,
            commission_rate=0.001,
            tax_rate=0.003,
            impact_model="fixed",
            short_borrow_rate=0.02,  # 2% annual
        )

        broker_no = SimBroker(config_no_borrow)
        broker_yes = SimBroker(config_with_borrow)

        order_no = self._make_sell_order()
        order_yes = self._make_sell_order()

        ts = datetime(2024, 1, 15, tzinfo=timezone.utc)
        trades_no = broker_no.execute([order_no], self._make_bars(), ts)
        trades_yes = broker_yes.execute([order_yes], self._make_bars(), ts)

        assert len(trades_no) == 1
        assert len(trades_yes) == 1
        assert trades_yes[0].commission > trades_no[0].commission

    def test_borrow_cost_zero_when_rate_zero(self) -> None:
        """With short_borrow_rate=0, no extra cost."""
        config = SimConfig(
            slippage_bps=0.0,
            commission_rate=0.001,
            tax_rate=0.003,
            impact_model="fixed",
            short_borrow_rate=0.0,
        )
        broker = SimBroker(config)
        order = self._make_sell_order()
        ts = datetime(2024, 1, 15, tzinfo=timezone.utc)
        trades = broker.execute([order], self._make_bars(), ts)
        assert len(trades) == 1
        # Commission = notional * (commission_rate + tax_rate) only
        notional = Decimal("100") * Decimal("100")  # qty * price (no slippage)
        expected = notional * Decimal("0.001") + notional * Decimal("0.003")
        assert trades[0].commission == expected

    def test_borrow_cost_calculation(self) -> None:
        """Verify the exact borrow cost calculation."""
        config = SimConfig(
            slippage_bps=0.0,
            commission_rate=0.0,
            tax_rate=0.0,
            impact_model="fixed",
            short_borrow_rate=0.0252,  # exactly 0.0252 annual → 0.0001/day
        )
        broker = SimBroker(config)
        order = self._make_sell_order(qty=100)
        ts = datetime(2024, 1, 15, tzinfo=timezone.utc)
        trades = broker.execute([order], self._make_bars(), ts)
        assert len(trades) == 1
        # notional = 100 * 100 = 10000; borrow = 10000 * 0.0252 / 252 = 1.0
        notional = Decimal("10000")
        expected_borrow = notional * Decimal("0.0252") / Decimal("252")
        assert abs(trades[0].commission - expected_borrow) < Decimal("0.01")


# ─── Price Outlier Detection (G8c) ───────────────────────


class TestPriceOutliers:
    def test_detect_extreme_return(self) -> None:
        """Detect daily return exceeding threshold."""
        dates = pd.date_range("2023-01-01", periods=10, freq="B")
        prices = [100, 100, 100, 100, 125, 100, 100, 100, 100, 100]  # 25% jump
        data = {"TEST": pd.DataFrame({"close": prices, "volume": 1000}, index=dates)}
        warnings = detect_price_outliers(data, threshold=0.20)
        assert len(warnings) >= 1
        assert any("TEST" in w and "return" in w for w in warnings)

    def test_detect_zero_volume(self) -> None:
        """Detect zero-volume days."""
        dates = pd.date_range("2023-01-01", periods=5, freq="B")
        data = {
            "ZV": pd.DataFrame(
                {"close": [100, 101, 102, 103, 104], "volume": [1000, 0, 1000, 0, 1000]},
                index=dates,
            )
        }
        warnings = detect_price_outliers(data)
        assert any("ZV" in w and "zero-volume" in w for w in warnings)

    def test_no_warnings_for_clean_data(self) -> None:
        """No warnings for normal price data."""
        dates = pd.date_range("2023-01-01", periods=100, freq="B")
        rng = np.random.RandomState(42)
        prices = 100 + np.cumsum(rng.randn(100) * 0.5)
        data = {
            "CLEAN": pd.DataFrame(
                {
                    "close": prices,
                    "open": prices - 0.1,
                    "volume": 1_000_000,
                },
                index=dates,
            )
        }
        warnings = detect_price_outliers(data, threshold=0.20)
        assert len(warnings) == 0

    def test_detect_price_gap(self) -> None:
        """Detect large gap between open and previous close."""
        dates = pd.date_range("2023-01-01", periods=5, freq="B")
        data = {
            "GAP": pd.DataFrame(
                {
                    "close": [100, 100, 100, 100, 100],
                    "open": [100, 100, 125, 100, 100],  # 25% gap on day 3
                    "volume": [1000, 1000, 1000, 1000, 1000],
                },
                index=dates,
            )
        }
        warnings = detect_price_outliers(data, threshold=0.20)
        assert any("GAP" in w and "gap" in w for w in warnings)
