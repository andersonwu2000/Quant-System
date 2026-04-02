"""Multi-strategy risk budgeting — combine strategy weights by risk contribution.

Allocates capital across style buckets (trend / fundamental / mean_reversion)
using inverse-volatility weighting with correlation adjustment.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class RiskBudgetConfig:
    buckets: dict[str, list[str]]  # bucket_name → [strategy_names]
    lookback_days: int = 120
    min_weight: float = 0.10
    max_weight: float = 0.60


@dataclass
class RiskBudgetResult:
    bucket_weights: dict[str, float]  # bucket → allocation weight
    bucket_vols: dict[str, float]  # bucket → annualized vol
    bucket_corrs: dict[str, dict[str, float]]  # pairwise correlations
    combined_vol: float
    diversification_ratio: float  # weighted avg vol / portfolio vol


def compute_risk_budget(
    strategy_returns: dict[str, pd.Series],  # strategy_name → daily returns
    config: RiskBudgetConfig,
) -> RiskBudgetResult:
    """Compute risk-budget allocation across style buckets."""
    bucket_names = list(config.buckets.keys())
    n = len(bucket_names)

    # 1. Compute each bucket's return as equal-weight average of its strategies
    bucket_returns: dict[str, pd.Series] = {}
    for bucket, strats in config.buckets.items():
        available = [strategy_returns[s] for s in strats if s in strategy_returns]
        if not available:
            raise ValueError(f"No return data for bucket '{bucket}'")
        combined = pd.concat(available, axis=1).iloc[-config.lookback_days:]
        bucket_returns[bucket] = combined.mean(axis=1)

    # 2. Bucket volatilities (annualized)
    bucket_vols = {
        b: float(ret.std() * np.sqrt(252)) for b, ret in bucket_returns.items()
    }

    # 3. Pairwise correlations
    ret_df = pd.DataFrame(bucket_returns)
    corr_matrix = ret_df.corr()
    bucket_corrs: dict[str, dict[str, float]] = {}
    for b in bucket_names:
        bucket_corrs[b] = {b2: float(corr_matrix.loc[b, b2]) for b2 in bucket_names}

    # 4. Inverse-volatility weighting
    inv_vols = np.array([1.0 / max(bucket_vols[b], 1e-8) for b in bucket_names])
    raw_weights = inv_vols / inv_vols.sum()

    # 5. Apply min/max constraints (clip then renormalize)
    clipped = np.clip(raw_weights, config.min_weight, config.max_weight)
    weights = clipped / clipped.sum()
    bucket_weights = {b: float(weights[i]) for i, b in enumerate(bucket_names)}

    # 6. Combined portfolio vol and diversification ratio
    w = weights.reshape(-1, 1)
    cov = ret_df[bucket_names].cov().values * 252
    combined_vol = float(np.sqrt((w.T @ cov @ w)[0, 0]))
    weighted_avg_vol = float(sum(weights[i] * bucket_vols[b] for i, b in enumerate(bucket_names)))
    diversification_ratio = weighted_avg_vol / max(combined_vol, 1e-8)

    return RiskBudgetResult(
        bucket_weights=bucket_weights,
        bucket_vols=bucket_vols,
        bucket_corrs=bucket_corrs,
        combined_vol=combined_vol,
        diversification_ratio=diversification_ratio,
    )
