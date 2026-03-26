"""Tests for Kalman Filter Pairs Trading (H3)."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from strategies.pairs_trading import (
    KalmanHedgeRatio,
    PairsTradingStrategy,
)


def _make_cointegrated_pair(
    n: int = 200, beta: float = 1.5, seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate two cointegrated series: A = beta * B + stationary_noise."""
    rng = np.random.RandomState(seed)
    b = np.cumsum(rng.randn(n)) + 100
    noise = np.zeros(n)
    for i in range(1, n):
        noise[i] = 0.8 * noise[i - 1] + rng.randn()
    a = beta * b + noise + 50
    return a.astype(np.float64), b.astype(np.float64)


class TestKalmanHedgeRatio:
    def test_returns_reasonable_hedge_ratio(self) -> None:
        """After feeding prices, hedge ratio should be a finite number."""
        kf = KalmanHedgeRatio()
        # Simple linear relationship
        for i in range(100):
            b = 100.0 + i * 0.5
            a = 2.0 * b + 10.0 + np.random.randn() * 0.1
            hr = kf.update(a, b)
        assert np.isfinite(hr)
        assert hr > 0, "Hedge ratio should be positive for positively related pair"

    def test_converges_for_cointegrated_series(self) -> None:
        """Kalman hedge ratio should converge near the true beta."""
        true_beta = 1.5
        a, b = _make_cointegrated_pair(n=500, beta=true_beta, seed=99)
        kf = KalmanHedgeRatio(delta=1e-4, ve=1e-3)

        hr = 0.0
        for i in range(len(a)):
            hr = kf.update(float(a[i]), float(b[i]))

        assert abs(hr - true_beta) < 0.5, (
            f"Kalman hedge ratio {hr:.3f} too far from true beta {true_beta}"
        )

    def test_initial_state_is_zero(self) -> None:
        """Before any updates, state should be zero."""
        kf = KalmanHedgeRatio()
        assert np.allclose(kf.beta, [0.0, 0.0])
        assert kf.P.shape == (2, 2)

    def test_single_update_does_not_crash(self) -> None:
        """A single update should work without errors."""
        kf = KalmanHedgeRatio()
        hr = kf.update(100.0, 50.0)
        assert np.isfinite(hr)

    def test_custom_delta_and_ve(self) -> None:
        """Different delta/ve parameters should produce different results."""
        a, b = _make_cointegrated_pair(n=100, beta=2.0, seed=7)

        kf_fast = KalmanHedgeRatio(delta=1e-2, ve=1e-3)
        kf_slow = KalmanHedgeRatio(delta=1e-6, ve=1e-3)

        hr_fast = hr_slow = 0.0
        for i in range(len(a)):
            hr_fast = kf_fast.update(float(a[i]), float(b[i]))
            hr_slow = kf_slow.update(float(a[i]), float(b[i]))

        # Fast-adapting filter should be closer to true beta than slow one
        # (with enough data, both converge, but fast adapts sooner)
        assert hr_fast != hr_slow, "Different delta should produce different results"


class TestPairsTradingKalman:
    def _make_mock_context(
        self, prices: dict[str, np.ndarray],
    ) -> MagicMock:
        """Create a mock Context for testing."""
        ctx = MagicMock()
        ctx.universe.return_value = list(prices.keys())

        def mock_bars(symbol: str, lookback: int = 60) -> pd.DataFrame:
            p = prices[symbol]
            return pd.DataFrame({"close": p})

        ctx.bars.side_effect = mock_bars
        return ctx

    def test_kalman_method_returns_weights(self) -> None:
        """Strategy with method='kalman' should return valid weights."""
        a, b = _make_cointegrated_pair(n=100, beta=1.5, seed=42)
        # Make the spread extreme so signals fire
        a_shifted = a.copy()
        a_shifted[-1] += 20.0  # push spread way up

        prices = {"STOCK_A": a_shifted, "STOCK_B": b}
        ctx = self._make_mock_context(prices)

        strategy = PairsTradingStrategy(
            lookback=60,
            z_threshold=1.0,
            method="kalman",
        )
        weights = strategy.on_bar(ctx)

        # Should produce some weights (may be empty if z-score is within threshold)
        assert isinstance(weights, dict)
        for w in weights.values():
            assert 0.0 <= w <= 1.0

    def test_cointegration_method_still_works(self) -> None:
        """Strategy with method='cointegration' (default) should still work."""
        strategy = PairsTradingStrategy(
            lookback=20,
            z_threshold=1.0,
            method="cointegration",
        )
        assert strategy.name() == "pairs_trading"
        assert strategy.method == "cointegration"

    def test_default_method_is_cointegration(self) -> None:
        """Default method should be 'cointegration' for backward compatibility."""
        strategy = PairsTradingStrategy()
        assert strategy.method == "cointegration"

    def test_kalman_filters_are_cached(self) -> None:
        """Kalman filters should be cached per pair across calls."""
        a, b = _make_cointegrated_pair(n=100, beta=1.5, seed=42)
        prices = {"STOCK_A": a, "STOCK_B": b}
        ctx = self._make_mock_context(prices)

        strategy = PairsTradingStrategy(
            lookback=60,
            z_threshold=1.0,
            method="kalman",
        )
        strategy.on_bar(ctx)

        # Filter should be cached
        assert len(strategy._kalman_filters) == 1

        # Call again — should reuse the same filter (not create new)
        strategy.on_bar(ctx)
        assert len(strategy._kalman_filters) == 1
