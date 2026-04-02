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


@dataclass
class DSRResult:
    """Deflated Sharpe Ratio result."""

    observed_sharpe: float
    deflated_sharpe: float
    haircut_pct: float  # (1 - deflated/observed) * 100
    n_trials: int
    p_value: float  # P(observed SR is due to luck given N trials)
    is_significant: bool  # p_value < 0.05

    def summary(self) -> str:
        status = "SIGNIFICANT" if self.is_significant else "LIKELY OVERFIT"
        lines = [
            "═══ Deflated Sharpe Ratio (Harvey et al. 2016) ═══",
            "",
            f"Observed SR:      {self.observed_sharpe:.3f}",
            f"Deflated SR:      {self.deflated_sharpe:.3f}",
            f"Haircut:          {self.haircut_pct:.1f}%",
            f"Trials (N):       {self.n_trials}",
            f"p-value:          {self.p_value:.4f}  ({status})",
            "",
            "DSR adjusts for multiple testing: higher N → higher bar.",
        ]
        return "\n".join(lines)


def compute_deflated_sharpe(
    returns: pd.Series,
    n_trials: int,
    annualize: bool = True,
) -> DSRResult:
    """Deflated Sharpe Ratio — Harvey, Liu & Zhu (2016).

    Adjusts the observed Sharpe ratio for the number of trials (N) conducted,
    accounting for non-normality (skewness, kurtosis) of returns.

    The key insight: if you test N strategies and pick the best, the expected
    maximum Sharpe under the null (all strategies have SR=0) grows as
    E[max(SR)] ≈ sqrt(2 * ln(N)) * (1 - γ/ln(N) + γ/(2*ln(N)²))
    where γ ≈ 0.5772 (Euler-Mascheroni constant).

    DSR = (SR_observed - SR_expected_max) / SE(SR)

    Args:
        returns: Daily return series of the selected strategy.
        n_trials: Total number of strategies/factors tested (including rejected).
        annualize: If True, annualize the Sharpe ratio.

    Returns:
        DSRResult with deflated Sharpe, haircut, and p-value.
    """
    from scipy import stats as sp_stats

    T = len(returns)
    if T < 10 or n_trials < 1:
        return DSRResult(
            observed_sharpe=0.0, deflated_sharpe=0.0,
            haircut_pct=100.0, n_trials=n_trials,
            p_value=1.0, is_significant=False,
        )

    # Observed Sharpe (daily)
    mu = float(returns.mean())
    sigma = float(returns.std(ddof=1))
    if sigma == 0:
        return DSRResult(
            observed_sharpe=0.0, deflated_sharpe=0.0,
            haircut_pct=100.0, n_trials=n_trials,
            p_value=1.0, is_significant=False,
        )

    sr_daily = mu / sigma
    sr = sr_daily * np.sqrt(252) if annualize else sr_daily

    # Non-normality adjustment (Bailey & López de Prado 2014, Eq. 4)
    skew = float(sp_stats.skew(returns, bias=False))
    kurt = float(sp_stats.kurtosis(returns, bias=False))  # excess kurtosis

    # Standard error of Sharpe ratio (Lo 2002, with non-normality correction)
    se_sr = np.sqrt(
        (1 - skew * sr_daily + (kurt - 1) / 4 * sr_daily ** 2) / T
    )
    if annualize:
        se_sr *= np.sqrt(252)

    # Expected maximum Sharpe under the null, given N independent trials
    # E[max] ≈ (1 - γ/ln(N)) * sqrt(2 * ln(N))  (Bailey & López de Prado 2014)
    if n_trials <= 1:
        sr_expected_max = 0.0
    else:
        euler_gamma = 0.5772156649
        ln_n = np.log(n_trials)
        sr_expected_max = float(
            np.sqrt(2 * ln_n) * (1 - euler_gamma / ln_n + euler_gamma / (2 * ln_n ** 2))
        )
        if annualize:
            # sr_expected_max is in daily units, annualize
            sr_expected_max *= np.sqrt(252) / np.sqrt(T)
            # More precise: E[max] for annualized = sqrt(V(SR)) * E[max(Z)]
            sr_expected_max = se_sr * np.sqrt(2 * ln_n) * (
                1 - euler_gamma / ln_n + euler_gamma / (2 * ln_n ** 2)
            )

    # Deflated Sharpe = observed minus expected max, in SE units
    dsr_stat = (sr - sr_expected_max) / se_sr if se_sr > 0 else 0.0

    # p-value: P(SR >= observed | null = max of N zero-SR strategies)
    p_value = float(1 - sp_stats.norm.cdf(dsr_stat))

    # Deflated Sharpe (intuitive form): how much SR survives after multiple testing
    deflated = max(0.0, sr - sr_expected_max)

    haircut = (1 - deflated / sr) * 100 if sr > 0 else 100.0

    return DSRResult(
        observed_sharpe=float(sr),
        deflated_sharpe=float(deflated),
        haircut_pct=float(haircut),
        n_trials=n_trials,
        p_value=float(p_value),
        is_significant=p_value < 0.05,
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
