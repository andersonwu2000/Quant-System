# Phase C：組合最佳化

> 完成日期：2026-03-24
> 狀態：✅ 完成

## 目標
實作多種組合最佳化方法與風險模型。

## 產出
- **PortfolioOptimizer** (`src/portfolio/optimizer.py`): 6 方法 — EW/InverseVol/RiskParity/MVO/BlackLitterman/HRP
- **RiskModel** (`src/portfolio/risk_model.py`): 共變異數估計（歷史/EWM/Ledoit-Wolf 收縮）+ 風險貢獻
- **CurrencyHedger** (`src/portfolio/currency.py`): 分級對沖策略 + HedgeRecommendation
- **BLView**: Black-Litterman 主觀觀點輸入
