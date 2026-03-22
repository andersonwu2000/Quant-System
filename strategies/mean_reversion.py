"""
均值回歸策略 — 買入偏離均線的股票。
"""

from __future__ import annotations

from src.strategy.base import Context, Strategy
from src.strategy.factors import mean_reversion
from src.strategy.optimizer import signal_weight, OptConstraints


class MeanReversionStrategy(Strategy):
    """
    均值回歸策略：
    - 買入 Z-score 低（價格偏離均線下方）的股票
    - 賣出 Z-score 高的股票（long-only 模式下忽略）
    """

    def __init__(self, lookback: int = 20, z_threshold: float = 1.5):
        self.lookback = lookback
        self.z_threshold = z_threshold

    def name(self) -> str:
        return "mean_reversion"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals: dict[str, float] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=self.lookback + 5)
            if len(bars) < self.lookback:
                continue

            factor = mean_reversion(bars, lookback=self.lookback)
            if not factor.empty and factor["z_score"] > self.z_threshold:
                signals[symbol] = factor["z_score"]

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.08, max_total_weight=0.90),
        )
