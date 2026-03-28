# Phase V — Kill Switch & Production Readiness Debug ✅ 已完成

**建立日期：** 2026-03-28
**優先級：** HIGH（涉及實盤資金安全）
**狀態：** 進行中

---

## 背景

從外部審查報告歸納出四個注意面向：實盤驗證、監控告警、災難恢復、單人開發。
本計畫聚焦風險最高的 **Kill Switch** 路徑，再擴展到其他三個面向。

---

## 一、Kill Switch Bug 狀態（原始 #19~#21）

| Bug | 原始問題 | 當前狀態 | 驗證依據 |
|-----|---------|---------|---------|
| #19 無限循環 | `kill_switch()` 只回傳 bool，不 apply_trades | **已修** | `app.py:321` fired flag + `app.py:344` apply_trades |
| #20 Re-trigger guard | 每 5 秒重觸發熔斷 | **已修** | `app.py:317-318` `if kill_switch_fired: continue` |
| #21 實盤不清倉 | engine.kill_switch() 只判斷不清倉 | **已修** | `app.py:331-348` + `realtime.py:113-133` 兩條路徑都有清倉 |

---

## 二、新發現問題：雙重清倉 Race Condition

### 問題描述

Kill Switch 現在有**兩條獨立的清倉路徑**，不互相協調：

**路徑 A — `src/api/app.py:_kill_switch_monitor`（每 5 秒輪詢）**
- 觸發條件：`portfolio.daily_drawdown > 5%`
- Guard：`state.kill_switch_fired`（全域共享 AppState）
- 清倉方式：在 `async with state.mutation_lock` 內執行（有鎖保護）

**路徑 B — `src/risk/realtime.py:on_price_update`（每個 tick）**
- 觸發條件：`intraday_drawdown < -5%`（不同指標）
- Guard：`_alerts_sent`（只存在 RealtimeRiskMonitor 本地，不跨路徑共享）
- 清倉方式：`asyncio.run_coroutine_threadsafe` → **不持有 mutation_lock**

### 風險

1. **雙重賣單**：兩條路徑可同時觸發清倉，對同一持倉送出兩批賣單
2. **無鎖保護**：路徑 B 的 `apply_trades` 不在 `mutation_lock` 內，與路徑 A 有 race condition
3. **指標不一致**：`daily_drawdown` vs `intraday_drawdown` 計算方式不同，可能一觸發一不觸發，行為不可預期

---

## 三、Debug 工作清單

### Step 1 — 確認 Guard 是否共用（✅ 已完成）
- [x] `realtime.py` 完全沒有 `kill_switch_fired` 引用 → 雙路徑問題確認
- [x] 路徑 B 只用本地 `_alerts_sent` 做防重觸發，不跨路徑共享

### Step 2 — 確認 mutation_lock 覆蓋（✅ 已完成）
- [x] 路徑 B 的 `_execute_liquidation` 直接呼叫 `apply_trades`，無 `mutation_lock`
- [x] **已修復**：加入 `async with state.mutation_lock` + 雙重檢查 `kill_switch_fired`

### Step 3 — 確認兩個回撤指標的差異（✅ 已完成）
- [x] 路徑 A：`daily_drawdown = -daily_pnl / nav_sod`（開盤 NAV 起算）
- [x] 路徑 B：`intraday_dd = (nav - nav_high) / nav_high`（日內高水位起算）
- [x] 兩者可能同時 > 5%（開盤直跌 5%），也可能只有一個超過（先漲後跌）

### Step 4 — 模擬測試（✅ 已完成 — 單元測試覆蓋）
- [x] `test_path_b_fires_first_path_a_skips` — 路徑 B 先觸發，路徑 A 跳過
- [x] `test_path_a_fires_first_path_b_skips` — 路徑 A 先觸發，路徑 B 跳過
- [x] `test_concurrent_path_b_only_one_succeeds` — 兩個路徑 B 併發，只有一個成功
- [x] `test_no_execution_when_already_fired` — fired=True 時路徑 B 直接跳過

### Step 5 — 修復（✅ 已完成 — 方案 B）
- [x] `RealtimeRiskMonitor.__init__` 加入 `app_state` 參數
- [x] `_execute_liquidation` 加入 `mutation_lock` + 雙重檢查 `kill_switch_fired`
- [x] 清倉成功後設 `state.kill_switch_fired = True`
- [x] 無 `app_state` 時降級為舊行為（backward compat）
- [x] Commit: `fa9a24f`

---

## 四、後續擴展：其他三個面向

完成 Kill Switch debug 後，依序處理：

### 4.1 實盤驗證
- [x] 確認 `SinopacConfig.simulation` 當前值 → **預設 True（安全），由 `QUANT_MODE=paper|live` 控制**
- [x] 確認 `reconcile.py` 是否真的被排程呼叫 → **原本只有 API 手動觸發，已加入排程**
  - 新增 `execute_daily_reconcile()` job，每日 14:30（台股收盤後）自動對帳
  - 差異自動透過通知系統告警
  - 可透過 `QUANT_RECONCILE_CRON` 調整 cron
- [x] 確認 PaperBroker/SimBroker 費率與 config 一致（BUG #34, #35）
  - PaperBroker 用 `CostModel.from_config()` → ✅ 已同步
  - SimBroker 在 `ExecutionService.initialize()` 用硬編碼預設 → **已修復**，改用 `SimConfig(commission_rate=config.commission_rate, ...)`
- [ ] paper trade log vs 券商後台比對（需要實際券商帳戶）

### 4.2 監控告警
- [x] Kill Switch 通知 → **已加入 Discord/LINE/Telegram 通知**
  - 路徑 A（app.py）：清倉後發送通知
  - 路徑 B（realtime.py）：清倉後發送通知
  - 通知失敗不阻塞清倉（try/except）
- [x] 通知端對端測試 → **4 個測試覆蓋**
  - `test_discrepancy_sends_notification` — 對帳差異觸發通知
  - `test_path_b_sends_notification` — kill switch 觸發通知
  - `test_path_b_notification_failure_does_not_block` — 通知失敗不影響清倉
- [x] Prometheus metrics export 覆蓋率 → **新增 `src/metrics.py` 集中模組**
  - `kill_switch_triggers_total` — Counter（path=poll/tick）
  - `risk_alerts_total` — Counter（severity=warning/critical/emergency）
  - `intraday_drawdown_pct` / `nav_current` — Gauge（每 tick 更新）
  - `reconcile_runs_total` / `reconcile_mismatches` — Counter/Gauge
  - `pipeline_runs_total` / `pipeline_trades_total` / `pipeline_duration_seconds`
  - `orders_submitted_total` / `orders_rejected_total`
- [x] 告警內容改善 → **所有 kill switch 告警加入 drawdown %、NAV、SOD、持倉明細**
  - 路徑 A：包含 `daily_drawdown %`、NAV vs SOD、top 5 持倉
  - 路徑 B：包含 `intraday drawdown`、清倉數量、NAV vs SOD、top 5 持倉
  - Reconcile Error：包含錯誤類型、mode、持倉數量

### 4.3 災難恢復
- [x] Crash recovery 模擬 → **4 個測試覆蓋**
  - `test_save_load_roundtrip` — 完整 save/load 含 positions, pending_settlements, nav_sod
  - `test_nav_sod_defaults_to_nav_when_zero` — E5 fix 確認
  - `test_load_returns_none_when_no_file` — 無持久化檔案時回傳 None
  - `test_atomic_write` — 原子寫入（tmp+rename）
- [x] `state.py:save_portfolio` 序列化確認 → **已驗證 nav_sod + pending_settlements 完整保存**
- [x] 重啟後不會重複再平衡 → **已驗證**
  - `_has_completed_run_today()` 和 `_has_completed_run_this_month()` 檢查 pipeline_runs JSON
  - `check_crashed_runs()` 偵測並標記 crashed 的 run
  - 3 個測試覆蓋 idempotency guard

---

## 五、相關檔案

| 檔案 | 用途 |
|------|------|
| `src/api/app.py:312-357` | Kill Switch 路徑 A（5 秒輪詢監控） |
| `src/risk/realtime.py:104-133` | Kill Switch 路徑 B（tick 觸發） |
| `src/risk/engine.py:161-201` | `kill_switch()` + `generate_liquidation_orders()` |
| `src/api/state.py` | `kill_switch_fired` flag、`mutation_lock` |
| `src/execution/oms.py` | `apply_trades()` |
| `src/core/models.py` | `daily_drawdown` property |
| `docs/claude/BUG_HISTORY.md` | 原始 Bug #19~#21 及其他風控 bug |
