"""
跨資產風險模型 — 相關矩陣估計 + 風險分解。

支援：
- 歷史法共變異數矩陣（指數加權可選）
- Ledoit-Wolf 收縮估計
- 因子風險分解
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class RiskModelConfig:
    """風險模型配置。"""

    lookback: int = 252            # 回望期（交易日）
    ewm_halflife: int | None = None  # 指數加權半衰期（None=等權）
    shrinkage: bool = True         # Ledoit-Wolf 收縮
    min_history: int = 60          # 最少需要的歷史長度
    annualize: bool = True         # 年化


class RiskModel:
    """跨資產風險模型。"""

    def __init__(self, config: RiskModelConfig | None = None):
        self._config = config or RiskModelConfig()

    def estimate_covariance(
        self,
        returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """估計共變異數矩陣。

        Args:
            returns: 日報酬 DataFrame, columns=symbols, index=dates

        Returns:
            共變異數矩陣 DataFrame (annualized if configured)
        """
        cfg = self._config

        if returns.empty or len(returns) < cfg.min_history:
            logger.warning(
                "Insufficient data for covariance: %d rows (need %d)",
                len(returns), cfg.min_history,
            )
            return pd.DataFrame()

        # 取最近 lookback 期
        r = returns.iloc[-cfg.lookback:].dropna(axis=1, how="all")
        r = r.fillna(0.0)

        if r.shape[1] < 2:
            return pd.DataFrame()

        if cfg.ewm_halflife is not None:
            # 指數加權共變異數
            cov = r.ewm(halflife=cfg.ewm_halflife).cov().iloc[-r.shape[1]:]
            cov.index = cov.index.droplevel(0)
        else:
            cov = r.cov()

        if cfg.shrinkage:
            cov = self._ledoit_wolf_shrink(cov, r)

        if cfg.annualize:
            cov = cov * 252

        return cov

    def estimate_correlation(
        self,
        returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """估計相關矩陣。"""
        cfg = self._config
        r = returns.iloc[-cfg.lookback:].dropna(axis=1, how="all").fillna(0.0)
        if r.shape[1] < 2:
            return pd.DataFrame()
        return r.corr()

    def compute_volatilities(
        self,
        returns: pd.DataFrame,
    ) -> pd.Series:
        """計算各資產年化波動率。"""
        cfg = self._config
        r = returns.iloc[-cfg.lookback:].dropna(axis=1, how="all").fillna(0.0)
        if r.empty:
            return pd.Series(dtype=float)
        vol = r.std()
        if cfg.annualize:
            vol = vol * np.sqrt(252)
        return vol

    def portfolio_risk(
        self,
        weights: dict[str, float],
        cov: pd.DataFrame,
    ) -> float:
        """計算組合年化波動率。

        Args:
            weights: symbol → weight
            cov: 共變異數矩陣

        Returns:
            組合波動率（年化）
        """
        if cov.empty or not weights:
            return 0.0

        symbols = [s for s in weights if s in cov.columns]
        if not symbols:
            return 0.0

        w = np.array([weights[s] for s in symbols])
        c = cov.loc[symbols, symbols].values

        variance = float(w @ c @ w)
        return float(np.sqrt(max(variance, 0.0)))

    def risk_contribution(
        self,
        weights: dict[str, float],
        cov: pd.DataFrame,
    ) -> dict[str, float]:
        """計算各資產的邊際風險貢獻。

        Returns:
            symbol → risk contribution (proportional, sums to 1)
        """
        if cov.empty or not weights:
            return {}

        symbols = [s for s in weights if s in cov.columns]
        if len(symbols) < 2:
            return {s: 1.0 for s in symbols}

        w = np.array([weights[s] for s in symbols])
        c = cov.loc[symbols, symbols].values

        port_var = float(w @ c @ w)
        if port_var <= 0:
            return {s: 1.0 / len(symbols) for s in symbols}

        # Marginal risk contribution: w_i * (Σw)_i / σ_p
        marginal = w * (c @ w)
        total = marginal.sum()
        if total <= 0:
            return {s: 1.0 / len(symbols) for s in symbols}

        rc = marginal / total
        return {symbols[i]: float(rc[i]) for i in range(len(symbols))}

    # ── VaR / CVaR ─────────────────────────────────────────

    @staticmethod
    def compute_var(
        returns: pd.Series,
        confidence: float = 0.95,
        method: str = "historical",
    ) -> float:
        """計算 Value at Risk。

        Args:
            returns: 日報酬序列
            confidence: 信心水準（如 0.95 表示 95% VaR）
            method: "historical" 或 "parametric"

        Returns:
            VaR（正數，代表損失）
        """
        clean = returns.dropna()
        if len(clean) < 2:
            return 0.0

        alpha = 1.0 - confidence

        if method == "parametric":
            mu = float(clean.mean())
            sigma = float(clean.std(ddof=1))
            if sigma <= 0:
                return 0.0
            z = float(stats.norm.ppf(alpha))
            var = -(mu + z * sigma)
            return float(max(var, 0.0))
        else:
            # historical
            quantile_val = float(np.percentile(clean.to_numpy(), alpha * 100))
            return float(max(-quantile_val, 0.0))

    @staticmethod
    def compute_cvar(
        returns: pd.Series,
        confidence: float = 0.95,
        method: str = "historical",
    ) -> float:
        """計算 Conditional VaR (Expected Shortfall)。

        Args:
            returns: 日報酬序列
            confidence: 信心水準
            method: "historical" 或 "parametric"

        Returns:
            CVaR（正數，代表損失）
        """
        clean = returns.dropna()
        if len(clean) < 2:
            return 0.0

        alpha = 1.0 - confidence

        if method == "parametric":
            mu = float(clean.mean())
            sigma = float(clean.std(ddof=1))
            if sigma <= 0:
                return 0.0
            z_alpha = stats.norm.ppf(alpha)
            # CVaR for normal: μ + σ * φ(z_α) / α  (but we want loss = negative)
            # ES = -(μ - σ * φ(Φ^{-1}(α)) / α)
            pdf_val = float(stats.norm.pdf(z_alpha))
            cvar = -(mu - sigma * pdf_val / alpha)
            return max(cvar, 0.0)
        else:
            # historical: average of returns at or below the VaR percentile
            quantile_val = float(np.percentile(clean.to_numpy(), alpha * 100))
            tail = clean[clean <= quantile_val]
            if len(tail) == 0:
                return float(max(-quantile_val, 0.0))
            return float(max(-float(tail.mean()), 0.0))

    # ── Ledoit-Wolf 收縮 ─────────────────────────────────

    @staticmethod
    def _ledoit_wolf_shrink(
        sample_cov: pd.DataFrame,
        returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """Ledoit-Wolf 線性收縮（向對角矩陣收縮）。"""
        n, p = returns.shape
        if n < 2 or p < 2:
            return sample_cov

        S = sample_cov.values
        target = np.diag(np.diag(S))  # 對角矩陣（個別變異數）

        # 計算最優收縮強度
        X = returns.values - returns.values.mean(axis=0)
        S2 = (X.T @ X) / n

        # 分子：E[||X_t X_t^T - S||^2]
        delta = S - target
        sum_sq = np.sum(delta ** 2)

        # Simplified Ledoit-Wolf formula
        # Optimal shrinkage intensity
        rho_num = 0.0
        for t in range(n):
            xt = X[t:t + 1, :]
            m = xt.T @ xt - S2
            rho_num += np.sum(m ** 2)
        rho_num /= n * n

        rho = min(max(rho_num / sum_sq, 0.0), 1.0) if sum_sq > 0 else 0.0

        shrunk = (1 - rho) * S + rho * target
        return pd.DataFrame(shrunk, index=sample_cov.index, columns=sample_cov.columns)


def shrink_mean(
    sample_mean: npt.NDArray[np.floating[Any]],
    n_obs: int | None = None,
    grand_mean: float | None = None,
) -> npt.NDArray[np.float64]:
    """James-Stein mean shrinkage estimator.

    μ_JS = (1-c)μ̂ + c·μ₀·1
    c = max(0, (p-2) / (n·‖μ̂ - μ₀·1‖²))

    Args:
        sample_mean: Sample mean vector (p-dimensional).
        n_obs: Number of observations used to compute the sample mean.
               If None, defaults to 252.
        grand_mean: Target shrinkage mean. If None, uses cross-sectional
                    average of sample_mean.

    Returns:
        Shrunk mean vector.
    """
    mu = np.asarray(sample_mean, dtype=np.float64).ravel()
    p = len(mu)

    # James-Stein requires p >= 3 to shrink
    if p < 3:
        return mu.copy()

    if n_obs is None:
        n_obs = 252

    if grand_mean is None:
        mu0 = float(np.mean(mu))
    else:
        mu0 = float(grand_mean)

    diff = mu - mu0
    norm_sq = float(diff @ diff)

    if norm_sq <= 0:
        return mu.copy()

    c = max(0.0, (p - 2) / (n_obs * norm_sq))
    c = min(c, 1.0)  # cap at 1 for stability

    result: npt.NDArray[np.float64] = (1.0 - c) * mu + c * mu0
    return result
