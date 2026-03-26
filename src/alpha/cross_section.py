"""
橫截面分析 — 分位數組合回測與多空收益歸因。

因子有效性的金標準：按因子值排序分組，驗證各組收益的單調性與多空價差。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class QuantileResult:
    """分位數組合回測結果。"""

    factor_name: str
    n_quantiles: int
    quantile_returns: pd.DataFrame  # index=date, columns=Q1..Qn, values=期報酬
    mean_returns: pd.Series  # 各分位的平均年化報酬
    long_short_return: pd.Series  # Qn - Q1 (多空組合) 時序
    long_short_sharpe: float
    long_short_annual_return: float
    long_short_max_drawdown: float
    monotonicity_score: float  # Spearman(分位序號, 平均報酬)
    turnover_by_quantile: pd.Series  # 各分位平均換手率

    def summary(self) -> str:
        lines = [
            f"═══ Quantile Analysis: {self.factor_name} ({self.n_quantiles} groups) ═══",
            "",
            "Mean Annualized Returns by Quantile:",
        ]
        for q in self.mean_returns.index:
            ret = self.mean_returns[q]
            bar = "█" * max(0, int(ret * 200))
            lines.append(f"  {q}: {ret:+.2%} {bar}")
        lines.extend([
            "",
            f"Long-Short (Q{self.n_quantiles} - Q1):",
            f"  Annual Return: {self.long_short_annual_return:+.2%}",
            f"  Sharpe:        {self.long_short_sharpe:.2f}",
            f"  Max Drawdown:  {self.long_short_max_drawdown:.2%}",
            f"  Monotonicity:  {self.monotonicity_score:.2f}",
        ])
        return "\n".join(lines)


def quantile_backtest(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    n_quantiles: int = 5,
    weight: str = "equal",
    factor_name: str = "",
) -> QuantileResult:
    """
    執行分位數組合回測。

    Args:
        factor_values: 中性化後的因子值 (index=date, columns=symbols)
        forward_returns: 未來 N 天報酬 (同形狀)
        n_quantiles: 分位數 (5=五分位, 10=十分位)
        weight: "equal" (等權) 或 "factor" (因子值加權)
        factor_name: 因子名稱 (用於報告)
    """
    common_dates = factor_values.index.intersection(forward_returns.index)
    common_symbols = factor_values.columns.intersection(forward_returns.columns)

    if len(common_dates) < 2 or len(common_symbols) < n_quantiles:
        return _empty_result(factor_name, n_quantiles)

    q_labels = [f"Q{i + 1}" for i in range(n_quantiles)]
    quantile_returns_rows: list[dict[str, float]] = []
    # 用於計算換手率
    prev_assignments: dict[str, set[str]] = {q: set() for q in q_labels}

    turnover_sums: dict[str, float] = {q: 0.0 for q in q_labels}
    turnover_counts = 0

    used_dates: list = []

    for dt in common_dates:
        fv = factor_values.loc[dt, common_symbols].dropna()
        fr = forward_returns.loc[dt, common_symbols].dropna()
        common = fv.index.intersection(fr.index)
        if len(common) < n_quantiles:
            continue

        fv_sorted = fv[common]
        fr_sorted = fr[common]

        # 分組：按因子值排序，分成 n_quantiles 組
        try:
            quantile_labels = pd.qcut(fv_sorted.rank(method="first"), n_quantiles, labels=q_labels)  # type: ignore[call-overload]
        except ValueError:
            continue

        row: dict[str, float] = {}
        for q in q_labels:
            members = quantile_labels[quantile_labels == q].index.tolist()
            if not members:
                row[q] = 0.0
                continue

            if weight == "factor":
                w = fv_sorted[members].abs()
                total_w = w.sum()
                if total_w > 0:
                    row[q] = float((fr_sorted[members] * w / total_w).sum())
                else:
                    row[q] = float(fr_sorted[members].mean())
            else:
                row[q] = float(fr_sorted[members].mean())

            # 換手率
            current_set = set(members)
            prev_set = prev_assignments[q]
            if prev_set:
                union = current_set | prev_set
                changed = current_set.symmetric_difference(prev_set)
                turnover_sums[q] += len(changed) / max(len(union), 1)
            prev_assignments[q] = current_set

        quantile_returns_rows.append(row)
        used_dates.append(dt)
        turnover_counts += 1

    if not quantile_returns_rows:
        return _empty_result(factor_name, n_quantiles)

    quantile_returns = pd.DataFrame(quantile_returns_rows, index=used_dates)

    # 平均報酬（年化 — 從實際交易日數推算，非硬編碼 252）
    mean_returns = quantile_returns.mean()
    if len(common_dates) >= 2:
        calendar_days = (common_dates[-1] - common_dates[0]).days
        periods_per_year = (
            len(common_dates) / (calendar_days / 365.25)
            if calendar_days > 0
            else 252.0
        )
    else:
        periods_per_year = 252.0
    mean_annual = mean_returns * periods_per_year

    # 多空組合
    long_short = quantile_returns[q_labels[-1]] - quantile_returns[q_labels[0]]
    ls_mean = float(long_short.mean())
    ls_std = float(long_short.std())
    ls_sharpe = (ls_mean / ls_std * np.sqrt(periods_per_year)) if ls_std > 0 else 0.0
    ls_annual = ls_mean * periods_per_year

    # 最大回撤
    ls_cum = (1 + long_short).cumprod()
    ls_peak = ls_cum.cummax()
    ls_dd = (ls_cum - ls_peak) / ls_peak
    ls_max_dd = float(abs(ls_dd.min())) if not ls_dd.empty else 0.0

    # 單調性
    from scipy.stats import spearmanr

    quantile_ranks = list(range(1, n_quantiles + 1))
    mean_rets_list = [float(mean_returns[q]) for q in q_labels]
    if len(quantile_ranks) >= 3:
        mono_corr, _ = spearmanr(quantile_ranks, mean_rets_list)
        monotonicity = float(mono_corr) if not np.isnan(mono_corr) else 0.0
    else:
        monotonicity = 0.0

    # 換手率
    turnover_by_q = pd.Series(
        {q: turnover_sums[q] / max(turnover_counts, 1) for q in q_labels}
    )

    return QuantileResult(
        factor_name=factor_name,
        n_quantiles=n_quantiles,
        quantile_returns=quantile_returns,
        mean_returns=mean_annual,
        long_short_return=long_short,
        long_short_sharpe=ls_sharpe,
        long_short_annual_return=ls_annual,
        long_short_max_drawdown=ls_max_dd,
        monotonicity_score=monotonicity,
        turnover_by_quantile=turnover_by_q,
    )


def long_short_analysis(result: QuantileResult) -> dict[str, float]:
    """多空組合深入分析。"""
    ls = result.long_short_return
    if ls.empty:
        return {"annual_return": 0, "sharpe": 0, "max_drawdown": 0, "win_rate": 0}

    win_rate = float((ls > 0).mean())
    return {
        "annual_return": result.long_short_annual_return,
        "sharpe": result.long_short_sharpe,
        "max_drawdown": result.long_short_max_drawdown,
        "win_rate": win_rate,
        "monotonicity": result.monotonicity_score,
    }


def _empty_result(factor_name: str, n_quantiles: int) -> QuantileResult:
    q_labels = [f"Q{i + 1}" for i in range(n_quantiles)]
    return QuantileResult(
        factor_name=factor_name,
        n_quantiles=n_quantiles,
        quantile_returns=pd.DataFrame(),
        mean_returns=pd.Series(0.0, index=q_labels),
        long_short_return=pd.Series(dtype=float),
        long_short_sharpe=0.0,
        long_short_annual_return=0.0,
        long_short_max_drawdown=0.0,
        monotonicity_score=0.0,
        turnover_by_quantile=pd.Series(0.0, index=q_labels),
    )
