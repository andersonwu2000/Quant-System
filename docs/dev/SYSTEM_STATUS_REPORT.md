# 系統現況追蹤報告書

> **日期**: 2026-03-27
> **版本**: v10.0
> **階段**: Phase A~M 完成, Phase N（Paper Trading）代碼就緒, Phase P（Auto Research）設計完成
> **開發計畫**: `docs/dev/DEVELOPMENT_PLAN.md` v13.0

---

## 1. 系統概要

| 指標 | 數值 |
|------|------|
| 後端 Python 檔案 | ~160 |
| 後端 LOC | ~29,000 |
| 測試數量 | **1,337** |
| API 端點 | **117**（16 路由模組） |
| Alpha 因子 | **83**（66 技術 + 17 基本面） |
| 策略 | **13** |
| 最佳化方法 | 14 |
| 風控規則 | 10 |
| 數據源 | 4（Yahoo / FinMind / FRED / Shioaji） |
| 本地價格 parquet | 895 支台股（含 40 支已下市） |
| 本地基本面 parquet | 408 檔（8 dataset × 51 支） |

---

## 2. 模組架構

| 模組 | 檔案 | 核心功能 |
|------|:----:|---------|
| `src/api/` | 24 | 117 REST 端點 + WebSocket 5 頻道 + JWT/RBAC |
| `src/alpha/` | 25 | Alpha Pipeline + FilterStrategy + Regime + Attribution + Auto-Alpha（9 子模組） |
| `src/backtest/` | 12 | BacktestEngine + 40+ 指標 + WF/PBO/DSR + StrategyValidator（13 項閘門） |
| `src/strategy/` | 12 | 83 因子 + 3 最佳化器 + Registry（13 策略） |
| `src/portfolio/` | 4 | 14 最佳化方法 + 風險模型（LW/GARCH/PCA）+ 幣別對沖 |
| `src/execution/` | 16 | SimBroker + SinopacBroker + TWAP + OMS + 對帳 |
| `src/data/` | 15 | Yahoo/FinMind/FRED/Shioaji + 品質檢查 + Parquet 快取 |
| `src/risk/` | 5 | 10 規則 + Kill Switch + RealtimeRiskMonitor |
| `src/allocation/` | 4 | 宏觀四因子 + 跨資產信號 + 戰術引擎 |
| `src/core/` | 6 | 模型 + 設定 + 日誌 + 交易日曆 + Trading Pipeline |
| `src/scheduler/` | 2 | APScheduler：月營收更新 + 月度再平衡 + 通知 |
| `src/notifications/` | 6 | Discord / LINE / Telegram |
| `strategies/` | 11 | 9 內建 + revenue_momentum_hedged + multi_strategy_combo |

---

## 3. 策略（13 個）

| # | 策略 | 類型 | 關鍵指標 |
|---|------|------|---------|
| 1 | Momentum | 規則型 | 12-1 月動量 |
| 2 | Mean Reversion | 規則型 | Z-score |
| 3 | RSI Oversold | 規則型 | RSI < 30 |
| 4 | MA Crossover | 規則型 | 均線交叉 |
| 5 | Multi-Factor | 規則型 | 動量+價值+品質 |
| 6 | Pairs Trading | 規則型 | 共整合 + Kalman |
| 7 | Sector Rotation | 規則型 | 板塊動量輪動 |
| 8 | **Revenue Momentum** | 條件篩選 | rev_yoy ICIR 0.674, CAGR +17.6%（含 40 天營收公布延遲） |
| 9 | **Revenue Momentum Hedged** | 條件篩選 | = #8 + 空頭偵測, OOS -5.4%（含 40 天營收公布延遲） |
| 10 | Trust Follow | 條件篩選 | 投信跟單 + 營收成長 |
| 11 | Multi-Strategy Combo | 組合型 | 多策略等權 |
| 12 | Alpha Pipeline | 管線型 | 可配置因子 + 中性化 |
| 13 | Multi-Asset | 管線型 | 戰術配置 → Alpha → 最佳化 |

---

## 4. 因子庫（83 個）

### 4.1 技術因子 FACTOR_REGISTRY（66 個，35 標記冗餘/無效）

**原始價格因子（11 個）**

| 因子 | 函式 | 方向 | 狀態 |
|------|------|:----:|:----:|
| momentum | `momentum()` | 正 | 有效 |
| mean_reversion | `mean_reversion()` | 負 | 冗餘(bollinger) |
| volatility | `volatility()` | 負 | 冗餘(ivol) |
| rsi | `rsi()` | 負 | 有效 |
| ma_cross | `moving_average_crossover()` | 正 | 有效 |
| vpt | `volume_price_trend()` | 正 | 無效 |
| reversal | `short_term_reversal()` | 負 | 無效 |
| illiquidity | `amihud_illiquidity()` | 正 | 邊緣 |
| ivol | `idiosyncratic_vol()` | 負 | 有效（大型股） |
| skewness | `skewness()` | 負 | 冗餘(idio_skew) |
| max_ret | `max_return()` | 負 | 冗餘(volatility) |

**技術指標（15 個）**

| 因子 | 論文 | 狀態 |
|------|------|:----:|
| bollinger_pos | Bollinger (2001) | 冗餘(rsi) |
| macd_hist | Appel (2005) | 無效 |
| obv_trend | Granville (1963) | 有效 |
| adx | Wilder (1978) | 有效 |
| cci | Lambert (1980) | 無效 |
| williams_r | Williams (1979) | 冗餘(stochastic_k) |
| stochastic_k | Lane (1984) | 無效 |
| atr_ratio | Wilder (1978) | 冗餘(volatility) |
| price_accel | Gu-Kelly-Xiu (2020) | 無效 |
| vol_momentum | Gervais et al. (2001) | 無效 |
| hl_range | Parkinson (1980) | 冗餘(volatility) |
| close_to_high | George-Hwang (2004) | 無效 |
| gap | Branch-Ma (2012) | 冗餘(overnight_ret) |
| intraday_ret | Heston et al. (2010) | 冗餘(alpha_33) |
| overnight_ret | Berkman et al. (2012) | 冗餘(gap) |

**學術因子（10 個）**

| 因子 | 論文 | 狀態 |
|------|------|:----:|
| momentum_1m | Jegadeesh-Titman (1993) | 無效 |
| momentum_6m | Jegadeesh-Titman (1993) | 有效 |
| momentum_12m | Jegadeesh-Titman (1993) | 冗餘(momentum) |
| lt_reversal | De Bondt-Thaler (1985) | 邊緣(hit < 50%) |
| beta | Sharpe (1964) | 無效(IC=0) |
| idio_skew | Harvey-Siddique (2000) | 冗餘(skewness) |
| max_daily_ret | Bali et al. (2011) | 冗餘(max_ret) |
| turnover_vol | Chordia et al. (2001) | 有效（反向） |
| price_delay | Hou-Moskowitz (2005) | 無效 |
| zero_days | Lesmond et al. (1999) | 無效 |

**Kakushadze 101 精選（30 個）** — 全部在台股成本結構下無效（換手率 55-84%）

冗餘群分析（factor_dedup_report.md）：
- 波動率群（6 個）：volatility/ivol/atr_ratio/hl_range/max_ret/max_daily_ret → 保留 `ivol`
- 均值回歸群（4 個）：mean_reversion/bollinger_pos/rsi/alpha_4 → 保留 `rsi`
- 日內報酬群（4 個）：intraday_ret/alpha_33/alpha_101/alpha_38 → 保留 `alpha_18`
- gap = overnight_ret（corr = 1.000）

### 4.2 基本面因子 FUNDAMENTAL_REGISTRY（17 個）

| 因子 | 類型 | 數據源 | ICIR | 狀態 |
|------|------|--------|:----:|:----:|
| **revenue_yoy** | 營收 | FinMind 月營收 | **0.674** | **核心因子** |
| **revenue_acceleration** | 營收 | FinMind 月營收 | **0.847**（60d） | **最強因子** |
| **revenue_new_high** | 營收 | FinMind 月營收 | 0.435 | 有效 |
| **revenue_momentum** | 營收 | FinMind 月營收 | 0.481 | 有效 |
| value_pe | Fama-French | FinMind PER | 0.282（反向） | 邊緣 |
| value_pb | Fama-French | FinMind PER | 0.037 | 無效 |
| quality_roe | Fama-French | FinMind 財報 | — | 未測 |
| size | Fama-French | price×vol proxy | — | 未測 |
| investment | Fama-French | FinMind 財報 | — | 缺數據 |
| gross_profit | Novy-Marx | FinMind 財報 | — | 缺數據 |
| dividend_yield | — | FinMind PER | 0.139 | 弱 |
| foreign_net | 籌碼 | FinMind 法人 | 0.086 | 無效 |
| trust_net | 籌碼 | FinMind 法人 | 0.040 | 無效 |
| director_change | 籌碼 | FinMind 持股 | — | 未測 |
| margin_change | 籌碼 | FinMind 融資融券 | 0.009 | 無效 |
| daytrading_ratio | 情緒 | FinMind 當沖 | 0.085 | 無效 |
| trust_cumulative | 籌碼 | FinMind 法人 | — | 策略用 |

### 4.3 因子研究結論（17 次實驗）

| 結論 | 證據 |
|------|------|
| **台股 alpha 在營收，不在價格** | 4 營收因子 ICIR > 0.3；66 price-volume 全 < 0.5 |
| **revenue_yoy 10 年 100% 穩定** | 2016-2025 每年 IC 正 |
| **營收因子不衰減** | 5d→60d ICIR 持續增強（vs 價格因子衰減） |
| **純營收組合 > 混合** | rev_yoy+mom_6m ICIR 0.024（從 0.674 崩跌） |
| **成本是台股瓶頸** | 換手率 > 10% 的因子全部虧損 |
| **Selection Bias 是最大陷阱** | ivol 32 支 ICIR 0.60 → 142 支 -0.06 |
| **1/N 等權極難打敗** | DeMiguel 2009 在台股完全驗證 |

---

## 5. 驗證狀態

### StrategyValidator 13 項（revenue_momentum, 296 支 × 2018-2025）

| # | 檢查 | 值 | 結果 |
|---|------|---:|:----:|
| 1 | CAGR | +17.6% | ✅ |
| 2 | Sharpe | 1.02 | ✅ |
| 3 | MDD | 26% | ✅ |
| 4 | Walk-Forward 5/5 | 100% | ✅ |
| 5 | Deflated Sharpe | 0.986 | ✅ |
| 6 | Bootstrap P(SR>0) | 100% | ✅ |
| 7 | OOS 2025 H2 | +49.1% | ✅ |
| 8 | vs 1/N 超額 | +9.6% | ✅ |
| 9 | PBO | 0% | ✅ |
| 10 | Worst regime | +0.95% | ✅ |
| 11 | Universe | 296 | ✅ |
| 12 | 成本佔比 | 42.1% | ❌ |
| 13 | Factor decay | -0.384 | ❌ |

**通過 11/13。** 公式驗證：Sharpe/Sortino 已修正（算術年化標準），SimBroker 成本模型/IC/ICIR/PBO 全部正確（24/24）。

---

## 6. API（117 端點）

| 路由 | 端點數 | 關鍵功能 |
|------|:------:|---------|
| auth | 3 | JWT 登入 + API Key |
| admin | 5 | 用戶 CRUD |
| portfolio | 11 | CRUD + optimize(14 方法) + risk-analysis + hedge |
| backtest | 12 | 回測 + WF + grid + kfold + PBO + full-validation |
| strategies | 5 | 列表 + 啟停 + factors(83) |
| alpha | 12 | IC + turnover + attribution + regime + filter-strategy + correlation + neutralize + event-rebalancer |
| auto_alpha | 16 | config + start/stop + status + history + factor-pool + safety + decision + WS |
| allocation | 3 | tactical + macro-factors + cross-asset |
| risk | 7 | rules + config + kill-switch + realtime |
| execution | 15 | status + smart-order + market-hours + reconcile + stop-orders |
| orders | 4 | CRUD |
| scanner | 7 | top-volume + gainers + losers + regulatory |
| data | 4 | quality-check + fundamentals + cache + macro |
| scheduler | 3 | jobs + notify + trigger |
| strategy_center | 7 | 策略中心 UI 支援 |
| system | 4 | health + status + metrics + alerts |

---

## 7. 組合最佳化（14 方法）

| 方法 | 說明 |
|------|------|
| Equal Weight | 等權重 |
| Inverse Volatility | 反波動率加權 |
| Risk Parity | 等風險貢獻 |
| Mean-Variance (MVO) | Markowitz |
| Black-Litterman | 含 BLView 主觀觀點 |
| HRP | 階層式風險平價 |
| Robust | 橢圓不確定集穩健最佳化 |
| Resampled (Michaud) | 蒙地卡羅重取樣 |
| CVaR | Rockafellar-Uryasev LP 重構 |
| Max Drawdown | 歷史模擬 SLSQP |
| Global Min Variance | 最小波動率 |
| Max Sharpe | Dinkelbach 分數規劃 |
| Index Tracking | LASSO 稀疏追蹤 |
| Semi-Variance | 下行風險最佳化 |

**風險模型**: 歷史/EWM/Ledoit-Wolf/GARCH(1,1)/PCA + VaR/CVaR + James-Stein 均值收縮

## 8. 風控規則（10 條）

| # | 規則 | 層級 | 預設 |
|---|------|------|------|
| 1 | max_position_weight | 個股 | 5% |
| 2 | max_order_notional | 個股 | 2% NAV |
| 3 | daily_drawdown_limit | 組合 | 3% |
| 4 | fat_finger_check | 個股 | 5% 偏離 |
| 5 | max_daily_trades | 組合 | 100 筆 |
| 6 | max_order_vs_adv | 個股 | 10% ADV |
| 7 | price_circuit_breaker | 個股 | ±10% |
| 8 | max_asset_class_weight | 跨資產 | 40% |
| 9 | max_currency_exposure | 跨資產 | 60% |
| 10 | max_gross_leverage | 跨資產 | 1.5x |

## 9. 交易執行層

| 模組 | 功能 |
|------|------|
| SimBroker | 回測撮合：sqrt 滑點 + min NT$20 手續費 + 證交稅 + 零股加滑點 + 漲跌停流動性檢查（±9.5%）+ ADV 10% 量限 |
| SinopacBroker | Shioaji SDK：非阻塞下單 + 成交回報 + 斷線重連 |
| ExecutionService | 模式路由（backtest/paper/live） |
| OMS | 訂單生命週期 + 成交記錄 |
| TWAPSplitter | 大單拆 N 筆子單 |
| Reconcile | EOD 持倉對帳 + auto_correct |
| StopOrderManager | 觸價委託 |
| MarketHours | 台股時段 + 國定假日 |

## 10. 本地數據資產

| 類別 | 檔案數 | 路徑 | 說明 |
|------|:------:|------|------|
| 價格 OHLCV | 895 | `data/market/*.parquet` | 2015-2025, 含 40 支已下市 |
| 財報 | 51 | `data/fundamental/*_financial_statement.parquet` | EPS/ROE |
| PER/PBR | 51 | `data/fundamental/*_per.parquet` | 每日本益比/淨值比 |
| 月營收 | 312 | `data/fundamental/*_revenue.parquet` | 月營收 + YoY |
| 法人買賣超 | 223 | `data/fundamental/*_institutional.parquet` | 外資/投信/自營 |
| 融資融券 | 51 | `data/fundamental/*_margin.parquet` | 餘額 |
| 董監持股 | 51 | `data/fundamental/*_shareholding.parquet` | 持股比例 |
| 當沖 | 51 | `data/fundamental/*_daytrading.parquet` | 當沖量 |
| 股利 | 51 | `data/fundamental/*_dividend.parquet` | 除權息 |

---

## 11. 測試 + CI

| 項目 | 數值 |
|------|------|
| pytest 測試數 | 1,337 passed |
| ruff lint | 0 errors |
| CI jobs | 9（lint + test + typecheck + build + e2e + android + release） |

---

## 12. 階段完成度

| 階段 | 日期 | 狀態 |
|------|------|:----:|
| A~E | 03-22~25 | ✅ |
| F~I | 03-26 | ✅ |
| R1-R4 | 03-26 | ✅ |
| K（數據品質 + 基本面因子） | 03-26 | ✅ |
| L（策略轉型 + 條件篩選） | 03-26 | ✅ |
| M（下行保護 + 因子驗證） | 03-27 | ✅ |
| N（Paper Trading）代碼 | 03-27 | ✅ 代碼就緒 |
| N（30 天 Paper Trading） | — | ⏳ 等 CA 憑證 |
| P（自動化 Alpha 研究） | 03-27 | 🔵 設計完成 |

---

## 13. 阻塞項

| 項目 | 狀態 |
|------|------|
| CA 憑證（永豐金） | ⏳ 使用者申請中 |
| Paper Trading 30 天驗證 | ⏳ 等 CA 憑證 |
| Phase P 實作 | 🔵 設計完成，可開始 |

---

## 14. 實驗報告索引

17 份實驗報告 + 5 CSV，詳見 `docs/dev/test/RESEARCH_SUMMARY.md`。

核心結論：
- rev_yoy ICIR 0.674（10 年 100% 穩定）
- revenue_momentum Validator 11/13 通過
- 純營收 > 營收+價格混合
- 1/N 等權在台股極難打敗
