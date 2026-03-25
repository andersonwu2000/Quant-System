# Phase H：實用精煉

> 完成日期：2026-03-26
> 狀態：✅ 完成

## 目標
只做有明確實用價值、難度合理的精煉項目。刪除了 Phase G 中學術性大於實用性的項目（MVSK、非高斯建模、HERC/NCO、EVaR、非線性收縮）。

## 產出

### H1: Deflated Sharpe Ratio + MinBTL
- `deflated_sharpe()`: Bailey & López de Prado (2014) — 校正 N_trials + skewness + kurtosis 後的 Sharpe ratio 顯著性
- `min_backtest_length()`: 給定 N 策略，最短回測長度避免偽陽性
- 實作位置：`src/backtest/analytics.py`

### H2: Semi-Variance 最佳化
- `OptimizationMethod.SEMI_VARIANCE`: 只懲罰下行波動的 semi-covariance matrix + SLSQP
- 第 14 個最佳化方法
- 實作位置：`src/portfolio/optimizer.py`

### H3: Kalman Filter Pairs Trading
- `KalmanHedgeRatio`: 線上 Kalman Filter 估計動態 hedge ratio
- `PairsTradingStrategy(method="kalman")`: 向後相容，filters cached per pair
- 實作位置：`strategies/pairs_trading.py`

## 被刪除的項目（學術性 > 實用性）
- MVSK 高階矩 — 小 universe 估計不穩定
- Tyler's M-estimator / skewed-t — 已有 LW+GARCH 足夠
- EVaR — 已有 CVaR 足夠
- HERC/NCO — 已有 HRP 足夠
- 非線性共變異數收縮 — 實作複雜，邊際改善有限
