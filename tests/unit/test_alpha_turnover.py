"""Tests for src/alpha/turnover.py — 換手率分析。"""

import numpy as np
import pandas as pd

from src.alpha.turnover import (
    analyze_factor_turnover,
    compute_turnover,
    compute_turnover_series,
    cost_adjusted_returns,
)


class TestComputeTurnover:
    def test_identical_weights_zero_turnover(self):
        w = pd.Series({"A": 0.5, "B": 0.5})
        assert compute_turnover(w, w) == 0.0

    def test_complete_rotation(self):
        old = pd.Series({"A": 0.5, "B": 0.5})
        new = pd.Series({"C": 0.5, "D": 0.5})
        # 所有舊倉平倉 + 所有新倉建倉 → turnover = 1.0
        assert compute_turnover(old, new) == 1.0

    def test_partial_change(self):
        old = pd.Series({"A": 0.5, "B": 0.5})
        new = pd.Series({"A": 0.5, "C": 0.5})
        # B 出 0.5, C 進 0.5 → single-sided = 0.5
        assert compute_turnover(old, new) == 0.5

    def test_empty_weights(self):
        assert compute_turnover(pd.Series(dtype=float), pd.Series(dtype=float)) == 0.0


class TestComputeTurnoverSeries:
    def test_constant_weights_zero_turnover(self):
        dates = pd.bdate_range("2020-01-01", periods=5)
        df = pd.DataFrame({"A": 0.5, "B": 0.5}, index=dates)
        ts = compute_turnover_series(df)
        assert len(ts) == 4
        assert all(t == 0.0 for t in ts)

    def test_changing_weights(self):
        dates = pd.bdate_range("2020-01-01", periods=3)
        df = pd.DataFrame(
            {"A": [0.5, 0.3, 0.1], "B": [0.5, 0.7, 0.9]},
            index=dates,
        )
        ts = compute_turnover_series(df)
        assert len(ts) == 2
        assert all(t > 0 for t in ts)


class TestAnalyzeFactorTurnover:
    def test_stable_factor_low_turnover(self):
        """穩定因子 → 低換手率。"""
        np.random.seed(42)
        dates = pd.bdate_range("2020-01-01", periods=30)
        # 因子值幾乎不變
        base = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        fv = pd.DataFrame(
            np.tile(base, (30, 1)) + np.random.randn(30, 10) * 0.01,
            index=dates,
            columns=[f"S{i}" for i in range(10)],
        )
        result = analyze_factor_turnover(fv, n_quantiles=5, factor_name="stable")
        assert result.avg_turnover < 0.3

    def test_returns_valid_result(self):
        np.random.seed(42)
        dates = pd.bdate_range("2020-01-01", periods=50)
        fv = pd.DataFrame(np.random.randn(50, 20), index=dates, columns=[f"S{i}" for i in range(20)])
        result = analyze_factor_turnover(fv, factor_name="test", gross_ic=0.05)
        assert result.avg_turnover >= 0
        assert result.cost_drag_annual_bps >= 0
        assert result.breakeven_cost_bps > 0
        assert len(result.summary()) > 0


class TestCostAdjustedReturns:
    def test_subtracts_cost(self):
        dates = pd.bdate_range("2020-01-01", periods=5)
        gross = pd.Series([0.01, 0.02, -0.01, 0.005, 0.015], index=dates)
        turnover = pd.Series([0.1, 0.2, 0.15, 0.1, 0.05], index=dates)
        net = cost_adjusted_returns(gross, turnover, cost_bps=30.0)
        # 每期淨報酬 < 毛報酬
        for dt in dates:
            assert net[dt] <= gross[dt]

    def test_zero_turnover_no_cost(self):
        dates = pd.bdate_range("2020-01-01", periods=3)
        gross = pd.Series([0.01, 0.02, 0.03], index=dates)
        turnover = pd.Series([0.0, 0.0, 0.0], index=dates)
        net = cost_adjusted_returns(gross, turnover, cost_bps=30.0)
        pd.testing.assert_series_equal(net, gross)
