"""CVaR / Max Drawdown 組合最佳化測試。"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.portfolio.optimizer import (
    OptimizationMethod,
    OptimizerConfig,
    PortfolioOptimizer,
)
from src.portfolio.risk_model import RiskModel


# ── 工具函數 ──────────────────────────────────────────────


def _make_returns(
    n_symbols: int = 5,
    n_days: int = 500,
    seed: int = 42,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    data = rng.normal(0.0003, 0.015, (n_days, n_symbols))
    return pd.DataFrame(data, index=dates, columns=symbols)


def _make_skewed_returns(
    n_symbols: int = 5,
    n_days: int = 500,
    seed: int = 42,
) -> pd.DataFrame:
    """建立有左偏尾部的報酬矩陣。"""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-02", periods=n_days)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    data = rng.normal(0.0003, 0.015, (n_days, n_symbols))
    # 在前兩個資產加大崩盤幅度
    for col_idx in range(2):
        crash_idx = rng.choice(n_days, size=15, replace=False)
        data[crash_idx, col_idx] -= rng.uniform(0.04, 0.10, 15)
    return pd.DataFrame(data, index=dates, columns=symbols)


def _weights_valid(weights: dict[str, float], tol: float = 0.02) -> bool:
    """驗證權重有效性：加總 ≈ 1、無負值。"""
    if not weights:
        return False
    total = sum(weights.values())
    if abs(total - 1.0) > tol:
        return False
    if any(v < -1e-8 for v in weights.values()):
        return False
    return True


# ── CVaR 最佳化測試 ──────────────────────────────────────


class TestCVarOptimization:
    def test_valid_weights(self) -> None:
        returns = _make_returns()
        cfg = OptimizerConfig(method=OptimizationMethod.CVAR_OPTIMIZATION)
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        assert _weights_valid(result.weights)
        assert result.method == "cvar_optimization"

    def test_bounds_respected(self) -> None:
        returns = _make_returns()
        cfg = OptimizerConfig(
            method=OptimizationMethod.CVAR_OPTIMIZATION,
            max_weight=0.30,
        )
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        for v in result.weights.values():
            assert v <= 0.30 + 1e-6

    def test_long_only(self) -> None:
        returns = _make_returns()
        cfg = OptimizerConfig(
            method=OptimizationMethod.CVAR_OPTIMIZATION,
            long_only=True,
        )
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        for v in result.weights.values():
            assert v >= -1e-8

    def test_cvar_lower_than_equal_weight(self) -> None:
        """在偏態資料上，CVaR 最佳化結果的 CVaR 應 <= 等權。"""
        returns = _make_skewed_returns(n_days=800, seed=77)

        # 等權
        eq_cfg = OptimizerConfig(method=OptimizationMethod.EQUAL_WEIGHT)
        eq_opt = PortfolioOptimizer(config=eq_cfg)
        eq_result = eq_opt.optimize(returns)
        eq_weights = np.array([eq_result.weights.get(s, 0.0) for s in returns.columns])
        eq_port = (returns.values @ eq_weights)
        eq_cvar = RiskModel.compute_cvar(pd.Series(eq_port), confidence=0.95)

        # CVaR 最佳化
        cvar_cfg = OptimizerConfig(
            method=OptimizationMethod.CVAR_OPTIMIZATION,
            min_weight=0.0,
        )
        cvar_opt = PortfolioOptimizer(config=cvar_cfg)
        cvar_result = cvar_opt.optimize(returns)
        cvar_weights = np.array([cvar_result.weights.get(s, 0.0) for s in returns.columns])
        cvar_port = (returns.values @ cvar_weights)
        opt_cvar = RiskModel.compute_cvar(pd.Series(cvar_port), confidence=0.95)

        # CVaR 最佳化的組合 CVaR 應 <= 等權（可能相等）
        assert opt_cvar <= eq_cvar + 1e-6

    def test_different_confidence(self) -> None:
        returns = _make_returns()
        cfg = OptimizerConfig(
            method=OptimizationMethod.CVAR_OPTIMIZATION,
            cvar_confidence=0.99,
        )
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        assert _weights_valid(result.weights)

    def test_small_data_fallback(self) -> None:
        """資料不足時應退回等權。"""
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2020-01-02", periods=5)
        data = rng.normal(0, 0.01, (5, 3))
        returns = pd.DataFrame(data, index=dates, columns=["A", "B", "C"])
        cfg = OptimizerConfig(method=OptimizationMethod.CVAR_OPTIMIZATION)
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        # Should still produce valid weights (fallback to equal weight)
        assert _weights_valid(result.weights, tol=0.05)


# ── Max Drawdown 最佳化測試 ───────────────────────────────


class TestMaxDrawdownOptimization:
    def test_valid_weights(self) -> None:
        returns = _make_returns()
        cfg = OptimizerConfig(method=OptimizationMethod.MAX_DRAWDOWN)
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        assert _weights_valid(result.weights)
        assert result.method == "max_drawdown"

    def test_bounds_respected(self) -> None:
        returns = _make_returns()
        cfg = OptimizerConfig(
            method=OptimizationMethod.MAX_DRAWDOWN,
            max_weight=0.30,
        )
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        for v in result.weights.values():
            assert v <= 0.30 + 1e-6

    def test_long_only(self) -> None:
        returns = _make_returns()
        cfg = OptimizerConfig(
            method=OptimizationMethod.MAX_DRAWDOWN,
            long_only=True,
        )
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        for v in result.weights.values():
            assert v >= -1e-8

    def test_small_data_fallback(self) -> None:
        """資料不足時應退回等權。"""
        rng = np.random.default_rng(42)
        dates = pd.bdate_range("2020-01-02", periods=5)
        data = rng.normal(0, 0.01, (5, 3))
        returns = pd.DataFrame(data, index=dates, columns=["A", "B", "C"])
        cfg = OptimizerConfig(method=OptimizationMethod.MAX_DRAWDOWN)
        opt = PortfolioOptimizer(config=cfg)
        result = opt.optimize(returns)
        assert _weights_valid(result.weights, tol=0.05)
