"""VaR / CVaR 風險指標測試。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.portfolio.risk_model import RiskModel


# ── 工具函數 ──────────────────────────────────────────────


def _make_returns(n: int = 500, seed: int = 42, mean: float = 0.0, std: float = 0.01) -> pd.Series:
    rng = np.random.default_rng(seed)
    data = rng.normal(mean, std, n)
    dates = pd.bdate_range("2020-01-02", periods=n)
    return pd.Series(data, index=dates)


def _make_skewed_returns(n: int = 1000, seed: int = 42) -> pd.Series:
    """建立左偏報酬序列（有較大的尾部損失）。"""
    rng = np.random.default_rng(seed)
    normal = rng.normal(0.0005, 0.01, n)
    # 加入少數大幅下跌
    crashes = rng.choice(n, size=20, replace=False)
    normal[crashes] -= rng.uniform(0.03, 0.08, 20)
    dates = pd.bdate_range("2020-01-02", periods=n)
    return pd.Series(normal, index=dates)


# ── VaR 測試 ─────────────────────────────────────────────


class TestComputeVaR:
    def test_historical_basic(self) -> None:
        returns = _make_returns()
        var = RiskModel.compute_var(returns, confidence=0.95, method="historical")
        assert var > 0
        assert isinstance(var, float)

    def test_parametric_basic(self) -> None:
        returns = _make_returns()
        var = RiskModel.compute_var(returns, confidence=0.95, method="parametric")
        assert var > 0
        assert isinstance(var, float)

    def test_higher_confidence_higher_var(self) -> None:
        returns = _make_returns()
        var_95 = RiskModel.compute_var(returns, confidence=0.95, method="historical")
        var_99 = RiskModel.compute_var(returns, confidence=0.99, method="historical")
        assert var_99 >= var_95

    def test_empty_series(self) -> None:
        returns = pd.Series(dtype=float)
        var = RiskModel.compute_var(returns, confidence=0.95)
        assert var == 0.0

    def test_single_value(self) -> None:
        returns = pd.Series([0.01])
        var = RiskModel.compute_var(returns, confidence=0.95)
        assert var == 0.0

    def test_constant_returns(self) -> None:
        returns = pd.Series([0.01] * 100)
        var_hist = RiskModel.compute_var(returns, confidence=0.95, method="historical")
        assert var_hist == pytest.approx(0.0, abs=1e-8)
        var_param = RiskModel.compute_var(returns, confidence=0.95, method="parametric")
        assert var_param == pytest.approx(0.0, abs=1e-8)

    def test_var_positive(self) -> None:
        """VaR 應回傳正數（代表損失）。"""
        returns = _make_returns(mean=-0.001)
        var = RiskModel.compute_var(returns, confidence=0.95)
        assert var >= 0.0


# ── CVaR 測試 ────────────────────────────────────────────


class TestComputeCVaR:
    def test_historical_basic(self) -> None:
        returns = _make_returns()
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="historical")
        assert cvar > 0
        assert isinstance(cvar, float)

    def test_parametric_basic(self) -> None:
        returns = _make_returns()
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="parametric")
        assert cvar > 0
        assert isinstance(cvar, float)

    def test_cvar_geq_var_historical(self) -> None:
        """CVaR 應 >= VaR（它是尾部的平均損失）。"""
        returns = _make_returns(n=1000, seed=123)
        var = RiskModel.compute_var(returns, confidence=0.95, method="historical")
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="historical")
        assert cvar >= var - 1e-10

    def test_cvar_geq_var_parametric(self) -> None:
        """CVaR >= VaR（參數法）。"""
        returns = _make_returns(n=1000, seed=456)
        var = RiskModel.compute_var(returns, confidence=0.95, method="parametric")
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="parametric")
        assert cvar >= var - 1e-10

    def test_empty_series(self) -> None:
        returns = pd.Series(dtype=float)
        cvar = RiskModel.compute_cvar(returns, confidence=0.95)
        assert cvar == 0.0

    def test_constant_returns(self) -> None:
        returns = pd.Series([0.01] * 100)
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="historical")
        assert cvar == pytest.approx(0.0, abs=1e-8)

    def test_skewed_returns_higher_cvar(self) -> None:
        """左偏分佈的 CVaR 應明顯大於 VaR。"""
        returns = _make_skewed_returns()
        var = RiskModel.compute_var(returns, confidence=0.95, method="historical")
        cvar = RiskModel.compute_cvar(returns, confidence=0.95, method="historical")
        assert cvar > var

    def test_cvar_geq_var_skewed(self) -> None:
        """CVaR >= VaR 即便在偏態分佈。"""
        returns = _make_skewed_returns(seed=99)
        var = RiskModel.compute_var(returns, confidence=0.99, method="historical")
        cvar = RiskModel.compute_cvar(returns, confidence=0.99, method="historical")
        assert cvar >= var - 1e-10
