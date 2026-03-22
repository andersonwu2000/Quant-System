"""
動量策略 — 12-1 個月動量，信號加權配置。
"""

from __future__ import annotations

from src.strategy.base import Context, Strategy
from src.strategy.factors import momentum
from src.strategy.optimizer import signal_weight, OptConstraints


class MomentumStrategy(Strategy):
    """
    經典 12-1 動量策略：
    - 買入過去 12 個月漲幅最大的股票（跳過最近 1 個月）
    - 信號加權分配權重
    - 每週/每月再平衡
    """

    def __init__(self, lookback: int = 252, skip: int = 21, max_holdings: int = 10):
        self.lookback = lookback
        self.skip = skip
        self.max_holdings = max_holdings

    def name(self) -> str:
        return "momentum_12_1"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals: dict[str, float] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=self.lookback + self.skip)
            if len(bars) < self.lookback:
                continue

            factor = momentum(bars, lookback=self.lookback, skip=self.skip)
            if not factor.empty:
                signals[symbol] = factor["momentum"]

        # 只取前 N 強
        if len(signals) > self.max_holdings:
            sorted_signals = sorted(signals.items(), key=lambda x: x[1], reverse=True)
            signals = dict(sorted_signals[: self.max_holdings])

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.10, max_total_weight=0.95),
        )
