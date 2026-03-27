# Phase G：學術基準升級

> 完成日期：2026-03-26
> 狀態：✅ 完成
> 參考：`docs/dev/SYSTEM_STATUS_REPORT.md` §11 + `docs/ref/papers/`

## 目標
基於 *Portfolio Optimization: Theory and Application* (Palomar, 608 頁) 教科書差距分析 + 論文，將系統提升至學術水準。

## 論文對照（已驗證公式正確性）

| 論文 | 實作 | 驗證 |
|------|------|------|
| Rockafellar & Uryasev (2000) | CVaR optimization — LP reformulation eq.(9)(17) | ✅ |
| Goldfarb & Iyengar (2003) | Robust portfolio — ellipsoidal uncertainty set | ✅ 簡化版 |
| Bailey et al. (2015) | PBO/CSCV — S partitions, C(S,S/2) combinations | ✅ |
| Jorion (1986) | James-Stein mean shrinkage — c = max(0, (p-2)/(n‖μ̂-μ₀‖²)) | ✅ |
| Benidis/Feng/Palomar (2018) | Index Tracking — LASSO L1 regularization | ✅ ETE variant |

## 產出

### G1 風險度量: VaR/CVaR 計算 + CVaR 最佳化 + MaxDD 最佳化
### G2 穩健最佳化: Worst-case Robust + Resampled (Michaud) + James-Stein
### G3 回測方法論: Randomized + PBO + k-fold CV + Stress Test (4 scenarios)
### G4 數據建模: GARCH(1,1) + PCA Factor Model Covariance
### G5 高階方法: GMV + Max Sharpe (Dinkelbach) + Index Tracking (LASSO)
### G6 策略升級: Pairs Trading Engle-Granger 共整合
### G7 績效指標: Omega Ratio + Rolling Sharpe
### G8 回測防護: 存活偏差偵測 + 借券成本 + 價格異常偵測

## 最終狀態
PortfolioOptimizer: 13 方法 | RiskModel: LW/GARCH/Factor/VaR/CVaR/James-Stein
