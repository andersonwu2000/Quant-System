# Phase B：跨資產 Alpha

> 完成日期：2026-03-24
> 狀態：✅ 完成

## 目標
建立資產類別間的信號生成與戰術配置引擎。

## 產出
- **MacroFactorModel** (`src/allocation/macro_factors.py`): 4 個宏觀因子（成長/通膨/利率/信用），FRED z-scores
- **CrossAssetSignals** (`src/allocation/cross_asset.py`): 動量/波動率/價值 per AssetClass
- **TacticalEngine** (`src/allocation/tactical.py`): 戰略權重 + 宏觀偏離 + 跨資產信號 + regime → `dict[AssetClass, float]`
- **API**: `POST /api/v1/allocation`
