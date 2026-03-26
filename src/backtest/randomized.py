"""
Randomized Backtest — 隨機抽樣資產和時間的多次回測，評估策略穩健性。

透過多次隨機抽取部分資產和部分時間區間執行回測，
收集績效指標分佈，判斷策略表現是否依賴特定資產或時段。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategy.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class RandomizedBacktestConfig:
    """隨機回測配置。"""

    n_iterations: int = 100
    asset_sample_pct: float = 0.7
    time_sample_pct: float = 0.8
    seed: int | None = None


@dataclass
class RandomizedBacktestResult:
    """隨機回測結果 — 績效指標的分佈統計。"""

    iterations: int
    sharpe_distribution: list[float]
    return_distribution: list[float]
    drawdown_distribution: list[float]

    median_sharpe: float
    sharpe_5th_pct: float
    sharpe_95th_pct: float
    probability_positive_sharpe: float

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"═══ Randomized Backtest Result ({self.iterations} iterations) ═══",
            "",
            "Sharpe Ratio Distribution:",
            f"  Median:       {self.median_sharpe:.3f}",
            f"  5th pct:      {self.sharpe_5th_pct:.3f}",
            f"  95th pct:     {self.sharpe_95th_pct:.3f}",
            f"  P(Sharpe>0):  {self.probability_positive_sharpe:.1%}",
            "",
            "Annual Return Distribution:",
            f"  Median:       {float(np.median(self.return_distribution)):+.2%}",
            f"  5th pct:      {float(np.percentile(self.return_distribution, 5)):+.2%}",
            f"  95th pct:     {float(np.percentile(self.return_distribution, 95)):+.2%}",
            "",
            "Max Drawdown Distribution:",
            f"  Median:       {float(np.median(self.drawdown_distribution)):.2%}",
            f"  95th pct:     {float(np.percentile(self.drawdown_distribution, 95)):.2%}",
        ]
        return "\n".join(lines)


def run_randomized_backtest(
    strategy_factory: Callable[[], Strategy],
    base_config: BacktestConfig,
    randomized_config: RandomizedBacktestConfig | None = None,
) -> RandomizedBacktestResult:
    """執行多次隨機抽樣回測，收集績效分佈。

    Args:
        strategy_factory: 零引數 callable，每次呼叫回傳新的 Strategy 實例。
        base_config: 基礎回測設定（universe / start / end 等）。
        randomized_config: 隨機回測配置。

    Returns:
        RandomizedBacktestResult 包含績效指標分佈。
    """
    if randomized_config is None:
        randomized_config = RandomizedBacktestConfig()

    rng = np.random.default_rng(randomized_config.seed)

    universe = base_config.universe
    start_ts = pd.Timestamp(base_config.start)
    end_ts = pd.Timestamp(base_config.end)
    total_days = (end_ts - start_ts).days

    sharpe_dist: list[float] = []
    return_dist: list[float] = []
    drawdown_dist: list[float] = []

    n_assets = max(1, int(len(universe) * randomized_config.asset_sample_pct))
    sample_days = max(30, int(total_days * randomized_config.time_sample_pct))

    for i in range(randomized_config.n_iterations):
        # 1. Randomly sample assets
        sampled_assets = list(
            rng.choice(universe, size=n_assets, replace=False)
        )

        # 2. Randomly sample a contiguous time sub-period
        max_offset = total_days - sample_days
        if max_offset > 0:
            offset = int(rng.integers(0, max_offset + 1))
        else:
            offset = 0
        sub_start = start_ts + pd.Timedelta(days=offset)
        sub_end = sub_start + pd.Timedelta(days=sample_days)
        # Clamp to original end
        if sub_end > end_ts:
            sub_end = end_ts

        engine = BacktestEngine()

        iter_config = BacktestConfig(
            universe=sampled_assets,
            start=sub_start.strftime("%Y-%m-%d"),
            end=sub_end.strftime("%Y-%m-%d"),
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
            result = engine.run(strategy, iter_config)
            sharpe_dist.append(result.sharpe)
            return_dist.append(result.annual_return)
            drawdown_dist.append(result.max_drawdown)
            logger.debug(
                "Iteration %d/%d: sharpe=%.3f return=%.2f%% dd=%.2f%%",
                i + 1, randomized_config.n_iterations,
                result.sharpe, result.annual_return * 100,
                result.max_drawdown * 100,
            )
        except Exception:
            logger.warning(
                "Iteration %d/%d failed, skipping",
                i + 1, randomized_config.n_iterations,
                exc_info=True,
            )
            continue

    if not sharpe_dist:
        return RandomizedBacktestResult(
            iterations=0,
            sharpe_distribution=[],
            return_distribution=[],
            drawdown_distribution=[],
            median_sharpe=0.0,
            sharpe_5th_pct=0.0,
            sharpe_95th_pct=0.0,
            probability_positive_sharpe=0.0,
        )

    sharpe_arr = np.array(sharpe_dist)
    positive_count = int(np.sum(sharpe_arr > 0))

    return RandomizedBacktestResult(
        iterations=len(sharpe_dist),
        sharpe_distribution=sharpe_dist,
        return_distribution=return_dist,
        drawdown_distribution=drawdown_dist,
        median_sharpe=float(np.median(sharpe_arr)),
        sharpe_5th_pct=float(np.percentile(sharpe_arr, 5)),
        sharpe_95th_pct=float(np.percentile(sharpe_arr, 95)),
        probability_positive_sharpe=positive_count / len(sharpe_dist),
    )
