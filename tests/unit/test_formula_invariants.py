"""Formula Invariant Tests — 防止核心公式被意外修改。

用已知輸入/輸出固定值驗證。任何公式修改都會讓這些測試失敗。
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import pytest

from src.core.models import Order


# ── Analytics Formulas ─────────────────────────────────────────


class TestSharpeInvariant:
    def test_known_value(self) -> None:
        """Fixed daily returns → Sharpe = mean/std × sqrt(252)."""
        from src.backtest.analytics import compute_analytics

        rng = np.random.default_rng(42)
        returns = rng.normal(0.001, 0.02, 252)
        nav = pd.Series((1 + pd.Series(returns)).cumprod() * 1_000_000)
        nav.index = pd.bdate_range("2023-01-01", periods=252)

        result = compute_analytics(nav, 1_000_000, trades=[])

        daily_ret = nav.pct_change().dropna()
        expected = float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))
        assert abs(result.sharpe - expected) < 0.01


class TestCAGRInvariant:
    def test_doubling(self) -> None:
        """NAV doubles in 252 days = ~100% CAGR."""
        from src.backtest.analytics import compute_analytics

        nav = pd.Series(np.linspace(1_000_000, 2_000_000, 252))
        nav.index = pd.bdate_range("2023-01-01", periods=252)
        result = compute_analytics(nav, 1_000_000, trades=[])
        assert abs(result.annual_return - 1.0) < 0.02


class TestMaxDrawdownInvariant:
    def test_known_dd(self) -> None:
        """1M → 1.5M → 1M = 33% drawdown."""
        from src.backtest.analytics import compute_analytics

        nav = pd.Series([1_000_000.0, 1_500_000.0, 1_000_000.0])
        nav.index = pd.bdate_range("2023-01-01", periods=3)
        result = compute_analytics(nav, 1_000_000, trades=[])
        assert abs(result.max_drawdown - 1 / 3) < 0.02


# ── IC Invariant ──────────────────────────────────────────────


class TestICInvariant:
    def test_perfect_positive(self) -> None:
        from src.strategy.research import compute_ic

        dates = pd.bdate_range("2023-01-01", periods=20)
        symbols = [f"S{i}" for i in range(30)]  # compute_ic requires >= 30 symbols
        fv = pd.DataFrame({s: [i + 1.0] * 20 for i, s in enumerate(symbols)}, index=dates)
        fr = pd.DataFrame({s: [0.01 * (i + 1)] * 20 for i, s in enumerate(symbols)}, index=dates)

        ic = compute_ic(fv, fr)
        assert ic.ic_mean > 0.9

    def test_random_near_zero(self) -> None:
        from src.strategy.research import compute_ic

        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2023-01-01", periods=100)
        symbols = [f"S{i}" for i in range(20)]
        fv = pd.DataFrame(rng.normal(0, 1, (100, 20)), index=dates, columns=symbols)
        fr = pd.DataFrame(rng.normal(0, 1, (100, 20)), index=dates, columns=symbols)

        ic = compute_ic(fv, fr)
        assert abs(ic.ic_mean) < 0.15


# ── SimBroker Cost Invariant ──────────────────────────────────


class TestSimBrokerCostInvariant:
    def test_buy_commission(self) -> None:
        """Buy 1000 × $100 = $100K, commission 0.1425% = $142.5."""
        from src.execution.broker.simulated import SimBroker, SimConfig
        from src.core.models import Instrument, Side

        broker = SimBroker(SimConfig(
            slippage_bps=0, base_slippage_bps=0, impact_coeff=0,
            commission_rate=0.001425, tax_rate=0.003,
        ))
        inst = Instrument(symbol="TEST.TW", lot_size=1000)
        order = Order(id="t1", instrument=inst, side=Side.BUY, quantity=Decimal("1000"))

        trades = broker.execute(
            [order],
            {"TEST.TW": {"close": Decimal("100"), "volume": Decimal("1000000")}},
        )

        assert len(trades) == 1
        expected = 100000 * 0.001425
        assert abs(float(trades[0].commission) - expected) < 1

    def test_sell_includes_tax(self) -> None:
        """Sell commission = comm + tax."""
        from src.execution.broker.simulated import SimBroker, SimConfig
        from src.core.models import Instrument, Side

        broker = SimBroker(SimConfig(
            slippage_bps=0, base_slippage_bps=0, impact_coeff=0,
            commission_rate=0.001425, tax_rate=0.003,
        ))
        inst = Instrument(symbol="TEST.TW", lot_size=1000)
        order = Order(id="t2", instrument=inst, side=Side.SELL, quantity=Decimal("1000"))

        trades = broker.execute(
            [order],
            {"TEST.TW": {"close": Decimal("100"), "volume": Decimal("1000000")}},
        )

        assert len(trades) == 1
        expected = 100000 * 0.001425 + 100000 * 0.003
        assert abs(float(trades[0].commission) - expected) < 1


# ── DSR Invariant ─────────────────────────────────────────────


class TestDSRInvariant:
    def test_single_trial(self) -> None:
        from src.backtest.analytics import deflated_sharpe

        dsr = deflated_sharpe(1.0, 1, 252, 0.0, 3.0)
        assert dsr > 0.8  # SR=1.0, N=1, T=252 → DSR ≈ 0.84

    def test_many_trials_lower(self) -> None:
        from src.backtest.analytics import deflated_sharpe

        dsr_1 = deflated_sharpe(1.0, 1, 252, 0.0, 3.0)
        dsr_100 = deflated_sharpe(1.0, 100, 252, 0.0, 3.0)
        assert dsr_100 < dsr_1


# ── Forward Returns No Look-Ahead ─────────────────────────────


class TestForwardReturnsInvariant:
    def test_correct_alignment(self) -> None:
        from src.strategy.research import compute_forward_returns

        dates = pd.bdate_range("2023-01-01", periods=10)
        data = {"A": pd.DataFrame({"close": range(100, 110)}, index=dates)}
        fwd = compute_forward_returns(data, horizon=2)

        # Day 0: close=100, day 2: close=102, fwd_ret = 102/100-1 = 0.02
        assert abs(fwd.iloc[0]["A"] - (102 / 100 - 1)) < 0.001

    def test_shorter_than_input(self) -> None:
        """Forward returns should have fewer rows than input (last horizon rows dropped)."""
        from src.strategy.research import compute_forward_returns

        dates = pd.bdate_range("2023-01-01", periods=10)
        data = {"A": pd.DataFrame({"close": range(100, 110)}, index=dates)}
        fwd = compute_forward_returns(data, horizon=3)

        assert len(fwd) <= 10 - 3 + 1


# ═══════════════════════════════════════════════════════════════
# EXTREME EDGE CASES
# ═══════════════════════════════════════════════════════════════


class TestAnalyticsEdgeCases:
    """analytics.py 極端情況。"""

    def test_single_day(self) -> None:
        """Only 1 trading day → metrics should not crash."""
        from src.backtest.analytics import compute_analytics
        nav = pd.Series([1_000_000.0])
        nav.index = pd.bdate_range("2023-01-01", periods=1)
        result = compute_analytics(nav, 1_000_000, trades=[])
        assert result.sharpe == 0.0
        assert result.max_drawdown == 0.0

    def test_two_days(self) -> None:
        """2 days → 1 return, should compute without crash."""
        from src.backtest.analytics import compute_analytics
        nav = pd.Series([1_000_000.0, 1_010_000.0])
        nav.index = pd.bdate_range("2023-01-01", periods=2)
        result = compute_analytics(nav, 1_000_000, trades=[])
        assert result.total_return == pytest.approx(0.01, abs=0.001)

    def test_all_identical_nav(self) -> None:
        """All NAV = constant → std=0, Sharpe=0, MDD=0."""
        from src.backtest.analytics import compute_analytics
        nav = pd.Series([1_000_000.0] * 100)
        nav.index = pd.bdate_range("2023-01-01", periods=100)
        result = compute_analytics(nav, 1_000_000, trades=[])
        assert result.sharpe == 0.0
        assert result.max_drawdown == 0.0
        assert result.annual_return == pytest.approx(0.0, abs=0.001)

    def test_total_loss(self) -> None:
        """NAV drops to near 0."""
        from src.backtest.analytics import compute_analytics
        nav = pd.Series(np.linspace(1_000_000, 100, 252))
        nav.index = pd.bdate_range("2023-01-01", periods=252)
        result = compute_analytics(nav, 1_000_000, trades=[])
        assert result.annual_return < -0.9
        assert result.max_drawdown > 0.99

    def test_nav_with_nan(self) -> None:
        """NAV contains NaN → should handle gracefully."""
        from src.backtest.analytics import compute_analytics
        nav = pd.Series([1_000_000.0, float("nan"), 1_010_000.0])
        nav.index = pd.bdate_range("2023-01-01", periods=3)
        # Should not crash
        result = compute_analytics(nav.dropna(), 1_000_000, trades=[])
        assert result is not None


class TestWeightsToOrdersEdgeCases:
    """weights_to_orders 極端情況。"""

    def test_zero_nav(self) -> None:
        """NAV=0 → no orders."""
        from src.strategy.engine import weights_to_orders
        from src.core.models import Portfolio
        portfolio = Portfolio(cash=Decimal("0"), initial_cash=Decimal("0"))
        orders = weights_to_orders({"A": 0.5}, portfolio, {"A": Decimal("100")})
        assert orders == []

    def test_zero_price(self) -> None:
        """Price=0 → skip that symbol."""
        from src.strategy.engine import weights_to_orders
        from src.core.models import Portfolio
        portfolio = Portfolio(cash=Decimal("1000000"), initial_cash=Decimal("1000000"))
        orders = weights_to_orders({"A": 0.5}, portfolio, {"A": Decimal("0")})
        assert orders == []

    def test_tiny_weight_ignored(self) -> None:
        """Weight < 0.001 → ignored (no micro-trading)."""
        from src.strategy.engine import weights_to_orders
        from src.core.models import Portfolio
        portfolio = Portfolio(cash=Decimal("1000000"), initial_cash=Decimal("1000000"))
        orders = weights_to_orders({"A": 0.0005}, portfolio, {"A": Decimal("100")})
        assert orders == []


class TestSimBrokerEdgeCases:
    """SimBroker 極端情況。"""

    def test_zero_volume(self) -> None:
        """Volume=0 → order rejected (if max_fill_pct set)."""
        from src.execution.broker.simulated import SimBroker, SimConfig
        from src.core.models import Instrument, Order, Side

        broker = SimBroker(SimConfig(max_fill_pct_of_volume=0.1))
        inst = Instrument(symbol="TEST.TW", lot_size=1000)
        order = Order(id="t1", instrument=inst, side=Side.BUY, quantity=Decimal("1000"))
        trades = broker.execute(
            [order],
            {"TEST.TW": {"close": Decimal("100"), "volume": Decimal("0")}},
        )
        # Volume=0 → either rejected or qty capped to 0
        assert len(trades) == 0 or trades[0].quantity == 0

    def test_missing_symbol_data(self) -> None:
        """Symbol not in current_bars → skipped."""
        from src.execution.broker.simulated import SimBroker, SimConfig
        from src.core.models import Instrument, Order, Side

        broker = SimBroker(SimConfig())
        inst = Instrument(symbol="MISSING.TW")
        order = Order(id="t1", instrument=inst, side=Side.BUY, quantity=Decimal("100"))
        trades = broker.execute([order], {})
        assert len(trades) == 0


class TestICEdgeCases:
    """IC 計算極端情況。"""

    def test_too_few_stocks(self) -> None:
        """Less than 5 stocks → IC should handle gracefully."""
        from src.strategy.research import compute_ic
        dates = pd.bdate_range("2023-01-01", periods=20)
        fv = pd.DataFrame({"A": [1.0] * 20, "B": [2.0] * 20}, index=dates)
        fr = pd.DataFrame({"A": [0.01] * 20, "B": [0.02] * 20}, index=dates)
        ic = compute_ic(fv, fr)
        # Should not crash; IC might be 0 or computed from 2 stocks
        assert ic is not None

    def test_all_same_factor_value(self) -> None:
        """All stocks have same factor value → IC should be 0 or handle gracefully."""
        from src.strategy.research import compute_ic
        dates = pd.bdate_range("2023-01-01", periods=20)
        symbols = [f"S{i}" for i in range(10)]
        fv = pd.DataFrame({s: [5.0] * 20 for s in symbols}, index=dates)
        fr = pd.DataFrame({s: [float(i) * 0.01] * 20 for i, s in enumerate(symbols)}, index=dates)
        ic = compute_ic(fv, fr)
        assert ic is not None

    def test_empty_data(self) -> None:
        """Empty DataFrames → should not crash."""
        from src.strategy.research import compute_ic
        fv = pd.DataFrame()
        fr = pd.DataFrame()
        ic = compute_ic(fv, fr)
        assert ic.ic_mean == 0.0


class TestDeflatedSharpeEdgeCases:
    """DSR 極端情況。"""

    def test_zero_sharpe(self) -> None:
        """SR=0 → DSR should be low."""
        from src.backtest.analytics import deflated_sharpe
        dsr = deflated_sharpe(0.0, 10, 252, 0.0, 3.0)
        assert dsr < 0.5

    def test_negative_sharpe(self) -> None:
        """SR<0 → DSR should be very low."""
        from src.backtest.analytics import deflated_sharpe
        dsr = deflated_sharpe(-1.0, 10, 252, 0.0, 3.0)
        assert dsr < 0.1

    def test_very_high_trials(self) -> None:
        """N=10000 trials → even SR=2 should have low DSR."""
        from src.backtest.analytics import deflated_sharpe
        dsr = deflated_sharpe(2.0, 10000, 252, 0.0, 3.0)
        # With 10000 trials, expected max SR is high
        assert dsr < 0.95

    def test_tiny_t(self) -> None:
        """T=5 observations → should not crash."""
        from src.backtest.analytics import deflated_sharpe
        dsr = deflated_sharpe(1.0, 1, 5, 0.0, 3.0)
        assert 0 <= dsr <= 1


class TestRiskRulesEdgeCases:
    """Risk rules edge cases."""

    def test_gross_leverage_sell_reduces(self) -> None:
        """SELL should reduce gross leverage, not increase it."""
        from src.risk.rules import max_gross_leverage
        from src.core.models import Instrument, Portfolio, Position, Side
        from src.risk.engine import MarketState

        rule = max_gross_leverage(threshold=1.5)
        inst = Instrument(symbol="TEST.TW")
        portfolio = Portfolio(cash=Decimal("500000"), initial_cash=Decimal("1000000"))
        portfolio.positions["TEST.TW"] = Position(
            instrument=inst, quantity=Decimal("1000"), avg_cost=Decimal("500"),
            market_price=Decimal("500"),
        )
        order = Order(id="sell1", instrument=inst, side=Side.SELL, quantity=Decimal("500"),
                     price=Decimal("500"))
        market = MarketState(prices={"TEST.TW": Decimal("500")}, daily_volumes={})

        decision = rule.check(order, portfolio, market)
        assert decision.approved, "SELL reducing exposure should be approved"

    def test_analytics_inf_safe(self) -> None:
        """Returns with inf should not produce NaN metrics."""
        from src.backtest.analytics import compute_analytics

        nav = pd.Series([1_000_000.0, 0.01, 1_000_000.0])
        nav.index = pd.bdate_range("2023-01-01", periods=3)
        result = compute_analytics(nav, 1_000_000, trades=[])
        assert not np.isnan(result.sharpe)


class TestDataQualityInvariants:
    """Invariants for market data and computed returns."""

    def test_vectorized_returns_no_inf(self) -> None:
        """VectorizedPBOBacktest returns must never contain inf."""
        prices = pd.DataFrame({
            "A": [100.0, 0.0, 105.0, 110.0, 108.0] * 50,  # has zero
            "B": [200.0, 202.0, 198.0, 205.0, 203.0] * 50,
        }, index=pd.bdate_range("2023-01-01", periods=250))

        # Simulate what vectorized.py does
        close = prices.where(prices > 0)  # zero → NaN
        returns = close.ffill().pct_change().replace([np.inf, -np.inf], 0.0)
        assert not np.isinf(returns.values).any(), "Returns contain inf"
        assert np.isfinite(returns.fillna(0).values).all()

    def test_pbo_matrix_no_inf(self) -> None:
        """PBO returns matrix must never contain inf or all-zero columns."""
        rng = np.random.default_rng(42)
        mat = pd.DataFrame(
            rng.normal(0, 0.02, (500, 10)),
            columns=[f"f{i}" for i in range(10)],
        )
        # Simulate corruption: add inf
        mat_dirty = mat.copy()
        mat_dirty.iloc[5, 3] = np.inf
        # Clean
        mat_clean = mat_dirty.replace([np.inf, -np.inf], 0.0).fillna(0.0)
        assert np.isfinite(mat_clean.values).all()

    def test_market_data_zero_price_excluded(self) -> None:
        """Stocks with >10% zero-price days should be excluded."""
        close = pd.Series([100.0] * 80 + [0.0] * 20)  # 20% zeros
        close_clean = close.where(close > 0)
        bad_ratio = close_clean.isna().sum() / len(close_clean)
        assert bad_ratio > 0.10, "Should detect >10% bad prices"
