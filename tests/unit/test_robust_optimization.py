"""Phase G2: Robust Portfolio Optimization tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.optimizer import (
    OptimizationMethod,
    OptimizerConfig,
    PortfolioOptimizer,
)
from src.portfolio.risk_model import shrink_mean


# ── Helpers ──────────────────────────────────────────────


def _make_returns(
    n_symbols: int = 5, n_days: int = 500, seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    data = rng.normal(0.0003, 0.015, (n_days, n_symbols))
    return pd.DataFrame(data, index=dates, columns=symbols)


# ── G2a: Robust optimization ─────────────────────────────


class TestRobustOptimization:
    def test_robust_weights_valid(self):
        """Robust weights sum to 1 and respect bounds."""
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.ROBUST,
            robust_epsilon=0.1,
        ))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        for w in result.weights.values():
            assert w >= 0.0

    def test_robust_more_conservative_than_mvo(self):
        """Robust should have lower or equal expected return than MVO."""
        r = _make_returns()
        mvo = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.MEAN_VARIANCE,
        ))
        robust = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.ROBUST,
            robust_epsilon=0.5,
        ))
        mvo_result = mvo.optimize(r)
        robust_result = robust.optimize(r)

        # Robust penalises uncertainty → should not exceed MVO return
        # (allow small tolerance for numerical reasons)
        assert robust_result.portfolio_return <= mvo_result.portfolio_return + 0.01

    def test_different_epsilon_different_results(self):
        """Different epsilon values produce different weight vectors."""
        r = _make_returns()
        opt_lo = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.ROBUST,
            robust_epsilon=0.01,
        ))
        opt_hi = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.ROBUST,
            robust_epsilon=1.0,
        ))
        result_lo = opt_lo.optimize(r)
        result_hi = opt_hi.optimize(r)

        # At least one weight should differ noticeably
        diff = sum(
            abs(result_lo.weights.get(s, 0) - result_hi.weights.get(s, 0))
            for s in set(result_lo.weights) | set(result_hi.weights)
        )
        assert diff > 0.01

    def test_robust_result_has_stats(self):
        """Robust result should have portfolio risk and sharpe."""
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.ROBUST,
        ))
        result = opt.optimize(r)
        assert result.method == "robust"
        assert result.portfolio_risk > 0
        assert len(result.risk_contributions) > 0


# ── G2b: Resampled (Michaud) optimization ─────────────────


class TestResampledOptimization:
    def test_resampled_weights_valid(self):
        """Resampled weights sum to 1 and respect bounds."""
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.RESAMPLED,
            resample_iterations=50,  # fewer for speed
        ))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        for w in result.weights.values():
            assert w >= 0.0

    def test_resampled_reduces_extreme_positions(self):
        """Resampled should be less concentrated than single MVO."""
        r = _make_returns()
        mvo = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.MEAN_VARIANCE,
        ))
        resampled = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.RESAMPLED,
            resample_iterations=100,
        ))
        mvo_result = mvo.optimize(r)
        resampled_result = resampled.optimize(r)

        # Max weight should be lower or equal for resampled (averaging smooths)
        mvo_max = max(mvo_result.weights.values()) if mvo_result.weights else 0
        resampled_max = max(resampled_result.weights.values()) if resampled_result.weights else 0
        # Resampled should not be MORE concentrated than MVO
        assert resampled_max <= mvo_max + 0.05

    def test_resampled_result_has_stats(self):
        """Resampled result should have portfolio stats."""
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.RESAMPLED,
            resample_iterations=20,
        ))
        result = opt.optimize(r)
        assert result.method == "resampled"
        assert result.portfolio_risk > 0


# ── G2c: James-Stein mean shrinkage ──────────────────────


class TestJamesSteinShrinkage:
    def test_shrinks_toward_grand_mean(self):
        """Shrunk mean should be closer to the grand mean than sample mean."""
        sample = np.array([0.1, 0.2, 0.05, 0.15, 0.25])
        grand = float(np.mean(sample))
        shrunk = shrink_mean(sample, n_obs=100)

        # Each element should be closer to grand mean
        for i in range(len(sample)):
            assert abs(shrunk[i] - grand) <= abs(sample[i] - grand) + 1e-10

    def test_dimension_one_no_shrinkage(self):
        """With p=1, James-Stein cannot shrink — returns sample mean."""
        sample = np.array([0.5])
        shrunk = shrink_mean(sample, n_obs=100)
        np.testing.assert_array_almost_equal(shrunk, sample)

    def test_dimension_two_no_shrinkage(self):
        """With p=2, James-Stein cannot shrink — returns sample mean."""
        sample = np.array([0.3, 0.7])
        shrunk = shrink_mean(sample, n_obs=100)
        np.testing.assert_array_almost_equal(shrunk, sample)

    def test_custom_grand_mean(self):
        """Can specify a custom target grand mean."""
        sample = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        shrunk = shrink_mean(sample, n_obs=50, grand_mean=0.0)
        # Should shrink toward 0
        for i in range(len(sample)):
            assert abs(shrunk[i]) <= abs(sample[i]) + 1e-10

    def test_integration_robust_with_shrunk_mean(self):
        """Robust optimization with James-Stein shrinkage should work end-to-end."""
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.ROBUST,
            robust_epsilon=0.1,
            shrink_mean=True,
        ))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        assert result.portfolio_risk > 0

    def test_integration_mvo_with_shrunk_mean(self):
        """MVO with James-Stein shrinkage should produce valid weights."""
        r = _make_returns()
        opt = PortfolioOptimizer(OptimizerConfig(
            method=OptimizationMethod.MEAN_VARIANCE,
            shrink_mean=True,
        ))
        result = opt.optimize(r)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
