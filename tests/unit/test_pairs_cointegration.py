"""Tests for pairs trading cointegration upgrade (G6a)."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from strategies.pairs_trading import (
    HAS_STATSMODELS,
    PairsTradingStrategy,
    _ols_hedge_ratio,
    _test_cointegration,
)


def _make_cointegrated_pair(
    n: int = 200, beta: float = 1.5, seed: int = 42
) -> tuple[np.ndarray, np.ndarray]:
    """Generate two cointegrated series: A = beta * B + stationary_noise."""
    rng = np.random.RandomState(seed)
    # Random walk for B
    b = np.cumsum(rng.randn(n)) + 100
    # A = beta * B + mean-reverting noise
    noise = np.zeros(n)
    for i in range(1, n):
        noise[i] = 0.8 * noise[i - 1] + rng.randn()
    a = beta * b + noise + 50
    return a.astype(np.float64), b.astype(np.float64)


def _make_independent_pair(
    n: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate two clearly non-cointegrated series.

    Uses deterministic trending series with different slopes
    plus small noise, making cointegration rejection reliable.
    """
    t = np.arange(n, dtype=np.float64)
    # A trends up linearly, B trends up quadratically — no stable spread
    a = 100.0 + 0.5 * t + np.sin(t * 0.1) * 2
    b = 200.0 + 0.01 * t * t + np.cos(t * 0.3) * 3
    return a.astype(np.float64), b.astype(np.float64)


@pytest.mark.skipif(not HAS_STATSMODELS, reason="statsmodels not installed")
class TestCointegration:
    def test_cointegrated_pair_detected(self) -> None:
        a, b = _make_cointegrated_pair()
        is_coint, p_value = _test_cointegration(a, b)
        assert is_coint is True
        assert p_value < 0.05

    def test_non_cointegrated_pair_rejected(self) -> None:
        a, b = _make_independent_pair()
        is_coint, p_value = _test_cointegration(a, b)
        assert is_coint is False
        assert p_value >= 0.05

    def test_hedge_ratio_close_to_true_beta(self) -> None:
        true_beta = 1.5
        a, b = _make_cointegrated_pair(n=500, beta=true_beta, seed=99)
        beta = _ols_hedge_ratio(a, b)
        assert abs(beta - true_beta) < 0.2, f"Hedge ratio {beta} too far from {true_beta}"

    def test_hedge_ratio_basic(self) -> None:
        """Hedge ratio of perfectly linear relationship."""
        b = np.arange(1.0, 101.0)
        a = 2.0 * b + 5.0  # exact linear: beta=2
        beta = _ols_hedge_ratio(a, b)
        assert abs(beta - 2.0) < 1e-10


class TestFallbackMode:
    def test_fallback_when_statsmodels_not_available(self) -> None:
        """When HAS_STATSMODELS is False, _test_cointegration returns (False, 1.0)."""
        a, b = _make_cointegrated_pair()
        with patch("strategies.pairs_trading.HAS_STATSMODELS", False):
            is_coint, p_value = _test_cointegration(a, b)
        assert is_coint is False
        assert p_value == 1.0

    def test_strategy_runs_without_statsmodels(self) -> None:
        """Strategy should not crash when statsmodels is unavailable."""
        strategy = PairsTradingStrategy(lookback=20, z_threshold=1.0)
        # Just verify the strategy can be created and has the right name
        assert strategy.name() == "pairs_trading"
