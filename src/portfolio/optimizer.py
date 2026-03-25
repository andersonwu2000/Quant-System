"""
多資產組合最佳化器。

方法：
- equal_weight: 等權重
- inverse_vol: 波動率倒數加權
- risk_parity: 等風險貢獻
- mean_variance: Markowitz MVO
- black_litterman: Black-Litterman（市場均衡 + 觀點）
- hrp: 階層風險平價 (Hierarchical Risk Parity)
- robust: 最差情境穩健最佳化 (Worst-case Robust)
- resampled: Michaud 重取樣最佳化 (Resampled Efficient Frontier)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.optimize import minimize as scipy_minimize
from scipy.spatial.distance import squareform

from src.portfolio.risk_model import RiskModel, shrink_mean

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    EQUAL_WEIGHT = "equal_weight"
    INVERSE_VOL = "inverse_vol"
    RISK_PARITY = "risk_parity"
    MEAN_VARIANCE = "mean_variance"
    BLACK_LITTERMAN = "black_litterman"
    HRP = "hrp"
    ROBUST = "robust"
    RESAMPLED = "resampled"
    CVAR_OPTIMIZATION = "cvar_optimization"
    MAX_DRAWDOWN = "max_drawdown"
    GLOBAL_MIN_VARIANCE = "global_min_variance"
    MAX_SHARPE = "max_sharpe"
    INDEX_TRACKING = "index_tracking"


@dataclass
class OptimizerConfig:
    """最佳化器配置。"""

    method: OptimizationMethod = OptimizationMethod.RISK_PARITY
    risk_free_rate: float = 0.02      # 無風險利率（年化）
    target_return: float | None = None  # MVO 目標報酬（None=最大 Sharpe）
    max_weight: float = 0.30          # 單一資產上限
    min_weight: float = 0.02          # 最小配置
    long_only: bool = True
    risk_aversion: float = 2.5        # MVO 風險趨避係數
    robust_epsilon: float = 0.1       # 穩健最佳化不確定性集大小
    resample_iterations: int = 500    # Michaud 重取樣迭代次數
    shrink_mean: bool = False         # 是否套用 James-Stein 均值收縮
    cvar_confidence: float = 0.95     # CVaR 最佳化信心水準
    tracking_index: str = ""          # 追蹤指數 symbol（Index Tracking 用）
    tracking_max_stocks: int = 30     # 追蹤組合最大持股數


@dataclass
class BLView:
    """Black-Litterman 觀點。"""

    asset: str                         # 資產 symbol
    expected_return: float             # 觀點預期年化報酬
    confidence: float = 0.5           # 觀點信心（0~1）


@dataclass
class OptimizationResult:
    """最佳化結果。"""

    weights: dict[str, float]
    method: str
    portfolio_return: float = 0.0
    portfolio_risk: float = 0.0
    sharpe_ratio: float = 0.0
    risk_contributions: dict[str, float] = field(default_factory=dict)


class PortfolioOptimizer:
    """多資產組合最佳化器。"""

    def __init__(
        self,
        config: OptimizerConfig | None = None,
        risk_model: RiskModel | None = None,
    ):
        self.config = config or OptimizerConfig()
        self.risk_model = risk_model or RiskModel()

    def optimize(
        self,
        returns: pd.DataFrame,
        views: list[BLView] | None = None,
        expected_returns: pd.Series | None = None,
    ) -> OptimizationResult:
        """執行組合最佳化。

        Args:
            returns: 日報酬 DataFrame (columns=symbols)
            views: Black-Litterman 觀點 (僅 BL 方法需要)
            expected_returns: 預期報酬 (MVO 用; None=用歷史均值)

        Returns:
            OptimizationResult
        """
        cfg = self.config

        if returns.empty or returns.shape[1] < 2:
            symbols = list(returns.columns) if not returns.empty else []
            w = {s: 1.0 / len(symbols) for s in symbols} if symbols else {}
            return OptimizationResult(weights=w, method=cfg.method.value)

        cov = self.risk_model.estimate_covariance(returns)
        if cov.empty:
            symbols = list(returns.columns)
            w = {s: 1.0 / len(symbols) for s in symbols}
            return OptimizationResult(weights=w, method=cfg.method.value)

        symbols = list(cov.columns)

        # 若啟用 James-Stein 均值收縮，事先處理預期報酬
        if cfg.shrink_mean:
            _mu_raw = (
                expected_returns
                if expected_returns is not None
                else returns[symbols].mean() * 252
            )
            _mu_shrunk_arr = shrink_mean(
                np.asarray(_mu_raw.reindex(symbols, fill_value=0.0).values, dtype=np.float64),
                n_obs=len(returns),
            )
            expected_returns = pd.Series(_mu_shrunk_arr, index=symbols)

        if cfg.method == OptimizationMethod.EQUAL_WEIGHT:
            raw = self._equal_weight(symbols)
        elif cfg.method == OptimizationMethod.INVERSE_VOL:
            raw = self._inverse_vol(returns, symbols)
        elif cfg.method == OptimizationMethod.RISK_PARITY:
            raw = self._risk_parity(cov, symbols)
        elif cfg.method == OptimizationMethod.MEAN_VARIANCE:
            mu = expected_returns if expected_returns is not None else returns.mean() * 252
            raw = self._mean_variance(mu, cov, symbols)
        elif cfg.method == OptimizationMethod.BLACK_LITTERMAN:
            raw = self._black_litterman(returns, cov, symbols, views or [])
        elif cfg.method == OptimizationMethod.HRP:
            raw = self._hrp(returns, cov, symbols)
        elif cfg.method == OptimizationMethod.ROBUST:
            mu = expected_returns if expected_returns is not None else returns.mean() * 252
            raw = self._optimize_robust(mu, cov, symbols)
        elif cfg.method == OptimizationMethod.RESAMPLED:
            raw = self._optimize_resampled(returns, cov, symbols, expected_returns)
        elif cfg.method == OptimizationMethod.CVAR_OPTIMIZATION:
            raw = self._optimize_cvar(returns, symbols)
        elif cfg.method == OptimizationMethod.MAX_DRAWDOWN:
            raw = self._optimize_max_drawdown(returns, symbols)
        elif cfg.method == OptimizationMethod.GLOBAL_MIN_VARIANCE:
            raw = self._optimize_gmv(cov, symbols)
        elif cfg.method == OptimizationMethod.MAX_SHARPE:
            mu = expected_returns if expected_returns is not None else returns.mean() * 252
            raw = self._optimize_max_sharpe(mu, cov, symbols)
        elif cfg.method == OptimizationMethod.INDEX_TRACKING:
            raw = self._optimize_index_tracking(returns, symbols)
        else:
            raw = self._equal_weight(symbols)

        # 套用約束
        weights = self._apply_constraints(raw, symbols)

        # 計算組合統計
        port_risk = self.risk_model.portfolio_risk(weights, cov)
        w_arr = np.array([weights.get(s, 0.0) for s in symbols])
        mu_arr = (returns[symbols].mean() * 252).values
        port_ret = float(w_arr @ mu_arr)
        sharpe = (port_ret - cfg.risk_free_rate) / port_risk if port_risk > 0 else 0.0
        rc = self.risk_model.risk_contribution(weights, cov)

        return OptimizationResult(
            weights=weights,
            method=cfg.method.value,
            portfolio_return=round(port_ret, 4),
            portfolio_risk=round(port_risk, 4),
            sharpe_ratio=round(sharpe, 4),
            risk_contributions=rc,
        )

    # ── 最佳化方法 ─────────────────────────────────────────

    @staticmethod
    def _equal_weight(symbols: list[str]) -> dict[str, float]:
        n = len(symbols)
        return {s: 1.0 / n for s in symbols} if n > 0 else {}

    def _inverse_vol(
        self, returns: pd.DataFrame, symbols: list[str],
    ) -> dict[str, float]:
        vol = self.risk_model.compute_volatilities(returns)
        inv = {}
        for s in symbols:
            v = vol.get(s, 0.0)
            inv[s] = 1.0 / v if v > 0 else 0.0
        total = sum(inv.values())
        if total <= 0:
            return self._equal_weight(symbols)
        return {s: inv[s] / total for s in symbols}

    def _risk_parity(
        self, cov: pd.DataFrame, symbols: list[str],
    ) -> dict[str, float]:
        """等風險貢獻 (Risk Parity) — 迭代法。"""
        n = len(symbols)
        w = np.ones(n) / n
        sigma = cov.loc[symbols, symbols].values

        for _ in range(100):
            port_var = w @ sigma @ w
            if port_var <= 0:
                break
            marginal = sigma @ w
            target_rc = port_var / n

            # 調整權重使風險貢獻趨於相等
            for i in range(n):
                if marginal[i] > 0:
                    w[i] = target_rc / marginal[i]

            # 正規化
            total = w.sum()
            if total > 0:
                w = w / total

        return {symbols[i]: float(w[i]) for i in range(n)}

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

    # ── 穩健最佳化 ──────────────────────────────────────────

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

        for _ in range(cfg.resample_iterations):
            sampled_returns = rng.multivariate_normal(mu, sigma, size=252)
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

    # ── CVaR / Max Drawdown 最佳化 ──────────────────────────

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

    # ── G5a: Global Minimum Variance ─────────────────────

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

    # ── G5b: Maximum Sharpe Ratio ──────────────────────────

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

    # ── G5c: Index Tracking (Sparse) ───────────────────────

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

    # ── 約束 ─────────────────────────────────────────────

    def _apply_constraints(
        self,
        raw: dict[str, float],
        symbols: list[str],
    ) -> dict[str, float]:
        """套用權重上下限約束。"""
        cfg = self.config
        w = dict(raw)

        for s in symbols:
            v = w.get(s, 0.0)
            if cfg.long_only:
                v = max(v, 0.0)
            v = min(v, cfg.max_weight)
            if abs(v) < cfg.min_weight:
                v = 0.0
            w[s] = v

        # 正規化
        total = sum(w.values())
        if total > 0:
            w = {s: v / total for s, v in w.items() if v > 0}

        return w
