"""Tests for Semi-Variance (Downside Risk) optimization (H2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.optimizer import (
    OptimizationMethod,
    OptimizerConfig,
    PortfolioOptimizer,
)


def _make_returns(
    n_symbols: int = 4, n_days: int = 500, seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    data = rng.normal(0.0003, 0.015, (n_days, n_symbols))
    return pd.DataFrame(data, index=dates, columns=symbols)


def _make_asymmetric_returns(
    n_days: int = 500, seed: int = 42,
) -> pd.DataFrame:
    """Create returns where SYM0 has large downside and SYM1 is defensive."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days)

    # SYM0: High mean but heavy left tail
    sym0 = rng.normal(0.001, 0.02, n_days)
    sym0[sym0 < -0.01] *= 3.0  # amplify losses

    # SYM1: Moderate mean, low downside
    sym1 = rng.normal(0.0005, 0.008, n_days)

    # SYM2: Similar to SYM0 but less extreme
    sym2 = rng.normal(0.0008, 0.015, n_days)

    return pd.DataFrame(
        {"SYM0": sym0, "SYM1": sym1, "SYM2": sym2},
        index=dates,
    )


class TestSemiVarianceOptimization:
    def test_weights_are_valid(self) -> None:
        """Semi-variance weights should sum to 1 and respect bounds."""
        returns = _make_returns()
        cfg = OptimizerConfig(
            method=OptimizationMethod.SEMI_VARIANCE,
            long_only=True,
            max_weight=0.50,
        )
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)

        total = sum(result.weights.values())
        assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"
        for s, w in result.weights.items():
            assert w >= 0.0, f"Weight for {s} is negative: {w}"
            assert w <= 0.51, f"Weight for {s} exceeds max: {w}"

    def test_prefers_low_downside_assets(self) -> None:
        """Semi-variance should overweight the defensive asset (SYM1)."""
        returns = _make_asymmetric_returns()
        cfg = OptimizerConfig(
            method=OptimizationMethod.SEMI_VARIANCE,
            long_only=True,
            max_weight=0.60,
            min_weight=0.01,
        )
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)

        # SYM1 (defensive) should have higher weight than SYM0 (heavy left tail)
        w1 = result.weights.get("SYM1", 0.0)
        w0 = result.weights.get("SYM0", 0.0)
        assert w1 > w0, f"Expected SYM1 ({w1}) > SYM0 ({w0})"

    def test_works_with_long_only(self) -> None:
        """All weights should be non-negative with long_only=True."""
        returns = _make_returns()
        cfg = OptimizerConfig(
            method=OptimizationMethod.SEMI_VARIANCE,
            long_only=True,
        )
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)

        for s, w in result.weights.items():
            assert w >= 0.0

    def test_result_has_risk_metrics(self) -> None:
        """OptimizationResult should have portfolio_risk and sharpe_ratio."""
        returns = _make_returns()
        cfg = OptimizerConfig(method=OptimizationMethod.SEMI_VARIANCE)
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)

        assert result.method == "semi_variance"
        assert result.portfolio_risk >= 0.0
        assert isinstance(result.sharpe_ratio, float)

    def test_small_dataset_fallback(self) -> None:
        """With fewer than 10 rows, should fall back to equal weight."""
        returns = _make_returns(n_days=5)
        cfg = OptimizerConfig(method=OptimizationMethod.SEMI_VARIANCE)
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)

        # Should get equal-ish weights
        values = list(result.weights.values())
        assert len(values) > 0
        assert max(values) - min(values) < 0.05  # roughly equal

    def test_different_from_equal_weight(self) -> None:
        """Semi-variance should produce different weights from equal weight."""
        returns = _make_asymmetric_returns()
        cfg_sv = OptimizerConfig(
            method=OptimizationMethod.SEMI_VARIANCE,
            min_weight=0.01,
            max_weight=0.60,
        )
        cfg_ew = OptimizerConfig(
            method=OptimizationMethod.EQUAL_WEIGHT,
            min_weight=0.01,
            max_weight=0.60,
        )

        result_sv = PortfolioOptimizer(config=cfg_sv).optimize(returns)
        result_ew = PortfolioOptimizer(config=cfg_ew).optimize(returns)

        # They should differ — semi-variance underweights high-downside assets
        all_symbols = sorted(
            set(list(result_sv.weights.keys()) + list(result_ew.weights.keys()))
        )
        sv_w = [result_sv.weights.get(s, 0.0) for s in all_symbols]
        ew_w = [result_ew.weights.get(s, 0.0) for s in all_symbols]
        diff = sum(abs(a - b) for a, b in zip(sv_w, ew_w))
        assert diff > 0.01, f"Semi-variance weights too close to equal weight: diff={diff}"
