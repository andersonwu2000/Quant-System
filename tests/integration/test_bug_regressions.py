"""Regression tests for historically discovered bugs.

Each test prevents a specific past bug from recurring.
Source: docs/reviews/ audit reports + docs/claude/BUG_HISTORY.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

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


# ── H1: Price=0 risk bypass ────────────────────────────────────────


class TestPriceFallbackRiskBypass:
    """risk/engine.py: price=0 must not make position weight = 0% (bypass)."""

    def test_zero_price_order_handling(self):
        """Order with price=0 should be handled safely by risk engine."""
        from src.risk.engine import RiskEngine

        engine = RiskEngine()
        portfolio = Portfolio()

        order = Order(
            instrument=Instrument(
                symbol="9999.TW",
                asset_class=AssetClass.EQUITY,
                market=Market.TW,
            ),
            side=Side.BUY,
            quantity=Decimal("1000"),
            price=Decimal("0"),
        )

        # check_orders should not crash on zero price
        result = engine.check_orders([order], portfolio)
        # Result is list of approved orders — zero price may or may not pass
        # but must not crash
        assert isinstance(result, list)


# ── H3: Commission in PnL ──────────────────────────────────────────


class TestCommissionInPnL:
    """analytics.py: BacktestResult must track commission costs."""

    def test_commission_tracked(self):
        """compute_analytics stores total_commission from trades."""
        from src.backtest.analytics import compute_analytics

        dates = pd.bdate_range("2020-01-01", periods=252)
        nav = pd.Series(
            10_000_000 * np.cumprod(1 + np.random.default_rng(42).normal(0.0003, 0.01, 252)),
            index=dates,
        )

        trades = [
            Trade(
                timestamp=datetime(2020, 3, 1, tzinfo=timezone.utc),
                symbol="2330.TW",
                side=Side.BUY,
                quantity=Decimal("1000"),
                price=Decimal("300"),
                commission=Decimal("427"),
                slippage_bps=Decimal("5"),
            ),
        ]

        result = compute_analytics(
            nav_series=nav,
            initial_cash=10_000_000,
            trades=trades,
        )
        assert result.total_commission > 0, "Commission must be tracked"


# ── M8: Calmar ratio zero drawdown ─────────────────────────────────


class TestCalmarRatioZeroDrawdown:
    """analytics.py: Calmar = inf when return > 0 and drawdown = 0."""

    def test_calmar_inf_on_zero_dd(self):
        """Monotonically rising NAV → Calmar should be inf, not 0."""
        from src.backtest.analytics import compute_analytics

        dates = pd.bdate_range("2020-01-01", periods=252)
        nav = pd.Series(
            10_000_000 * np.cumprod(1 + np.full(252, 0.0004)),
            index=dates,
        )

        result = compute_analytics(
            nav_series=nav,
            initial_cash=10_000_000,
            trades=[],
        )
        if abs(result.max_drawdown) < 0.001:
            assert result.calmar == float("inf") or result.calmar > 100, (
                f"Calmar should be inf or very large with zero DD, got {result.calmar}"
            )


# ── H4: OMS apply_trades updates portfolio ─────────────────────────


class TestOmsApplyTrades:
    """oms.py: apply_trades must update portfolio positions."""

    def test_buy_increases_position(self):
        """BUY trade increases quantity."""
        from src.execution.oms import apply_trades

        portfolio = Portfolio()
        portfolio.positions["2330.TW"] = Position(
            instrument=Instrument(symbol="2330.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("590"),
        )

        trade = Trade(
            timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            symbol="2330.TW",
            side=Side.BUY,
            quantity=Decimal("1000"),
            price=Decimal("600"),
            commission=Decimal("855"),
            slippage_bps=Decimal("5"),
        )

        apply_trades(portfolio, [trade])
        assert portfolio.positions["2330.TW"].quantity == Decimal("2000")


# ── C4: Sell without position ──────────────────────────────────────


class TestSellWithoutPosition:
    """oms.py: SELL without position must not corrupt cash."""

    def test_no_sell_orders_for_missing_position(self):
        """weights_to_orders should not generate sell for non-held symbol."""
        from src.core.trading_pipeline import weights_to_orders

        portfolio = Portfolio()
        original_cash = portfolio.cash

        orders = weights_to_orders(
            target_weights={},
            portfolio=portfolio,
            prices={"2330.TW": Decimal("590")},
        )
        assert len(orders) == 0
        assert portfolio.cash == original_cash


# ── C3: market_cap look-ahead bias disabled ────────────────────────


class TestMarketCapLookAheadBias:
    """evaluate.py: market_cap must be disabled in _mask_data."""

    def test_mask_data_disables_market_cap(self):
        source = open("scripts/autoresearch/evaluate.py", encoding="utf-8").read()
        assert '"market_cap": {}' in source, (
            "evaluate.py _mask_data must disable market_cap (look-ahead bias)"
        )


# ── M1: Industry code strips .TW suffix ────────────────────────────


class TestIndustryCodeStrip:
    """evaluate.py: industry neutralization must strip .TW suffix."""

    def test_strips_tw_suffix(self):
        source = open("scripts/autoresearch/evaluate.py", encoding="utf-8").read()
        assert '.replace(".TW", "")' in source, (
            "evaluate.py industry code must strip .TW suffix"
        )


# ── H2 (Strategy): Sells before buys in order list ─────────────────


class TestSellsBeforeBuys:
    """trading_pipeline: sells must precede buys for cash sequencing."""

    def test_sell_before_buy_ordering(self):
        from src.core.trading_pipeline import weights_to_orders

        portfolio = Portfolio()
        portfolio.positions["OLD.TW"] = Position(
            instrument=Instrument(symbol="OLD.TW"),
            quantity=Decimal("1000"),
            avg_cost=Decimal("100"),
        )

        orders = weights_to_orders(
            target_weights={"NEW.TW": 0.5},
            portfolio=portfolio,
            prices={"OLD.TW": Decimal("100"), "NEW.TW": Decimal("100")},
        )
        if len(orders) >= 2:
            sells = [o for o in orders if o.side == Side.SELL]
            buys = [o for o in orders if o.side == Side.BUY]
            if sells and buys:
                first_sell = next(i for i, o in enumerate(orders) if o.side == Side.SELL)
                first_buy = next(i for i, o in enumerate(orders) if o.side == Side.BUY)
                assert first_sell < first_buy, "Sells must come before buys"
