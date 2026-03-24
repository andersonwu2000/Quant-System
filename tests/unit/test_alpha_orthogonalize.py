"""Tests for src/alpha/orthogonalize.py — 因子正交化。"""

import numpy as np
import pandas as pd
import pytest

from src.alpha.orthogonalize import (
    factor_correlation_matrix,
    orthogonalize_sequential,
    orthogonalize_symmetric,
)


def _make_correlated_factors() -> dict[str, pd.DataFrame]:
    """產生有相關性的因子。"""
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", periods=30)
    symbols = [f"S{i}" for i in range(20)]

    # factor_a: 隨機
    a = pd.DataFrame(np.random.randn(30, 20), index=dates, columns=symbols)
    # factor_b: 與 a 高度相關 (a + 小噪聲)
    b = a + np.random.randn(30, 20) * 0.3
    # factor_c: 獨立
    c = pd.DataFrame(np.random.randn(30, 20), index=dates, columns=symbols)

    return {"factor_a": a, "factor_b": b, "factor_c": c}


class TestOrthogonalizeSequential:
    def test_first_factor_unchanged(self):
        factors = _make_correlated_factors()
        result = orthogonalize_sequential(factors, priority=["factor_a", "factor_b", "factor_c"])
        pd.testing.assert_frame_equal(result["factor_a"], factors["factor_a"])

    def test_reduces_correlation(self):
        factors = _make_correlated_factors()
        # 正交化前的相關性
        corr_before = factor_correlation_matrix(factors)
        ab_before = abs(corr_before.loc["factor_a", "factor_b"])

        result = orthogonalize_sequential(factors, priority=["factor_a", "factor_b", "factor_c"])
        corr_after = factor_correlation_matrix(result)
        ab_after = abs(corr_after.loc["factor_a", "factor_b"])

        assert ab_after < ab_before

    def test_unknown_factor_raises(self):
        factors = _make_correlated_factors()
        with pytest.raises(ValueError, match="not_exist"):
            orthogonalize_sequential(factors, priority=["not_exist"])

    def test_single_factor(self):
        factors = {"only": pd.DataFrame(np.random.randn(10, 5), index=pd.bdate_range("2020-01-01", periods=10))}
        result = orthogonalize_sequential(factors)
        pd.testing.assert_frame_equal(result["only"], factors["only"])


class TestOrthogonalizeSymmetric:
    def test_reduces_correlation(self):
        factors = _make_correlated_factors()
        corr_before = factor_correlation_matrix(factors)
        ab_before = abs(corr_before.loc["factor_a", "factor_b"])

        result = orthogonalize_symmetric(factors)
        corr_after = factor_correlation_matrix(result)
        ab_after = abs(corr_after.loc["factor_a", "factor_b"])

        assert ab_after < ab_before

    def test_empty_dict(self):
        result = orthogonalize_symmetric({})
        assert result == {}


class TestCorrelationMatrix:
    def test_diagonal_is_one(self):
        factors = _make_correlated_factors()
        corr = factor_correlation_matrix(factors)
        for name in factors:
            assert abs(corr.loc[name, name] - 1.0) < 0.05

    def test_correlated_factors_detected(self):
        factors = _make_correlated_factors()
        corr = factor_correlation_matrix(factors)
        # a 和 b 應高度相關
        assert abs(corr.loc["factor_a", "factor_b"]) > 0.5
        # a 和 c 應低相關
        assert abs(corr.loc["factor_a", "factor_c"]) < 0.5

    def test_spearman_vs_pearson(self):
        factors = _make_correlated_factors()
        sp = factor_correlation_matrix(factors, method="spearman")
        pe = factor_correlation_matrix(factors, method="pearson")
        # 兩者應大致一致
        assert abs(sp.loc["factor_a", "factor_b"] - pe.loc["factor_a", "factor_b"]) < 0.3
