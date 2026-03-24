"""Tests for src/alpha/attribution.py — 因子報酬歸因。"""

import numpy as np
import pandas as pd

from src.alpha.attribution import AttributionResult, attribute_returns


def _make_returns(n: int = 200, seed: int = 42) -> pd.Series:
    dates = pd.bdate_range("2020-01-01", periods=n)
    return pd.Series(
        np.random.RandomState(seed).normal(0, 0.01, n), index=dates
    )


class TestWeightBasedAttribution:
    def test_sums_to_total(self):
        composite = _make_returns(200, seed=42)
        f1 = _make_returns(200, seed=10)
        f2 = _make_returns(200, seed=20)
        weights = {"f1": 0.6, "f2": 0.4}
        result = attribute_returns(
            composite, {"f1": f1, "f2": f2}, weights, method="weight_based"
        )
        # total ≈ sum(factor contributions) + residual
        total_from_parts = sum(result.factor_contributions.values()) + result.residual_return
        assert abs(result.total_return - total_from_parts) < 1e-10

    def test_single_factor(self):
        f1 = _make_returns(200, seed=10)
        # Composite = factor itself × weight
        composite = f1 * 0.5
        result = attribute_returns(
            composite, {"f1": f1}, {"f1": 0.5}, method="weight_based"
        )
        # Residual should be near zero
        assert abs(result.residual_return) < 1e-10

    def test_contribution_series_shape(self):
        composite = _make_returns(200)
        f1 = _make_returns(200, seed=10)
        result = attribute_returns(
            composite, {"f1": f1}, {"f1": 1.0}, method="weight_based"
        )
        assert isinstance(result.contribution_series, pd.DataFrame)
        assert "f1" in result.contribution_series.columns
        assert "residual" in result.contribution_series.columns


class TestRegressionAttribution:
    def test_regression_basic(self):
        np.random.seed(42)
        n = 200
        dates = pd.bdate_range("2020-01-01", periods=n)
        f1 = pd.Series(np.random.normal(0, 0.01, n), index=dates)
        f2 = pd.Series(np.random.normal(0, 0.01, n), index=dates)
        # Composite = 0.7*f1 + 0.3*f2 + noise
        composite = 0.7 * f1 + 0.3 * f2 + np.random.normal(0, 0.001, n)
        composite.index = dates
        result = attribute_returns(
            composite, {"f1": f1, "f2": f2}, {}, method="regression"
        )
        assert isinstance(result, AttributionResult)
        assert "f1" in result.factor_contributions
        assert "f2" in result.factor_contributions


class TestEdgeCases:
    def test_empty_data(self):
        result = attribute_returns(
            pd.Series(dtype=float), {}, {}, method="weight_based"
        )
        assert result.total_return == 0.0

    def test_no_factor_returns(self):
        composite = _make_returns(50)
        result = attribute_returns(composite, {}, {}, method="weight_based")
        assert result.total_return == 0.0
