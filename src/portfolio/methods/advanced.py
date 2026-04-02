"""Advanced portfolio optimization methods: HRP, robust, resampled, CVaR, max drawdown, index tracking, semi-variance."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.optimize import minimize as scipy_minimize
from scipy.spatial.distance import squareform

logger = logging.getLogger(__name__)


class AdvancedMethods:
    """Mixin providing advanced optimization methods."""

    def _hrp(
        self,
        returns: pd.DataFrame,
        cov: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """Hierarchical Risk Parity (de Prado 2016)。"""
        n = len(symbols)
        if n < 2:
            return self._equal_weight(symbols)

        # 1. 建立距離矩陣並做層次聚類
        corr = returns[symbols].corr().fillna(0.0)
        dist = np.sqrt(0.5 * (1.0 - corr.values))
        np.fill_diagonal(dist, 0.0)
        dist = np.maximum(dist, 0.0)

        condensed = squareform(dist, checks=False)
        link = linkage(condensed, method="single")
        order = list(leaves_list(link))

        # 2. 遞迴平分
        sigma = cov.loc[symbols, symbols].values
        ordered_symbols = [symbols[i] for i in order]
        w = self._hrp_bisect(ordered_symbols, sigma, symbols)

        return w

    def _hrp_bisect(
        self,
        ordered: list[str],
        sigma: npt.NDArray[np.floating[Any]],
        all_symbols: list[str],
    ) -> dict[str, float]:
        """HRP 遞迴平分。"""
        sym_idx = {s: i for i, s in enumerate(all_symbols)}
        weights = {s: 1.0 for s in ordered}

        clusters = [ordered]
        while clusters:
            new_clusters = []
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                mid = len(cluster) // 2
                left = cluster[:mid]
                right = cluster[mid:]

                # 計算各子群的變異數
                var_left = self._cluster_var(left, sigma, sym_idx)
                var_right = self._cluster_var(right, sigma, sym_idx)

                total_var = var_left + var_right
                if total_var <= 0:
                    alpha = 0.5
                else:
                    alpha = 1.0 - var_left / total_var

                for s in left:
                    weights[s] *= alpha
                for s in right:
                    weights[s] *= (1.0 - alpha)

                if len(left) > 1:
                    new_clusters.append(left)
                if len(right) > 1:
                    new_clusters.append(right)

            clusters = new_clusters

        # 正規化
        total = sum(weights.values())
        if total > 0:
            weights = {s: w / total for s, w in weights.items()}

        return weights

    @staticmethod
    def _cluster_var(
        cluster: list[str],
        sigma: npt.NDArray[np.floating[Any]],
        sym_idx: dict[str, int],
    ) -> float:
        """子群的等權組合變異數。"""
        n = len(cluster)
        if n == 0:
            return 0.0
        idxs = [sym_idx[s] for s in cluster]
        w = np.ones(n) / n
        sub_cov = sigma[np.ix_(idxs, idxs)]
        return float(w @ sub_cov @ w)

    def _optimize_robust(
        self,
        expected_returns: pd.Series,
        cov: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """Worst-case robust MVO with ellipsoidal uncertainty set.

        Maximizes: μ̂'w - ε√(w'Σw) - λ w'Σw
        """
        cfg = self.config
        n = len(symbols)
        mu: npt.NDArray[np.float64] = np.asarray(
            expected_returns.reindex(symbols, fill_value=0.0).values, dtype=np.float64,
        )
        sigma: npt.NDArray[np.float64] = np.asarray(
            cov.loc[symbols, symbols].values, dtype=np.float64,
        )
        eps = cfg.robust_epsilon
        lam = cfg.risk_aversion

        def neg_objective(w: npt.NDArray[np.floating[Any]]) -> float:
            port_var = float(w @ sigma @ w)
            port_std = float(np.sqrt(max(port_var, 1e-12)))
            ret = float(mu @ w)
            return float(-(ret - eps * port_std - lam * port_var))

        w0 = np.ones(n) / n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        lb = 0.0 if cfg.long_only else -cfg.max_weight
        bounds = [(lb, cfg.max_weight)] * n

        result = scipy_minimize(
            neg_objective,
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

    def _optimize_resampled(
        self,
        returns: pd.DataFrame,
        cov: pd.DataFrame,
        symbols: list[str],
        expected_returns: pd.Series | None = None,
    ) -> dict[str, float]:
        """Michaud resampled efficient frontier.

        Draws Monte-Carlo samples from (μ̂, Σ̂), runs MVO on each,
        and averages the resulting weight vectors.
        """
        cfg = self.config
        n = len(symbols)
        mu: npt.NDArray[np.float64] = np.asarray(
            expected_returns.reindex(symbols, fill_value=0.0).values
            if expected_returns is not None
            else (returns[symbols].mean() * 252).values,
            dtype=np.float64,
        )
        sigma: npt.NDArray[np.float64] = np.asarray(
            cov.loc[symbols, symbols].values, dtype=np.float64,
        )

        rng = np.random.default_rng(42)
        accumulated = np.zeros(n)
        valid_count = 0

        # Convert annual mu/sigma to daily for sampling
        daily_mu = mu / 252
        daily_sigma = sigma / 252

        # Ensure numerical stability: force positive-definite via eigenvalue floor
        eigvals, eigvecs = np.linalg.eigh(daily_sigma)
        eigvals = np.maximum(eigvals, 1e-10)
        daily_sigma = eigvecs @ np.diag(eigvals) @ eigvecs.T
        # Symmetrize to avoid floating-point asymmetry
        daily_sigma = (daily_sigma + daily_sigma.T) / 2

        for _ in range(cfg.resample_iterations):
            try:
                sampled_returns = rng.multivariate_normal(daily_mu, daily_sigma, size=252)
            except np.linalg.LinAlgError:
                continue
            sample_mu = sampled_returns.mean(axis=0) * 252
            sample_cov = np.cov(sampled_returns, rowvar=False) * 252

            sample_mu_series = pd.Series(sample_mu, index=symbols)
            sample_cov_df = pd.DataFrame(sample_cov, index=symbols, columns=symbols)
            w = self._mean_variance(sample_mu_series, sample_cov_df, symbols)

            w_arr = np.array([w.get(s, 0.0) for s in symbols])
            accumulated += w_arr
            valid_count += 1

        if valid_count > 0:
            avg = accumulated / valid_count
        else:
            avg = np.ones(n) / n

        if cfg.long_only:
            avg = np.maximum(avg, 0.0)
        total = avg.sum()
        if total > 0:
            avg = avg / total
        else:
            return self._equal_weight(symbols)

        return {symbols[i]: float(avg[i]) for i in range(n)}

    def _optimize_cvar(
        self,
        returns: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """最小化 CVaR (Expected Shortfall) — LP 近似。

        使用 Rockafellar-Uryasev 線性規劃重構：
        min  α + 1/((1-β)·T) Σ_t max(0, -r_t·w - α)
        s.t. Σ w_i = 1, bounds
        """
        cfg = self.config
        n = len(symbols)
        r = returns[symbols].dropna().values  # (T, n)
        T = r.shape[0]

        if T < 10:
            return self._equal_weight(symbols)

        beta = cfg.cvar_confidence

        # 目標函數：CVaR 近似
        def cvar_objective(x: npt.NDArray[np.floating[Any]]) -> float:
            w = x[:n]
            alpha_var = x[n]
            port_returns = r @ w  # (T,)
            losses = np.maximum(-port_returns - alpha_var, 0.0)
            return float(alpha_var + losses.mean() / (1.0 - beta))

        # 初始猜測：等權 + VaR 近似
        w0 = np.ones(n) / n
        alpha0 = 0.0
        x0 = np.append(w0, alpha0)

        # 約束
        def sum_to_one(x: npt.NDArray[np.floating[Any]]) -> float:
            return float(np.sum(x[:n]) - 1.0)

        constraints = [{"type": "eq", "fun": sum_to_one}]

        lb = 0.0 if cfg.long_only else -cfg.max_weight
        bounds = [(lb, cfg.max_weight)] * n + [(None, None)]  # α 無界

        try:
            result = scipy_minimize(
                cvar_objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 500, "ftol": 1e-10},
            )
            if result.success:
                w = result.x[:n]
                # 確保正規化
                total = w.sum()
                if total > 0:
                    w = w / total
                return {symbols[i]: float(w[i]) for i in range(n)}
        except Exception:
            logger.warning("CVaR optimization failed, falling back to equal weight")

        return self._equal_weight(symbols)

    def _optimize_max_drawdown(
        self,
        returns: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """最小化最大回撤 — 歷史模擬法。"""
        cfg = self.config
        n = len(symbols)
        r = returns[symbols].dropna().values  # (T, n)
        T = r.shape[0]

        if T < 10:
            return self._equal_weight(symbols)

        def max_drawdown_objective(w: npt.NDArray[np.floating[Any]]) -> float:
            port_returns = r @ w  # (T,)
            nav = np.cumprod(1.0 + port_returns)
            cummax = np.maximum.accumulate(nav)
            drawdowns = (nav - cummax) / cummax
            return float(-drawdowns.min())  # 最大回撤（正數）

        w0 = np.ones(n) / n

        def sum_to_one(w: npt.NDArray[np.floating[Any]]) -> float:
            return float(np.sum(w) - 1.0)

        constraints = [{"type": "eq", "fun": sum_to_one}]

        lb = 0.0 if cfg.long_only else -cfg.max_weight
        bounds = [(lb, cfg.max_weight)] * n

        try:
            result = scipy_minimize(
                max_drawdown_objective,
                w0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 500, "ftol": 1e-10},
            )
            if result.success:
                w = result.x
                total = w.sum()
                if total > 0:
                    w = w / total
                return {symbols[i]: float(w[i]) for i in range(n)}
        except Exception:
            logger.warning("Max drawdown optimization failed, falling back to equal weight")

        return self._equal_weight(symbols)

    def _optimize_index_tracking(
        self,
        returns: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """Sparse index tracking via LASSO relaxation.

        min ||r_portfolio - r_index||^2 + lambda * ||w||_1
        s.t. sum(w) = 1, bounds
        """
        cfg = self.config
        n = len(symbols)
        r = returns[symbols].dropna().values  # (T, n)
        T = r.shape[0]

        if T < 10:
            return self._equal_weight(symbols)

        # Use equal-weighted portfolio of all symbols as index proxy
        # if no tracking_index is specified
        if cfg.tracking_index and cfg.tracking_index in returns.columns:
            r_index = returns[cfg.tracking_index].dropna().values[-T:]
        else:
            r_index = r.mean(axis=1)

        max_stocks = cfg.tracking_max_stocks

        def tracking_objective(
            w: npt.NDArray[np.floating[Any]], lam: float,
        ) -> float:
            r_port = r @ w
            tracking_err = float(np.sum((r_port - r_index) ** 2) / T)
            l1_penalty = float(lam * np.sum(np.abs(w)))
            return tracking_err + l1_penalty

        lb = 0.0 if cfg.long_only else -cfg.max_weight
        bounds = [(lb, cfg.max_weight)] * n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

        # Binary search for lambda that gives ~tracking_max_stocks non-zero
        lam_low = 0.0
        lam_high = 1.0
        best_w = np.ones(n) / n

        for _ in range(20):
            lam_mid = (lam_low + lam_high) / 2.0
            w0 = np.ones(n) / n

            try:
                result = scipy_minimize(
                    lambda w, _lam=lam_mid: tracking_objective(w, _lam),
                    w0,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=constraints,
                    options={"maxiter": 300, "ftol": 1e-10},
                )
                if result.success:
                    w = result.x
                    if cfg.long_only:
                        w = np.maximum(w, 0.0)
                    n_nonzero = int(np.sum(np.abs(w) > 1e-4))

                    if n_nonzero <= max_stocks:
                        best_w = w.copy()
                        lam_high = lam_mid
                    else:
                        lam_low = lam_mid
                else:
                    lam_low = lam_mid
            except Exception:
                lam_low = lam_mid

        # Zero out tiny weights
        best_w[np.abs(best_w) < 1e-4] = 0.0
        total = best_w.sum()
        if total > 0:
            best_w = best_w / total
        else:
            return self._equal_weight(symbols)

        return {symbols[i]: float(best_w[i]) for i in range(n)}

    def _optimize_semi_variance(
        self,
        returns: pd.DataFrame,
        symbols: list[str],
    ) -> dict[str, float]:
        """Semi-variance optimization — only penalizes downside co-movements.

        Computes semi-covariance matrix:
            Σ_down[i,j] = E[min(r_i - μ_i, 0) × min(r_j - μ_j, 0)]
        Minimizes w'Σ_down w subject to sum(w)=1, bounds.
        """
        cfg = self.config
        n = len(symbols)
        r = returns[symbols].dropna().values  # (T, n)
        T = r.shape[0]

        if T < 10:
            return self._equal_weight(symbols)

        # Compute semi-covariance matrix
        mu = r.mean(axis=0)
        downside = np.minimum(r - mu, 0.0)  # (T, n)
        semi_cov: npt.NDArray[np.float64] = np.asarray(
            (downside.T @ downside) / T, dtype=np.float64,
        )

        # Regularize to ensure positive semi-definite
        semi_cov += np.eye(n) * 1e-8

        def semi_var_objective(w: npt.NDArray[np.floating[Any]]) -> float:
            return float(w @ semi_cov @ w)

        w0 = np.ones(n) / n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        lb = 0.0 if cfg.long_only else -cfg.max_weight
        bounds = [(lb, cfg.max_weight)] * n

        try:
            result = scipy_minimize(
                semi_var_objective,
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
            logger.warning("Semi-variance optimization failed, falling back to equal weight")

        return self._equal_weight(symbols)
