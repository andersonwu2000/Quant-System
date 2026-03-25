"""Unit tests for Probability of Backtest Overfitting (Phase G3b)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.overfitting import compute_pbo


# ── Helpers ──────────────────────────────────────────────────


def _random_returns_matrix(
    n_days: int = 500,
    n_strategies: int = 10,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a matrix of random daily returns."""
    rng = np.random.default_rng(seed)
    data = rng.normal(0, 0.02, size=(n_days, n_strategies))
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    return pd.DataFrame(
        data,
        index=dates,
        columns=[f"strategy_{i}" for i in range(n_strategies)],
    )


def _trending_returns_matrix(
    n_days: int = 500,
    n_strategies: int = 10,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate returns where strategy_0 has a clear edge."""
    rng = np.random.default_rng(seed)
    data = rng.normal(0, 0.02, size=(n_days, n_strategies))
    # Give strategy_0 a strong positive drift
    data[:, 0] += 0.001
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    return pd.DataFrame(
        data,
        index=dates,
        columns=[f"strategy_{i}" for i in range(n_strategies)],
    )


# ═══════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════


class TestPBO:

    def test_pbo_in_zero_one_range(self) -> None:
        mat = _random_returns_matrix()
        result = compute_pbo(mat, n_partitions=10)
        assert 0.0 <= result.pbo <= 1.0

    def test_random_returns_pbo_nonnegative(self) -> None:
        """With purely random returns, PBO should be non-negative."""
        mat = _random_returns_matrix(seed=123)
        result = compute_pbo(mat, n_partitions=10)
        # PBO is valid (non-negative) even with random returns
        assert result.pbo >= 0.0
        assert result.n_combinations > 0

    def test_n_combinations_correct(self) -> None:
        mat = _random_returns_matrix(n_strategies=5)
        result = compute_pbo(mat, n_partitions=6)
        # C(6, 3) = 20
        assert result.n_combinations == 20

    def test_is_overfit_flag(self) -> None:
        mat = _random_returns_matrix()
        result = compute_pbo(mat, n_partitions=10)
        assert result.is_overfit == (result.pbo > 0.5)

    def test_summary_is_string(self) -> None:
        mat = _random_returns_matrix()
        result = compute_pbo(mat, n_partitions=10)
        s = result.summary()
        assert isinstance(s, str)
        assert "Probability of Backtest Overfitting" in s

    def test_raises_on_single_strategy(self) -> None:
        mat = _random_returns_matrix(n_strategies=1)
        with pytest.raises(ValueError, match="at least 2 columns"):
            compute_pbo(mat)

    def test_raises_on_insufficient_data(self) -> None:
        mat = _random_returns_matrix(n_days=5, n_strategies=3)
        with pytest.raises(ValueError, match="Not enough data rows"):
            compute_pbo(mat, n_partitions=10)

    def test_odd_n_partitions_adjusted_to_even(self) -> None:
        mat = _random_returns_matrix()
        result = compute_pbo(mat, n_partitions=7)
        # 7 is adjusted to 8, C(8, 4) = 70
        assert result.n_combinations == 70
