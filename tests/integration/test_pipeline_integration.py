"""
Integration test — full trading pipeline end-to-end.

Tests the complete flow:
  Strategy.on_bar() → weights_to_orders() → RiskEngine.check_orders()
  → SimBroker.execute() → apply_trades() → Portfolio updated

Also tests the unified execute_one_bar() entry point.

Self-contained, no network access, uses synthetic data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from src.core.models import (
    AssetClass,
    Instrument,
    Market,
    Order,
    OrderStatus,
    Portfolio,
    Position,
    Side,
    Trade,
)
from src.core.trading_pipeline import execute_one_bar
from src.data.feed import DataFeed
from src.execution.broker.simulated import SimBroker, SimConfig
from src.execution.oms import apply_trades
from src.risk.engine import RiskEngine
from src.risk.rules import (
    MarketState,
    default_rules,
    max_position_weight,
    max_order_notional,
    daily_drawdown_limit,
)
from src.strategy.base import Context, Strategy
from src.strategy.engine import weights_to_orders


# ─── Constants ───────────────────────────────────────────

TW50_SYMBOLS = ["2330.TW", "2317.TW", "2454.TW", "2881.TW", "2882.TW"]

INITIAL_CASH = Decimal("10000000")  # $10M TWD

# Realistic prices for the 5 TW50 stocks
STOCK_PRICES: dict[str, Decimal] = {
    "2330.TW": Decimal("580"),   # TSMC
    "2317.TW": Decimal("105"),   # Hon Hai
    "2454.TW": Decimal("950"),   # MediaTek
    "2881.TW": Decimal("62"),    # Fubon FHC
    "2882.TW": Decimal("44"),    # Cathay FHC
}

STOCK_VOLUMES: dict[str, Decimal] = {
    "2330.TW": Decimal("30000000"),
    "2317.TW": Decimal("25000000"),
    "2454.TW": Decimal("8000000"),
    "2881.TW": Decimal("15000000"),
    "2882.TW": Decimal("20000000"),
}


# ─── Test Instruments ────────────────────────────────────

def _make_instruments() -> dict[str, Instrument]:
    return {
        sym: Instrument(
            symbol=sym,
            name=sym.split(".")[0],
            asset_class=AssetClass.EQUITY,
            market=Market.TW,
            currency="TWD",
            lot_size=1000,
            commission_rate=Decimal("0.001425"),
            tax_rate=Decimal("0.003"),
        )
        for sym in TW50_SYMBOLS
    }


# ─── Fake DataFeed ───────────────────────────────────────

class FakeDataFeed(DataFeed):
    """Minimal DataFeed backed by synthetic OHLCV data (no network)."""

    def __init__(self, symbols: list[str], prices: dict[str, Decimal], n_bars: int = 60):
        self._symbols = symbols
        self._prices = prices
        self._bars_cache: dict[str, pd.DataFrame] = {}
        self._n_bars = n_bars
        self._build_bars()

    def _build_bars(self) -> None:
        dates = pd.bdate_range(end="2025-12-31", periods=self._n_bars, freq="B")
        for sym in self._symbols:
            base = float(self._prices[sym])
            # Random walk around the base price
            rng = np.random.default_rng(hash(sym) % (2**31))
            returns = rng.normal(0, 0.015, self._n_bars)
            closes = base * np.exp(np.cumsum(returns))
            # Force the last close to match the known price
            closes[-1] = base
            df = pd.DataFrame(
                {
                    "open": closes * (1 + rng.uniform(-0.01, 0.01, self._n_bars)),
                    "high": closes * (1 + rng.uniform(0, 0.02, self._n_bars)),
                    "low": closes * (1 - rng.uniform(0, 0.02, self._n_bars)),
                    "close": closes,
                    "volume": rng.integers(5_000_000, 40_000_000, self._n_bars).astype(float),
                },
                index=dates,
            )
            self._bars_cache[sym] = df

    def get_bars(
        self,
        symbol: str,
        start: datetime | str | None = None,
        end: datetime | str | None = None,
        freq: str = "1d",
    ) -> pd.DataFrame:
        return self._bars_cache.get(symbol, pd.DataFrame())

    def get_latest_price(self, symbol: str) -> Decimal:
        return self._prices.get(symbol, Decimal("0"))

    def get_universe(self) -> list[str]:
        return list(self._symbols)


# ─── Mock Strategy ───────────────────────────────────────

class EqualWeightStrategy(Strategy):
    """Equal-weight strategy over a fixed universe — deterministic for testing."""

    def __init__(self, symbols: list[str]):
        self._symbols = symbols

    def name(self) -> str:
        return "test_equal_weight"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        n = len(self._symbols)
        if n == 0:
            return {}
        w = 1.0 / n  # 20% each for 5 stocks
        return {sym: w for sym in self._symbols}


class ConcentratedStrategy(Strategy):
    """Put 60% into one stock — designed to trigger risk limits."""

    def __init__(self, symbol: str):
        self._symbol = symbol

    def name(self) -> str:
        return "test_concentrated"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        return {self._symbol: 0.60}


# ─── Fixtures ────────────────────────────────────────────

@pytest.fixture
def instruments() -> dict[str, Instrument]:
    return _make_instruments()


@pytest.fixture
def feed() -> FakeDataFeed:
    return FakeDataFeed(TW50_SYMBOLS, STOCK_PRICES)


@pytest.fixture
def portfolio() -> Portfolio:
    return Portfolio(
        cash=INITIAL_CASH,
        initial_cash=INITIAL_CASH,
        nav_sod=INITIAL_CASH,
    )


@pytest.fixture
def sim_config() -> SimConfig:
    return SimConfig(
        slippage_bps=5.0,
        commission_rate=0.001425,
        tax_rate=0.003,
        impact_model="fixed",
        partial_fill=False,
        max_fill_pct_of_volume=0.10,
    )


@pytest.fixture
def sim_broker(sim_config: SimConfig) -> SimBroker:
    return SimBroker(config=sim_config)


@pytest.fixture
def risk_engine() -> RiskEngine:
    """Risk engine with permissive position limit (25%) for equal-weight tests."""
    rules = [
        max_position_weight(0.25),
        max_order_notional(0.50),
        daily_drawdown_limit(0.03),
    ]
    return RiskEngine(rules=rules)


@pytest.fixture
def strict_risk_engine() -> RiskEngine:
    """Risk engine with default strict 5% position limit for rejection tests."""
    return RiskEngine(rules=default_rules())


@pytest.fixture
def current_bars() -> dict[str, dict]:
    """Bar data dict expected by SimBroker.execute()."""
    return {
        sym: {
            "close": float(price),
            "volume": float(STOCK_VOLUMES[sym]),
        }
        for sym, price in STOCK_PRICES.items()
    }


@pytest.fixture
def market_lot_sizes() -> dict[str, int]:
    return {".TW": 1000}


# ─── Tests: Step-by-step pipeline ────────────────────────


class TestStepByStepPipeline:
    """Test each pipeline stage individually, then the whole chain."""

    def test_strategy_produces_weights(self, feed: FakeDataFeed, portfolio: Portfolio):
        """Stage 1: strategy.on_bar() returns valid target weights."""
        strategy = EqualWeightStrategy(TW50_SYMBOLS)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        weights = strategy.on_bar(ctx)

        assert len(weights) == 5
        for sym in TW50_SYMBOLS:
            assert sym in weights
            assert abs(weights[sym] - 0.20) < 1e-9
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_weights_to_orders_generates_buy_orders(
        self, portfolio: Portfolio, instruments: dict[str, Instrument]
    ):
        """Stage 2: weights_to_orders() converts weights to Order objects."""
        target_weights = {sym: 0.20 for sym in TW50_SYMBOLS}

        orders = weights_to_orders(
            target_weights,
            portfolio,
            STOCK_PRICES,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )

        # Phase AM: odd-lot orders may be generated for remainders
        round_lot_orders = [o for o in orders if o.order_lot.value == "COMMON"]
        odd_lot_orders = [o for o in orders if o.order_lot.value == "ODD_LOT"]
        assert len(round_lot_orders) + len(odd_lot_orders) == len(orders)
        assert len(round_lot_orders) <= 5
        for order in round_lot_orders:
            assert order.side == Side.BUY
            assert order.quantity > 0
            assert order.quantity % 1000 == 0, "TW stock round-lot orders must be in round lots"
            assert order.order_type.value == "MARKET"
            assert order.instrument.symbol in TW50_SYMBOLS

    def test_risk_engine_approves_balanced_orders(
        self,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        instruments: dict[str, Instrument],
    ):
        """Stage 3: RiskEngine approves orders within limits."""
        target_weights = {sym: 0.20 for sym in TW50_SYMBOLS}
        orders = weights_to_orders(
            target_weights,
            portfolio,
            STOCK_PRICES,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )

        market_state = MarketState(
            prices=STOCK_PRICES,
            daily_volumes=STOCK_VOLUMES,
        )
        approved = risk_engine.check_orders(orders, portfolio, market_state)

        # All 5 orders should pass risk checks (20% each is reasonable)
        assert len(approved) == len(orders)

    def test_sim_broker_executes_orders(
        self,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
        portfolio: Portfolio,
    ):
        """Stage 4: SimBroker fills orders and produces Trade objects."""
        target_weights = {sym: 0.20 for sym in TW50_SYMBOLS}
        orders = weights_to_orders(
            target_weights,
            portfolio,
            STOCK_PRICES,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )
        ts = datetime(2025, 12, 31, tzinfo=timezone.utc)

        trades = sim_broker.execute(orders, current_bars, timestamp=ts)

        assert len(trades) == 5
        for trade in trades:
            assert trade.quantity > 0
            assert trade.price > 0
            assert trade.commission > 0
            assert trade.symbol in TW50_SYMBOLS
            assert trade.timestamp == ts

        # All orders should be FILLED
        for order in orders:
            assert order.status == OrderStatus.FILLED

    def test_apply_trades_updates_portfolio(
        self,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
        portfolio: Portfolio,
    ):
        """Stage 5: apply_trades() updates cash and positions correctly."""
        target_weights = {sym: 0.20 for sym in TW50_SYMBOLS}
        orders = weights_to_orders(
            target_weights,
            portfolio,
            STOCK_PRICES,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )

        trades = sim_broker.execute(orders, current_bars)
        initial_cash = portfolio.cash

        apply_trades(portfolio, trades)

        # Cash should have decreased (we bought stocks)
        assert portfolio.cash < initial_cash

        # Should have 5 positions
        assert len(portfolio.positions) == 5
        for sym in TW50_SYMBOLS:
            assert sym in portfolio.positions
            pos = portfolio.positions[sym]
            assert pos.quantity > 0
            assert pos.market_price > 0

        # NAV should be close to initial (only slippage + commission lost)
        nav = portfolio.nav
        assert nav < INITIAL_CASH, "NAV should be slightly below initial due to costs"
        cost_ratio = float((INITIAL_CASH - nav) / INITIAL_CASH)
        assert cost_ratio < 0.01, f"Transaction costs {cost_ratio:.4%} should be < 1%"


class TestFullPipelineChain:
    """Test the complete chain from strategy signal to portfolio update."""

    def test_full_chain_equal_weight(
        self,
        feed: FakeDataFeed,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """Run the entire pipeline manually and verify end state."""
        strategy = EqualWeightStrategy(TW50_SYMBOLS)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        # 1. Strategy
        weights = strategy.on_bar(ctx)
        assert len(weights) == 5

        # 2. Orders
        orders = weights_to_orders(
            weights, portfolio, STOCK_PRICES,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )
        assert len(orders) > 0

        # 3. Risk
        market_state = MarketState(prices=STOCK_PRICES, daily_volumes=STOCK_VOLUMES)
        approved = risk_engine.check_orders(orders, portfolio, market_state)
        assert len(approved) > 0

        # 4. Execute
        trades = sim_broker.execute(approved, current_bars)
        assert len(trades) > 0

        # 5. Apply
        apply_trades(portfolio, trades)

        # Verify final state
        assert len(portfolio.positions) == 5
        assert portfolio.cash < INITIAL_CASH
        assert portfolio.cash > 0, "Should still have some cash after buying"

        # Check position weights are roughly equal
        for sym in TW50_SYMBOLS:
            w = float(portfolio.get_position_weight(sym))
            assert 0.10 < w < 0.30, f"{sym} weight {w:.2%} should be roughly 20%"

    def test_sell_then_buy_rebalance(
        self,
        feed: FakeDataFeed,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """Rebalance an existing portfolio: sell overweight, buy underweight."""
        # Start with a moderately overweight TSMC position (~40% of NAV)
        tsmc = instruments["2330.TW"]
        cash = Decimal("6000000")
        tsmc_qty = Decimal("4000")
        tsmc_mv = tsmc_qty * Decimal("580")  # 2.32M
        nav = cash + tsmc_mv  # ~8.32M
        portfolio = Portfolio(
            cash=cash,
            initial_cash=nav,
            nav_sod=nav,
            positions={
                "2330.TW": Position(
                    instrument=tsmc,
                    quantity=tsmc_qty,
                    avg_cost=Decimal("550"),
                    market_price=Decimal("580"),
                ),
            },
        )

        # Use a permissive risk engine for rebalance (no notional cap issues)
        rebalance_risk = RiskEngine(rules=[
            max_position_weight(0.30),
            daily_drawdown_limit(0.05),
        ])

        strategy = EqualWeightStrategy(TW50_SYMBOLS)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        weights = strategy.on_bar(ctx)
        orders = weights_to_orders(
            weights, portfolio, STOCK_PRICES,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )

        # Should have both BUY and SELL orders
        buy_orders = [o for o in orders if o.side == Side.BUY]
        sell_orders = [o for o in orders if o.side == Side.SELL]
        assert len(buy_orders) >= 3, "Should buy into new positions"
        assert len(sell_orders) >= 1, "Should sell some TSMC (overweight)"

        # Execute full chain
        market_state = MarketState(prices=STOCK_PRICES, daily_volumes=STOCK_VOLUMES)
        approved = rebalance_risk.check_orders(orders, portfolio, market_state)
        trades = sim_broker.execute(approved, current_bars)
        apply_trades(portfolio, trades)

        # After rebalance, should have positions in most/all 5 stocks
        assert len(portfolio.positions) >= 4
        # TSMC weight should be closer to 20% (down from ~28%)
        if "2330.TW" in portfolio.positions:
            tsmc_w = float(portfolio.get_position_weight("2330.TW"))
            assert tsmc_w < 0.35, "TSMC weight should be reduced toward equal weight"


class TestExecuteOneBar:
    """Test the unified execute_one_bar() entry point from trading_pipeline.py."""

    def test_execute_one_bar_produces_trades(
        self,
        feed: FakeDataFeed,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """execute_one_bar() orchestrates the full pipeline in one call."""
        strategy = EqualWeightStrategy(TW50_SYMBOLS)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=STOCK_PRICES,
            volumes=STOCK_VOLUMES,
            current_bars=current_bars,
            sim_broker=sim_broker,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
            timestamp=datetime(2025, 12, 31, tzinfo=timezone.utc),
        )

        # Trades produced
        assert len(trades) == 5
        for t in trades:
            assert isinstance(t, Trade)
            assert t.quantity > 0
            assert t.commission > 0

        # Portfolio mutated
        assert len(portfolio.positions) == 5
        assert portfolio.cash < INITIAL_CASH
        assert portfolio.nav > 0

    def test_execute_one_bar_empty_weights(
        self,
        feed: FakeDataFeed,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """If strategy returns empty weights, no trades should occur."""

        class EmptyStrategy(Strategy):
            def name(self) -> str:
                return "empty"

            def on_bar(self, ctx: Context) -> dict[str, float]:
                return {}

        ctx = Context(feed=feed, portfolio=portfolio)
        trades = execute_one_bar(
            strategy=EmptyStrategy(),
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=STOCK_PRICES,
            current_bars=current_bars,
            sim_broker=sim_broker,
        )

        assert trades == []
        assert portfolio.cash == INITIAL_CASH
        assert len(portfolio.positions) == 0

    def test_execute_one_bar_no_broker_returns_empty(
        self,
        feed: FakeDataFeed,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        instruments: dict[str, Instrument],
    ):
        """Without a SimBroker, execute_one_bar returns empty list."""
        strategy = EqualWeightStrategy(TW50_SYMBOLS)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=STOCK_PRICES,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
            sim_broker=None,
            current_bars=None,
        )

        assert trades == []


class TestRiskRejection:
    """Test that risk engine correctly rejects or modifies dangerous orders."""

    def test_concentrated_position_gets_partial_rejection(
        self,
        feed: FakeDataFeed,
        portfolio: Portfolio,
        strict_risk_engine: RiskEngine,
        instruments: dict[str, Instrument],
    ):
        """A strategy requesting 60% in one stock should trigger risk limits."""
        strategy = ConcentratedStrategy("2330.TW")
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        weights = strategy.on_bar(ctx)
        orders = weights_to_orders(
            weights, portfolio, STOCK_PRICES,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )

        # Default max_position_weight is 5% — 60% should be rejected or modified
        market_state = MarketState(prices=STOCK_PRICES, daily_volumes=STOCK_VOLUMES)
        approved = strict_risk_engine.check_orders(orders, portfolio, market_state)

        # The order should either be rejected (empty list) or modified to a smaller qty
        if len(approved) == 0:
            # Rejected entirely — expected with default 5% limit
            pass
        else:
            # Modified qty — the approved order should have reduced quantity
            order = approved[0]
            projected_weight = float(
                order.quantity * STOCK_PRICES["2330.TW"] / portfolio.nav
            )
            assert projected_weight <= 0.10, (
                f"Approved weight {projected_weight:.2%} should be capped by risk"
            )

    def test_kill_switch_detection(self, portfolio: Portfolio, risk_engine: RiskEngine):
        """Kill switch triggers when daily drawdown exceeds 5%."""
        # Simulate a big loss: NAV dropped from 10M SOD to 9.4M
        portfolio.nav_sod = INITIAL_CASH
        portfolio.cash = Decimal("9400000")  # 6% drawdown
        assert risk_engine.kill_switch(portfolio) is True

    def test_no_kill_switch_normal(self, portfolio: Portfolio, risk_engine: RiskEngine):
        """Kill switch should NOT trigger under normal conditions."""
        portfolio.nav_sod = INITIAL_CASH
        assert risk_engine.kill_switch(portfolio) is False


class TestTransactionCosts:
    """Verify that transaction costs are correctly applied."""

    def test_commission_and_tax_on_sell(
        self,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """Sell orders should incur both commission and tax."""
        sell_order = Order(
            instrument=instruments["2330.TW"],
            side=Side.SELL,
            quantity=Decimal("1000"),
            price=Decimal("580"),
        )

        trades = sim_broker.execute([sell_order], current_bars)
        assert len(trades) == 1

        trade = trades[0]
        notional = trade.quantity * trade.price
        # Commission should include both commission_rate and tax_rate
        expected_min_commission = float(notional) * (0.001425 + 0.003) * 0.8
        assert float(trade.commission) > expected_min_commission

    def test_commission_only_on_buy(
        self,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """Buy orders should incur commission but NOT tax."""
        buy_order = Order(
            instrument=instruments["2330.TW"],
            side=Side.BUY,
            quantity=Decimal("1000"),
            price=Decimal("580"),
        )

        trades = sim_broker.execute([buy_order], current_bars)
        assert len(trades) == 1

        trade = trades[0]
        notional = trade.quantity * trade.price
        # Commission = commission_rate only (no tax on buy)
        expected_max = float(notional) * 0.001425 * 1.5  # generous upper bound
        assert float(trade.commission) < expected_max


class TestPortfolioConsistency:
    """Verify portfolio accounting invariants after trades."""

    def test_nav_conservation(
        self,
        feed: FakeDataFeed,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """NAV before trades ~= NAV after trades + total costs (conservation)."""
        nav_before = portfolio.nav

        strategy = EqualWeightStrategy(TW50_SYMBOLS)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        trades = execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=STOCK_PRICES,
            volumes=STOCK_VOLUMES,
            current_bars=current_bars,
            sim_broker=sim_broker,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )

        nav_after = portfolio.nav
        total_commission = sum(t.commission for t in trades)

        # NAV drop should be approximately equal to total costs
        # (there is also slippage embedded in position market_price vs close)
        nav_drop = nav_before - nav_after
        assert nav_drop >= 0, "NAV should not increase from buying (costs exist)"
        assert nav_drop < nav_before * Decimal("0.01"), "NAV drop should be < 1%"

        # Commission should be positive and reasonable
        assert total_commission > 0
        commission_ratio = float(total_commission / nav_before)
        assert commission_ratio < 0.005, f"Commission ratio {commission_ratio:.4%} too high"

    def test_cash_plus_positions_equals_nav(
        self,
        feed: FakeDataFeed,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """Portfolio.nav == cash + sum(position.market_value) after trades."""
        strategy = EqualWeightStrategy(TW50_SYMBOLS)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=STOCK_PRICES,
            volumes=STOCK_VOLUMES,
            current_bars=current_bars,
            sim_broker=sim_broker,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )

        # NAV identity: cash + sum(market_value) == nav
        total_mv = sum(p.market_value for p in portfolio.positions.values())
        expected_nav = portfolio.cash + total_mv
        assert portfolio.nav == expected_nav

    def test_no_negative_cash_after_buying(
        self,
        feed: FakeDataFeed,
        portfolio: Portfolio,
        risk_engine: RiskEngine,
        sim_broker: SimBroker,
        instruments: dict[str, Instrument],
        current_bars: dict[str, dict],
    ):
        """Cash should remain non-negative after reasonable allocations."""
        strategy = EqualWeightStrategy(TW50_SYMBOLS)
        ctx = Context(feed=feed, portfolio=portfolio, current_time=datetime(2025, 12, 31))

        execute_one_bar(
            strategy=strategy,
            ctx=ctx,
            portfolio=portfolio,
            risk_engine=risk_engine,
            prices=STOCK_PRICES,
            volumes=STOCK_VOLUMES,
            current_bars=current_bars,
            sim_broker=sim_broker,
            instruments=instruments,
            market_lot_sizes={".TW": 1000},
        )

        assert portfolio.cash >= 0, f"Cash is negative: {portfolio.cash}"
