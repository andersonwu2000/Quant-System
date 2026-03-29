# Live Trading 基礎設施 Code Review

**日期**：2026-03-29
**範圍**：sinopac.py、base.py（PaperBroker）、service.py、jobs.py、state.py、reconcile.py、config.py、scheduler_routes.py、app.py
**方法**：逐檔檢查「simulation=False 時會壞什麼」
**結論**：**系統不能直接用於實盤交易。** 9 個 CRITICAL bug，其中 1 個連 paper trading 也會 crash。

---

## 統計

| 嚴重度 | 數量 | 已驗證 |
|:------:|:----:|:------:|
| CRITICAL | 9 | 3 個代碼驗證確認 |
| HIGH | 6 | — |
| MEDIUM | 6 | — |
| LOW | 1 | — |
| **合計** | **22** | |

---

## CRITICAL（9 個）

### LT-1：PaperBroker.submit_order() 每次 crash ⚠️ 已驗證

**位置**：`base.py:104-110`

```python
is_odd = order.quantity < 1000 and (
    sym.endswith(".TW") or sym.endswith(".TWO")  # sym 未定義
)
# ... line 110:
sym = order.instrument.symbol  # 太晚了
```

`sym` 在 line 104 使用但 line 110 才賦值 → `UnboundLocalError`。

**影響**：PaperBroker 完全無法下單。paper trading 和回測中使用 PaperBroker 的路徑全部壞掉。

**已驗證**：`python -c "PaperBroker().submit_order(order)"` → `UnboundLocalError`。

**修復**：把 `sym = order.instrument.symbol` 移到 line 104 之前。

### LT-2：CA 憑證缺失時 connect() 仍回傳 True ⚠️ 已驗證

**位置**：`sinopac.py:131-143`

LIVE 模式下 CA 未設定 → log critical 但繼續 → `return True` → 系統認為連線成功 → 所有訂單被交易所拒絕 → 無通知。

**修復**：CA 缺失或 activate_ca 失敗時 → `self._connected = False; return False`。

### LT-3：non_blocking 模式下訂單 ID 可能無效

**位置**：`sinopac.py:226-233`

`timeout=0` 時 Shioaji 立即回傳，trade 物件可能不完整。fallback `str(id(trade))` 不是真正的 broker ID → callback 找不到對應訂單 → 成交丟失。

**修復**：LIVE 模式強制 blocking（`timeout=None`）。

### LT-4：_find_broker_id_for_deal 可能匹配到錯誤訂單

**位置**：`sinopac.py:509-518`

用 symbol + status 做 first-match。同一支股票有多筆 pending 訂單時，fill 會歸到錯誤的訂單 → 成本基礎錯誤 → NAV 不準。

**修復**：如果同一 symbol 有多筆 pending → 拒絕匹配並告警。

### LT-5：config.py 沒有驗證 LIVE 模式的必要設定 ⚠️ 已驗證

**位置**：`config.py:69-72`

`mode="live"` 時 sinopac_api_key、ca_path 可以是空字串 → app 啟動但 broker 初始化靜默失敗。

**修復**：加 `@model_validator` — live 模式必須有 API key + CA path。

### LT-6：ExecutionService 初始化失敗但 broker 仍被設定

**位置**：`service.py:~140`

如果 `connect()` 沒呼叫（API key 空）或失敗，`self._broker = broker` 仍執行 → pipeline 拿到未連線的 broker → 第一筆訂單才報錯。

**修復**：`initialize()` 失敗 + mode=live → 拒絕啟動。

### LT-7：async fill callback 可能在 set_portfolio() 之前被呼叫

**位置**：`service.py:363-398`

`_on_broker_fill` 用 `getattr(self, '_portfolio', None)` — 如果 reconnect thread 在 `set_portfolio()` 之前收到 fill → callback 靜默 return → **成交丟失，portfolio 不更新**。

**修復**：`set_portfolio()` 必須在 broker connect 之前呼叫。或在 callback 中 raise 而非靜默 return。

### LT-8：scheduler_routes 沒有 LIVE 模式保護

**位置**：`scheduler_routes.py:109`

任何有 `trader` role 的 API key 都能觸發 pipeline。LIVE 模式下等於任何知道 API key 的人能執行真實交易。

**修復**：LIVE 模式的 pipeline trigger 需要額外確認機制。

### LT-9：pipeline 執行中 broker 斷線無檢測

**位置**：`jobs.py` execute_pipeline

pipeline 提交 10 筆訂單，中間 broker 斷線 → 前 5 筆成交、後 5 筆失敗 → 系統認為 10 筆都提交了 → NAV 和實際持倉不一致。

**修復**：每筆訂單提交後檢查 broker.is_connected()。

---

## HIGH（6 個）

| # | 位置 | 問題 |
|---|------|------|
| LT-10 | sinopac.py:202 | 零股交易時段外的委託靜默跳過，不設 order status |
| LT-11 | sinopac.py:235,267 | submitted_shares 計算在部分失敗時 fallback 到 order.quantity |
| LT-12 | base.py:55 | PaperBroker 缺 update_order/query_trading_limits 等方法 |
| LT-13 | jobs.py:474 | 傳 ExecutionService 給期望 BrokerAdapter 的函式 |
| LT-14 | sinopac.py:463 | fill callback 的 status 更新不在 lock 內（和 cancel 競爭） |
| LT-15 | reconcile.py:185 | auto_correct 不驗證 broker_cost 合理性 |

---

## MEDIUM（6 個）

| # | 位置 | 問題 |
|---|------|------|
| LT-16 | sinopac.py:528 | reconnect daemon thread 不 join on shutdown → 半提交訂單 |
| LT-17 | sinopac.py:254 | simulation rejected 但回傳 non-empty broker_id |
| LT-18 | state.py:70 | portfolio 持久化用 replace 不夠 atomic |
| LT-19 | state.py:117 | nav_sod="0" 被當作「未設定」 |
| LT-20 | reconcile.py:102 | tolerance 預設 0 → 零股 1 股偏差也報 |
| LT-21 | sinopac.py:533 | reconnect backoff 在特定條件下不 reset |

---

## 修復優先級

### 立即（阻塞所有交易）

| # | 修復 | 工作量 |
|---|------|:------:|
| **LT-1** | PaperBroker `sym` 移到 `is_odd` 之前 | **1 行** |
| **LT-2** | CA 缺失 → return False | 3 行 |
| **LT-5** | config.py 加 live mode validator | 10 行 |

### paper trading 前（阻塞 paper trading）

LT-1 修完 PaperBroker 才能跑。**這個比所有其他項目都急。**

### 微額實盤前（阻塞真實交易）

| # | 修復 | 工作量 |
|---|------|:------:|
| LT-3 | LIVE 強制 blocking | 3 行 |
| LT-4 | 多筆 pending 同 symbol → 拒絕匹配 | 10 行 |
| LT-6 | init 失敗 + live → 拒絕啟動 | 5 行 |
| LT-7 | set_portfolio 在 connect 前 | 5 行 |
| LT-8 | LIVE pipeline 加確認 | 15 行 |
| LT-9 | 每筆訂單後 check connected | 5 行 |

### 逐步改善（不阻塞但改善穩健性）

LT-10 ~ LT-21 按 HIGH → MEDIUM 順序處理。

---

## 和 NEXT_ACTIONS 的關係

**LT-1 是最緊急的** — PaperBroker crash 意味著 Phase 1（開盤第一天啟動 paper trading）無法執行。必須在 Phase 0 修。

**LT-2 ~ LT-9 阻塞微額實盤** — 必須在 Phase 2.4（CA 憑證取得後）之前修完。

建議把 LT-1 加入 NEXT_ACTIONS Phase 0，LT-2~LT-9 加入 Phase 2。
