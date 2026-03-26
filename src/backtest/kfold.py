"""
K-Fold Cross-Validation Backtest — 將時序切為 k 折，輪流作為測試集。

與傳統 k-fold 不同，為保持時序連續性，每一折是連續的時間區間。
訓練集為其餘所有折的合集（不用於策略擬合，僅收集測試集績效）。

注意：因為策略不做 fold 內參數優化，這裡的 k-fold 主要用來
評估策略在不同時段的穩定性，而非傳統 ML 的交叉驗證。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from src.backtest.analytics import BacktestResult
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategy.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class KFoldBacktestResult:
    """K-Fold 回測結果。"""

    k: int
    fold_results: list[BacktestResult] = field(default_factory=list)
    avg_sharpe: float = 0.0
    std_sharpe: float = 0.0
    avg_return: float = 0.0

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"═══ K-Fold Backtest Result (k={self.k}) ═══",
            "",
            f"Avg Sharpe:    {self.avg_sharpe:.3f} ± {self.std_sharpe:.3f}",
            f"Avg Return:    {self.avg_return:+.2%}",
            "",
            "Per-fold results:",
        ]
        for i, r in enumerate(self.fold_results):
            lines.append(
                f"  Fold {i}: sharpe={r.sharpe:.3f}  "
                f"return={r.annual_return:+.2%}  "
                f"maxdd={r.max_drawdown:.2%}"
            )
        return "\n".join(lines)


def run_kfold_backtest(
    strategy_factory: Callable[[], Strategy],
    base_config: BacktestConfig,
    k: int = 5,
) -> KFoldBacktestResult:
    """執行 k-fold 時序交叉驗證回測。

    Args:
        strategy_factory: 零引數 callable，每次呼叫回傳新的 Strategy 實例。
        base_config: 基礎回測設定。
        k: 折數（≥ 2）。

    Returns:
        KFoldBacktestResult 包含各折績效和匯總統計。

    Raises:
        ValueError: k < 2 或日期範圍不足。
    """
    if k < 2:
        raise ValueError(f"k must be >= 2, got {k}")

    start_ts = pd.Timestamp(base_config.start)
    end_ts = pd.Timestamp(base_config.end)
    total_days = (end_ts - start_ts).days

    if total_days < k * 30:
        raise ValueError(
            f"Insufficient date range for {k} folds. "
            f"Need at least {k * 30} days, got {total_days}."
        )

    # Split into k equal time segments
    fold_size_days = total_days // k
    fold_boundaries: list[tuple[str, str]] = []

    for j in range(k):
        fs_ts = start_ts + pd.Timedelta(days=j * fold_size_days)
        if j < k - 1:
            fe_ts = start_ts + pd.Timedelta(days=(j + 1) * fold_size_days - 1)
        else:
            fe_ts = end_ts
        fold_boundaries.append((
            fs_ts.strftime("%Y-%m-%d"),
            fe_ts.strftime("%Y-%m-%d"),
        ))

    logger.info(
        "K-Fold Backtest: k=%d, fold_size=%d days, %s ~ %s",
        k, fold_size_days, base_config.start, base_config.end,
    )

    fold_results: list[BacktestResult] = []

    for i, (fold_start, fold_end) in enumerate(fold_boundaries):
        logger.info("Fold %d/%d: %s ~ %s", i + 1, k, fold_start, fold_end)

        engine = BacktestEngine()

        fold_config = BacktestConfig(
            universe=base_config.universe,
            start=fold_start,
            end=fold_end,
            initial_cash=base_config.initial_cash,
            freq=base_config.freq,
            rebalance_freq=base_config.rebalance_freq,
            slippage_bps=base_config.slippage_bps,
            commission_rate=base_config.commission_rate,
            tax_rate=base_config.tax_rate,
            risk_rules=base_config.risk_rules,
            execution_delay=base_config.execution_delay,
            enable_kill_switch=base_config.enable_kill_switch,
            settlement_days=base_config.settlement_days,
            impact_model=base_config.impact_model,
        )

        try:
            strategy = strategy_factory()
            result = engine.run(strategy, fold_config)
            fold_results.append(result)
            logger.info(
                "Fold %d: sharpe=%.3f return=%.2f%% maxdd=%.2f%%",
                i + 1, result.sharpe,
                result.annual_return * 100,
                result.max_drawdown * 100,
            )
        except Exception:
            logger.warning("Fold %d failed, skipping", i + 1, exc_info=True)
            continue

    sharpes = [r.sharpe for r in fold_results]
    returns = [r.annual_return for r in fold_results]

    return KFoldBacktestResult(
        k=k,
        fold_results=fold_results,
        avg_sharpe=float(np.mean(sharpes)) if sharpes else 0.0,
        std_sharpe=float(np.std(sharpes)) if sharpes else 0.0,
        avg_return=float(np.mean(returns)) if returns else 0.0,
    )
