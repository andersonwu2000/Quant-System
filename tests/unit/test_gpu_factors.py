"""Tests for src.strategy.factors.gpu — GPU-accelerated factor computation.

All tests are skipped when CUDA is not available.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")

from src.strategy.factors.gpu import (  # noqa: E402
    compute_factors_gpu,
    gpu_available,
)

requires_cuda = pytest.mark.skipif(not gpu_available(), reason="CUDA not available")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _random_price_matrix(n_dates: int = 300, n_symbols: int = 5, seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate synthetic close and volume matrices."""
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2023-01-01", periods=n_dates)
    symbols = [f"SYM{i}" for i in range(n_symbols)]
    # Random walk prices starting at 100
    returns = 1 + rng.randn(n_dates, n_symbols) * 0.02
    prices = 100 * np.cumprod(returns, axis=0)
    volumes = rng.randint(1000, 100000, size=(n_dates, n_symbols)).astype(float)
    close_df = pd.DataFrame(prices, index=dates, columns=symbols)
    volume_df = pd.DataFrame(volumes, index=dates, columns=symbols)
    return close_df, volume_df


def _cpu_momentum(close_df: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
    """CPU reference: momentum factor via pandas."""
    result = pd.DataFrame(np.nan, index=close_df.index, columns=close_df.columns)
    for i in range(lookback, len(close_df)):
        result.iloc[i] = close_df.iloc[i - skip] / close_df.iloc[i - lookback] - 1
    return result


def _cpu_volatility(close_df: pd.DataFrame, lookback: int = 20) -> pd.DataFrame:
    """CPU reference: rolling annualized volatility via pandas."""
    returns = close_df.pct_change()
    vol = returns.rolling(lookback).std() * np.sqrt(252)
    return vol


def _cpu_rsi(close_df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """CPU reference: RSI via pandas."""
    returns = close_df.pct_change()
    gains = returns.clip(lower=0)
    losses = (-returns).clip(lower=0)
    avg_gain = gains.rolling(period).mean()
    avg_loss = losses.rolling(period).mean()
    rs = avg_gain / avg_loss.clip(lower=1e-10)
    rsi_vals = 100 - 100 / (1 + rs)
    return rsi_vals


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@requires_cuda
class TestMomentumGPU:
    def test_matches_cpu(self) -> None:
        close_df, _ = _random_price_matrix()
        cpu_result = _cpu_momentum(close_df)
        gpu_result = compute_factors_gpu(close_df, close_df, ["momentum"])["momentum"]
        # Compare only non-NaN rows
        mask = cpu_result.notna() & gpu_result.notna()
        np.testing.assert_allclose(
            gpu_result.values[mask], cpu_result.values[mask], rtol=1e-4, atol=1e-6,
        )


@requires_cuda
class TestVolatilityGPU:
    def test_matches_cpu(self) -> None:
        close_df, vol_df = _random_price_matrix()
        cpu_result = _cpu_volatility(close_df)
        gpu_result = compute_factors_gpu(close_df, vol_df, ["volatility"])["volatility"]
        # Compare valid rows (skip first lookback rows that are NaN)
        mask = cpu_result.notna() & gpu_result.notna()
        np.testing.assert_allclose(
            gpu_result.values[mask], cpu_result.values[mask], rtol=1e-3, atol=1e-4,
        )


@requires_cuda
class TestRSIGPU:
    def test_matches_cpu(self) -> None:
        close_df, vol_df = _random_price_matrix()
        cpu_result = _cpu_rsi(close_df)
        gpu_result = compute_factors_gpu(close_df, vol_df, ["rsi"])["rsi"]
        mask = cpu_result.notna() & gpu_result.notna()
        np.testing.assert_allclose(
            gpu_result.values[mask], cpu_result.values[mask], rtol=1e-3, atol=0.5,
        )


@requires_cuda
class TestNaNHandling:
    def test_short_series_produces_nans(self) -> None:
        """If the series is shorter than lookback, output should be all NaN."""
        dates = pd.bdate_range("2023-01-01", periods=10)
        symbols = ["A", "B"]
        close_df = pd.DataFrame(
            np.random.rand(10, 2) * 100 + 50, index=dates, columns=symbols,
        )
        vol_df = close_df.copy()
        result = compute_factors_gpu(close_df, vol_df, ["momentum"])
        # With only 10 rows and lookback=252, all should be NaN
        assert result["momentum"].isna().all().all()


@requires_cuda
class TestComputeFactorsGPU:
    def test_multiple_factors(self) -> None:
        close_df, vol_df = _random_price_matrix()
        results = compute_factors_gpu(close_df, vol_df, ["momentum", "volatility", "rsi"])
        assert set(results.keys()) == {"momentum", "volatility", "rsi"}
        for name, df in results.items():
            assert df.shape == close_df.shape
            assert list(df.columns) == list(close_df.columns)

    def test_unknown_factor_skipped(self) -> None:
        close_df, vol_df = _random_price_matrix()
        results = compute_factors_gpu(close_df, vol_df, ["momentum", "nonexistent"])
        assert "momentum" in results
        assert "nonexistent" not in results
