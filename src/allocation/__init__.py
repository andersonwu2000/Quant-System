"""資產間 Alpha — 戰術資產配置層。

回答「現在應該把多少比例放在股票、債券ETF、商品、現金？」

模組：
- macro_factors: 宏觀因子模型（成長/通膨/利率/信用）
- cross_asset: 跨資產信號（動量/carry/value/volatility）
- tactical: 戰術配置引擎（合成信號 → 資產類別權重）
"""

from src.allocation.cross_asset import CrossAssetSignals
from src.allocation.macro_factors import MacroFactorModel, MacroSignals
from src.allocation.tactical import (
    StrategicAllocation,
    TacticalConfig,
    TacticalEngine,
)

__all__ = [
    "CrossAssetSignals",
    "MacroFactorModel",
    "MacroSignals",
    "StrategicAllocation",
    "TacticalConfig",
    "TacticalEngine",
]
