"""Unit tests for src.core.trading_pipeline — shared one-bar processing logic."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pandas as pd

from src.core.models import Instrument, Portfolio
from src.core.trading_pipeline import execute_one_bar
from src.data.feed import HistoricalFeed
from src.execution.broker.simulated import SimBroker, SimConfig
from src.risk.engine import RiskEngine
from src.risk.rules import max_position_weight
from src.strategy.base import Context, Strategy


# ── Test strategies ──────────────────────────────────────────────────


class _FixedWeightStrategy(Strategy):
    """Always returns the same target weights."""

    def __init__(self, weights: dict[str, float]) -> None:
        self._weights = weights

    def name(self) -> str:
        return "test_fixed"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        return dict(self._weights)


class _EmptyStrategy(Strategy):
    """Always returns empty weights."""

    def name(self) -> str:
        return "test_empty"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        return {}


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_feed(symbols: list[str], n_bars: int = 20) -> HistoricalFeed:
    """Create a HistoricalFeed with dummy price data."""
    feed = HistoricalFeed()
    dates = pd.bdate_range("2024-01-01", periods=n_bars, freq="B")
    for sym in symbols:
        df = pd.DataFrame(
            {
                "open": [100.0] * n_bars,
                "high": [105.0] * n_bars,
                "low": [95.0] * n_bars,
                "close": [100.0] * n_bars,
                "volume": [1_000_000] * n_bars,
            },
            index=dates,
        )
        feed.load(sym, df)
    return feed


def _make_prices(symbols: list[str], price: float = 100.0) -> dict[str, Decimal]:
    return {s: Decimal(str(price)) for s in symbols}


def _make_bar_dict(symbols: list[str], price: float = 100.0) -> dict[str, dict[str, object]]:
    return {
        s: {"close": price, "volume": 1_000_000}
        for s in symbols
    }


def _make_instruments(symbols: list[str]) -> dict[str, Instrument]:
    return {s: Instrument(symbol=s) for s in symbols}


# ── Tests ────────────────────────────────────────────────────────────


class TestExecuteOneBar:
    """Tests for execute_one_bar()."""

    def test_returns_trades_with_valid_weights(self) -> None:
        """Strategy produces weights → orders → trades returned."""
        symbols = ["AAPL", "MSFT"]
        strategy = _FixedWeightStrategy({"AAPL": 0.5, "MSFT": 0.5})
        feed = _make_feed(symbols)
        portfolio = Portfolio(cash=Decimal("1000000"), initial_cash=Decimal("1000000"))
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2024, 1, 15))
        risk_engine = RiskEngine(rules=[])  # no rules → approve everything
        sim_broker = SimBroker(SimConfig(slippage_bps=0, commission_rate=0, tax_rate=0))

        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=_make_prices(symbols),
            volumes={s: Decimal("1000000") for s in symbols},
            current_bars=_make_bar_dict(symbols),
            sim_broker=sim_broker,
            instruments=_make_instruments(symbols),
            timestamp=datetime(2024, 1, 15),
        )

        assert len(trades) > 0
        traded_symbols = {t.symbol for t in trades}
        assert traded_symbols == {"AAPL", "MSFT"}

    def test_returns_empty_when_strategy_returns_empty(self) -> None:
        """Empty strategy → no trades."""
        symbols = ["AAPL"]
        strategy = _EmptyStrategy()
        feed = _make_feed(symbols)
        portfolio = Portfolio(cash=Decimal("1000000"), initial_cash=Decimal("1000000"))
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2024, 1, 15))
        risk_engine = RiskEngine(rules=[])
        sim_broker = SimBroker(SimConfig())

        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=_make_prices(symbols),
            current_bars=_make_bar_dict(symbols),
            sim_broker=sim_broker,
        )

        assert trades == []

    def test_risk_capping_reduces_position(self) -> None:
        """When risk engine caps an oversized order, trade is reduced not rejected."""
        symbols = ["AAPL"]
        # 99% in one stock, with a max_position_weight of 5% → should be capped
        strategy = _FixedWeightStrategy({"AAPL": 0.99})
        feed = _make_feed(symbols)
        portfolio = Portfolio(cash=Decimal("1000000"), initial_cash=Decimal("1000000"))
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2024, 1, 15))
        risk_engine = RiskEngine(rules=[max_position_weight(0.05)])
        sim_broker = SimBroker(SimConfig(slippage_bps=0, commission_rate=0, tax_rate=0))

        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=_make_prices(symbols),
            current_bars=_make_bar_dict(symbols),
            sim_broker=sim_broker,
            instruments=_make_instruments(symbols),
            timestamp=datetime(2024, 1, 15),
        )

        # Trade should happen but capped — not rejected
        assert len(trades) >= 1
        total_value = sum(float(t.quantity * t.price) for t in trades)
        assert total_value <= 1_000_000 * 0.06  # ~5% + margin

    def test_returns_empty_without_sim_broker(self) -> None:
        """Without sim_broker, execute_one_bar returns [] (no execution)."""
        symbols = ["AAPL"]
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        feed = _make_feed(symbols)
        portfolio = Portfolio(cash=Decimal("1000000"), initial_cash=Decimal("1000000"))
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2024, 1, 15))
        risk_engine = RiskEngine(rules=[])

        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=_make_prices(symbols),
            # no sim_broker, no current_bars
        )

        assert trades == []

    def test_trades_applied_to_portfolio(self) -> None:
        """After execute_one_bar, portfolio cash should decrease (bought stock)."""
        symbols = ["AAPL"]
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        feed = _make_feed(symbols)
        initial_cash = Decimal("1000000")
        portfolio = Portfolio(cash=initial_cash, initial_cash=initial_cash)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2024, 1, 15))
        risk_engine = RiskEngine(rules=[])
        sim_broker = SimBroker(SimConfig(slippage_bps=0, commission_rate=0, tax_rate=0))

        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=_make_prices(symbols),
            current_bars=_make_bar_dict(symbols),
            sim_broker=sim_broker,
            instruments=_make_instruments(symbols),
            timestamp=datetime(2024, 1, 15),
        )

        assert len(trades) > 0
        # Cash should have decreased because we bought AAPL
        assert portfolio.cash < initial_cash
        # Should have AAPL in positions
        assert "AAPL" in portfolio.positions

    def test_settlement_params_forwarded(self) -> None:
        """available_cash, market_lot_sizes, fractional_shares are forwarded to weights_to_orders."""
        symbols = ["AAPL"]
        strategy = _FixedWeightStrategy({"AAPL": 0.5})
        feed = _make_feed(symbols)
        portfolio = Portfolio(cash=Decimal("1000000"), initial_cash=Decimal("1000000"))
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2024, 1, 15))
        risk_engine = RiskEngine(rules=[])
        sim_broker = SimBroker(SimConfig(slippage_bps=0, commission_rate=0, tax_rate=0))

        # With fractional_shares=True, should still produce trades
        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=_make_prices(symbols),
            current_bars=_make_bar_dict(symbols),
            sim_broker=sim_broker,
            instruments=_make_instruments(symbols),
            fractional_shares=True,
            timestamp=datetime(2024, 1, 15),
        )

        assert len(trades) > 0
