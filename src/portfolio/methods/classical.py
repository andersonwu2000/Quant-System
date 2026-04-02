"""Classical portfolio optimization methods: MVO, Black-Litterman, GMV, Max Sharpe."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.optimize import minimize as scipy_minimize

if TYPE_CHECKING:
    from src.portfolio.optimizer import BLView

logger = logging.getLogger(__name__)


class ClassicalMethods:
    """Mixin providing classical optimization methods."""

    def _mean_variance(
        self,
        expected_returns: pd.Series,
        cov: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """Markowitz MVO — 最大 Sharpe 或最小變異數。"""
        cfg = self.config
        n = len(symbols)
        mu = expected_returns.reindex(symbols, fill_value=0.0).values
        sigma = cov.loc[symbols, symbols].values

        # 最大 Sharpe: w = Σ^(-1)(μ - rf) / sum
        try:
            sigma_inv = np.linalg.inv(sigma + np.eye(n) * 1e-8)
        except np.linalg.LinAlgError:
            return self._equal_weight(symbols)

        excess = np.asarray(mu, dtype=np.float64) - cfg.risk_free_rate
        raw_w = sigma_inv @ excess

        if cfg.long_only:
            raw_w = np.maximum(raw_w, 0.0)

        total = raw_w.sum()
        if total <= 0:
            return self._equal_weight(symbols)

        w = raw_w / total
        return {symbols[i]: float(w[i]) for i in range(n)}

    def _black_litterman(
        self,
        returns: pd.DataFrame,
        cov: pd.DataFrame,
        symbols: list[str],
        views: list[BLView],
    ) -> dict[str, float]:
        """Black-Litterman 模型。"""
        cfg = self.config
        n = len(symbols)
        sigma = cov.loc[symbols, symbols].values
        sym_idx = {s: i for i, s in enumerate(symbols)}

        # 市場均衡報酬: π = δΣw_mkt (假設等權為市場)
        w_mkt = np.ones(n) / n
        pi = cfg.risk_aversion * sigma @ w_mkt

        if not views:
            # 無觀點 → 用均衡報酬做 MVO
            mu = pd.Series(pi, index=symbols)
            return self._mean_variance(mu, cov, symbols)

        # 建構 P, Q, Ω 矩陣
        k = len(views)
        P = np.zeros((k, n))
        Q = np.zeros(k)
        omega_diag = np.zeros(k)
        tau = 0.05  # 不確定性參數

        for j, v in enumerate(views):
            if v.asset in sym_idx:
                P[j, sym_idx[v.asset]] = 1.0
                Q[j] = v.expected_return
                # Ω_jj = (1/confidence - 1) × τ × σ_asset^2
                asset_var = sigma[sym_idx[v.asset], sym_idx[v.asset]]
                conf = max(min(v.confidence, 0.99), 0.01)
                omega_diag[j] = (1.0 / conf - 1.0) * tau * asset_var

        # BL 後驗報酬: μ_BL = [(τΣ)^-1 + P'Ω^-1 P]^-1 [(τΣ)^-1 π + P'Ω^-1 Q]
        try:
            tau_sigma_inv = np.linalg.inv(tau * sigma + np.eye(n) * 1e-10)
            omega_inv = np.diag(1.0 / np.maximum(omega_diag, 1e-10))

            A = tau_sigma_inv + P.T @ omega_inv @ P
            A_inv = np.linalg.inv(A + np.eye(n) * 1e-10)
            b = tau_sigma_inv @ pi + P.T @ omega_inv @ Q
            mu_bl = A_inv @ b
        except np.linalg.LinAlgError:
            mu_bl = pi

        mu_series = pd.Series(mu_bl, index=symbols)
        return self._mean_variance(mu_series, cov, symbols)

    def _optimize_gmv(
        self,
        cov: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """Global Minimum Variance: min w'Sigma w s.t. sum(w)=1."""
        cfg = self.config
        n = len(symbols)
        sigma: npt.NDArray[np.float64] = np.asarray(
            cov.loc[symbols, symbols].values, dtype=np.float64,
        )

        def portfolio_variance(w: npt.NDArray[np.floating[Any]]) -> float:
            return float(w @ sigma @ w)

        w0 = np.ones(n) / n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        lb = 0.0 if cfg.long_only else -cfg.max_weight
        bounds = [(lb, cfg.max_weight)] * n

        result = scipy_minimize(
            portfolio_variance,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-12},
        )

        w = result.x
        if cfg.long_only:
            w = np.maximum(w, 0.0)
        total = w.sum()
        if total > 0:
            w = w / total
        else:
            return self._equal_weight(symbols)

        return {symbols[i]: float(w[i]) for i in range(n)}

    def _optimize_max_sharpe(
        self,
        expected_returns: pd.Series,
        cov: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """Maximum Sharpe Ratio via Dinkelbach / SLSQP.

        Unconstrained analytical: w* = Sigma^{-1}(mu-rf) / 1'Sigma^{-1}(mu-rf)
        With constraints: maximize (mu'w - rf) / sqrt(w'Sigma w) via SLSQP.
        """
        cfg = self.config
        n = len(symbols)
        mu: npt.NDArray[np.float64] = np.asarray(
            expected_returns.reindex(symbols, fill_value=0.0).values, dtype=np.float64,
        )
        sigma: npt.NDArray[np.float64] = np.asarray(
            cov.loc[symbols, symbols].values, dtype=np.float64,
        )
        rf = cfg.risk_free_rate

        def neg_sharpe(w: npt.NDArray[np.floating[Any]]) -> float:
            port_ret = float(mu @ w)
            port_var = float(w @ sigma @ w)
            port_std = float(np.sqrt(max(port_var, 1e-12)))
            return float(-(port_ret - rf) / port_std)

        w0 = np.ones(n) / n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        lb = 0.0 if cfg.long_only else -cfg.max_weight
        bounds = [(lb, cfg.max_weight)] * n

        try:
            result = scipy_minimize(
                neg_sharpe,
                w0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 500, "ftol": 1e-12},
            )
            if result.success:
                w = result.x
                if cfg.long_only:
                    w = np.maximum(w, 0.0)
                total = w.sum()
                if total > 0:
                    w = w / total
                return {symbols[i]: float(w[i]) for i in range(n)}
        except Exception:
            logger.warning("Max Sharpe optimization failed, falling back to MVO")

        # Fallback: analytical MVO
        return self._mean_variance(expected_returns, cov, symbols)
