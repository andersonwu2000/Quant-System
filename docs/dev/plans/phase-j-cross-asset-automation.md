# Phase J：Alpha 自動化擴展至跨資產

> 狀態：待開發
> 前置：Phase I 完成 + API Key 取得

## 目標
從「台股個股選股」擴展至「ETF 配置 + 跨市場」。

## J1: ETF Alpha Pipeline（🟡 P1）

Asness et al. (2013) 證明 value + momentum 在股票/債券/外匯/商品中普遍有效。

- `AlphaConfig` 新增 `asset_type: Literal["stock", "etf", "mixed"]`
- ETF 因子：momentum + value (yield/PE) + volatility + carry
- Universe：台灣 ETF (0050/0056/00878/00713) + 美國 ETF (SPY/QQQ/TLT/GLD)
- 整合至 AutoAlphaScheduler

## J2: 兩層自動化整合（🟢 P2）

```
每日流水線（擴展版）：
1. TacticalEngine → 資產類別權重 (股票 60% / 債券 ETF 25% / 商品 ETF 15%)
2. 股票部位 → AutoAlpha 個股選股（現有 Phase F 流程）
3. 債券/商品部位 → ETF Alpha Pipeline（J1）
4. 合併 → PortfolioOptimizer → 最終權重
```
