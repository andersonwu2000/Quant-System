# 全系統最終代碼審查 — 2026 Q1

> 日期：2026-03-27 23:00
> 範圍：20 個核心模組（88+ bug 修復後的最終審查）
> 目的：Production deployment 前的最終確認

---

## 審查範圍

| # | Module | File |
|---|--------|------|
| 1 | Data Models | src/core/models.py |
| 2 | Config | src/core/config.py |
| 3 | Backtest Engine | src/backtest/engine.py |
| 4 | Analytics | src/backtest/analytics.py |
| 5 | Validator | src/backtest/validator.py |
| 6 | Risk Engine | src/risk/engine.py |
| 7 | Risk Rules | src/risk/rules.py |
| 8 | Realtime Risk | src/risk/realtime.py |
| 9 | Execution Service | src/execution/service.py |
| 10 | PaperBroker | src/execution/broker/base.py |
| 11 | SimBroker | src/execution/broker/simulated.py |
| 12 | SinopacBroker | src/execution/broker/sinopac.py |
| 13 | OMS | src/execution/oms.py |
| 14 | Scheduler | src/scheduler/__init__.py |
| 15 | Pipeline Jobs | src/scheduler/jobs.py |
| 16 | Trading Pipeline | src/core/trading_pipeline.py |
| 17 | Strategy Engine | src/strategy/engine.py |
| 18 | Factor Evaluator | src/alpha/auto/factor_evaluator.py |
| 19 | Autoresearch | scripts/autoresearch/evaluate.py |
| 20 | App Lifespan | src/api/app.py |

---

## HIGH Severity (5)

### H1: Pipeline runs 紀錄雙重寫入

**File:** `src/scheduler/jobs.py:517,564`

`execute_pipeline`（外層）在 L517 寫 "started"，`_execute_pipeline_inner`（內層）在 L564 又寫一次。如果分鐘數跨越，`_today_run_id()` 不同，idempotency check 可能用錯 run_id。

**Fix:** 從外層傳 `run_id` 給內層，或移除內層的寫入。

### H2: execute_from_weights 缺 current_bars 驗證

**File:** `src/core/trading_pipeline.py:136`

如果 `broker` 是 `SimBroker` 且 `current_bars=None`，SimBroker 會 crash。Pipeline 呼叫時不傳 `current_bars`（paper/live 模式不需要），但函式簽名不阻止錯誤組合。

**Fix:** 加 `if isinstance(broker, SimBroker) and current_bars is None: raise ValueError`。

### H3: apply_trades 在回測時 import API state

**File:** `src/execution/oms.py:116`

`apply_trades` 每次呼叫都 `from src.core.config import get_config`，如果 mode 是 paper/live 就 `from src.api.state import save_portfolio`。回測模式不需要 API state，但 import 仍會執行。如果 API 依賴缺失，回測也會 crash。

**Fix:** 用 try/except 包裝，或只在非 backtest 模式才 import。

### H4: kill_switch 在 lock 外讀 portfolio

**File:** `src/risk/realtime.py:113`

`on_price_update` 在 L82 釋放 `portfolio.lock` 後，L113 呼叫 `risk_engine.kill_switch(self.portfolio)`。kill_switch 重新讀 `portfolio.daily_drawdown`，此時另一個 tick 可能已改了 price。

**Fix:** 在 lock 內計算 drawdown，傳給 kill_switch 判斷（而非讓它重讀）。

### H5: 風控 projected portfolio 對 market orders 無效

**File:** `src/risk/engine.py:106`

`check_orders` 用 `order.price or Decimal("0")`。Market orders 的 price 可能是 None → notional=0 → projected portfolio 不變 → 後續訂單的權重檢查基於錯誤的 projected state。

**Fix:** Fallback 到 MarketState 的價格，而非 Decimal("0")。

---

## MEDIUM Severity (9)

### M1: DSR 預設 n_trials=1 → 永遠 auto-pass

**File:** `src/backtest/validator.py:307`

`ValidationConfig.n_trials` 預設 1，`n_trials <= 1` 時 DSR 自動通過。除非 caller 明確設 n_trials，這個檢查形同虛設。

### M2: SinopacBroker deal callback 只比對 symbol

**File:** `src/execution/broker/sinopac.py:488`

多筆同 symbol 訂單時，成交回報可能歸到錯誤的訂單。

### M3: monthly_revenue_update 不檢查腳本是否存在

**File:** `src/scheduler/jobs.py:263`

如果 `scripts.download_finmind_data` 被刪或改名，subprocess 失敗後靜默重試再放棄。

### M4: app.py 存取 broker._config（私有屬性）

**File:** `src/api/app.py:161`

應用 `broker.simulation` 公開屬性代替 `broker._config.simulation`。

### M5: weight normalization 靜默改變策略行為

**File:** `src/strategy/engine.py:92-98`

total_weight > 1.5 時靜默正規化。130/30 策略會被改變。

### M6: Benchmark 年化和策略年化用不同公式

**File:** `src/backtest/validator.py:628`

Benchmark 用 `len(bars) / 252`，策略用 `len(nav) - 1 / 252`。off-by-one 不一致。

### M7: Sortino ddof=0 vs Sharpe ddof=1

**File:** `src/backtest/analytics.py:316 vs 308`

設計選擇但未文件化。

### M8: PaperBroker 對 price=None 的訂單直接 REJECTED

**File:** `src/execution/broker/base.py:76-78`

Market order 在 pipeline 裡有 price（from `get_latest_price`），但如果因某種原因 price 是 None，不會 fallback 到其他來源。

### M9: Odd lot 偵測對非台股不正確

**File:** `src/execution/broker/simulated.py:170`

`lot_size_check = getattr(order.instrument, "lot_size", 1000) or 1000`。非台股的 `lot_size=1`，`1 or 1000 = 1`（不是 1000）。但如果 `lot_size=0`，`0 or 1000 = 1000`。邏輯混亂。

---

## LOW Severity (7)

### L1: pending_settlements 類型不明確（包含 commission 與否）
### L2: 極短回測 CAGR 可能極端
### L3: autoresearch evaluate.py 的全局 cache 非 thread-safe（單線程，無害）
### L4: asyncio.Lock TOCTOU（單線程，無害）
### L5: 預設 admin 密碼和 JWT secret（dev-only guard 已有）
### L6: apply_trades kill switch 路徑未 capture 回傳值
### L7: factor.py baseline 有 divide by zero warning

---

## 總結

| Severity | Count | Production Risk |
|:--------:|:-----:|:---------------:|
| HIGH | 5 | 需要修復 |
| MEDIUM | 9 | 應修復 |
| LOW | 7 | 可接受 |
| **Total** | **21** | |

### 與今日第一次審查的比較

| 項目 | 第一次（今日早上） | 最終（現在） |
|------|:-----------------:|:------------:|
| HIGH | 很多（未計數） | **5** |
| 總 bug | **88+** | **21 殘留** |
| 測試通過 | 1,385 | **1,725** |

### Production 部署建議

1. **必須修**：H1（雙重紀錄）、H3（backtest import）、H5（market order projected）
2. **應該修**：H2（validation）、H4（lock scope）、M4（encapsulation）、M6（benchmark）
3. **可延後**：其餘 MEDIUM + LOW

### 最高風險場景

1. **Pipeline 在月初正常觸發但寫了兩個 pipeline_runs 紀錄** → 第二天 idempotency 可能用錯紀錄
2. **Market orders 在風控 projected check 中被忽略** → 同時送出多筆大額 market order 可能超過風控限制
3. **Backtest 在沒有 API 環境的機器上 crash** → CI/CD 或獨立回測腳本可能受影響
