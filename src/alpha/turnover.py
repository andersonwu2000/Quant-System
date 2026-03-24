"""
換手率分析 — 量化因子信號的穩定性與交易成本侵蝕。

一個因子即使 IC 很高，如果換手率太高，交易成本會吃掉大部分 Alpha。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class TurnoverResult:
    """因子換手率分析結果。"""

    factor_name: str
    avg_turnover: float  # 平均單邊換手率 (0~1)
    turnover_series: pd.Series  # 每期換手率時序
    cost_drag_annual_bps: float  # 年化成本侵蝕 (bps)
    net_ic: float  # 成本調整後的 IC
    breakeven_cost_bps: float  # 盈虧平衡交易成本 (bps)

    def summary(self) -> str:
        return (
            f"═══ Turnover Analysis: {self.factor_name} ═══\n"
            f"  Avg Turnover:     {self.avg_turnover:.1%} per period\n"
            f"  Cost Drag:        {self.cost_drag_annual_bps:.1f} bps/year\n"
            f"  Net IC:           {self.net_ic:+.4f}\n"
            f"  Breakeven Cost:   {self.breakeven_cost_bps:.1f} bps\n"
            f"  Periods:          {len(self.turnover_series)}"
        )


def compute_turnover(
    weights_old: pd.Series,
    weights_new: pd.Series,
) -> float:
    """
    計算單邊換手率 = sum(|w_new - w_old|) / 2。

    Args:
        weights_old: 前一期權重 (symbol → weight)
        weights_new: 當期權重 (symbol → weight)

    Returns:
        單邊換手率 (0~1)
    """
    all_symbols = set(weights_old.index) | set(weights_new.index)
    if not all_symbols:
        return 0.0

    old = weights_old.reindex(list(all_symbols), fill_value=0.0)
    new = weights_new.reindex(list(all_symbols), fill_value=0.0)
    return float(np.abs(new - old).sum()) / 2


def compute_turnover_series(
    weight_timeseries: pd.DataFrame,
) -> pd.Series:
    """
    從權重時序計算逐期換手率。

    Args:
        weight_timeseries: index=date, columns=symbols, values=weights
    """
    dates = weight_timeseries.index
    turnover_values: list[float] = []
    turnover_dates: list[object] = []

    for i in range(1, len(dates)):
        old_w = weight_timeseries.iloc[i - 1].dropna()
        new_w = weight_timeseries.iloc[i].dropna()
        t = compute_turnover(old_w, new_w)
        turnover_values.append(t)
        turnover_dates.append(dates[i])

    return pd.Series(turnover_values, index=turnover_dates, dtype=float)


def analyze_factor_turnover(
    factor_values: pd.DataFrame,
    n_quantiles: int = 5,
    holding_period: int = 5,
    cost_bps: float = 30.0,
    gross_ic: float = 0.0,
    factor_name: str = "",
) -> TurnoverResult:
    """
    完整的因子換手率分析。

    模擬等權重的分位數組合，計算最高分位（做多組）的換手率。

    Args:
        factor_values: 中性化後因子值 (index=date, columns=symbols)
        n_quantiles: 分位數
        holding_period: 持倉週期天數（用於年化）
        cost_bps: 單邊交易成本 (bps)
        gross_ic: 毛 IC (用於計算淨 IC)
        factor_name: 因子名稱
    """
    dates = factor_values.index
    q_label = f"Q{n_quantiles}"

    # 模擬最高分位的等權組合
    weight_rows: list[dict[str, float]] = []
    weight_dates: list[object] = []

    for dt in dates:
        fv = factor_values.loc[dt].dropna()
        if len(fv) < n_quantiles:
            continue

        try:
            q_labels = pd.qcut(fv.rank(method="first"), n_quantiles, labels=False)
        except ValueError:
            continue

        top_quantile = fv.index[q_labels == n_quantiles - 1].tolist()
        if not top_quantile:
            continue

        w = 1.0 / len(top_quantile)
        row = {sym: w for sym in top_quantile}
        weight_rows.append(row)
        weight_dates.append(dt)

    if len(weight_rows) < 2:
        return TurnoverResult(
            factor_name=factor_name,
            avg_turnover=0.0,
            turnover_series=pd.Series(dtype=float),
            cost_drag_annual_bps=0.0,
            net_ic=gross_ic,
            breakeven_cost_bps=0.0,
        )

    weights_df = pd.DataFrame(weight_rows, index=weight_dates).fillna(0.0)
    turnover_series = compute_turnover_series(weights_df)

    avg_turnover = float(turnover_series.mean()) if not turnover_series.empty else 0.0

    # 年化成本侵蝕：每期換手率 × 雙邊成本 × 每年期數
    rebalances_per_year = 252 / max(holding_period, 1)
    cost_drag = avg_turnover * 2 * cost_bps * rebalances_per_year  # bps/year

    # 淨 IC：粗略估算 — IC 減去成本侵蝕對 IC 的等效影響
    # 簡化：net_ic ≈ gross_ic - cost_drag / 10000 (成本轉為比例)
    net_ic = gross_ic - cost_drag / 10000

    # 盈虧平衡成本：使 net alpha = 0 的單邊成本
    if avg_turnover > 0 and rebalances_per_year > 0:
        breakeven = (gross_ic * 10000) / (avg_turnover * 2 * rebalances_per_year)
    else:
        breakeven = float("inf") if gross_ic > 0 else 0.0

    return TurnoverResult(
        factor_name=factor_name,
        avg_turnover=avg_turnover,
        turnover_series=turnover_series,
        cost_drag_annual_bps=cost_drag,
        net_ic=net_ic,
        breakeven_cost_bps=breakeven if not np.isinf(breakeven) else 9999.0,
    )


def cost_adjusted_returns(
    gross_returns: pd.Series,
    turnover: pd.Series,
    cost_bps: float = 30.0,
) -> pd.Series:
    """
    從毛報酬扣除交易成本，得到淨報酬。

    Args:
        gross_returns: 每期毛報酬
        turnover: 每期換手率
        cost_bps: 單邊成本 (bps)
    """
    common = gross_returns.index.intersection(turnover.index)
    if common.empty:
        return gross_returns

    cost_per_period = turnover[common] * 2 * cost_bps / 10000
    net = gross_returns.copy()
    net[common] = gross_returns[common] - cost_per_period
    return net
