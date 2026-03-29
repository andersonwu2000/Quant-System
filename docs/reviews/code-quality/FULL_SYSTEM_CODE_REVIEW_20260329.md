# 全系統 Code Review（第二次）

**日期**：2026-03-29
**範圍**：engine.py、jobs.py、models.py、optimizer.py、yahoo.py、finmind.py、config.py、app.py、realtime.py、cross_section.py
**排除**：已在 CODE_REVIEW_20260329.md 覆蓋的模組（validator、analytics、oms、sinopac、evaluate.py、eval_server.py、strategy_builder、revenue_momentum）

---

## 統計

| 嚴重度 | 數量 | 驗證結果 |
|:------:|:----:|:-------:|
| CRITICAL | 1（CR-1 已驗證降級為 LOW） | CR-2 ✅ 準確 |
| HIGH | 6 | 全部 ✅ 準確 |
| MEDIUM | 8 | M-1 ❌ 不準確（其餘 ✅） |
| LOW | 5 | 全部 ✅（L-3 為設計選擇） |
| **合計** | **20（19 confirmed, 1 invalid）** | |

---

## CRITICAL（2 個）

### ~~CR-1：Yahoo/FinMind 價格未調整除權息~~ → 降級為 LOW

**已驗證（2026-03-29）**：Yahoo Finance `auto_adjust=True` **已包含除權息調整**。

驗證方式：2412.TW（中華電信）2023-07-18 除息 4.595 元
- Unadjusted：7/17 = 116.5、7/18 = 115.0（正常交易波動，未反映除息）
- Adjusted：7/17 = 107.92、7/18 = 106.53（歷史價格被向下調整 ~8.5 元，包含除息效果）

**結論**：Yahoo 數據源正確。FinMind 的價格是否已調整仍需確認（但系統主要用 Yahoo）。降級為 LOW — 只需更新 yahoo.py 的註釋說明 `auto_adjust=True` 包含股利調整。

### CR-2：realtime.py 清倉的 race condition

**位置**：`realtime.py:120-200`

RealtimeRiskMonitor 觸發 kill switch 後用 async 執行清倉。在觸發和清倉之間：
- 如果 app.py 的 kill switch monitor 同時觸發 → 兩路同時嘗試清倉
- `state.kill_switch_fired` flag 防止重複，但 flag 的設定和讀取不在同一個 lock 內

H-02 修復了 app.py 側的 double-check，但 realtime.py 側的 `_execute_liquidation` 仍在 lock 外讀 portfolio。

**建議**：清倉邏輯統一到一個入口點，用 `mutation_lock` 保護。

---

## HIGH（6 個）

### H-1：engine.py 除息注入順序造成 look-ahead bias

**位置**：`engine.py:301-303`

除息現金在 kill switch 檢查之後、策略 rebalance 之前注入。策略在 rebalance 時看到膨脹的現金（包含今天的除息）。

**影響**：策略可能因為看到多出的現金而買入更多。實際交易中除息到帳需要 T+2。

**建議**：除息注入移到 rebalance 之後（或 T+2 延遲注入）。

### H-2：optimizer.py signal_weight 沒有限制空頭總曝險

**位置**：`optimizer.py:48-78`

`long_only=False` 時，個股權重 clamp 到 `[-max_weight, +max_weight]`，但沒有限制空頭總曝險。20 支股票 × -5% = -100% 空頭。

**影響**：目前系統只用 long-only，所以不觸發。但 `long_only=False` 路徑存在且未被保護。

**建議**：加 `total_short <= max_total_weight` 約束。或在 long-only 模式下禁止負權重。

### H-3：realtime.py 每日 drawdown 基線在第一個 tick 前不準

**位置**：`realtime.py:82-89`

`_nav_high` 在日期切換時重置（line 70），但重置後的值是**前一天最後的 NAV**，不是今天 SOD 的 NAV。第一個 tick 進來前，drawdown 基線是錯的。

**建議**：日期切換時設 `_nav_high = portfolio.nav_sod`（如果可用）。

### H-4：yahoo.py 零價格沒有過濾

**位置**：`yahoo.py:160-166`

`df.dropna()` 移除 NaN 行，但 close=0 或 volume=0 的行通過。close=0 進入 pct_change → inf → 汙染整個因子計算（BUG_HISTORY 的 close=0 事故）。

**建議**：加 `df = df[(df[["open","high","low","close"]] > 0).all(axis=1)]`。

### H-5：config.py kill_switch_weekly_drawdown_pct 從未使用

**位置**：`config.py:46`

定義了 `kill_switch_weekly_drawdown_pct = 0.10` 但代碼中沒有任何地方讀取它。日回撤 3%（warning）和 5%（kill switch）是硬編碼在不同檔案。

**建議**：統一為 config 讀取，或刪除未使用的設定。

### H-6：jobs.py nav_sod 初始化和 execute 之間沒有持鎖

**位置**：`jobs.py:356-451`

`nav_sod` 在 `mutation_lock` 內初始化（line 356），但策略計算（line 364-440）在 lock 外。kill switch 可能在此期間改變 portfolio。

**影響**：paper/live 模式下，reconciliation 的 nav_sod 可能是過時的。回測不受影響（單線程）。

**建議**：paper/live 模式下擴大 lock 範圍。

---

## MEDIUM（8 個）

| # | 位置 | 問題 |
|---|------|------|
| ~~M-1~~ | ~~engine.py:283~~ | ~~Kill switch cooldown off-by-one~~ ❌ **驗證不成立** — 報告引用行號錯誤，實際邏輯在 `safety.py:157`，用 `<` 比較是正確的 |
| M-2 | yahoo.py:96-105 | Cache 覆蓋率檢查過寬（end 超出 cache 仍回傳舊數據） |
| M-3 | finmind.py:106-110 | 磁碟 cache 永不過期（和 Phase AD 重疊） |
| M-4 | app.py:40-67 | Kill switch 通知在 lock 外讀 portfolio（stale data） |
| M-5 | realtime.py:114 | 5% kill switch 門檻硬編碼，不讀 config |
| M-6 | cross_section.py:117-124 | Turnover 計算對 sparse quantile 膨脹 |
| M-7 | cross_section.py:135-147 | 年化假設 daily frequency，event-driven 不準 |
| M-8 | config.py:52-57 | Lot size mapping 在 execution layer 沒有 fallback 驗證 |

---

## LOW（4 個）

| # | 位置 | 問題 |
|---|------|------|
| L-1 | yahoo.py:74-76 | 時區正規化做了兩次 |
| L-2 | app.py:165-208 | Price polling fallback 邏輯過度複雜 |
| L-3 | cross_section.py:163-171 | Monotonicity n_quantiles < 3 回傳 0（應允許 n=2） |
| L-4 | config.py:58 | fractional_shares 定義了但從未使用 |

---

## 修復和改進建議

### 立即驗證（最高優先）

| # | 項目 | 做法 | 預期 |
|---|------|------|------|
| **V-1** | **驗證 Yahoo 是否已調整除權息** | 下載 2412.TW 2023 年價格，比對除息日前後 close 是否有跳空 | 如果沒調整 → CR-1 確認為系統最嚴重 bug |

```python
# 驗證腳本
import yfinance as yf
df = yf.download("2412.TW", start="2023-07-01", end="2023-08-01")
# 2412.TW 2023 除息日約 7/18，每股 4.5 元
# 如果 auto_adjust=True 已調整，7/17 和 7/18 的 close 不該有 ~4.5 元跳空
print(df[["Close"]].iloc[10:15])
```

### 開盤前可修（LOW effort, HIGH impact）

| # | 項目 | 改動 | 狀態 |
|---|------|------|:----:|
| 1 | yahoo.py 零價格過濾 | `df = df[(df[price_cols] > 0).all(axis=1)]` after dropna | ✅ 已修 |
| 2 | realtime.py drawdown 基線 | 日期切換時用 `nav_sod`（fallback to nav） | ✅ 已修 |
| 3 | config.py 刪除未使用的 weekly_drawdown | 移除 `kill_switch_weekly_drawdown_pct` | ✅ 已修 |

### 短期（開盤後）

| # | 項目 | 改動 | 工作量 |
|---|------|------|:------:|
| 4 | 除息注入順序 | engine.py 移到 rebalance 後 | ~10 行 |
| 5 | signal_weight 空頭約束 | optimizer.py 加 total_short check | ~5 行 |
| 6 | kill switch 門檻統一讀 config | realtime.py + engine.py | ~10 行 |
| 7 | 清倉邏輯統一入口 | realtime.py + app.py 合併 | ~30 行 |

### 中期

| # | 項目 | 說明 |
|---|------|------|
| 8 | yahoo.py cache 覆蓋率檢查 | 和 Phase AD 一起做 |
| 9 | jobs.py lock 範圍擴大 | paper/live 模式專用 |
| 10 | cross_section.py 年化參數化 | 加 frequency 參數 |

---

## 和第一次 Code Review 的對比

| 指標 | 第一次 (CODE_REVIEW_20260329) | 第二次（本報告） |
|------|:---:|:---:|
| CRITICAL | 9（全修） | 2 |
| HIGH | 8（全修） | 6 |
| MEDIUM | 11（8 修 / 3 未修） | 8 |
| 範圍 | validator, sinopac, oms, jobs, analytics | engine, data, config, api, risk, cross_section |

第一次的 CRITICAL/HIGH 全部已修。第二次發現的問題集中在數據層（除權息、零價格）和並發（清倉 race condition）。**CR-1（除權息）需要先驗證再判定嚴重度。**
