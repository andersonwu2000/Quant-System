# Web 前端架構 v2.0 — 推倒重寫

> 日期：2026-03-27
> 版本：v2.1（加入業界設計研究檢討）
> 前提：後端 Phase A~M 完成，進入 Paper Trading 階段
> 設計原則：以實際使用場景為核心，砍掉研究殘留
> 設計參考：TradingView、Bloomberg Terminal、IBKR Desktop、Tremor、shadcn/ui
> 視覺規範：[WEB_DESIGN_SYSTEM.md](WEB_DESIGN_SYSTEM.md)（配色、字型、間距、元件模板、動畫）

---

## 1. 反思：v1 的問題

### 為什麼要推倒

v1 是在研究階段逐步堆疊出來的 15 個 feature 目錄。問題：

| 問題 | 具體 |
|------|------|
| **功能膨脹** | 15 個 feature 但只有 3-4 個在 Paper Trading 階段有用 |
| **路由混亂** | `/trading`、`/orders`、`/portfolio`、`/paper-trading` 四個頁面做類似的事 |
| **研究 UI 殘留** | Alpha Research、Auto-Alpha、Allocation — 研究已完成，這些頁面不再需要 |
| **策略列表過時** | 展示 13 個策略但只有 `revenue_momentum_hedged` 會用於生產 |
| **Guide 頁面** | 7 章教學 — 系統穩定前沒人會看 |
| **Admin 頁面** | 單人系統不需要用戶管理 |

### 什麼真正重要

用戶（你）的日常操作只有：

```
每月一次：看策略選了什麼股 → 確認 → 下單/自動下單
每天一次：看 NAV 和持倉 → 檢查有沒有異常
偶爾一次：跑回測驗證 → 看結果
```

---

## 2. 新架構：4 頁就夠

### 頁面規劃

| 路由 | 頁面 | 核心功能 | 優先級 |
|------|------|---------|:------:|
| `/` | **總覽** | NAV 走勢 + 持倉 + 今日 P&L + 系統狀態 | P0 |
| `/strategy` | **策略** | 月度選股結果 + 空頭偵測狀態 + 一鍵再平衡 + 歷史選股紀錄 | P0 |
| `/risk` | **風控** | Drawdown 警示 + Kill Switch + 即時風控狀態 | P0 |
| `/backtest` | **回測** | 跑回測 + 看結果（保留，低頻使用） | P1 |
| `/settings` | **設定** | API Key + 連線狀態 + 通知設定 | P1 |

**砍掉的頁面**：Alpha Research、Auto-Alpha、Allocation、Guide、Admin、Orders（合併到策略頁）

### 資訊架構

```
/                       ← 總覽（首頁）
├── 即時 NAV + 當日損益
├── 持倉列表（即時更新）
├── 空頭偵測狀態（bull/bear/sideways）
└── 系統健康（API 連線 + 資料更新時間）

/strategy               ← 策略中心（最重要的頁面）
├── 當月選股結果（標的 + 權重 + 營收 YoY）
├── 目標 vs 實際持倉偏差
├── 一鍵再平衡按鈕（→ 產生訂單 → 確認 → 下單）
├── 空頭偵測詳情（0050 MA200 / vol 圖表）
└── 歷史選股紀錄（月度，可展開查看）

/risk                   ← 風控
├── 當日 Drawdown（即時 WebSocket）
├── Kill Switch 開關
├── 風控規則狀態（12 條）
└── 歷史告警列表

/backtest               ← 回測（簡化版）
├── 策略選擇（預設 revenue_momentum_hedged）
├── 期間 + Universe 設定
├── 結果：報酬 / Sharpe / MDD / 績效圖表
└── Walk-Forward 結果

/settings               ← 設定
├── Shioaji API Key + CA 憑證路徑
├── 連線狀態（即時 ping）
├── 通知設定（Discord / LINE / Telegram）
├── 語言 / 主題
└── 資料更新狀態（最新營收日期 / parquet 數量）
```

---

## 3. 設計研究檢討

> 基於 TradingView、Bloomberg Terminal、IBKR Desktop、Alpaca、QuantConnect、Tremor、shadcn/ui 等平台的研究

### 3.1 原架構（v2.0）的問題

| 問題 | 來源 | 修正 |
|------|------|------|
| **缺少再平衡倒數計時** | Bloomberg 的任務導向設計 | 策略頁加入「距下次再平衡 N 天」 |
| **無即時連線狀態指示** | TradingView 的 LiveDot 模式 | Sidebar 底部加 LiveDot（綠/黃/紅脈動） |
| **漲跌色未考慮台灣慣例** | 台灣紅漲綠跌（與歐美相反） | locale-aware 配色，zh-TW 時紅=漲 |
| **數字未用等寬字型** | Bloomberg 的 tabular-nums | 所有數值欄位加 `font-variant-numeric: tabular-nums` |
| **無數據新鮮度標記** | IBKR 的「最後更新：2s 前」 | MetricCard 旁加相對時間 |
| **無即時更新閃爍** | TradingView 的 flash highlight | WebSocket 更新時 0.3s 黃底 fade |
| **MetricCard 缺迷你圖** | Tremor SparkChart、Robinhood | NAV/P&L 卡片內嵌 7 天 sparkline |
| **表格手機端不可用** | Devexperts 手機優先設計 | <640px 改為卡片堆疊 |

### 3.2 配色修正

**v2.0 的問題**：未定義具體配色，未考慮台灣紅漲綠跌慣例。

**v2.1 配色方案**：

| 語義 | Light | Dark | 說明 |
|------|-------|------|------|
| 漲/獲利 | `rose-600` (#E11D48) | `rose-400` | 台灣慣例：紅=漲 |
| 跌/虧損 | `emerald-600` (#059669) | `emerald-400` | 台灣慣例：綠=跌 |
| 風險-低 | `emerald-500` | `emerald-400` | |
| 風險-中 | `amber-500` | `amber-400` | |
| 風險-高 | `rose-500` | `rose-400` | |
| CTA 按鈕 | `blue-600` | `blue-400` | |
| 背景 | `white` / `slate-50` | `#0F172A`（非純黑） | |
| 文字 | `slate-900` | `slate-200`（偏暖，護眼） | |

**色盲無障礙**：漲跌同時用 `▲`/`▼` 箭頭 + `+`/`-` 符號，不只靠顏色。

### 3.3 元件庫選型

| 庫 | 用途 | 原因 |
|-----|------|------|
| **shadcn/ui** | 基礎 UI（Dialog, Dropdown, Tabs, Button） | copy-paste 模式，零 bundle 開銷，Tailwind 原生 |
| **Tremor** | 圖表 + KPI 卡（SparkChart, AreaChart, BarList） | 金融場景專用，React + Tailwind，免費 |
| **Recharts** | 備選圖表（v1 已用，保留） | 如果 Tremor 不夠再補 |

**不用的**：
- ~~@quant/shared~~（v1 共享套件，改為直接 fetch，減少一層抽象）
- ~~TanStack Virtual~~（表格最多 15 檔，不需要虛擬滾動）

### 3.4 資訊密度

| 層級 | 時間 | 內容 | 元件 |
|------|------|------|------|
| **一眼** | < 2s | NAV + 日損益 + 連線狀態 | 3 個 SparklineCard |
| **掃視** | < 10s | NAV 曲線 + 持倉前 5 + 空頭偵測 | 1 AreaChart + 1 BarList + 1 Badge |
| **深入** | 按需 | 完整持倉 + 回測 + 風控細節 | 分頁/子路由 |

**反金字塔**：最重要的（NAV、損益）放左上角。Bloomberg 的核心設計原則。

---

## 4. 技術架構

### 技術選型（保持不變）

- **React 18** + TypeScript
- **Vite** build
- **Tailwind CSS** + 深色模式
- **React Router v6** — 5 個路由
- **TanStack Query** — 伺服器狀態管理（取代手寫 useEffect + fetch）
- **Recharts** — 圖表（NAV 走勢、Drawdown、績效曲線）
- **WebSocket** — 即時 NAV、持倉、風控告警

### 目錄結構

```
apps/web/src/
├── app/
│   ├── App.tsx              # Router + Providers
│   ├── routes.tsx           # 路由定義（5 個）
│   └── providers.tsx        # Theme + i18n + Auth + QueryClient
│
├── pages/                   # 頁面組件（每頁一個檔案）
│   ├── OverviewPage.tsx     # /
│   ├── StrategyPage.tsx     # /strategy
│   ├── RiskPage.tsx         # /risk
│   ├── BacktestPage.tsx     # /backtest
│   └── SettingsPage.tsx     # /settings
│
├── features/                # 業務邏輯模組
│   ├── portfolio/           # 持倉 + NAV
│   │   ├── hooks.ts         # usePortfolio, useNAV
│   │   ├── PortfolioTable.tsx
│   │   └── NAVChart.tsx
│   │
│   ├── strategy/            # 策略中心
│   │   ├── hooks.ts         # useMonthlySelection, useRebalance, useRegime
│   │   ├── SelectionCard.tsx     # 當月選股結果
│   │   ├── DriftTable.tsx        # 目標 vs 實際偏差
│   │   ├── RebalanceButton.tsx   # 一鍵再平衡
│   │   ├── RegimeIndicator.tsx   # 空頭偵測
│   │   └── SelectionHistory.tsx  # 歷史紀錄
│   │
│   ├── risk/                # 風控
│   │   ├── hooks.ts         # useDrawdown, useKillSwitch, useAlerts
│   │   ├── DrawdownGauge.tsx
│   │   ├── KillSwitchToggle.tsx
│   │   └── AlertList.tsx
│   │
│   ├── backtest/            # 回測
│   │   ├── hooks.ts         # useBacktest
│   │   ├── BacktestForm.tsx
│   │   └── BacktestResult.tsx
│   │
│   └── connection/          # 連線狀態
│       ├── hooks.ts         # useShioajiStatus, useWSStatus
│       └── StatusBadge.tsx
│
├── shared/                  # 共用 UI
│   ├── ui/
│   │   ├── Card.tsx
│   │   ├── Button.tsx
│   │   ├── Table.tsx
│   │   ├── Badge.tsx
│   │   ├── Skeleton.tsx
│   │   ├── Toast.tsx
│   │   └── Modal.tsx
│   │
│   ├── layout/
│   │   ├── Sidebar.tsx      # 5 個 nav item（不是 15 個）
│   │   └── Header.tsx
│   │
│   └── hooks/
│       ├── useWebSocket.ts  # WS 連線管理
│       └── useApi.ts        # TanStack Query wrapper
│
├── lib/
│   ├── api.ts               # HTTP client（簡化，直接用 fetch）
│   ├── ws.ts                # WebSocket client
│   ├── format.ts            # 格式化（金額、百分比、日期）
│   └── i18n.ts              # 繁中 / English
│
└── types/
    └── index.ts             # 後端 schema 鏡像（只留用到的）
```

### 與 v1 的差異

| 項目 | v1 | v2 |
|------|-----|-----|
| 頁面數 | 11 | **5** |
| Feature 目錄 | 15 | **5** |
| 組件數（估計） | ~80 | **~30** |
| 路由 | 15+（含 redirect） | **5** |
| 型別定義 | ~40 types | **~15 types** |
| API endpoints 使用 | ~25 | **~12** |
| @quant/shared 依賴 | 重度 | **輕度（直接用 fetch）** |

---

## 4. 核心頁面設計

### 5.1 總覽頁（`/`）

```
┌─────────────────────────────────────────────────────────┐
│ ⚡ 台股大盤 23,456 ▲+1.2%  │  櫃買 245.6 ▼-0.3%       │  ← MarketTicker（跑馬燈）
├─────────────┬──────────────┬────────────────────────────┤
│  NAV        │ 今日損益      │ 現金比率                   │
│ $10,234,567 │ ▲ +$12,345   │ 18% ($1,842,000)          │
│ ╭──────╮   │ (+0.12%)      │ ████████░░░░░░░            │  ← SparklineCard
│ │ 7d ↗ │   │ ╭──╮         │ 持倉 12 檔                 │
│ ╰──────╯   │ ╰──╯ 日內    │                             │
├─────────────┴──────────────┴────────────────────────────┤
│  市場環境: 🟢 Bull │ 距下次再平衡: 12 天 (04-11)        │  ← RegimeBadge + 倒數
│  [查看策略詳情 →]                                        │
├─────────────────────────────────────────────────────────┤
│  NAV 走勢  [1M] [3M] [6M] [1Y] [ALL]          更新: 2s │  ← AreaChart + 新鮮度
│  ╭─────────────────────────────────────────╮             │
│  │        ╱╲    ╱────────╲               ╱ │             │
│  │───────╱──╲──╱──────────╲─────────────╱  │             │
│  ╰─────────────────────────────────────────╯             │
├─────────────────────────────────────────────────────────┤
│  持倉明細                            [展開全部 ▾]        │
│  ┌────────┬──────┬─────────┬────────┬──────────┐        │
│  │ 標的    │ 權重  │ 損益    │ 營收YoY │ 偏差      │        │
│  │ 2330.TW │ 8.5% │ ▲+3.2% │ +45%   │ +0.2%    │        │  ← flash on WS update
│  │ 2454.TW │ 7.1% │ ▼-1.1% │ +38%   │ -0.1%    │        │
│  │ 3034.TW │ 6.8% │ ▲+0.8% │ +52%   │ 0.0%     │        │
│  │ ... (前 5 檔)                                  │        │
│  └────────┴──────┴─────────┴────────┴──────────┘        │
├─────────────────────────────────────────────────────────┤
│  🟢 API  🟢 WS  🟢 Shioaji  營收: 2026-03-11 (16天前)  │  ← LiveDot × 3
└─────────────────────────────────────────────────────────┘
```

改進（vs v2.0）：
- 加入 **MarketTicker 跑馬燈**（台股大盤 + 櫃買）
- MetricCard 內嵌 **7 天 sparkline**（Tremor SparkChart）
- 加入**再平衡倒數計時**（最重要的月度操作提示）
- 持倉表加入**偏差欄**（目標 vs 實際，一眼看出需不需要再平衡）
- 數據**新鮮度標記**（「更新: 2s」）
- **LiveDot**（🟢 脈動圓點）取代純文字狀態
- 持倉表預設前 5 檔 + 展開（資訊密度控制）
- 漲跌用 **▲/▼ + 台灣紅漲綠跌配色**

**數據來源**：
- NAV + 持倉：`GET /api/v1/portfolio` + WebSocket `portfolio` channel
- 系統狀態：`GET /api/v1/system/health`
- 空頭偵測：`GET /api/v1/execution/status`（新增 regime 欄位）

### 5.2 策略頁（`/strategy`）— 最重要的頁面

```
┌─────────────────────────────────────────────────────────┐
│  📈 策略中心                    revenue_momentum_hedged  │
├────────────────────────┬────────────────────────────────┤
│  空頭偵測               │  0050.TW vs MA200              │
│                         │  ╭────────────────────────╮    │
│  🟢 Bull               │  │       ╱────── (MA200)   │    │
│  「All clear」          │  │  ────╱                  │    │
│                         │  │ 當前: 196.5             │    │
│  MA200: 185.3 (+6.0%)  │  │ MA200: 185.3            │    │
│  Vol 20d: 12.8%        │  │ Vol: 12.8% (< 25%)     │    │
│  倉位: 100%            │  ╰────────────────────────╯    │
├────────────────────────┴────────────────────────────────┤
│                                                          │
│  2026-03 選股結果                          3/11 產生     │
│  ┌────────┬───────┬────────┬────────┬──────┬──────────┐ │
│  │ 標的    │ 目標%  │ 營收YoY │ 3M/12M │ 持有? │ 偏差    │ │
│  │ 2330.TW │ 6.7%  │ ▲+45%  │ 1.32   │ ✅    │ -0.2%  │ │
│  │ 3034.TW │ 6.7%  │ ▲+52%  │ 1.41   │ ❌ 新  │ -6.7%  │ │
│  │ 2454.TW │ 6.7%  │ ▲+38%  │ 1.28   │ ✅    │ +0.3%  │ │
│  │ ... (15 檔)                                          │ │
│  └────────┴───────┴────────┴────────┴──────┴──────────┘ │
│                                                          │
│  摘要: 目標 15 檔 | 已持有 12 | 新進 3 | 退出 1          │
│  最大偏差: 3034.TW -6.7% (需買入)                        │
│                                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐       │
│  │  📋 預覽再平衡訂單   │  │  🔄 執行再平衡      │       │  ← 兩步操作
│  │  （查看不下單）       │  │  （確認後下單）      │       │
│  └─────────────────────┘  └─────────────────────┘       │
│                                                          │
├──────────────────────────────────────────────────────────┤
│  歷史選股                                    [展開全部]  │
│  ┌────────┬──────┬────────┬─────────────────────────┐   │
│  │ 月份    │ 檔數  │ 月報酬  │ 持有期績效              │   │
│  │ 2026-03 │ 15   │ (進行中)│ ████████ +2.1%         │   │  ← 迷你條狀圖
│  │ 2026-02 │ 15   │ +4.2%  │ █████████████ +4.2%    │   │
│  │ 2026-01 │ 13   │ +1.8%  │ ██████ +1.8%           │   │
│  │ 2025-12 │ 14   │ ▼-2.1% │ ▒▒▒▒▒▒ -2.1%          │   │
│  └────────┴──────┴────────┴─────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

改進（vs v2.0）：
- 空頭偵測**左右分欄**：左邊文字指標 + 右邊 0050 vs MA200 迷你圖
- 選股表加入**偏差欄**和**持有狀態**，一眼看出要買/賣什麼
- **兩步操作**：先「預覽」（看不下單）→ 再「執行」（確認後下單）
- 歷史選股加入**迷你條狀圖**（BarList，Tremor 元件）
- 倉位百分比顯示（bull=100%, sideways=30%, bear=0%）

**數據來源**：
- 選股結果：讀取 `data/paper_trading/selections/{date}.json`（新 API endpoint）
- 目標 vs 實際：`GET /api/v1/portfolio` + selection JSON 比對
- 再平衡：`POST /api/v1/portfolio/saved/{id}/rebalance-preview` → 確認 → `POST /api/v1/orders`

### 4.3 風控頁（`/risk`）

```
┌──────────────────────────────────────────────┐
│  🛡️ 風控                                     │
├──────────┬──────────┬────────────────────────┤
│ 當日DD   │ Kill Switch │ 告警               │
│ -0.3%    │   🟢 OFF   │ 0 active            │
│ ▓▓░░░░░░ │            │                      │
│ (limit 5%)│            │                      │
├──────────┴──────────┴────────────────────────┤
│  Drawdown 走勢（近 30 天，WebSocket）         │
│  ─────────────────────                        │
│                     \___/                     │
├──────────────────────────────────────────────┤
│  風控規則                                     │
│  ✅ max_position_weight (5%)                  │
│  ✅ max_daily_drawdown (3%)                   │
│  ✅ kill_switch (5%)                          │
│  ... (10 條)                                  │
├──────────────────────────────────────────────┤
│  歷史告警                                     │
│  2026-03-15 WARN: MDD exceeded 2%            │
│  2026-03-09 CRIT: Market drop -5.7%          │
└──────────────────────────────────────────────┘
```

### 4.4 回測頁（`/backtest`）— 簡化版

```
┌──────────────────────────────────────────────┐
│  🧪 回測                                      │
├──────────────────────────────────────────────┤
│  策略: [revenue_momentum_hedged ▼]            │
│  期間: [2018-01-01] ~ [2024-12-31]           │
│  再平衡: [monthly ▼]                          │
│                                               │
│  [ 🚀 執行回測 ]                               │
├──────────────────────────────────────────────┤
│  結果                                         │
│  CAGR: +26.5%  Sharpe: 1.48  MDD: 21.4%     │
│                                               │
│  績效曲線                                     │
│  ████████████████████████████▓                │
│                                               │
│  年度明細                                     │
│  2018: +1%  2019: +39%  2020: +64%  ...      │
└──────────────────────────────────────────────┘
```

---

## 5. API Endpoints

### 新增（`src/api/routes/strategy_center.py` ✅ 已實作 + 7 tests）

| Endpoint | Method | 說明 |
|----------|--------|------|
| `/api/v1/strategy/selection/latest` | GET | 最新月度選股結果 |
| `/api/v1/strategy/selection/history` | GET | 歷史選股列表（可分頁） |
| `/api/v1/strategy/regime` | GET | 空頭偵測狀態 + MA200/vol 指標值 |
| `/api/v1/strategy/drift` | GET | 目標 vs 實際持倉偏差 |
| `/api/v1/strategy/rebalance` | POST | 一鍵再平衡（trader 角色） |
| `/api/v1/strategy/info` | GET | 策略基本資訊 |
| `/api/v1/strategy/data-status` | GET | 營收數據更新狀態 |

### 保留使用的

| Endpoint | 用途 | 對應頁面 |
|----------|------|---------|
| `/api/v1/portfolio` | 持倉 + NAV | 總覽 |
| `/api/v1/risk/*` | 風控規則 + 告警 + Kill Switch | 風控 |
| `/api/v1/backtest` | 回測執行 + 結果 | 回測 |
| `/api/v1/system/health` | 系統狀態 | 總覽 footer |
| `/api/v1/auth/*` | 認證 | 設定 |
| `/api/v1/orders` | 下單 | 策略（再平衡後） |
| `/api/v1/execution/status` | 連線狀態 | 設定 |

### 降低優先級（不在 v2 首版使用）

- `/api/v1/alpha/*` — 研究完成
- `/api/v1/allocation/*` — Phase J
- `/api/v1/auto-alpha/*` — 改用月度排程
- `/api/v1/admin/*` — 單人系統
- `/api/v1/scanner/*` — 低頻使用

---

## 6. WebSocket 頻道

| 頻道 | 用途 | 更新頻率 |
|------|------|---------|
| `portfolio` | NAV + 持倉即時更新 | 盤中每分鐘 |
| `alerts` | 風控告警 | 事件驅動 |
| `orders` | 訂單狀態（下單/成交/取消） | 事件驅動 |

移除：`market`（tick 行情 — Paper Trading 不需要在前端顯示）

---

## 7. 狀態管理

### TanStack Query 取代手寫 fetch

```typescript
// v1: 每個頁面自己管 loading/error/data
const [data, setData] = useState(null);
const [loading, setLoading] = useState(true);
useEffect(() => { fetch(...).then(setData).finally(() => setLoading(false)); }, []);

// v2: TanStack Query
const { data, isLoading } = useQuery({
  queryKey: ['portfolio'],
  queryFn: () => api.portfolio.get(),
  refetchInterval: 60_000, // 每分鐘刷新
});
```

好處：自動快取、重試、refetch、dedup、devtools。

### WebSocket 整合 Query

```typescript
// WebSocket 更新自動 invalidate query
useWebSocket('portfolio', (data) => {
  queryClient.setQueryData(['portfolio'], data);
});
```

---

## 8. 開發計畫

### Phase 1：核心骨架（1-2 天）

- [ ] 新建 Vite + React + Tailwind 專案
- [ ] 路由設定（5 頁）
- [ ] Sidebar 導航
- [ ] API client + TanStack Query 設定
- [ ] WebSocket hook
- [ ] 認證流程（API Key）
- [ ] 共用 UI：Card, Button, Table, Badge, Skeleton, Toast

### Phase 2：總覽 + 策略（1-2 天）

- [ ] 總覽頁：NAV 圖表 + 持倉表 + 系統狀態
- [ ] 策略頁：選股結果 + 空頭偵測 + 偏差表
- [ ] 一鍵再平衡流程
- [ ] 後端新增 API（selection/regime/drift/rebalance）

### Phase 3：風控 + 回測（1 天）

- [ ] 風控頁：Drawdown 圖 + Kill Switch + 告警列表
- [ ] 回測頁：表單 + 結果展示

### Phase 4：設定 + 收尾（1 天）

- [ ] 設定頁：API Key + 連線 + 通知
- [ ] i18n（繁中/英文）
- [ ] 深色模式
- [ ] 測試（Vitest + Playwright E2E）

---

## 9. 設計原則

1. **一個頁面做一件事** — 不把研究/交易/監控混在一起
2. **操作最多 2 步** — 預覽 → 確認執行（Bloomberg「隱藏複雜度」原則）
3. **即時 > 手動刷新** — WebSocket 推送 + flash highlight + 新鮮度標記
4. **反金字塔資訊層級** — NAV/損益在左上角（< 2 秒可見），細節按需展開
5. **台灣在地化** — 紅漲綠跌、繁體中文優先、台股交易時段
6. **等寬數字** — 所有數值用 `tabular-nums`（Bloomberg 字型核心）
7. **色盲無障礙** — 漲跌同時用 ▲/▼ 符號 + 顏色，WCAG 4.5:1 對比度
8. **元件庫**：shadcn/ui（基礎）+ Tremor（圖表/KPI）— 不造輪子
9. **暗色模式**：`#0F172A` 背景（非純黑），`slate-200` 文字（偏暖護眼）
10. **數據密度適中** — 不是交易員多螢幕，是一個人用筆電每月操作一次

### 參考來源

- Bloomberg Terminal — 資訊密度 + 隱藏複雜度
- TradingView — LiveDot + flash highlight + 圖表互動
- IBKR Desktop — 可自定義面板 + 多螢幕
- Devexperts — Lite/Pro 模式切換
- Tremor — 金融場景 React 元件庫
- shadcn/ui — Tailwind 原生基礎元件
- Eleken — Fintech 設計指南 2026
- Phoenix Strategy Group — 金融 Dashboard 配色
