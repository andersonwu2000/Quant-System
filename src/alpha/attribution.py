"""
因子報酬歸因 — 分解組合報酬為各因子的貢獻。

兩種方法：
- weight_based: contribution = weight × factor_return
- regression: OLS 回歸分解
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class AttributionResult:
    """因子歸因結果。"""

    total_return: float  # 年化總報酬
    factor_contributions: dict[str, float] = field(default_factory=dict)  # 各因子貢獻
    residual_return: float = 0.0  # 殘差（無法歸因的部分）
    contribution_series: pd.DataFrame = field(default_factory=pd.DataFrame)  # 逐日貢獻


def attribute_returns(
    composite_returns: pd.Series,
    factor_returns: dict[str, pd.Series],
    composite_weights: dict[str, float],
    method: str = "weight_based",
) -> AttributionResult:
    """
    將組合報酬分解為因子貢獻。

    Args:
        composite_returns: 組合多空報酬時序
        factor_returns: {因子名: 因子多空報酬時序}
        composite_weights: 合成權重 {因子名: 權重}
        method: "weight_based" 或 "regression"

    Returns:
        AttributionResult
    """
    if composite_returns.empty or not factor_returns:
        return AttributionResult(total_return=0.0)

    if method == "regression":
        return _regression_attribution(composite_returns, factor_returns)
    return _weight_based_attribution(composite_returns, factor_returns, composite_weights)


def _weight_based_attribution(
    composite_returns: pd.Series,
    factor_returns: dict[str, pd.Series],
    composite_weights: dict[str, float],
) -> AttributionResult:
    """權重法歸因：contribution_i = weight_i × factor_return_i。"""
    common_dates = composite_returns.index
    for fr in factor_returns.values():
        common_dates = common_dates.intersection(fr.index)

    if len(common_dates) == 0:
        return AttributionResult(total_return=0.0)

    # 逐日貢獻
    contribution_data: dict[str, pd.Series] = {}
    for name, fr in factor_returns.items():
        w = composite_weights.get(name, 0.0)
        contribution_data[name] = fr.loc[common_dates] * w

    contribution_df = pd.DataFrame(contribution_data)

    # 殘差 = 實際報酬 - Σ(因子貢獻)
    total_contribution = contribution_df.sum(axis=1)
    residual_series = composite_returns.loc[common_dates] - total_contribution
    contribution_df["residual"] = residual_series

    # 年化
    ann_factor = 252
    total_return = float(composite_returns.loc[common_dates].mean() * ann_factor)
    factor_contributions = {
        name: float(contribution_data[name].mean() * ann_factor)
        for name in factor_returns
    }
    residual_return = float(residual_series.mean() * ann_factor)

    return AttributionResult(
        total_return=total_return,
        factor_contributions=factor_contributions,
        residual_return=residual_return,
        contribution_series=contribution_df,
    )


def _regression_attribution(
    composite_returns: pd.Series,
    factor_returns: dict[str, pd.Series],
) -> AttributionResult:
    """回歸法歸因：OLS composite ~ factors。"""
    names = list(factor_returns.keys())
    common_dates = composite_returns.index
    for fr in factor_returns.values():
        common_dates = common_dates.intersection(fr.index)

    if len(common_dates) < len(names) + 2:
        return AttributionResult(total_return=0.0)

    y = np.array(composite_returns.loc[common_dates].values, dtype=np.float64)

    # 建構因子報酬矩陣 (加截距)
    x_cols = [
        np.array(factor_returns[name].loc[common_dates].values, dtype=np.float64)
        for name in names
    ]
    x_data = np.column_stack(x_cols)
    x_with_const = np.column_stack([np.ones(len(common_dates)), x_data])

    # OLS
    result = np.linalg.lstsq(x_with_const, y, rcond=None)
    coeffs = result[0]  # [intercept, beta_1, ..., beta_n]
    betas = coeffs[1:]

    # 因子貢獻 = beta_i × mean(factor_return_i)
    ann_factor = 252
    factor_contributions = {}
    contribution_data: dict[str, pd.Series] = {}
    for i, name in enumerate(names):
        fr_aligned = factor_returns[name].loc[common_dates]
        contribution_data[name] = fr_aligned * betas[i]
        factor_contributions[name] = float(fr_aligned.mean() * betas[i] * ann_factor)

    contribution_df = pd.DataFrame(contribution_data)
    total_contribution = contribution_df.sum(axis=1)
    residual_series = composite_returns.loc[common_dates] - total_contribution
    contribution_df["residual"] = residual_series

    total_return = float(composite_returns.loc[common_dates].mean() * ann_factor)
    residual_return = total_return - sum(factor_contributions.values())

    return AttributionResult(
        total_return=total_return,
        factor_contributions=factor_contributions,
        residual_return=residual_return,
        contribution_series=contribution_df,
    )
