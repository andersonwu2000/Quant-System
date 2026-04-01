# 歷史 Bug 紀錄（60+ 個已修復）

> 從 CLAUDE.md 移出。按類別分類，供修改相關檔案時參考。

## 公式與計算（9 個）
1. Sharpe 幾何/算術混用（analytics.py）
2. Sortino 下行偏差只算負值（analytics.py）
3. factor_evaluator ICIR ddof 不一致（factor_evaluator.py）
4. beat_magnitude 13 月 vs 12 月 off-by-one（alpha_research_agent.py）
5. rev_breakout 包含當月 → 永遠回傳 0（alpha_research_agent.py）
6. rev_accel_2nd_derivative 算一階非二階導數（alpha_research_agent.py）
7. forward return off-by-one: after[h-1] vs after[h]（alpha_research_agent.py）
8. CAGR n_days off-by-one: len(nav) 應為 len(nav)-1（analytics.py）
9. DSR kurtosis double correction: scipy excess + deflated_sharpe -3（validator.py）

## Look-Ahead Bias（8 個）
10. 自動因子代碼無 40 天營收延遲（alpha_research_agent.py）— 所有因子 IC 被高估
11. trust_follow.py 營收無 40 天延遲
12. 5 個研究因子檔案缺 40 天延遲（rev_consecutive_beat 等）
13. L5 Walk-Forward 是空殼（passed=True），不做實際檢查（factor_evaluator.py）

## 風控（12 個）
14. order.side.value == "BUY" 脆弱 enum 比較，4 處（rules.py）
15. check_orders 無累積效應，10 筆各 9% 合計 90% 通過（engine.py）
16. max_daily_trades 在 check 階段就 increment（rules.py）
17. max_gross_leverage SELL 對賣空不正確（rules.py）
18. default_rules 門檻硬編碼 10%，config 是 5%（rules.py）
19. Kill switch 不 apply_trades → 無限循環（app.py）— **CRITICAL**
20. Kill switch 無 re-trigger guard → 每 5 秒重觸發（app.py）
21. Kill switch 在實盤不清倉（只回傳 bool）（engine.py, realtime.py）
22. RealtimeRiskMonitor 無 thread safety（realtime.py）
23. RealtimeRiskMonitor 無自動日期重置（realtime.py）
24. 無 post-trade 風控檢查（engine.py）
25. 無累計回撤限制（只有日回撤）（rules.py）

## 管線與流程（12 個）
26. 營收更新和再平衡靠 35 分鐘 cron gap（scheduler/__init__.py）
27. monthly_revenue_update --start 硬編碼 2024-01-01（jobs.py）
28. 三條管線路徑無互斥保證（scheduler/__init__.py）
29. execute_rebalance 空 portfolio 無 fallback（jobs.py）
30. Pipeline 無 trade log 持久化（jobs.py）
31. Pipeline 風控 check_order 未傳 MarketState（jobs.py）
32. Pipeline universe 只用現有持倉（jobs.py）
33. _async_revenue_update 丟棄回傳值（jobs.py）
34. PaperBroker 無滑價模擬（base.py）
35. PaperBroker 費率硬編碼（base.py）
36. save_portfolio 缺 nav_sod 和 pending_settlements（state.py）
37. Validator cost_ratio 用 net return 當分母（validator.py）

## 並發與狀態（7 個）
38. Portfolio 讀寫 race condition（tick vs apply_trades）（models.py）
39. Crash 後重複再平衡（無月度 idempotency）（jobs.py）
40. Trade log 在 apply_trades 後才存（crash 丟失紀錄）（jobs.py）
41. RealtimeRiskMonitor 用 UTC 而非 UTC+8 判斷日期（realtime.py）
42. Rebalance/Pipeline 無 mutation_lock（strategy_center.py, jobs.py）
43. Shioaji 線程 vs asyncio 事件循環競爭（realtime.py）
44. Portfolio 狀態無持久化，重啟丟失（state.py）

## 語義與數據（8 個）
45. compute_forward_returns 日期交集 → 大 universe 空結果（research.py）
46. Validator PBO 用 noise perturbation 非 CSCV（validator.py）
47. Validator PBO 數據不足回傳 0（最樂觀值）（validator.py）
48. Validator 固定用零股（和實際整張不一致）（validator.py）
49. Validator OOS 日期和 IS 可能重疊（validator.py）
50. cross_section 日期錯位（cross_section.py）
51. engine _col_index 跨矩陣快取碰撞（engine.py）
52. apply_trades sell overflow 可能產生負持倉（oms.py）

## 方法論錯誤（3 個）— 代碼審計無法發現
53. PBO v1: noise perturbation 不是 CSCV — 假策略（加噪音）不等於真策略變體（validator.py）
54. PBO v2: N 定義錯誤 — 用 10 個 portfolio construction 變體做 N，但 Bailey 定義 N = 所有測試過的因子。測的是 portfolio sensitivity 不是 factor selection overfitting（validator.py）
55. PBO v3: 加速了錯誤的計算 — 向量化讓 v2 更快但沒修正 N 的定義。三次實作三次錯，根因是沒讀原論文就實作（vectorized.py, validator.py）

## 2026-03-31 Bug Hunt（7 個）

### 回測引擎
56. Trade PnL matching 不管數量 — `_trade_stats` 的 FIFO 只存 price 不存 qty，pop(0) 忽略數量匹配。2 筆 BUY 各 100 股 + 1 筆 SELL 200 股 → 用第一筆買價乘 200 股，勝率和平均盈虧失真（analytics.py）
57. Kill switch 不清空頭 — `_execute_kill_switch` 只檢查 `quantity > 0`，空頭持倉在熔斷後仍暴露（engine.py）
58. Weekly rebalance 假日跳過 — `_is_rebalance_day` 硬編碼 `weekday == 0`，週一休市則整週跳過再平衡（engine.py）
59. Turnover 用雙邊定義 — `_estimate_turnover` 用 total_traded（買+賣），Validator 的 0.80 門檻在雙邊下過嚴（analytics.py）

### 執行層
60. weights_to_orders 字母排序先買後賣 — 滿倉換股時先處理 BUY 導致資金不足被拒，SELL 釋放的資金來不及用（strategy/engine.py）
61. max_position_weight all-or-nothing — 5.1% 超過 5.0% 整單 REJECT 而非 cap 到限制值，已有 MODIFY API 但規則沒用（rules.py）
62. SimBroker 不檢查零股時段 — simulation 模式不檢查 09:10-13:30，paper trading 可在任何時間「成交」零股（simulated.py）

### Autoresearch
63. market_cap look-ahead bias — `_mask_data` 直傳最新 market_cap（close × shares_issued）未做 PIT 截斷，agent 用 size 因子有前視偏差（evaluate.py）

## 2026-04-01 跨模組整合 Bug（9 個）

### 數據一致性
64. evaluate.py `_FactorStrategy` data dict 缺 per_history/margin/institutional — Validator 用不完整數據判定因子，per_value 因子在 Validator 裡必定失敗（evaluate.py）
65. `strategy_builder.py` data dict 同樣缺 per_history/margin/institutional — 部署後因子拿不到數據（strategy_builder.py）
66. `deployed_executor.py` data dict 只有 bars — 日頻執行的因子完全沒有基本面數據（deployed_executor.py）
67. `Context.get_revenue` 直接讀 parquet_path 繞過 DataCatalog — 沒有 FinLab panel 合併，Validator 回測只用 7 年數據而 evaluate.py 用 21 年（base.py）
68. 權重公式不一致 — evaluate.py 用 `1/n`（100% 投資），strategy_builder 用 `0.95/n`（95%），部署後行為不同（evaluate.py, strategy_builder.py）

### 回測引擎
69. vectorized.py `_build_market_matrices` 死碼 — `continue` 後面的 try block 永遠不會執行，PBO 分析讀不到價格（vectorized.py）
70. vectorized.py `_load_revenue` 同樣死碼 — revenue 載入被跳過（vectorized.py）
71. Validator 回測 `enable_kill_switch=True` — kill switch 在月頻策略觸發 20+ 次，人為壓低 CAGR（validator.py）

### 執行層
72. Reconciliation symbol 格式不一致 — System 用 `.TW`（`2330.TW`），Sinopac broker 用 bare（`2330`），matched 永遠為 0（reconcile.py）
73. Paper mode 假 Discord 告警 — SimBroker 每次重啟清空持倉，和持久化的 Portfolio 比對必定不一致，每天假告警（jobs.py）
74. evaluate.py saturation + novelty check 用舊路徑 `data/market` — Phase AD 後路徑已改為 `data/yahoo`，VectorizedPBOBacktest 找不到檔案（evaluate.py）
75. Context.get_revenue yoy_growth 為 NaN — FinLab（2005-2018）有 yoy_growth，FinMind（2019+）沒有。合併後 `isna().all()` = False 跳過重算，但 lookback 截斷到最近 36 月（全 FinMind = 全 NaN）→ revenue_acceleration 因子在 Validator/OOS 回傳空（base.py）**CRITICAL — 因子在回測中完全失效**

## 2026-04-01 Paper Trading Bug

76. Paper mode kill switch 假清倉 — 伺服器重啟後 ShioajiFeed 無報價（盤前），fallback 到 catalog 價格導致 NAV 跳到 4.89 億（SOD 1,312 萬），_nav_high 被污染後微幅下跌即觸發 kill switch，SimBroker 以錯誤市價執行 92 筆 liquidation。根因有三：(1) NAV/SOD 比率無 sanity check (2) paper mode 不應執行真正的 liquidation (3) path A（_kill_switch_monitor）也有同樣問題。（realtime.py, app.py）
77. `_atomic_write` Windows rename 失敗 — `Path.rename()` 在 Windows 上不能覆蓋既有檔案，需先 `unlink` 再 `rename`（refresh.py）

## 預防措施（2026-04-01）

78. 啟動冷卻期 — ExecutionService.initialize() 後 120 秒內拒絕所有訂單，防止報價未穩定時誤交易（service.py）
79. 每分鐘訂單限速 — 滑動窗口 10 筆/分鐘，防止策略異常產生訂單洪水（service.py）
80. 檔案型 Kill Switch — `data/emergency_halt.flag` 存在即拒絕所有訂單，API server crash 時仍可手動停止交易（service.py）
81. Paper mode 行為集中管控 — `config.enable_kill_switch_liquidation` / `enable_reconciliation` / `enable_portfolio_persistence` 三個 property 取代散佈各處的 `if mode == "paper"` 判斷（config.py）
