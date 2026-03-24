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

import numpy as np
import pandas as pd

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
