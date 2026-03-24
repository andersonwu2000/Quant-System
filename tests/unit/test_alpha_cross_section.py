"""Tests for src/alpha/cross_section.py — 分位數組合回測。"""

import numpy as np
import pandas as pd

from src.alpha.cross_section import long_short_analysis, quantile_backtest


def _make_factor_and_returns(n_dates: int = 50, n_symbols: int = 20, predictive: bool = True):
    """
    產生因子值和前瞻報酬。

    predictive=True 時，因子值和報酬正相關（模擬有效因子）。
    """
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", periods=n_dates)
    symbols = [f"S{i:03d}" for i in range(n_symbols)]

    factor_values = pd.DataFrame(np.random.randn(n_dates, n_symbols), index=dates, columns=symbols)

    if predictive:
        # 報酬 = 因子值 * 0.01 + 噪聲
        noise = np.random.randn(n_dates, n_symbols) * 0.005
        forward_returns = factor_values * 0.01 + noise
    else:
        forward_returns = pd.DataFrame(np.random.randn(n_dates, n_symbols) * 0.01, index=dates, columns=symbols)

    return factor_values, forward_returns


class TestQuantileBacktest:
    def test_predictive_factor_has_positive_monotonicity(self):
        fv, fr = _make_factor_and_returns(predictive=True)
        result = quantile_backtest(fv, fr, n_quantiles=5, factor_name="test")
        assert result.monotonicity_score > 0.5

    def test_random_factor_has_low_monotonicity(self):
        fv, fr = _make_factor_and_returns(predictive=False)
        result = quantile_backtest(fv, fr, n_quantiles=5, factor_name="random")
        assert abs(result.monotonicity_score) < 0.8

    def test_quantile_returns_shape(self):
        fv, fr = _make_factor_and_returns()
        result = quantile_backtest(fv, fr, n_quantiles=5)
        assert "Q1" in result.quantile_returns.columns
        assert "Q5" in result.quantile_returns.columns
        assert len(result.mean_returns) == 5

    def test_long_short_return_exists(self):
        fv, fr = _make_factor_and_returns()
        result = quantile_backtest(fv, fr, n_quantiles=5)
        assert len(result.long_short_return) > 0

    def test_summary_string(self):
        fv, fr = _make_factor_and_returns()
        result = quantile_backtest(fv, fr, factor_name="momentum")
        s = result.summary()
        assert "momentum" in s
        assert "Monotonicity" in s

    def test_too_few_symbols(self):
        """不足分組數量時回傳空結果。"""
        dates = pd.bdate_range("2020-01-01", periods=10)
        fv = pd.DataFrame({"A": np.random.randn(10), "B": np.random.randn(10)}, index=dates)
        fr = pd.DataFrame({"A": np.random.randn(10) * 0.01, "B": np.random.randn(10) * 0.01}, index=dates)
        result = quantile_backtest(fv, fr, n_quantiles=5, factor_name="test")
        assert result.long_short_sharpe == 0.0


class TestLongShortAnalysis:
    def test_returns_dict(self):
        fv, fr = _make_factor_and_returns()
        result = quantile_backtest(fv, fr, n_quantiles=5)
        analysis = long_short_analysis(result)
        assert "annual_return" in analysis
        assert "sharpe" in analysis
        assert "win_rate" in analysis
        assert "monotonicity" in analysis
