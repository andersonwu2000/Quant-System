"""
配對交易策略 — 利用價格比率的均值回歸特性。
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import numpy.typing as npt

from src.strategy.base import Context, Strategy
from src.strategy.optimizer import equal_weight, OptConstraints


class PairsTradingStrategy(Strategy):
    """
    配對交易策略：
    - 對每一對股票，計算價格比率的 Z-score
    - 當 Z-score > 閾值時，買入相對弱勢的那一方
    - 因為 long_only 限制，只做買入被低估的標的
    - 使用等權重配置
    """

    def __init__(self, lookback: int = 60, z_threshold: float = 1.5):
        self.lookback = lookback
        self.z_threshold = z_threshold

    def name(self) -> str:
        return "pairs_trading"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        universe = ctx.universe()
        if len(universe) < 2:
            return {}

        # 收集所有標的的收盤價序列
        price_data: dict[str, npt.NDArray[np.float64]] = {}
        for symbol in universe:
            bars = ctx.bars(symbol, lookback=self.lookback + 10)
            if len(bars) < self.lookback:
                continue
            price_data[symbol] = np.asarray(bars["close"].values[-self.lookback:], dtype=np.float64)

        if len(price_data) < 2:
            return {}

        # 對每一對股票計算價格比率的 Z-score
        signals: dict[str, float] = {}
        symbols = list(price_data.keys())

        for sym_a, sym_b in combinations(symbols, 2):
            prices_a = price_data[sym_a]
            prices_b = price_data[sym_b]

            # 避免除以零
            if np.any(prices_b == 0):
                continue

            ratio = prices_a / prices_b
            ratio_mean = np.mean(ratio)
            ratio_std = np.std(ratio)

            if ratio_std == 0:
                continue

            z = (ratio[-1] - ratio_mean) / ratio_std

            # Z > threshold: A 相對 B 偏高，買入 B（被低估方）
            if z > self.z_threshold:
                signals[sym_b] = signals.get(sym_b, 0.0) + abs(z)
            # Z < -threshold: B 相對 A 偏高，買入 A（被低估方）
            elif z < -self.z_threshold:
                signals[sym_a] = signals.get(sym_a, 0.0) + abs(z)

        return equal_weight(
            signals,
            OptConstraints(max_weight=0.15, max_total_weight=0.90),
        )
