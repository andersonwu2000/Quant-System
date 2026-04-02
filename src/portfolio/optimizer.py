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

import numpy as np
import pandas as pd

from src.portfolio.methods import AdvancedMethods, BasicMethods, ClassicalMethods
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
    SEMI_VARIANCE = "semi_variance"


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


class PortfolioOptimizer(BasicMethods, ClassicalMethods, AdvancedMethods):
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
        elif cfg.method == OptimizationMethod.SEMI_VARIANCE:
            raw = self._optimize_semi_variance(returns, symbols)
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
