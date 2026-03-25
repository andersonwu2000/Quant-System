# Phase I：Alpha 因子庫擴展

> 狀態：待開發
> 論文來源：`docs/ref/papers/alpha/`（10 篇）
> 差距分析：`docs/dev/SYSTEM_STATUS_REPORT.md` §11.7

## 目標
基於學術論文擴展因子庫，校正篩選閾值，增加 momentum crash 防護。

## I1: Fama-French 因子補齊（🔴 P0）

| 因子 | 定義 | 論文 | 數據 |
|------|------|------|------|
| `size` (SMB) | log(market_cap) | Fama-French (1993) | FinMind 市值 |
| `investment` (CMA) | YoY total asset growth | Fama-French (2015) | FinMind 財報 |
| `gross_profitability` | (Revenue - COGS) / Assets | Novy-Marx (2013) | FinMind 財報 |

實作：`src/strategy/factors.py` + `FUNDAMENTAL_REGISTRY`

## I2: Kakushadze 101 精選（🟡 P1）

從 101 個公式中挑選 10~15 個低相關、高 Sharpe 的 price-volume 因子。
- 平均持有期 0.6~6.4 天（短天期 alpha）
- 平均配對相關性 15.9%（高分散化）
- 篩選標準：台股 IC > 0.02 + 低與現有因子相關性

## I3: 因子篩選閾值校正（🔴 P0）

| 修正 | 論文依據 |
|------|---------|
| `min_icir` 0.3 → 0.5 | Harvey (2016): t > 3.0 才顯著 |
| IS→OOS 衰減係數 | McLean & Pontiff (2016): OOS alpha ≈ 0.42× IS |
| 1/N benchmark | DeMiguel (2009): N>25 T<500 時 1/N 難以打敗 |

## I4: Momentum Crash 防護（🟡 P1）

Daniel & Moskowitz (2016): momentum crash 在恐慌狀態後發生，可預測。
- SafetyChecker 新增 crash 偵測（市場跌幅 > 20% + 高波動率）
- `REGIME_FACTOR_BIAS[BEAR]["momentum"]` 0.5 → 0.1
- 可選 volatility-scaling: `w_mom × (σ_target / σ_realized_20d)`
