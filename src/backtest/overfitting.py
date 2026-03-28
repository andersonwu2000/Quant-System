"""
Probability of Backtest Overfitting (PBO) — Bailey et al. (2017) CSCV 方法。

Combinatorially Symmetric Cross-Validation (CSCV):
將回報時序切成 S 等分，對所有 C(S, S/2) 組合進行 IS/OOS 排名比較，
衡量策略過擬合的機率。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PBOResult:
    """PBO 計算結果。"""

    pbo: float
    logits: list[float]
    n_combinations: int
    is_overfit: bool

    def summary(self) -> str:
        """Human-readable summary."""
        status = "OVERFIT" if self.is_overfit else "OK"
        lines = [
            "═══ Probability of Backtest Overfitting ═══",
            "",
            f"PBO:              {self.pbo:.3f}  ({status})",
            f"Combinations:     {self.n_combinations}",
            f"Logits (mean):    {float(np.mean(self.logits)):.3f}" if self.logits else "Logits: N/A",
            "",
            "PBO > 0.5 indicates the strategy is likely overfit.",
        ]
        return "\n".join(lines)


def compute_pbo(
    returns_matrix: pd.DataFrame,
    n_partitions: int = 10,
) -> PBOResult:
    """計算 Probability of Backtest Overfitting (CSCV).

    Args:
        returns_matrix: DataFrame，每一欄是一個策略/試驗的日收益率序列，
                        index 是日期，columns 是策略/試驗標籤。
                        至少需要 2 欄（2 個策略變體）。
        n_partitions: 時序切割份數 S（必須為偶數，≥ 2）。

    Returns:
        PBOResult 包含過擬合機率和相關統計。

    Raises:
        ValueError: 參數不合法時。
    """
    if returns_matrix.shape[1] < 2:
        raise ValueError(
            f"returns_matrix needs at least 2 columns (strategies), "
            f"got {returns_matrix.shape[1]}"
        )

    if n_partitions < 2:
        raise ValueError(f"n_partitions must be >= 2, got {n_partitions}")

    # Force even number of partitions
    if n_partitions % 2 != 0:
        n_partitions += 1
        logger.info("Adjusted n_partitions to %d (must be even)", n_partitions)

    n_rows = len(returns_matrix)
    if n_rows < n_partitions:
        raise ValueError(
            f"Not enough data rows ({n_rows}) for {n_partitions} partitions"
        )

    # Step 1: Split into S equal sub-periods (discard remainder for equal partitions)
    partition_size = n_rows // n_partitions
    usable_rows = partition_size * n_partitions
    trimmed = returns_matrix.iloc[:usable_rows]
    partitions: list[pd.DataFrame] = []
    for i in range(n_partitions):
        start_idx = i * partition_size
        end_idx = start_idx + partition_size
        partitions.append(trimmed.iloc[start_idx:end_idx])

    half = n_partitions // 2

    # Limit combinations to avoid combinatorial explosion
    max_combos = 500
    all_combos = list(combinations(range(n_partitions), half))
    if len(all_combos) > max_combos:
        rng = np.random.default_rng(42)
        combo_indices = rng.choice(len(all_combos), size=max_combos, replace=False)
        selected_combos = [all_combos[i] for i in combo_indices]
    else:
        selected_combos = all_combos

    logits: list[float] = []
    strategies = returns_matrix.columns.tolist()
    n_strats = len(strategies)

    for is_indices in selected_combos:
        oos_indices = tuple(i for i in range(n_partitions) if i not in is_indices)

        is_data = pd.concat([partitions[i] for i in is_indices])
        oos_data = pd.concat([partitions[i] for i in oos_indices])

        is_sharpes: dict[str, float] = {}
        oos_sharpes: dict[str, float] = {}

        for col in strategies:
            is_sharpes[col] = _sharpe(is_data[col].dropna())
            oos_sharpes[col] = _sharpe(oos_data[col].dropna())

        best_is_strategy = max(is_sharpes, key=lambda k: is_sharpes[k])
        oos_sharpe_best = oos_sharpes[best_is_strategy]

        # OOS rank ratio: fraction of OTHER strategies that best-IS beats
        rank_below = sum(
            1 for s in strategies
            if s != best_is_strategy and oos_sharpes[s] < oos_sharpe_best
        )
        rank_ratio = rank_below / max(n_strats - 1, 1)

        # Logit: log(p / (1-p)), clamped to avoid log(0)/log(inf)
        p = max(0.01, min(0.99, rank_ratio))
        logit = float(np.log(p / (1.0 - p)))
        logits.append(logit)

    # PBO = fraction of combinations where logit <= 0
    # (best-IS strategy ranked at or below median OOS)
    pbo = sum(1 for val in logits if val <= 0) / len(logits) if logits else 1.0

    return PBOResult(
        pbo=pbo,
        logits=logits,
        n_combinations=len(selected_combos),
        is_overfit=pbo > 0.5,
    )


def _sharpe(returns: pd.Series) -> float:
    """年化 Sharpe ratio（無風險利率=0）。"""
    if len(returns) < 2:
        return 0.0
    mean_ret = float(returns.mean())
    std_ret = float(returns.std())
    if std_ret == 0:
        return 0.0
    return float(mean_ret / std_ret * np.sqrt(252))
