# Paper Trading 基礎設施 Code Review

**日期**：2026-03-29
**範圍**：PaperBroker、SimBroker、ExecutionService、trading_pipeline、jobs.py（paper mode）、paper_deployer、deployed_executor、state.py
**方法**：追蹤「明天開始 paper trading，什麼會壞」的完整路徑
**注意**：初始報告有 3 個 CRITICAL 誤判已排除（ExecutionService 有 execute()、reconciliation 有排程、nav_sod 重設是刻意的）

---

## 統計

| 嚴重度 | 數量 |
|:------:|:----:|
| CRITICAL | 1 |
| HIGH | 4 |
| MEDIUM | 5 |
| LOW | 2 |
| **合計** | **12** |

---

## CRITICAL（1 個）

### PT-1：PaperBroker 內部持倉用 float，和 Portfolio 的 Decimal 精度不一致

**位置**：`base.py:112-118`

```python
self._positions[sym]["qty"] = float(Decimal(...) + order.quantity)
```

每次交易 Decimal → float → Decimal 轉換損失精度。10-20 筆交易後：
- PaperBroker._positions 的 qty 和 Portfolio.positions 的 qty 不同
- reconciliation 偵測到虛假偏差
- 累積到一定程度可能觸發錯誤的 auto-correct

**修復**：PaperBroker 內部直接存 Decimal，只在 JSON 序列化時轉 float。

---

## HIGH（4 個）

### PT-2：PaperBroker vs SimBroker 執行行為不一致

**位置**：`base.py` vs `simulated.py`

| 功能 | SimBroker（回測） | PaperBroker（paper trading） |
|------|-----------------|---------------------------|
| 漲跌停檢查 | ✅ 有 | ❌ 沒有 |
| 成交量上限 | ✅ 有 | ❌ 沒有 |
| 零股額外滑價 | ✅ 有 | ❌ 沒有 |
| 市場衝擊模型 | ✅ sqrt/linear | ❌ 固定 bps |

回測用 SimBroker 會在漲停時拒絕委託，但 paper trading 用 PaperBroker 會直接成交。**Paper trading 的績效會比回測更好**（因為少了限制），導致比較結果不可靠。

**修復**：PaperBroker 應和 SimBroker 共用核心執行邏輯，或者 paper mode 改用 SimBroker。

### PT-3：empty weights 不觸發平倉

**位置**：`jobs.py:459-466`

策略回傳空 weights → pipeline return early → 現有持倉不賣。如果策略因為 regime 或數據問題回傳空值，持倉會一直留著。

**修復**：空 weights 時仍走 `execute_from_weights(target_weights={}, ...)` 來賣出所有持倉。

### PT-4：deployed_executor NAV 計算不含交易成本

**位置**：`deployed_executor.py:159-169`

```python
portfolio_return += w * daily_ret  # no cost deduction
new_nav = strategy_info.current_nav * (1 + portfolio_return)
```

自動部署因子的 NAV 不扣手續費/稅/滑價。和主策略（有成本）的 NAV 不可比。

**修復**：加入簡化成本扣除（`net_return = gross_return - estimated_cost`）。

### PT-5：PaperDeployer 多實例 race condition

**位置**：`jobs.py:502` vs `deployed_executor.py:85`

兩處各自 `PaperDeployer()` new 一個實例 → 各自從磁碟載入狀態 → 可能互相覆蓋。

**修復**：PaperDeployer 改為 singleton 或通過 AppState 共享單一實例。

---

## MEDIUM（5 個）

| # | 位置 | 問題 |
|---|------|------|
| PT-6 | base.py:114 | BUY 更新 avg_cost 是 naive（不做加權平均） |
| PT-7 | state.py:116-119 | nav_sod 載入值是上次的，不是今天 SOD。restart 後 kill switch 基線不是今天的起點 |
| PT-8 | jobs.py:489 | 缺價格的標的靜默跳過，不告警有多少目標因缺價格而未執行 |
| PT-9 | deployed_executor.py:118-131 | 不檢查市場數據新鮮度 — 可能用一週前的收盤價算 NAV |
| PT-10 | paper_deployer.py:148-161 | kill switch 和 30 天 expire 同時觸發時，只有最後一個的 status 生效 |

---

## LOW（2 個）

| # | 位置 | 問題 |
|---|------|------|
| PT-11 | base.py:129 | query_positions 回傳 float dict，和 Portfolio 的 Decimal 不一致 |
| PT-12 | paper_deployer.py:137-146 | update_nav 不驗證 new_nav 合理性（可以是負數或零） |

---

## 修復優先級

### 阻塞 paper trading 啟動

| # | 問題 | 工作量 |
|---|------|:------:|
| PT-1 | PaperBroker float precision | ~15 行（改 _positions 存 Decimal） |
| PT-3 | empty weights 不平倉 | ~5 行 |

### 阻塞 paper vs 回測 NAV 比較可信度

| # | 問題 | 工作量 |
|---|------|:------:|
| PT-2 | PaperBroker 缺漲跌停/成交量 | ~20 行（或 paper mode 改用 SimBroker） |
| PT-4 | deployed_executor 不扣成本 | ~10 行 |

### 穩健性改善

| # | 問題 | 工作量 |
|---|------|:------:|
| PT-5 | PaperDeployer singleton | ~10 行 |
| PT-7 | nav_sod restart 行為 | ~5 行 |
| PT-8 | 缺價格告警 | ~3 行 |

---

## 已排除的誤判

初始審計報告了 3 個 CRITICAL 但經代碼驗證不成立：

| 誤判 | 實際 |
|------|------|
| ~~ExecutionService 沒有 execute()~~ | `service.py:186` 有 `def execute()` → 委託 `submit_orders()` |
| ~~reconciliation 從未被呼叫~~ | `scheduler/__init__.py:136` 有 daily_reconcile job |
| ~~nav_sod restart 後 kill switch 被繞過~~ | line 581 的 nav_sod 重設是再平衡後的刻意行為。restart 載入上次的值是合理的 fallback（但 PT-7 指出應在 SOD 時重設為當天開盤 NAV） |
