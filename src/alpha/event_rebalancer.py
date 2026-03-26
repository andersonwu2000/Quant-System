"""事件驅動再平衡 — 取代固定月度再平衡。

觸發條件（OR 邏輯，任一成立即觸發）：
1. 月營收公布日（每月 10 日前後）T+1
2. 法人異常買超（投信 10 日累計 > 歷史 3σ）

FinLab 研究發現：
- 營收公布後 T+1 進場比月底固定再平衡 Sharpe 高 ~30%
- 跳過事件後前 3 天，第 4-7 天進場績效最好（過度反應修正）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class RebalanceSignal:
    """再平衡觸發信號。"""
    should_rebalance: bool
    trigger: str = ""  # "revenue_announcement" | "institutional_surge" | "monthly" | ""
    skip_days: int = 0  # 跳過前 N 天（過度反應修正）


class EventDrivenRebalancer:
    """事件驅動再平衡器。

    Parameters
    ----------
    revenue_trigger_day_range : tuple[int, int]
        月營收公布日範圍（預設 10~13 日，即公布後 T+1~T+3）。
    institutional_sigma : float
        法人異常買超的 σ 閾值（預設 3.0）。
    skip_overreaction_days : int
        事件後跳過的天數（FinLab 研究：跳過前 3 天）。
    fallback_monthly : bool
        若事件未觸發，是否 fallback 到月底再平衡。
    """

    def __init__(
        self,
        revenue_trigger_day_range: tuple[int, int] = (11, 13),
        institutional_sigma: float = 3.0,
        skip_overreaction_days: int = 0,
        fallback_monthly: bool = True,
    ):
        self.revenue_day_lo = revenue_trigger_day_range[0]
        self.revenue_day_hi = revenue_trigger_day_range[1]
        self.institutional_sigma = institutional_sigma
        self.skip_days = skip_overreaction_days
        self.fallback_monthly = fallback_monthly
        self._last_trigger_month: str = ""

    def check(self, current_date: pd.Timestamp | str) -> RebalanceSignal:
        """檢查是否應該觸發再平衡。

        Parameters
        ----------
        current_date : 當前日期

        Returns
        -------
        RebalanceSignal
        """
        dt = pd.Timestamp(current_date)
        current_month = dt.strftime("%Y-%m")

        # 避免同月重複觸發
        if current_month == self._last_trigger_month:
            return RebalanceSignal(should_rebalance=False)

        # 條件 1: 月營收公布日 T+1~T+3（每月 10-13 日）
        if self.revenue_day_lo <= dt.day <= self.revenue_day_hi:
            self._last_trigger_month = current_month
            return RebalanceSignal(
                should_rebalance=True,
                trigger="revenue_announcement",
                skip_days=self.skip_days,
            )

        # 條件 2: 月底 fallback（每月最後 3 個交易日）
        if self.fallback_monthly and dt.day >= 25:
            # 只在該月首次到達 25 日後觸發
            self._last_trigger_month = current_month
            return RebalanceSignal(
                should_rebalance=True,
                trigger="monthly_fallback",
            )

        return RebalanceSignal(should_rebalance=False)

    # TODO: 整合到 check() 中，需要 trust_net_series 從 ctx 取得
    def check_institutional_surge(
        self,
        trust_net_series: pd.Series,
        lookback: int = 60,
    ) -> bool:
        """檢查投信是否異常買超（> historical 3σ）。

        Parameters
        ----------
        trust_net_series : 投信每日淨買超序列
        lookback : 歷史回望天數

        Returns
        -------
        True if 近 10 日累計 > lookback 期間的 mean + sigma × std
        """
        if len(trust_net_series) < lookback:
            return False

        recent_10d = trust_net_series.iloc[-10:].sum()
        # guard: need at least 20 historical points
        hist = trust_net_series.iloc[-lookback:-10]
        if len(hist) < 20:
            return False

        # 計算 10 日 rolling sum 的歷史分佈
        rolling_10d = trust_net_series.iloc[-lookback:].rolling(10).sum().dropna()
        if len(rolling_10d) < 10:
            return False

        mean = rolling_10d.mean()
        std = rolling_10d.std()
        if std <= 0:
            return False

        return bool(recent_10d > mean + self.institutional_sigma * std)
