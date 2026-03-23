"""
多因子策略 — 結合動量、均值回歸、RSI 的複合評分模型。
"""

from __future__ import annotations

import numpy as np

from src.strategy.base import Context, Strategy
from src.strategy.factors import momentum, mean_reversion, rsi
from src.strategy.optimizer import signal_weight, OptConstraints


class MultiFactorStrategy(Strategy):
    """
    多因子策略：
    - momentum_score: 正規化動量（百分位排名）
    - value_score: 負 Z-score（越超賣分數越高）
    - quality_score: 1 - RSI/100（RSI 越低分數越高）
    - composite = 加權平均
    - 只買入複合分數為正的標的
    """

    def __init__(
        self,
        momentum_weight: float = 0.4,
        value_weight: float = 0.3,
        quality_weight: float = 0.3,
    ):
        self.momentum_weight = momentum_weight
        self.value_weight = value_weight
        self.quality_weight = quality_weight

    def name(self) -> str:
        return "multi_factor"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        raw_scores: dict[str, dict[str, float]] = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=300)
            if len(bars) < 252:
                continue

            # 動量因子
            mom = momentum(bars, lookback=252, skip=21)
            if mom.empty:
                continue

            # 均值回歸因子（Z-score，已經取負號：越低估值越高）
            mr = mean_reversion(bars, lookback=20)
            if mr.empty:
                continue

            # RSI 因子
            rsi_factor = rsi(bars, period=14)
            if rsi_factor.empty:
                continue

            raw_scores[symbol] = {
                "momentum": mom["momentum"],
                "z_score": mr["z_score"],  # 已取反：負偏離→正值
                "rsi": rsi_factor["rsi"],
            }

        if not raw_scores:
            return {}

        # 正規化：對每個因子做百分位排名
        symbols = list(raw_scores.keys())
        n = len(symbols)

        if n < 2:
            # 只有一個標的，無法排名，直接使用原始分數
            sym = symbols[0]
            s = raw_scores[sym]
            composite = (
                self.momentum_weight * (1.0 if s["momentum"] > 0 else 0.0)
                + self.value_weight * max(0.0, s["z_score"] / 3.0)
                + self.quality_weight * (1.0 - s["rsi"] / 100.0)
            )
            if composite > 0:
                return signal_weight(
                    {sym: composite},
                    OptConstraints(max_weight=0.08, max_total_weight=0.90),
                )
            return {}

        # 提取各因子的值
        mom_values = [raw_scores[s]["momentum"] for s in symbols]
        z_values = [raw_scores[s]["z_score"] for s in symbols]
        rsi_values = [raw_scores[s]["rsi"] for s in symbols]

        # 排名百分位（0~1）
        def rank_percentile(values: list[float]) -> list[float]:
            arr = np.array(values)
            ranks = np.argsort(np.argsort(arr)).astype(float)
            result: list[float] = (ranks / (len(ranks) - 1)).tolist()
            return result

        mom_ranks = rank_percentile(mom_values)
        z_ranks = rank_percentile(z_values)

        signals: dict[str, float] = {}
        for i, symbol in enumerate(symbols):
            momentum_score = mom_ranks[i]
            value_score = z_ranks[i]
            quality_score = 1.0 - rsi_values[i] / 100.0

            composite = (
                self.momentum_weight * momentum_score
                + self.value_weight * value_score
                + self.quality_weight * quality_score
            )

            if composite > 0:
                signals[symbol] = composite

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.08, max_total_weight=0.90),
        )
