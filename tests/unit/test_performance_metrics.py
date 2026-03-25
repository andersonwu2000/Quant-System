"""Tests for new performance metrics (G7): Omega ratio, rolling Sharpe."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.analytics import (
    compute_omega_ratio,
    compute_rolling_sharpe,
)


class TestOmegaRatio:
    def test_positive_mean_returns_above_one(self) -> None:
        """Omega > 1 for a series with positive mean."""
        rng = np.random.RandomState(42)
        returns = pd.Series(rng.randn(500) * 0.01 + 0.001)  # positive drift
        omega = compute_omega_ratio(returns, threshold=0.0)
        assert omega > 1.0

    def test_negative_mean_returns_below_one(self) -> None:
        """Omega < 1 for a series with negative mean."""
        rng = np.random.RandomState(42)
        returns = pd.Series(rng.randn(500) * 0.01 - 0.002)  # negative drift
        omega = compute_omega_ratio(returns, threshold=0.0)
        assert omega < 1.0

    def test_all_positive_returns_inf(self) -> None:
        """Omega = inf when all returns are above threshold."""
        returns = pd.Series([0.01, 0.02, 0.03, 0.005])
        omega = compute_omega_ratio(returns, threshold=0.0)
        assert omega == float("inf")

    def test_empty_returns_zero(self) -> None:
        omega = compute_omega_ratio(pd.Series(dtype=float))
        assert omega == 0.0

    def test_custom_threshold(self) -> None:
        """With a high threshold, omega should be lower."""
        rng = np.random.RandomState(42)
        returns = pd.Series(rng.randn(500) * 0.01 + 0.001)
        omega_0 = compute_omega_ratio(returns, threshold=0.0)
        omega_high = compute_omega_ratio(returns, threshold=0.005)
        assert omega_high < omega_0


class TestRollingSharpe:
    def test_correct_length(self) -> None:
        """Rolling Sharpe should have len(returns) - window + 1 elements."""
        returns = pd.Series(np.random.randn(100) * 0.01)
        window = 63
        result = compute_rolling_sharpe(returns, window=window)
        assert len(result) == len(returns) - window + 1

    def test_values_are_finite(self) -> None:
        rng = np.random.RandomState(42)
        returns = pd.Series(rng.randn(200) * 0.01 + 0.0005)
        result = compute_rolling_sharpe(returns, window=63)
        assert all(np.isfinite(v) for v in result)

    def test_empty_when_too_short(self) -> None:
        """Returns empty list when data is shorter than window."""
        returns = pd.Series([0.01, 0.02, 0.03])
        result = compute_rolling_sharpe(returns, window=63)
        assert result == []

    def test_small_window(self) -> None:
        """Works with a smaller window."""
        rng = np.random.RandomState(42)
        returns = pd.Series(rng.randn(50) * 0.01)
        result = compute_rolling_sharpe(returns, window=10)
        assert len(result) == 41  # 50 - 10 + 1

    def test_constant_returns_zero_std(self) -> None:
        """Constant returns → std=0 → rolling Sharpe = 0."""
        returns = pd.Series([0.01] * 70)
        result = compute_rolling_sharpe(returns, window=63)
        # std is 0 for constant series → sharpe should be 0
        assert all(v == 0.0 for v in result)
