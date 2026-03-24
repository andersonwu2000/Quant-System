"""多資產組合最佳化模組測試。"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd

from src.portfolio.currency import CurrencyHedger, HedgeConfig, HedgeRecommendation
from src.portfolio.optimizer import (
    BLView,
    OptimizationMethod,
    OptimizerConfig,
    OptimizationResult,
    PortfolioOptimizer,
)
from src.portfolio.risk_model import RiskModel, RiskModelConfig


# ── 測試資料 ──────────────────────────────────────────────


def _make_returns(
    n_symbols: int = 5, n_days: int = 500, seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    data = rng.normal(0.0003, 0.015, (n_days, n_symbols))
    return pd.DataFrame(data, index=dates, columns=symbols)


# ── RiskModel ─────────────────────────────────────────────


class TestRiskModel:
    def test_estimate_covariance(self):
        r = _make_returns()
        rm = RiskModel()
        cov = rm.estimate_covariance(r)
        assert not cov.empty
        assert cov.shape[0] == cov.shape[1] == 5
        # 對角線應為正（變異數）
        for i in range(5):
            assert cov.iloc[i, i] > 0

    def test_covariance_symmetric(self):
        r = _make_returns()
        rm = RiskModel()
        cov = rm.estimate_covariance(r)
        np.testing.assert_array_almost_equal(cov.values, cov.values.T)

    def test_estimate_correlation(self):
        r = _make_returns()
        rm = RiskModel()
        corr = rm.estimate_correlation(r)
        # 對角線為 1
        for i in range(corr.shape[0]):
            assert abs(corr.iloc[i, i] - 1.0) < 0.01
        # 值在 [-1, 1]
        assert corr.abs().max().max() <= 1.01

    def test_compute_volatilities(self):
        r = _make_returns()
        rm = RiskModel()
        vol = rm.compute_volatilities(r)
        assert len(vol) == 5
        for v in vol:
            assert v > 0

    def test_portfolio_risk(self):
        r = _make_returns()
        rm = RiskModel()
        cov = rm.estimate_covariance(r)
        w = {f"SYM{i}": 0.2 for i in range(5)}
        risk = rm.portfolio_risk(w, cov)
        assert risk > 0

    def test_risk_contribution_sums_to_one(self):
        r = _make_returns()
        rm = RiskModel()
        cov = rm.estimate_covariance(r)
        w = {f"SYM{i}": 0.2 for i in range(5)}
        rc = rm.risk_contribution(w, cov)
        assert abs(sum(rc.values()) - 1.0) < 0.01

    def test_empty_returns(self):
        rm = RiskModel()
        cov = rm.estimate_covariance(pd.DataFrame())
        assert cov.empty

    def test_short_data(self):
        r = _make_returns(n_days=10)
        rm = RiskModel(RiskModelConfig(min_history=60))
        cov = rm.estimate_covariance(r)
        assert cov.empty

    def test_ewm_covariance(self):
        r = _make_returns()
        rm = RiskModel(RiskModelConfig(ewm_halflife=60))
        cov = rm.estimate_covariance(r)
        assert not cov.empty

    def test_no_shrinkage(self):
        r = _make_returns()
        rm = RiskModel(RiskModelConfig(shrinkage=False))
        cov = rm.estimate_covariance(r)
        assert not cov.empty


# ── PortfolioOptimizer ────────────────────────────────────


class TestPortfolioOptimizer:
    def test_equal_weight(self):
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(method=OptimizationMethod.EQUAL_WEIGHT))
        result = opt.optimize(r)
        assert isinstance(result, OptimizationResult)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        for w in result.weights.values():
            assert abs(w - 0.2) < 0.01

    def test_inverse_vol(self):
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(method=OptimizationMethod.INVERSE_VOL))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        assert all(w > 0 for w in result.weights.values())

    def test_risk_parity(self):
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(method=OptimizationMethod.RISK_PARITY))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        assert all(w > 0 for w in result.weights.values())

    def test_mean_variance(self):
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(method=OptimizationMethod.MEAN_VARIANCE))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01

    def test_black_litterman_no_views(self):
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(method=OptimizationMethod.BLACK_LITTERMAN))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01

    def test_black_litterman_with_views(self):
        r = _make_returns()
        views = [
            BLView(asset="SYM0", expected_return=0.15, confidence=0.8),
            BLView(asset="SYM1", expected_return=-0.05, confidence=0.6),
        ]
        opt = PortfolioOptimizer(OptimizerConfig(method=OptimizationMethod.BLACK_LITTERMAN))
        result = opt.optimize(r, views=views)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        # SYM0 有正向觀點，權重應較高
        assert result.weights.get("SYM0", 0) > result.weights.get("SYM1", 0)

    def test_hrp(self):
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(method=OptimizationMethod.HRP))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        assert all(w > 0 for w in result.weights.values())

    def test_max_weight_constraint(self):
        r = _make_returns(n_symbols=5)
        opt = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.RISK_PARITY,
            max_weight=0.30,
        ))
        result = opt.optimize(r)
        for w in result.weights.values():
            assert w <= 0.35  # tolerance after normalization

    def test_result_has_stats(self):
        r = _make_returns()
        opt = PortfolioOptimizer()
        result = opt.optimize(r)
        assert result.portfolio_risk > 0
        assert result.method == "risk_parity"
        assert len(result.risk_contributions) > 0

    def test_empty_returns(self):
        opt = PortfolioOptimizer()
        result = opt.optimize(pd.DataFrame())
        assert result.weights == {}

    def test_single_asset(self):
        r = _make_returns(n_symbols=1)
        opt = PortfolioOptimizer()
        result = opt.optimize(r)
        assert len(result.weights) <= 1


# ── CurrencyHedger ────────────────────────────────────────


class TestCurrencyHedger:
    def test_no_hedge_for_base_currency(self):
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            {"TWD": Decimal("1000000"), "USD": Decimal("50000")},
            Decimal("1500000"),
        )
        # Only USD should have recommendation
        assert all(r.currency != "TWD" for r in recs)

    def test_small_exposure_no_hedge(self):
        hedger = CurrencyHedger(HedgeConfig(min_hedge_amount=100000))
        recs = hedger.analyze(
            {"USD": Decimal("5000")},
            Decimal("1000000"),
        )
        assert len(recs) == 1
        assert recs[0].hedge_ratio == 0.0

    def test_moderate_exposure_partial_hedge(self):
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            {"USD": Decimal("200000")},
            Decimal("1000000"),
        )
        assert len(recs) == 1
        assert recs[0].hedge_ratio == 0.5  # 20% exposure → partial

    def test_high_exposure_partial_hedge(self):
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            {"USD": Decimal("600000")},
            Decimal("1000000"),
        )
        assert len(recs) == 1
        # 60% > max_unhedged(40%) → hedge_ratio = 1 - 0.40/0.60 ≈ 0.33
        assert recs[0].hedge_ratio > 0.0

    def test_very_high_exposure_aggressive_hedge(self):
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            {"USD": Decimal("900000")},
            Decimal("1000000"),
        )
        assert len(recs) == 1
        # 90% → hedge_ratio = 1 - 0.40/0.90 ≈ 0.56
        assert recs[0].hedge_ratio > 0.5

    def test_hedge_recommendation_to_dict(self):
        rec = HedgeRecommendation(
            currency="USD",
            gross_exposure=100000.0,
            hedge_ratio=0.5,
            hedged_amount=50000.0,
            unhedged_amount=50000.0,
            annual_cost_bps=25.0,
            reason="test",
        )
        d = rec.to_dict()
        assert d["currency"] == "USD"
        assert d["hedge_ratio"] == 0.5

    def test_multiple_currencies(self):
        hedger = CurrencyHedger()
        recs = hedger.analyze(
            {"USD": Decimal("300000"), "EUR": Decimal("200000")},
            Decimal("1000000"),
        )
        assert len(recs) == 2
        currencies = {r.currency for r in recs}
        assert currencies == {"USD", "EUR"}
