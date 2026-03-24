"""
市場環境分類與條件 IC 分析。

根據市場整體走勢將時間區間分為牛市/熊市/盤整，
分析因子在不同環境下的預測力差異。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from src.strategy.research import ICResult, compute_ic


class MarketRegime(Enum):
    """市場環境分類。"""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"


@dataclass
class RegimeDefinition:
    """環境分類參數。"""

    lookback: int = 60  # 回望天數
    bull_threshold: float = 0.10  # 年化報酬閾值 (>10% = 牛市)
    bear_threshold: float = -0.10  # (<-10% = 熊市)


@dataclass
class RegimeICResult:
    """環境條件 IC 分析結果。"""

    factor_name: str
    ic_by_regime: dict[MarketRegime, ICResult] = field(default_factory=dict)
    regime_counts: dict[MarketRegime, int] = field(default_factory=dict)


def classify_regimes(
    market_returns: pd.Series,
    config: RegimeDefinition | None = None,
) -> pd.Series:
    """
    將每個日期分類為市場環境。

    使用 trailing lookback 天的年化報酬判斷：
    - 年化 > bull_threshold → BULL
    - 年化 < bear_threshold → BEAR
    - 其他 → SIDEWAYS

    Args:
        market_returns: 日報酬序列 (index=date)
        config: 分類參數

    Returns:
        Series, index=date, values=MarketRegime
    """
    c = config or RegimeDefinition()

    if len(market_returns) < c.lookback:
        return pd.Series(dtype=object)

    # 滾動年化報酬
    rolling_cum = market_returns.rolling(c.lookback).sum()
    annualized = rolling_cum * (252 / c.lookback)

    regimes: list[MarketRegime] = []
    dates: list[pd.Timestamp] = []

    for dt in annualized.dropna().index:
        ann_ret = float(annualized.loc[dt])
        if ann_ret > c.bull_threshold:
            regimes.append(MarketRegime.BULL)
        elif ann_ret < c.bear_threshold:
            regimes.append(MarketRegime.BEAR)
        else:
            regimes.append(MarketRegime.SIDEWAYS)
        dates.append(dt)

    return pd.Series(regimes, index=dates)


def compute_regime_ic(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    regime_series: pd.Series,
    method: str = "rank",
    factor_name: str = "",
) -> RegimeICResult:
    """
    計算各市場環境下的因子 IC。

    Args:
        factor_values: index=date, columns=symbols
        forward_returns: 同上
        regime_series: index=date, values=MarketRegime
        factor_name: 因子名稱

    Returns:
        RegimeICResult，包含各環境的 ICResult 和樣本數
    """
    result = RegimeICResult(factor_name=factor_name)

    for regime in MarketRegime:
        # 取屬於此環境的日期
        regime_dates = regime_series[regime_series == regime].index
        if len(regime_dates) == 0:
            result.regime_counts[regime] = 0
            continue

        # 過濾因子值和前向報酬
        common_dates = factor_values.index.intersection(regime_dates)
        common_dates = common_dates.intersection(forward_returns.index)

        if len(common_dates) < 5:
            result.regime_counts[regime] = len(common_dates)
            result.ic_by_regime[regime] = ICResult(
                factor_name=factor_name, ic_mean=0.0, ic_std=0.0, icir=0.0
            )
            continue

        fv_filtered = factor_values.loc[common_dates]
        fr_filtered = forward_returns.loc[common_dates]

        ic = compute_ic(fv_filtered, fr_filtered, method=method)
        ic.factor_name = factor_name
        result.ic_by_regime[regime] = ic
        result.regime_counts[regime] = len(common_dates)

    return result
