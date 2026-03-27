"""多策略組合 — 合併多個子策略降低集中風險。

FinLab 研究：54 策略輪動/組合 > 單策略。
本策略組合低相關子策略，對有持倉的策略等權分配。

預設組合：
- revenue_momentum（營收動能，核心）
- trust_follow（投信跟單，中小型股）
"""

from __future__ import annotations

import logging

import pandas as pd

from src.strategy.base import Context, Strategy

logger = logging.getLogger(__name__)


class MultiStrategyCombo(Strategy):
    """多策略等權組合。

    每個子策略獨立產出目標權重，本策略對有持倉的子策略
    等權分配後合併。

    Parameters
    ----------
    strategies : 子策略列表（預設 revenue_momentum + trust_follow）
    """

    def __init__(
        self,
        strategies: list[Strategy] | None = None,
    ):
        if strategies is None:
            strategies = self._default_strategies()
        self.strategies = strategies
        self._last_month: str = ""
        self._cached_weights: dict[str, float] = {}

    @staticmethod
    def _default_strategies() -> list[Strategy]:
        """載入預設子策略組合。"""
        from strategies.revenue_momentum import RevenueMomentumStrategy
        from strategies.trust_follow import TrustFollowStrategy

        return [
            RevenueMomentumStrategy(
                max_holdings=15,
                min_yoy_growth=15.0,
                weight_method="signal",
                enable_regime_hedge=True,
            ),
            TrustFollowStrategy(
                max_holdings=10,
                trust_threshold=10000,
                min_yoy_growth=15.0,
                enable_regime_hedge=True,
            ),
        ]

    def name(self) -> str:
        return "multi_strategy_combo"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        current_date = ctx.now()
        current_month = pd.Timestamp(current_date).strftime("%Y-%m")
        if current_month == self._last_month:
            return self._cached_weights

        # 1. 各子策略獨立產出權重
        sub_weights_list: list[dict[str, float]] = []
        for strat in self.strategies:
            try:
                w = strat.on_bar(ctx)
                sub_weights_list.append(w)
            except Exception as e:
                logger.debug("Sub-strategy %s failed: %s", strat.name(), e)
                sub_weights_list.append({})

        # 2. 計算子策略分配權重
        strategy_allocs = self._compute_strategy_allocations(sub_weights_list)

        # 3. 合併：strategy_alloc × sub_weights
        merged: dict[str, float] = {}
        for i, (strat, alloc) in enumerate(zip(self.strategies, strategy_allocs)):
            sub_w = sub_weights_list[i]
            for sym, wt in sub_w.items():
                merged[sym] = merged.get(sym, 0.0) + wt * alloc

        # 4. 正規化（總權重不超過 0.95）
        total = sum(merged.values())
        if total > 0.95:
            scale = 0.95 / total
            merged = {k: v * scale for k, v in merged.items()}

        # 過濾極小權重
        merged = {k: v for k, v in merged.items() if v > 0.001}

        self._last_month = current_month
        self._cached_weights = merged
        return merged

    def _compute_strategy_allocations(
        self, sub_weights_list: list[dict[str, float]]
    ) -> list[float]:
        """等權分配給有持倉的子策略。"""
        n = len(self.strategies)
        active = [i for i, w in enumerate(sub_weights_list) if len(w) > 0]
        if not active:
            return [1.0 / n] * n

        allocs = [0.0] * n
        weight_per = 1.0 / len(active)
        for i in active:
            allocs[i] = weight_per
        return allocs
