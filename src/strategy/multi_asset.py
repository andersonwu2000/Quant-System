"""
MultiAssetStrategy — 兩層配置策略。

流程：
1. 戰術配置 → dict[AssetClass, float]（宏觀+跨資產+regime）
2. 各資產類別內選標的（Alpha Pipeline 或等權）
3. 組合最佳化（Risk Parity / BL / HRP）
4. 輸出最終 symbol-level 權重
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.allocation.cross_asset import CrossAssetSignals
from src.allocation.tactical import StrategicAllocation, TacticalEngine
from src.alpha.regime import MarketRegime, classify_regimes
from src.core.models import AssetClass
from src.portfolio.optimizer import (
    OptimizationMethod,
    OptimizerConfig,
    PortfolioOptimizer,
)
from src.strategy.base import Context, Strategy

logger = logging.getLogger(__name__)


@dataclass
class MultiAssetConfig:
    """多資產策略配置。"""

    strategic_weights: dict[AssetClass, float] = field(default_factory=lambda: {
        AssetClass.EQUITY: 0.55,
        AssetClass.ETF: 0.35,
        AssetClass.FUTURE: 0.10,
    })
    optimization_method: OptimizationMethod = OptimizationMethod.RISK_PARITY
    max_single_weight: float = 0.15     # 單一標的上限
    lookback_bars: int = 300            # 資料回望期
    rebalance_freq: str = "monthly"     # 宏觀配置再平衡頻率


class MultiAssetStrategy(Strategy):
    """兩層配置策略：資產類別 → 標的選擇 → 組合最佳化。"""

    def __init__(self, config: MultiAssetConfig | None = None):
        self._config = config or MultiAssetConfig()
        self._tactical = TacticalEngine(
            strategic=StrategicAllocation(weights=self._config.strategic_weights),
        )
        self._cross_asset = CrossAssetSignals()
        self._optimizer = PortfolioOptimizer(OptimizerConfig(
            method=self._config.optimization_method,
            max_weight=self._config.max_single_weight,
        ))
        self._prev_weights: dict[str, float] | None = None

    def name(self) -> str:
        return "multi_asset"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        """兩層配置 + 組合最佳化 → 最終權重。"""
        universe = ctx.universe()
        if not universe:
            return self._prev_weights or {}

        # 收集資料
        data: dict[str, pd.DataFrame] = {}
        for sym in universe:
            bars = ctx.bars(sym, lookback=self._config.lookback_bars)
            if not bars.empty and len(bars) >= 60:
                data[sym] = bars

        if len(data) < 2:
            return self._prev_weights or {}

        # Step 1: 分類 universe
        from src.instrument.registry import InstrumentRegistry
        registry = InstrumentRegistry()
        class_groups: dict[AssetClass, list[str]] = {}
        for sym in data:
            inst = registry.get_or_create(sym)
            ac = inst.asset_class
            if ac not in class_groups:
                class_groups[ac] = []
            class_groups[ac].append(sym)

        # Step 2: 跨資產信號（各類別的代表性價格）
        price_by_class: dict[AssetClass, pd.Series] = {}
        for ac, syms in class_groups.items():
            # 用第一個標的的 close 作為代表
            rep = syms[0]
            price_by_class[ac] = data[rep]["close"]

        cross_asset_signals = self._cross_asset.compute(price_by_class)

        # Step 3: 市場狀態
        all_returns = pd.concat(
            [df["close"].pct_change() for df in data.values()], axis=1,
        ).mean(axis=1).dropna()
        regime = MarketRegime.SIDEWAYS
        if len(all_returns) > 60:
            regime_series = classify_regimes(all_returns)
            if not regime_series.empty:
                regime = regime_series.iloc[-1]

        # Step 4: 戰術配置
        tactical_weights = self._tactical.compute(
            cross_asset_signals=cross_asset_signals,
            regime=regime,
        )

        # Step 5: 各類別內等權（或信號加權）→ symbol weights
        raw_weights: dict[str, float] = {}
        for ac, class_weight in tactical_weights.items():
            syms = class_groups.get(ac, [])
            if not syms:
                continue
            per_sym = class_weight / len(syms)
            for sym in syms:
                raw_weights[sym] = per_sym

        if not raw_weights:
            return self._prev_weights or {}

        # Step 6: 組合最佳化
        common_syms = [s for s in raw_weights if s in data]
        if len(common_syms) >= 2:
            returns_df = pd.DataFrame({
                s: data[s]["close"].pct_change() for s in common_syms
            }).dropna()

            if len(returns_df) >= 60:
                result = self._optimizer.optimize(returns_df)
                if result.weights:
                    raw_weights = result.weights

        # 過濾極小權重
        final = {s: w for s, w in raw_weights.items() if w >= 0.005}
        self._prev_weights = final
        return final
