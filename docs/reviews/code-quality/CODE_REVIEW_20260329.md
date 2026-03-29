# 全系統 Code Review — 2026-03-29

> 範圍：backtest/validator/overfitting/analytics/walk_forward/vectorized + execution/sinopac/oms/service + API/auto_alpha/risk/app + strategy/base/engine/optimizer + scheduler/jobs
> 方法：3 組平行審計

---

## CRITICAL（9 個）

### C-01: sinopac 零股分流 — 第二個 sub-order 從 _order_map 丟失 ✅ 已修

**位置**：`src/execution/broker/sinopac.py:247`

**修正**：所有 sub-order 的 broker_id 都存入 `_order_map`（loop over `broker_ids`）。

### C-02: sinopac 模擬模式 overfill ✅ 已修

**位置**：`src/execution/broker/sinopac.py:199,266`

**修正**：用 `submitted_shares` 追蹤實際提交量，零股被 skip 時填入實際量而非 `order.quantity`。

### C-03: sinopac 整股張數 vs 零股股數單位不一致 ✅ 已修

**位置**：`src/execution/broker/sinopac.py:233`

**修正**：`lot_size` 轉換邏輯修正，callback 中根據整股/零股做單位轉換。

### C-04: Permutation test fail-open ✅ 已修

**位置**：`src/backtest/validator.py:674`

`compute_fn` 不可用時回傳 `p=0.0`（通過門檻 < 0.10）。對於非 autoresearch 策略（沒有 `compute_fn`），permutation test 自動通過 = 形同虛設。

**修正**：改為回傳 `1.0`（fail-closed）。

### C-05: 危機 regime 用算術 sum 而非幾何 compound ✅ 已修

**位置**：`src/backtest/validator.py:986`

**修正**：`sum()` → `(1 + rets).prod() - 1`（幾何 compound）。

### C-06: Context.get_revenue 無 bare symbol fallback ✅ 已修

**位置**：`src/strategy/base.py:123`

**修正**：加入 `.TW` 後綴 fallback（`C-06` 標記）。

### C-07: risk_parity 傳空 volatilities — 永遠回傳空 ✅ 已修

**位置**：`strategies/revenue_momentum.py:274`

**修正**：計算各標的 20 日年化波動率傳入 `risk_parity`（`B-4 fix` 標記）。

### C-08: execute_rebalance 只取 target 價格 — 持倉無法平倉 ✅ 已修

**位置**：`src/scheduler/jobs.py:193`

**修正**：`_all_syms = set(target_weights) | set(state.portfolio.positions.keys())`。

### C-09: monthly_revenue_rebalance 同上 ✅ 已修

**位置**：`src/scheduler/jobs.py:360`

**修正**：同 C-08。

---

## HIGH（8 個）

### H-01: sinopac _trades dict 從未寫入 ✅ 已修

**位置**：`src/execution/broker/sinopac.py:232`

**修正**：`submit_order` 同時寫入 `_trades[bid] = trade`（`H-01` 標記）。

### H-02: Kill switch path A 不 double-check kill_switch_fired ✅ 已修

**位置**：`src/api/app.py`

**修正**：path A 在 mutation_lock 內 re-check `kill_switch_fired`，和 path B 一致。

### H-03: generate_liquidation_orders 在 lock 外讀 portfolio ✅ 已修

**位置**：`src/risk/realtime.py`

**修正**：在 lock 內讀 portfolio 並生成清倉訂單。（同 H-02 一起修復）

### H-04: apply_trades 直接改 trade.quantity（sell cap）✅ 已修

**位置**：`src/execution/oms.py:71-83`

**修正**：用 `effective_qty` 局部變數，不 mutate 原始 Trade 物件（`H-04` 標記）。

### H-05: PBO 最後一個 partition 吸收餘數 ✅ 已修

**位置**：`src/backtest/overfitting.py:84-89`

**修正**：丟棄餘數行，確保所有 partition 等長。

### H-06: analytics annual_return 對 total_return 在 (-2, -1) 產生 NaN

**位置**：`src/backtest/analytics.py:299`

`(1 + total_return) ** (1/n_years)` 對負底數分數次方 → NaN 或 complex。guard 只檢查 `> -1`。

### H-07: walk_forward OOS 串接可能有重疊日期

**位置**：`src/backtest/walk_forward.py:197`

如果 fold 有重疊期間，`pd.concat(all_oos_daily)` 不去重 → Sharpe 分母被稀釋。

### H-08: strategy_builder _all_bars 只在 _needs_data=True 定義

**位置**：`src/alpha/auto/strategy_builder.py:167`

`_needs_data=False` 時三元運算子不 evaluate `_all_bars.get()`（Python 短路），但如果代碼重構可能觸發 NameError。

---

## MEDIUM（11 個）

| # | 位置 | 問題 |
|---|------|------|
| M-01 | sinopac:453-457 | ✅ 已修：callback 寫 filled_qty/avg_price 移入 lock 內 |
| M-02 | auto_alpha:716 | ✅ 已修：strip leading digits + `.isidentifier()` check |
| M-03 | auto_alpha:703-713 | ✅ 已修：FORBIDDEN_PATTERNS 擴展至 14 項（+importlib/open/sys/socket/pathlib/globals） |
| M-04 | auto_alpha:806-813 | ✅ 已修：部署條件改為硬/軟門檻 |
| M-05 | service.py:151 | ✅ 已修：屬性名已修正 |
| M-06 | risk.py:81 | ✅ 已修：手動 kill switch 設 `kill_switch_fired=True` |
| M-07 | revenue_momentum:36 | 全域 `_revenue_cache` 不過期 → 長期運行用過時營收 |
| M-08 | engine.py:158 | `available_cash` 可能被第一個 BUY 超支（Decimal 精度） |
| M-09 | engine.py:106 | `all_symbols` 是 set → 遍歷順序不確定 → 資金有限時非最優分配 |
| M-10 | vectorized.py:189 | NAV 硬編碼 10M → 自訂 initial_cash 時 lot rounding 不準 |
| M-11 | validator.py:843 | ✅ 已修：`ffill(limit=5)` → `fillna(0.0)` |

---

## LOW（11 個）

| # | 位置 | 問題 |
|---|------|------|
| L-01 | overfitting.py:131 | logit clamp 0.01/0.99 在 N=2 時系統性偏差 |
| L-02 | analytics.py:323 | drawdown div-by-zero 風險（NAV=0 時） |
| L-03 | analytics.py:314 | Sortino numerator `mean*252` vs Sharpe `mean/std*√252` 語義差異 |
| L-04 | walk_forward.py:357 | `np.std()` 用 ddof=0，其餘用 ddof=1 |
| L-05 | overfitting.py:155 | `_sharpe` 對 < 2 筆資料回傳 0.0 → 排名中位 |
| L-06 | optimizer.py:72 | long-short 模式 `raw_w` 分子用原值、分母用絕對值 → 多空不平衡 |
| L-07 | strategy_builder.py:147 | `direction=-1` 只影響選股不影響做空 → 所有權重仍為正 |
| L-08 | scheduler/jobs.py:751 | pipeline record 被寫兩次（inner + outer） |
| L-09 | scheduler/jobs.py:569 | `_today_run_id()` 跨分鐘可能不一致 |
| L-10 | app.py:356 | `_dd_pct` 讀 portfolio 在 lock 外（notification 用途） |
| L-11 | realtime.py:86 | `_nav_high` 讀在 lock 外 → 技術上 data race |

---

## 修復狀態總覽（2026-03-29 最終更新）

### CRITICAL（9 個）：✅ 全部已修
C-01~C-03（sinopac 零股）、C-04（permutation fail-open）、C-05（regime compound）、C-06（revenue fallback）、C-07（risk_parity vols）、C-08~C-09（execute_rebalance 平倉）

### HIGH（8 個）：✅ 全部已修
H-01（_trades 寫入）、H-02（kill switch double-check）、H-03（liquidation lock）、H-04（Trade mutate）、H-05（PBO 不等分）、H-06~H-08（analytics/walk_forward/strategy_builder）

### MEDIUM（11 個）：8 已修 / 3 未修
✅ M-01, M-02, M-03, M-04, M-05, M-06, M-11
❌ M-07（revenue_cache 不過期 — Phase AF 處理）、M-08（cash 超支）、M-09（set 遍歷順序）、M-10（NAV 硬編碼）

### LOW（11 個）：未追蹤
非阻塞性問題，視情況處理。
