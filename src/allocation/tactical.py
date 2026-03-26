"""
戰術配置引擎 — 結合戰略配置 + 宏觀信號 + 跨資產信號 → 資產類別權重。

輸出：dict[AssetClass, float]（各資產類別的目標比例，sum ≈ 1.0）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from src.alpha.regime import MarketRegime
from src.core.models import AssetClass

logger = logging.getLogger(__name__)


@dataclass
class StrategicAllocation:
    """戰略配置 — 長期目標比例（靜態設定值）。"""

    weights: dict[AssetClass, float] = field(default_factory=lambda: {
        AssetClass.EQUITY: 0.55,
        AssetClass.ETF: 0.35,
        AssetClass.FUTURE: 0.10,
    })

    def __post_init__(self) -> None:
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "Strategic weights sum to %.3f, normalizing to 1.0", total,
            )
            if total > 0:
                self.weights = {k: v / total for k, v in self.weights.items()}


@dataclass
class TacticalConfig:
    """戰術配置參數。"""

    # 各資產類別最大偏離度（相對於戰略配置 ±）
    max_deviation: float = 0.15

    # 信號強度縮放
    macro_weight: float = 0.5      # 宏觀信號權重
    cross_asset_weight: float = 0.3  # 跨資產信號權重
    regime_weight: float = 0.2     # 市場狀態權重

    # 宏觀因子對各資產類別的敏感度矩陣
    # factor → {asset_class → sensitivity}
    # 正值 = 該因子正向時超配該資產
    macro_sensitivity: dict[str, dict[AssetClass, float]] = field(
        default_factory=lambda: {
            "growth": {
                AssetClass.EQUITY: 0.5,
                AssetClass.ETF: -0.3,
                AssetClass.FUTURE: 0.1,
            },
            "inflation": {
                AssetClass.EQUITY: -0.2,
                AssetClass.ETF: -0.3,
                AssetClass.FUTURE: 0.5,
            },
            "rates": {
                AssetClass.EQUITY: 0.3,
                AssetClass.ETF: 0.4,
                AssetClass.FUTURE: -0.1,
            },
            "credit": {
                AssetClass.EQUITY: 0.4,
                AssetClass.ETF: 0.2,
                AssetClass.FUTURE: -0.1,
            },
        }
    )

    # 市場狀態對各資產的調整
    regime_adjustment: dict[MarketRegime, dict[AssetClass, float]] = field(
        default_factory=lambda: {
            MarketRegime.BULL: {
                AssetClass.EQUITY: 0.05,
                AssetClass.ETF: -0.03,
                AssetClass.FUTURE: -0.02,
            },
            MarketRegime.BEAR: {
                AssetClass.EQUITY: -0.10,
                AssetClass.ETF: 0.08,
                AssetClass.FUTURE: 0.02,
            },
            MarketRegime.SIDEWAYS: {
                AssetClass.EQUITY: 0.0,
                AssetClass.ETF: 0.0,
                AssetClass.FUTURE: 0.0,
            },
        }
    )

    # 最小配置比例（避免某類資產被完全排除）
    min_weight: float = 0.02


class TacticalEngine:
    """戰術配置引擎。

    將三類信號（宏觀、跨資產、市場狀態）合成為資產類別的戰術權重。
    """

    def __init__(
        self,
        strategic: StrategicAllocation | None = None,
        config: TacticalConfig | None = None,
    ):
        self.strategic = strategic or StrategicAllocation()
        self.config = config or TacticalConfig()

    def compute(
        self,
        macro_signals: dict[str, float] | None = None,
        cross_asset_signals: dict[AssetClass, float] | None = None,
        regime: MarketRegime | None = None,
    ) -> dict[AssetClass, float]:
        """計算戰術權重。

        Args:
            macro_signals: 宏觀因子 z-scores {"growth": 0.5, "inflation": -0.3, ...}
            cross_asset_signals: 跨資產信號 {AssetClass.EQUITY: 0.2, ...}
            regime: 當前市場狀態

        Returns:
            dict[AssetClass, float] — 戰術權重，sum ≈ 1.0
        """
        cfg = self.config
        asset_classes = list(self.strategic.weights.keys())

        # 1. 起點：戰略配置
        weights = dict(self.strategic.weights)

        # 2. 宏觀信號調整
        if macro_signals:
            macro_adj = self._macro_adjustment(macro_signals, asset_classes)
            for ac in asset_classes:
                weights[ac] += cfg.macro_weight * macro_adj.get(ac, 0.0)

        # 3. 跨資產信號調整
        if cross_asset_signals:
            ca_adj = self._cross_asset_adjustment(cross_asset_signals, asset_classes)
            for ac in asset_classes:
                weights[ac] += cfg.cross_asset_weight * ca_adj.get(ac, 0.0)

        # 4. 市場狀態調整
        if regime is not None:
            regime_adj = cfg.regime_adjustment.get(regime, {})
            for ac in asset_classes:
                weights[ac] += cfg.regime_weight * regime_adj.get(ac, 0.0)

        # 5. 約束：最大偏離、最小比例、正值
        weights = self._apply_constraints(weights, asset_classes)

        # 6. 正規化至 sum = 1.0
        weights = self._normalize(weights)

        return weights

    def _macro_adjustment(
        self,
        macro_signals: dict[str, float],
        asset_classes: list[AssetClass],
    ) -> dict[AssetClass, float]:
        """用敏感度矩陣計算宏觀信號的資產調整量。"""
        adj: dict[AssetClass, float] = {ac: 0.0 for ac in asset_classes}
        sensitivity = self.config.macro_sensitivity

        for factor_name, signal_value in macro_signals.items():
            if factor_name not in sensitivity:
                continue
            for ac in asset_classes:
                s = sensitivity[factor_name].get(ac, 0.0)
                adj[ac] += s * signal_value * 0.01  # 縮放至小幅調整

        return adj

    def _cross_asset_adjustment(
        self,
        signals: dict[AssetClass, float],
        asset_classes: list[AssetClass],
    ) -> dict[AssetClass, float]:
        """跨資產信號直接映射為權重調整。"""
        adj: dict[AssetClass, float] = {}
        for ac in asset_classes:
            adj[ac] = signals.get(ac, 0.0) * 0.01  # 縮放
        return adj

    def _apply_constraints(
        self,
        weights: dict[AssetClass, float],
        asset_classes: list[AssetClass],
    ) -> dict[AssetClass, float]:
        """套用偏離限制和最小比例。"""
        cfg = self.config
        strategic = self.strategic.weights

        for ac in asset_classes:
            base = strategic.get(ac, 0.0)
            # 偏離限制
            lower = max(base - cfg.max_deviation, cfg.min_weight)
            upper = base + cfg.max_deviation
            weights[ac] = float(np.clip(weights[ac], lower, upper))
            # 確保正值
            weights[ac] = max(weights[ac], cfg.min_weight)

        return weights

    @staticmethod
    def _normalize(weights: dict[AssetClass, float]) -> dict[AssetClass, float]:
        """正規化至 sum = 1.0。"""
        total = sum(weights.values())
        if total <= 0:
            n = len(weights)
            return {ac: 1.0 / n for ac in weights} if n > 0 else weights
        return {ac: w / total for ac, w in weights.items()}
