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
