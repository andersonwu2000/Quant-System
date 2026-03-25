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
    use_garch: bool = False        # GARCH(1,1) 波動率模型
    factor_model: bool = False     # PCA 因子模型共變異數
    n_factors: int = 5             # PCA 因子數


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

        if cfg.factor_model:
            factor_cov = estimate_factor_covariance(r, n_factors=cfg.n_factors)
            cov = pd.DataFrame(factor_cov, index=cov.index, columns=cov.columns)

        if cfg.use_garch:
            cov = self._apply_garch_covariance(r, cov)

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

    # ── GARCH covariance ─────────────────────────────────

    def _apply_garch_covariance(
        self,
        returns: pd.DataFrame,
        sample_cov: pd.DataFrame,
    ) -> pd.DataFrame:
        """DCC-like approach: GARCH vols on diagonal + sample correlation.

        Replace diagonal of covariance with GARCH-estimated variances while
        keeping the correlation structure from the sample.
        """
        symbols = list(sample_cov.columns)

        # Extract correlation from sample covariance
        vols = np.sqrt(np.diag(sample_cov.values))
        safe_vols = np.where(vols > 0, vols, 1.0)
        D_inv = np.diag(1.0 / safe_vols)
        corr_mat = D_inv @ sample_cov.values @ D_inv
        np.fill_diagonal(corr_mat, 1.0)

        # Estimate GARCH vols per asset
        garch_vols = np.zeros(len(symbols))
        for i, sym in enumerate(symbols):
            if sym in returns.columns:
                vol_series = estimate_garch_volatility(
                    returns[sym].dropna(), annualize=False,
                )
                if len(vol_series) > 0:
                    garch_vols[i] = float(vol_series.iloc[-1])
                else:
                    garch_vols[i] = safe_vols[i]
            else:
                garch_vols[i] = safe_vols[i]

        # Reconstruct: Σ = D_garch · R · D_garch
        D_garch = np.diag(garch_vols)
        cov_mat = D_garch @ corr_mat @ D_garch

        return pd.DataFrame(cov_mat, index=sample_cov.index, columns=sample_cov.columns)

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


# ── GARCH(1,1) Volatility ──────────────────────────────────


def estimate_garch_volatility(
    returns: pd.Series,
    p: int = 1,
    q: int = 1,
    annualize: bool = True,
) -> pd.Series:
    """Estimate time-varying volatility via simple GARCH(1,1).

    Uses recursive variance: sigma2_t = omega + alpha * eps2_{t-1} + beta * sigma2_{t-1}
    Parameters estimated via moment-matching heuristic (EWM-based).

    Args:
        returns: Daily return series.
        p: GARCH lag order (currently only 1 supported).
        q: ARCH lag order (currently only 1 supported).
        annualize: Whether to annualize (multiply by sqrt(252)).

    Returns:
        Annualized volatility series (same index as input).
    """
    _ = p, q  # reserved for future extension
    r = returns.dropna()
    if len(r) < 10:
        return pd.Series(dtype=float)

    # Heuristic GARCH(1,1) parameters via EWM calibration
    # alpha ~ 0.06, beta ~ 0.93, omega from unconditional variance
    alpha = 0.06
    beta = 0.93
    omega_scale = 1.0 - alpha - beta  # = 0.01
    unconditional_var = float(r.var())
    omega = omega_scale * unconditional_var

    r_arr = np.asarray(r.values, dtype=np.float64)
    eps2 = (r_arr - r_arr.mean()) ** 2
    n = len(eps2)
    sigma2 = np.empty(n)
    sigma2[0] = unconditional_var

    for t in range(1, n):
        sigma2[t] = omega + alpha * eps2[t - 1] + beta * sigma2[t - 1]
        # Floor to avoid numerical issues
        sigma2[t] = max(sigma2[t], 1e-12)

    vol = np.sqrt(sigma2)
    if annualize:
        vol = vol * np.sqrt(252)

    return pd.Series(vol, index=r.index, name="garch_vol")


# ── Factor Model Covariance ────────────────────────────────


def estimate_factor_covariance(
    returns: pd.DataFrame,
    n_factors: int = 5,
) -> npt.NDArray[np.float64]:
    """PCA-based factor model covariance: Sigma = B Sigma_f B' + Psi.

    Args:
        returns: Daily returns DataFrame (T x N).
        n_factors: Number of PCA factors to extract.

    Returns:
        Structured covariance matrix (N x N) as numpy array.
    """
    r = returns.dropna().values
    T, N = r.shape

    if T < 10 or N < 2:
        return np.cov(r, rowvar=False)

    # Cap n_factors at min(T, N) - 1
    k = min(n_factors, min(T, N) - 1)

    # Demean
    r_centered = r - r.mean(axis=0)

    # SVD for PCA
    U, S, Vt = np.linalg.svd(r_centered, full_matrices=False)

    # Factor loadings: B = V[:k, :].T * S[:k] / sqrt(T)
    # Factor returns: F = U[:, :k] * S[:k]
    F = U[:, :k] * S[:k]  # (T, k)
    B = Vt[:k, :].T  # (N, k)

    # Factor covariance
    Sigma_f = np.cov(F, rowvar=False)  # (k, k)
    if Sigma_f.ndim == 0:
        Sigma_f = np.array([[float(Sigma_f)]])

    # Residuals
    residuals = r_centered - F @ B.T  # (T, N)
    Psi = np.diag(np.var(residuals, axis=0))  # diagonal idiosyncratic

    # Structured covariance
    cov: npt.NDArray[np.float64] = B @ Sigma_f @ B.T + Psi
    return cov
