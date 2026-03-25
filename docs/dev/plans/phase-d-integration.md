# Phase D：系統整合 + 風控升級

> 完成日期：2026-03-25
> 狀態：✅ 完成

## 目標
串接所有模組為完整的兩層配置策略，強化跨資產風控。

## 產出
- **MultiAssetStrategy** (`src/strategy/multi_asset.py`): 兩層配置（戰術→資產內 Alpha→組合最佳化）
- **跨資產風控規則**: `max_asset_class_weight`、`max_currency_exposure`、`max_gross_leverage`
- **AllocationPage 前端**: 戰術配置計算 + 視覺化
- **Bug fixes**: FX per-bar 更新 / 總權重驗證 / FRED ffill(66)
- **Alpha 強化**: +5 技術因子 (reversal/illiquidity/ivol/skewness/max_ret) + Rolling IC + Regime + Attribution
