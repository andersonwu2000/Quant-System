# 全系統 Code Review — 2026-03-29

> 範圍：backtest/validator/overfitting/analytics/walk_forward/vectorized + execution/sinopac/oms/service + API/auto_alpha/risk/app + strategy/base/engine/optimizer + scheduler/jobs
> 方法：3 組平行審計

---

## CRITICAL（9 個）

### C-01: sinopac 零股分流 — 第二個 sub-order 從 _order_map 丟失

**位置**：`src/execution/broker/sinopac.py:239`

`_shares_to_lots` 回傳 list（整股+零股），`submit_order` loop 收集所有 `broker_ids` 但只把 `broker_ids[0]` 存進 `self._order_map`。第二個 sub-order（零股）的 fill callback 在 `_on_order_callback` 中找不到 order → 靜默丟棄成交。

### C-02: sinopac 模擬模式 overfill

**位置**：`src/execution/broker/sinopac.py:259-261`

模擬模式設 `order.filled_qty = order.quantity`（原始全部股數）。但如果零股部分被 `is_odd_lot_session()` skip，實際只送出整股部分，order 仍標記為全部 FILLED。

### C-03: sinopac 整股張數 vs 零股股數單位不一致

**位置**：`src/execution/broker/sinopac.py`

`_shares_to_lots` 回傳 `(lots, False)` 其中 lots = 張數（非股數）。Shioaji API 整股用張數、零股用股數。但 `_on_order_callback` 的 `filled_qty` 是從交易所回報的，整股回報張數 → 需乘 1000 轉股數才能和 `order.quantity`（股數）比較。目前沒有這個轉換。

### C-04: Permutation test fail-open ✅ 已修

**位置**：`src/backtest/validator.py:674`

`compute_fn` 不可用時回傳 `p=0.0`（通過門檻 < 0.10）。對於非 autoresearch 策略（沒有 `compute_fn`），permutation test 自動通過 = 形同虛設。

**修正**：改為回傳 `1.0`（fail-closed）。

### C-05: 危機 regime 用算術 sum 而非幾何 compound ✅ 已修

**位置**：`src/backtest/validator.py:986`

**修正**：`sum()` → `(1 + rets).prod() - 1`（幾何 compound）。

### C-06: Context.get_revenue 無 bare symbol fallback

**位置**：`src/strategy/base.py:121`

```python
rev_path = fund_dir / f"{symbol}_revenue.parquet"
```

如果 `symbol="1101"`（無 `.TW`），找不到 `1101_revenue.parquet`（磁碟上是 `1101.TW_revenue.parquet`）。靜默回傳空 DataFrame。目前所有路徑恰好都用 `.TW` 格式所以沒觸發，但無防禦性 fallback。

### C-07: risk_parity 傳空 volatilities — 永遠回傳空

**位置**：`strategies/revenue_momentum.py:274`

```python
weights = risk_parity(signals, {}, constraints)
```

空 dict → 所有標的被排除 → 回傳 `{}`。`weight_method="risk_parity"` 路徑完全壞掉。

### C-08: execute_rebalance 只取 target 價格 — 持倉無法平倉

**位置**：`src/scheduler/jobs.py:195-197`

```python
prices = {s: feed.get_latest_price(s) for s in target_weights}
```

不包含持倉中但不在 target 的標的 → `weights_to_orders` 找不到價格 → 無法產生 SELL 訂單 → 持倉永遠不被賣出。

（注意：`execute_pipeline` 正確處理了此問題，但 `execute_rebalance` 和 `monthly_revenue_rebalance` 都有此 bug。）

### C-09: monthly_revenue_rebalance 同上

**位置**：`src/scheduler/jobs.py:357-366`

同 C-08。

---

## HIGH（8 個）

### H-01: sinopac _trades dict 從未寫入

**位置**：`src/execution/broker/sinopac.py`

`submit_order` 寫 `_order_map` 但不寫 `_trades`。`cancel_order` 和 `update_order` 查 `_trades.get(order_id)` → 永遠回傳 None → 撤單/改單永遠失敗。

### H-02: Kill switch path A 不 double-check kill_switch_fired

**位置**：`src/api/app.py:318-322`

Path A 在 lock 外設 `kill_switch_fired = True`，lock 內不再 re-check。Path B 有 double-check（lock 外 + lock 內）。如果 path A 和 path B 同時讀到 `False`，path B 會在 lock 內 re-check 跳過，但 path A 不會 → 可能 double liquidation。

### H-03: generate_liquidation_orders 在 lock 外讀 portfolio

**位置**：`src/risk/realtime.py:120`

從 Shioaji SDK 線程呼叫，`portfolio.lock` 已釋放。生成清倉訂單和 async 執行之間，持倉可能被 `apply_trades` 改變。

### H-04: apply_trades 直接改 trade.quantity（sell cap）

**位置**：`src/execution/oms.py:79`

```python
trade.quantity = pos_qty  # mutate original Trade object
```

汙染 Trade 歷史記錄。如果 Trade 被其他地方引用（日誌、對帳），顯示的是 capped 數量而非原始請求。

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
| M-01 | sinopac:453-457 | `_on_order_callback` 寫 filled_qty/avg_price 在 lock 外 → 並發 fill race |
| M-02 | auto_alpha:716 | name sanitization 允許數字開頭（`123factor` → 非法 Python identifier） |
| M-03 | auto_alpha:703-713 | 安全檢查可被 `importlib.import_module('os')` 繞過 |
| M-04 | auto_alpha:806-813 | ✅ 已修：部署條件改為硬/軟門檻 |
| M-05 | service.py:151 | `sinopac_simulation` 屬性不存在 → AttributeError（paper/live mode） |
| M-06 | risk.py:81 | 手動 kill switch endpoint 不設 `kill_switch_fired=True` → 5 秒後 auto re-trigger |
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

## 優先修復

### 第一批：實盤交易路徑（C-01~C-03, H-01）

sinopac 零股分流引入的 3 個 CRITICAL + `_trades` 從未寫入。這是實盤交易路徑，成交丟失和 overfill 會直接造成資金損失。

### 第二批：策略執行路徑（C-08~C-09, C-07）

`execute_rebalance` 無法平倉 + `risk_parity` 永遠空。影響 paper trading 和月度再平衡。

### 第三批：Validator 正確性（C-04, C-05, H-05）

permutation fail-open + regime sum vs compound + PBO 不等分。影響因子驗證的可信度。

### 第四批：安全 + 並發（H-02, H-03, M-06）

kill switch double liquidation + stale portfolio + 手動 kill switch 不設 flag。影響風控。
