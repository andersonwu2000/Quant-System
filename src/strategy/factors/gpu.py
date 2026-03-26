"""GPU-accelerated factor computation using PyTorch CUDA."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import torch

logger = logging.getLogger(__name__)

_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def gpu_available() -> bool:
    """Return True if CUDA is available."""
    return torch.cuda.is_available()


def compute_factors_gpu(
    close_matrix: pd.DataFrame,
    volume_matrix: pd.DataFrame,
    factors: list[str],
) -> dict[str, pd.DataFrame]:
    """Compute multiple factors simultaneously on GPU.

    Args:
        close_matrix: DataFrame (dates x symbols) of close prices.
        volume_matrix: DataFrame (dates x symbols) of volumes.
        factors: List of factor names to compute.

    Returns:
        ``{factor_name: DataFrame (dates x symbols) of factor values}``
    """
    device = _DEVICE
    logger.info("Computing %d factors on %s (%d dates x %d symbols)", len(factors), device, *close_matrix.shape)

    # Move to GPU tensors
    close_t = torch.tensor(close_matrix.values, dtype=torch.float32, device=device)
    _volume_t = torch.tensor(volume_matrix.values, dtype=torch.float32, device=device)  # reserved for future volume factors
    returns_t = close_t[1:] / close_t[:-1] - 1  # daily returns

    results: dict[str, pd.DataFrame] = {}
    dates = close_matrix.index
    symbols = close_matrix.columns

    for factor in factors:
        if factor == "momentum":
            val = _momentum_gpu(close_t, lookback=252, skip=21)
        elif factor == "volatility":
            val = _volatility_gpu(returns_t, lookback=20)
        elif factor == "ma_cross":
            val = _ma_cross_gpu(close_t, fast=10, slow=50)
        elif factor == "mean_reversion":
            val = _mean_reversion_gpu(close_t, lookback=20)
        elif factor == "rsi":
            val = _rsi_gpu(returns_t, period=14)
        else:
            logger.warning("Unknown GPU factor: %s, skipping", factor)
            continue

        # Move back to CPU and create DataFrame
        val_np = val.cpu().numpy()
        # Pad to match original dates length
        if val_np.shape[0] < len(dates):
            pad = np.full((len(dates) - val_np.shape[0], val_np.shape[1]), np.nan)
            val_np = np.vstack([pad, val_np])
        results[factor] = pd.DataFrame(val_np, index=dates, columns=symbols)

    return results


def _momentum_gpu(close: torch.Tensor, lookback: int = 252, skip: int = 21) -> torch.Tensor:
    """Momentum: close[-skip] / close[-lookback] - 1."""
    T, N = close.shape
    result = torch.full((T, N), float("nan"), device=close.device)
    if T > lookback:
        # For row i (i >= lookback): result[i] = close[i - skip] / close[i - lookback] - 1
        numerator = close[lookback - skip : T - skip]
        denominator = close[: T - lookback]
        result[lookback:] = numerator / denominator - 1
    return result


def _volatility_gpu(returns: torch.Tensor, lookback: int = 20) -> torch.Tensor:
    """Rolling volatility (annualized) via unfold for vectorized computation."""
    T, N = returns.shape
    result = torch.full((T, N), float("nan"), device=returns.device)
    if T >= lookback:
        # Use unfold to create rolling windows: (T - lookback + 1, lookback, N)
        windows = returns.unfold(0, lookback, 1)  # shape: (T - lookback + 1, N, lookback)
        stds = windows.std(dim=2) * (252**0.5)
        result[lookback - 1 :] = stds
    return result


def _ma_cross_gpu(close: torch.Tensor, fast: int = 10, slow: int = 50) -> torch.Tensor:
    """MA crossover signal: fast_ma / slow_ma - 1."""
    T, N = close.shape
    result = torch.full((T, N), float("nan"), device=close.device)
    if T > slow:
        # Compute rolling means using cumsum
        cumsum = torch.cumsum(close, dim=0)
        # fast MA: need indices [fast:] and [:-fast]
        # cumsum[i] - cumsum[i-fast] for i >= fast
        padded = torch.zeros((1, N), device=close.device)
        cumsum_padded = torch.cat([padded, cumsum], dim=0)
        fast_ma = (cumsum_padded[fast:] - cumsum_padded[:-fast]) / fast
        slow_ma = (cumsum_padded[slow:] - cumsum_padded[:-slow]) / slow
        # Align: fast_ma starts at index fast-1, slow_ma at slow-1
        offset = slow - fast
        signal = fast_ma[offset:] / slow_ma - 1
        result[slow:] = signal[1:]  # align to match date indices
    return result


def _mean_reversion_gpu(close: torch.Tensor, lookback: int = 20) -> torch.Tensor:
    """Z-score of price vs rolling mean (negated for mean-reversion signal)."""
    T, N = close.shape
    result = torch.full((T, N), float("nan"), device=close.device)
    if T > lookback:
        padded = torch.zeros((1, N), device=close.device)
        cumsum = torch.cat([padded, torch.cumsum(close, dim=0)], dim=0)
        rolling_mean = (cumsum[lookback:] - cumsum[:-lookback]) / lookback
        # Rolling std via cumsum of squares
        cumsum_sq = torch.cat([padded, torch.cumsum(close**2, dim=0)], dim=0)
        rolling_var = (cumsum_sq[lookback:] - cumsum_sq[:-lookback]) / lookback - rolling_mean**2
        rolling_std = torch.sqrt(torch.clamp(rolling_var, min=1e-10))
        # Z-score at each point: (close[t] - mean) / std
        z = (close[lookback:] - rolling_mean[1:]) / rolling_std[1:]
        result[lookback:] = -z  # negative = mean reversion signal
    return result


def _rsi_gpu(returns: torch.Tensor, period: int = 14) -> torch.Tensor:
    """RSI computed on GPU using unfold for vectorized rolling windows."""
    T, N = returns.shape
    result = torch.full((T, N), float("nan"), device=returns.device)
    if T >= period:
        gains = torch.clamp(returns, min=0)
        losses = torch.clamp(-returns, min=0)

        # Unfold for rolling windows
        gain_windows = gains.unfold(0, period, 1)  # (T - period + 1, N, period)
        loss_windows = losses.unfold(0, period, 1)

        avg_gain = gain_windows.mean(dim=2)
        avg_loss = loss_windows.mean(dim=2)

        rs = avg_gain / torch.clamp(avg_loss, min=1e-10)
        rsi_vals = 100 - 100 / (1 + rs)
        result[period - 1 :] = rsi_vals
    return result
