"""
營收動能策略 — 基於 FinLab 研究的台股最強公開因子。

FinLab 對標：月營收動能策略（CAGR 33.5%）+ AI 因子挖掘最佳迭代（CAGR 18.6%）
核心邏輯：營收 3M avg > 12M avg + 營收 YoY > 15% + 股價趨勢確認 + 流動性篩選
"""

from __future__ import annotations

import logging

import pandas as pd

from src.strategy.base import Context, Strategy
from src.strategy.optimizer import equal_weight, OptConstraints

logger = logging.getLogger(__name__)


class RevenueMomentumStrategy(Strategy):
    """
    營收動能 + 價格確認策略。

    篩選條件：
    1. 營收 3M avg > 12M avg（營收動能）
    2. 營收 YoY > threshold（成長確認）
    3. 股價 > 60 日均線（趨勢確認）
    4. 近 60 日漲幅 > 0（動能確認）
    5. 20 日均量 > min_volume 張（流動性）

    排序：營收 YoY 取前 max_holdings 檔，等權配置。
    """

    def __init__(
        self,
        max_holdings: int = 15,
        min_yoy_growth: float = 15.0,
        min_volume_lots: int = 300,
        max_weight: float = 0.10,
    ):
        self.max_holdings = max_holdings
        self.min_yoy_growth = min_yoy_growth
        self.min_volume_lots = min_volume_lots
        self.max_weight = max_weight

    def name(self) -> str:
        return "revenue_momentum"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        candidates: list[tuple[str, float]] = []  # (symbol, yoy_growth)

        current_date = ctx.now()
        start_str = (
            pd.Timestamp(current_date) - pd.DateOffset(years=2)
        ).strftime("%Y-%m-%d")
        end_str = pd.Timestamp(current_date).strftime("%Y-%m-%d")

        for symbol in ctx.universe():
            try:
                bars = ctx.bars(symbol, lookback=252)
                if len(bars) < 120:
                    continue

                close = bars["close"]
                volume = bars["volume"]

                # 條件 5: 流動性 — 20 日均量 > min_volume_lots 張
                avg_vol_20 = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else 0
                if avg_vol_20 < self.min_volume_lots * 1000:
                    continue

                # 條件 3: 股價 > 60 日均線
                if len(close) >= 60:
                    ma60 = float(close.iloc[-60:].mean())
                    if float(close.iloc[-1]) <= ma60:
                        continue
                else:
                    continue

                # 條件 4: 近 60 日漲幅 > 0
                ret_60d = float(close.iloc[-1]) / float(close.iloc[-60]) - 1
                if ret_60d <= 0:
                    continue

                # 條件 1 & 2: 營收數據
                if ctx._fundamentals is None:
                    continue

                rev_df = ctx._fundamentals.get_revenue(symbol, start_str, end_str)
                if rev_df.empty or len(rev_df) < 12:
                    continue

                revenues = rev_df["revenue"].values
                # 3M avg vs 12M avg
                rev_3m_avg = float(revenues[-3:].mean()) if len(revenues) >= 3 else 0
                rev_12m_avg = float(revenues[-12:].mean()) if len(revenues) >= 12 else 0

                if rev_12m_avg <= 0 or rev_3m_avg <= rev_12m_avg:
                    continue

                # 營收 YoY
                yoy_values = rev_df["yoy_growth"].values
                latest_yoy = float(yoy_values[-1]) if len(yoy_values) > 0 else 0

                if latest_yoy < self.min_yoy_growth:
                    continue

                candidates.append((symbol, latest_yoy))

            except Exception as e:
                logger.debug("Skip %s: %s", symbol, e)
                continue

        if not candidates:
            return {}

        # 按 YoY 排序取前 N
        candidates.sort(key=lambda x: x[1], reverse=True)
        selected = candidates[: self.max_holdings]

        signals = {sym: yoy for sym, yoy in selected}

        return equal_weight(
            signals,
            OptConstraints(
                max_weight=self.max_weight,
                max_total_weight=0.95,
            ),
        )
