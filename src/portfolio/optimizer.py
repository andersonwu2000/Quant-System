"""
多資產組合最佳化器。

方法：
- equal_weight: 等權重
- inverse_vol: 波動率倒數加權
- risk_parity: 等風險貢獻
- mean_variance: Markowitz MVO
- black_litterman: Black-Litterman（市場均衡 + 觀點）
- hrp: 階層風險平價 (Hierarchical Risk Parity)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.spatial.distance import squareform

from src.portfolio.risk_model import RiskModel

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    EQUAL_WEIGHT = "equal_weight"
    INVERSE_VOL = "inverse_vol"
    RISK_PARITY = "risk_parity"
    MEAN_VARIANCE = "mean_variance"
    BLACK_LITTERMAN = "black_litterman"
    HRP = "hrp"


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
        sigma: np.ndarray,
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
        sigma: np.ndarray,
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
