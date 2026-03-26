"""
投信跟單策略 — 基於 FinLab 研究的法人跟單術。

FinLab 對標：法人跟單策略（CAGR 31.7%）
核心邏輯：投信 10 日累計買超 + 營收 3M avg 創 12M 新高 + 營收 YoY > 20%
關鍵發現：投信 > 外資（投信專注台股中小型，外資逆向策略 CAGR -11.2%）
"""

from __future__ import annotations

import logging

import pandas as pd

from src.strategy.base import Context, Strategy
from src.strategy.optimizer import equal_weight, OptConstraints

logger = logging.getLogger(__name__)


class TrustFollowStrategy(Strategy):
    """
    投信跟單 + 營收成長策略。

    篩選條件：
    1. 投信 10 日累計買超 > trust_threshold 股
    2. 營收 3M avg 創 12M 新高
    3. 營收 YoY > min_yoy_growth%
    4. 20 日均量 > min_volume_lots 張

    排序：投信買超金額取前 max_holdings 檔。
    單一持股上限 position_limit。
    """

    def __init__(
        self,
        max_holdings: int = 10,
        trust_threshold: float = 15000,
        min_yoy_growth: float = 20.0,
        trust_days: int = 10,
        min_volume_lots: int = 300,
        position_limit: float = 0.15,
    ):
        self.max_holdings = max_holdings
        self.trust_threshold = trust_threshold
        self.min_yoy_growth = min_yoy_growth
        self.trust_days = trust_days
        self.min_volume_lots = min_volume_lots
        self.position_limit = position_limit

    def name(self) -> str:
        return "trust_follow"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        candidates: list[tuple[str, float]] = []  # (symbol, trust_cumulative)

        current_date = ctx.now()
        # Need institutional data for the past trust_days + buffer
        inst_start = (
            pd.Timestamp(current_date) - pd.DateOffset(days=self.trust_days + 30)
        ).strftime("%Y-%m-%d")
        end_str = pd.Timestamp(current_date).strftime("%Y-%m-%d")

        # Revenue data needs longer history for 12M comparison
        rev_start = (
            pd.Timestamp(current_date) - pd.DateOffset(years=2)
        ).strftime("%Y-%m-%d")

        for symbol in ctx.universe():
            try:
                bars = ctx.bars(symbol, lookback=60)
                if len(bars) < 20:
                    continue

                volume = bars["volume"]

                # 條件 4: 流動性
                avg_vol_20 = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else 0
                if avg_vol_20 < self.min_volume_lots * 1000:
                    continue

                if ctx._fundamentals is None:
                    continue

                # 條件 1: 投信 N 日累計買超
                inst_df = ctx._fundamentals.get_institutional(
                    symbol, inst_start, end_str
                )
                if inst_df.empty:
                    continue

                # Take last trust_days rows
                recent_inst = inst_df.tail(self.trust_days)
                trust_cumulative = float(recent_inst["trust_net"].sum())
                if trust_cumulative < self.trust_threshold:
                    continue

                # 條件 2 & 3: 營收數據
                rev_df = ctx._fundamentals.get_revenue(symbol, rev_start, end_str)
                if rev_df.empty or len(rev_df) < 12:
                    continue

                revenues = rev_df["revenue"].values

                # 3M avg hits 12M high
                rev_3m_avg = float(revenues[-3:].mean()) if len(revenues) >= 3 else 0
                rev_12m_max = float(
                    pd.Series(revenues[-12:]).rolling(3).mean().max()
                ) if len(revenues) >= 12 else 0

                if rev_12m_max <= 0 or rev_3m_avg < rev_12m_max * 0.99:
                    continue

                # 營收 YoY
                yoy_values = rev_df["yoy_growth"].values
                latest_yoy = float(yoy_values[-1]) if len(yoy_values) > 0 else 0

                if latest_yoy < self.min_yoy_growth:
                    continue

                candidates.append((symbol, trust_cumulative))

            except Exception as e:
                logger.debug("Skip %s: %s", symbol, e)
                continue

        if not candidates:
            return {}

        # 按投信買超排序取前 N
        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = candidates[: self.max_holdings]

        signals = {sym: tc for sym, tc in selected}

        return equal_weight(
            signals,
            OptConstraints(
                max_weight=self.position_limit,
                max_total_weight=0.95,
            ),
        )
