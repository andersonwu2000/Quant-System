# Phase AH：Web 前端全面更新

> 現狀：5 頁能跑但功能停在 Phase N2（2026-03-26）。缺 paper trading 監控、實盤監控、autoresearch 狀態、管線健康度。
> 目標：讓前端成為日常營運的唯一介面 — 不需要開終端機就能監控一切。
> 原則：不重寫，在現有 React 18 + Vite + Tailwind + React Query 架構上擴展。
> 依據：PAPER_TRADING_BEHAVIOR_AUDIT、LIVE_TRADING_INFRA_REVIEW、NEXT_ACTIONS Phase 3-4

---

## 1. 現狀審計

### 已有的 5 頁

| 頁面 | 路由 | 功能 | 狀態 |
|------|------|------|:----:|
| Overview | `/` | Portfolio NAV、持倉、P&L、regime | ✅ 完整 |
| Strategy | `/strategy` | 選股結果、再平衡觸發、drift 監控 | ✅ 完整（缺 regime chart） |
| Backtest | `/backtest` | 提交回測、結果展示 | ✅ 完整（硬編碼 universe） |
| Risk | `/risk` | Drawdown、kill switch、alerts | ✅ 完整 |
| Settings | `/settings` | API key 設定 | ✅ 最小可用 |

### 缺的

| 功能 | 後端 API | 共享型別 | 前端 UI |
|------|:--------:|:--------:|:-------:|
| Paper trading 監控 | ✅ | ✅ | ❌ |
| 實盤交易監控 | ✅ | ✅ | ❌ |
| 訂單管理 | ✅ | ✅ | ❌ |
| Autoresearch 狀態 | ✅ | ✅ | ❌ |
| Alpha 研究（IC/ICIR 視覺化） | ✅ | ✅ | ❌ |
| Reconciliation | ✅ | ✅ | ❌ |
| WebSocket 即時更新 | ✅ | ✅ | ❌（infra 有，未接） |
| Recharts 圖表 | 已裝 | — | ❌（未使用） |

### 技術債

| 項目 | 說明 |
|------|------|
| 硬編碼 universe | BacktestPage 有 20 支股票寫死在代碼裡 |
| 硬編碼策略名 | 4 個策略名寫死 |
| Regime chart placeholder | StrategyPage 寫 "TBD" 但從未實作 |
| Recharts 已裝未用 | 裝了 recharts 但沒有任何圖表 |
| WebSocket 未接 | shared 有完整 WS manager，web 沒用 |
| 無單元測試 | test infra 有（Vitest + Testing Library）但 0 個測試 |

---

## 2. 設計

### 新增 3 頁 + 改進 2 頁

```
現有                    新增/改進
├── Overview       ← 改進：加 paper vs 實盤 NAV 雙線圖
├── Strategy       ← 改進：regime chart 實作
├── Backtest       （不動）
├── Risk           （不動）
├── Settings       （不動）
├── Trading   [NEW] ← 實盤 + paper trading 統一監控
├── Research  [NEW] ← autoresearch 狀態 + 因子研究
└── Orders    [NEW] ← 訂單管理 + reconciliation
```

### 2.1 Trading 頁面（最重要）

**路由**：`/trading`

**用途**：paper trading + 微額實盤的雙軌監控。日常營運時最常看的頁面。

**設計依據**：NEXT_ACTIONS §1.2（雙軌 NAV 比較 = 執行落差的真實度量）

**區塊**：

```
┌─────────────────────────────────────────────┐
│ Trading Status                              │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│ │ Paper    │ │ Live     │ │ NAV Gap  │      │
│ │ NAV: 10M │ │ NAV: 9.8K│ │ -2.1%    │      │
│ │ ✅ Active │ │ ✅ Active │ │ ⚠️ Watch │      │
│ └──────────┘ └──────────┘ └──────────┘      │
├─────────────────────────────────────────────┤
│ NAV Comparison Chart (Recharts LineChart)   │
│ [Paper NAV ── vs Live NAV ──── vs 0050 ──] │
│ 30d / 90d / All toggle                      │
├─────────────────────────────────────────────┤
│ Positions Comparison                        │
│ Symbol | Paper Wt | Live Wt | Drift | Alert │
│ 2330   | 8.2%     | 7.9%    | 0.3%  | ✅    │
│ 2317   | 6.1%     | 0.0%    | 6.1%  | ❌    │
├─────────────────────────────────────────────┤
│ Execution Metrics (微額實盤 only)           │
│ Slippage | Fill Rate | API Uptime | Cost    │
│ 3.2 bps  | 97%       | 99.8%      | 0.18%  │
│ (signal_price vs fill_price 追蹤 — A-2)    │
├─────────────────────────────────────────────┤
│ Pipeline Health (多管線 — NEXT_ACTIONS 4D) │
│ Pipeline | NAV  | DD   | Status | Overlap  │
│ main     | 10K  | 1.2% | active | —        │
│ auto_1   | 500  | 0.3% | active | 20% main │
│ auto_2   | 500  | 2.8% | ⚠️warn | 60% auto1│
├─────────────────────────────────────────────┤
│ Recent Trades (last 20)                     │
│ Time | Symbol | Side | Qty | Price | Status │
└─────────────────────────────────────────────┘
```

**API 來源**：
- `GET /api/v1/execution/paper-trading/status` — paper trading 狀態
- `GET /api/v1/portfolio` — 實盤持倉
- `GET /api/v1/execution/queued-orders` — 待成交訂單
- `GET /api/v1/trading/comparison` — Paper vs Live NAV 時序（新增）
- `GET /api/v1/trading/pipeline-health` — 多管線健康度（新增）
- WebSocket `orders` channel — 即時成交更新

**多管線監控**（NEXT_ACTIONS 4D.4）：
- 每條 auto 管線顯示 NAV、DD、status（active/killed/expired）
- 管線間持倉重疊率（Jaccard overlap）
- 重疊 > 50% 顯示紅色警告
- 管線間 NAV correlation > 0.8 顯示「分散不足」

### 2.2 Research 頁面

**路由**：`/research`

**用途**：autoresearch 狀態監控 + 因子研究結果視覺化。

**區塊**：

```
┌─────────────────────────────────────────────┐
│ Autoresearch Status                         │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│ │ Total    │ │ L5 Pass  │ │ Budget   │      │
│ │ 75 exps  │ │ 3 (4%)   │ │ 17/50 L5 │      │
│ └──────────┘ └──────────┘ └──────────┘      │
├─────────────────────────────────────────────┤
│ Factor Library Health                       │
│ avg|ρ|: 0.18 | eff_n: 12.3 | diversity: 77%│
├─────────────────────────────────────────────┤
│ Results Timeline (Recharts scatter)         │
│ x=experiment#, y=composite_score            │
│ color=level (L1 grey, L3 yellow, L5 green)  │
├─────────────────────────────────────────────┤
│ Top Factors                                 │
│ Name | ICIR | Level | Direction | Saturation│
│ risk_adj_mom | strong | L5 | momentum | LOW │
├─────────────────────────────────────────────┤
│ Learnings Summary                           │
│ Forbidden: VWAP variants, delta reversal    │
│ Successful: revenue accel, institutional    │
└─────────────────────────────────────────────┘
```

**API 來源**：
- `GET /api/v1/auto-alpha/status` — autoresearch 狀態
- `GET http://evaluator:5000/learnings` — 經驗摘要（需 proxy 或後端轉發）
- 讀取 `results.tsv`（需要後端 API 包裝）

### 2.3 Orders 頁面

**路由**：`/orders`

**用途**：訂單生命週期 + reconciliation。

**區塊**：

```
┌─────────────────────────────────────────────┐
│ Open Orders                                 │
│ ID | Symbol | Side | Qty | Price | Status   │
├─────────────────────────────────────────────┤
│ Today's Trades                              │
│ Time | Symbol | Side | Qty | Fill Price     │
├─────────────────────────────────────────────┤
│ Reconciliation                              │
│ Last run: 13:35 | Deviations: 0             │
│ [Run Reconcile] [Auto-Correct]              │
├─────────────────────────────────────────────┤
│ Trade History (paginated)                   │
│ Date | Symbol | Side | Qty | Price | PnL    │
└─────────────────────────────────────────────┘
```

**API 來源**：
- `GET /api/v1/orders` — 訂單列表
- `POST /api/v1/execution/reconcile` — 觸發 reconciliation
- `GET /api/v1/execution/queued-orders` — 排隊中訂單

### 2.4 Overview 改進

- 加入 paper vs 實盤 NAV 雙線對比（用 Recharts LineChart）
- 加入累計報酬 vs 0050.TW benchmark 的對比圖

### 2.5 Strategy 改進

- Regime chart：0050.TW 收盤價 vs MA200，標記 bear/bull 區間
- 策略名和 universe 從後端 API 讀取，不再硬編碼

---

## 3. 技術改進

### 3.1 WebSocket 接入

shared 已有完整的 `WebSocketManager`（auto-reconnect、ping/pong、channel subscription）。接入到 Trading 和 Orders 頁面：

```typescript
// Trading page
const ws = useWebSocket("orders");
ws.onMessage((data) => {
  queryClient.invalidateQueries(["orders"]);
  showToast(`Order ${data.status}: ${data.symbol}`);
});
```

需要新增 `useWebSocket` hook（~20 行）。

### 3.2 Recharts 圖表啟用

已安裝但未使用。需要的圖表：

| 圖表 | 頁面 | 類型 |
|------|------|------|
| NAV 雙線對比 | Trading | LineChart |
| NAV vs benchmark | Overview | LineChart |
| Regime (0050 vs MA200) | Strategy | LineChart + ReferenceArea |
| 實驗結果散佈圖 | Research | ScatterChart |
| Drawdown 時序 | Risk | AreaChart |

### 3.3 硬編碼清理

| 項目 | 現在 | 改為 |
|------|------|------|
| BacktestPage universe | 20 支寫死 | `GET /api/v1/universe` |
| BacktestPage strategies | 4 個寫死 | `GET /api/v1/strategies` |
| StrategyPage regime chart | "TBD" | Recharts LineChart |

### 3.4 後端 API 新增（前端需要但後端沒有的）

| API | 用途 | 工作量 | 依賴 |
|-----|------|:------:|------|
| `GET /api/v1/universe` | 回傳可用 universe 列表 | ~10 行 | — |
| `GET /api/v1/strategies` | 回傳已註冊策略列表 | ~10 行 | — |
| `GET /api/v1/research/status` | 轉發 results.tsv + learnings 摘要 | ~30 行 | evaluator 或直接讀檔 |
| `GET /api/v1/trading/comparison` | Paper vs Live NAV 時序 | ~30 行 | paper_trading/ 日誌 |
| `GET /api/v1/trading/pipeline-health` | 多管線健康度 + 持倉重疊 | ~40 行 | PaperDeployer + overlap 計算 |
| `GET /api/v1/nav/history` | NAV 歷史（chart 用） | ~20 行 | portfolio_state.json |
| `GET /api/v1/trading/slippage` | signal_price vs fill_price 追蹤 | ~20 行 | 需在 broker callback 記錄 |

---

## 4. 實施順序

按 NEXT_ACTIONS 的時間線排：

### Step 1：Trading 頁面（Phase 1-2，開盤第一週）

Paper trading 啟動後最需要的就是監控介面。

| 任務 | 工作量 |
|------|:------:|
| TradingPage.tsx 基本框架 + 狀態卡片 | 2 小時 |
| 持倉比對表格（paper vs live columns） | 1 小時 |
| Pipeline Health 區塊（多管線監控 — NEXT_ACTIONS 4D.4） | 2 小時 |
| 後端 API：trading/comparison + pipeline-health | 2 小時 |
| WebSocket useWebSocket hook | 1 小時 |
| **小計** | **~8 小時** |

### Step 2：圖表 + Overview 改進（Phase 3，前 30 天）

有了 30 天數據後圖表才有意義。

| 任務 | 工作量 |
|------|:------:|
| NAV 雙線圖（Recharts） | 2 小時 |
| NAV vs benchmark 圖 | 1 小時 |
| Regime chart（0050 vs MA200） | 2 小時 |
| Drawdown 時序圖 | 1 小時 |
| 後端 API：nav/history | 1 小時 |
| **小計** | **~7 小時** |

### Step 3：Research 頁面（Phase 4，autoresearch 跑了之後）

因子累積到 20+ 個後才有東西看。

| 任務 | 工作量 |
|------|:------:|
| ResearchPage.tsx | 2 小時 |
| 實驗結果散佈圖 | 1 小時 |
| Learnings 摘要展示 | 1 小時 |
| 後端 API：research/status | 1 小時 |
| **小計** | **~5 小時** |

### Step 4：Orders 頁面 + 技術債清理

| 任務 | 工作量 |
|------|:------:|
| OrdersPage.tsx | 2 小時 |
| Reconciliation 觸發 UI | 1 小時 |
| 硬編碼清理（universe, strategies） | 1 小時 |
| 後端 API：universe, strategies | 1 小時 |
| **小計** | **~5 小時** |

---

## 5. 總工作量

| Step | 內容 | 工作量 | 時機 | 依賴 |
|------|------|:------:|------|------|
| 1 | Trading 頁面 + 多管線 | ~8 小時 | 開盤第一週 | paper trading 已啟動 |
| 2 | 圖表 + Overview | ~7 小時 | 第 2-4 週 | 有 2+ 週 NAV 數據 |
| 3 | Research 頁面 | ~5 小時 | 30 天後 | autoresearch 已跑 20+ 實驗 |
| 4 | Orders + 清理 | ~5 小時 | 隨時 | — |
| **總計** | | **~25 小時** | | |

---

## 6. 和其他計畫的交叉依賴

| Phase AH 項目 | 依賴 | 說明 |
|--------------|------|------|
| Trading 頁 Slippage Metrics | NEXT_ACTIONS 0.6（A-2 滑價追蹤） | 後端要先記錄 signal_price vs fill_price |
| Trading 頁 Pipeline Health | NEXT_ACTIONS 4D.1-4D.5（管線管理） | 後端要先有 overlap 計算和 correlation |
| Research 頁 Learnings | Phase AF（learnings.jsonl） | ✅ 已完成 |
| Research 頁 Factor Library Health | Phase AF（library_health_metrics） | ✅ 已完成 |
| Overview NAV chart | Phase AD1（數據自動更新） | 沒有每日數據就沒有每日 NAV |
| Strategy Regime chart | 0050.TW 進 feed | 目前 0050 不在 feed → chart 空的 |

---

## 7. 不做的事

| 項目 | 為什麼 |
|------|--------|
| 換框架（Next.js/Remix） | React 18 + Vite 完全夠用 |
| 加 state management（Redux/Zustand） | React Query 已處理所有 async state |
| SSR | 內部工具不需要 SEO |
| i18n | 單一使用者，中英混合即可 |
| Mobile app 同步 | Android app 獨立存在 |
| 完整的 design system | Tailwind + 現有 UI components 夠用 |
| 前端單元測試 | infra 有但 0 個測試。不寫 — 內部工具、單一使用者、手動驗證更快 |
