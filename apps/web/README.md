# quant-web

量化交易系統前端儀表板。提供投組監控、策略管理、回測、風控等功能，支援繁體中文 / English 切換。

## Tech Stack

| 層次 | 技術 |
|------|------|
| 建置 | Vite 5 |
| UI | React 18 + TypeScript 5 |
| 樣式 | Tailwind CSS 3（深色主題） |
| 路由 | React Router DOM 6 |
| 圖表 | Recharts 2 |
| 圖示 | Lucide React |
| 測試 | Playwright |

## 功能頁面

| 路徑 | 頁面 | 說明 |
|------|------|------|
| `/` | Dashboard | NAV 即時折線圖、策略狀態、持倉總覽（WebSocket） |
| `/portfolio` | Portfolio | 完整持倉表、曝險指標 |
| `/strategies` | Strategies | 啟動／停止策略、策略說明手風琴 |
| `/orders` | Orders | 訂單查詢，支援狀態篩選 |
| `/backtest` | Backtest | 提交回測參數、輪詢進度、績效曲線 |
| `/risk` | Risk | 風控規則開關、即時警報串流、Kill Switch |
| `/settings` | Settings | API Key 設定、語言切換、系統狀態 |

## 快速開始

```bash
# 安裝依賴
npm install

# 啟動開發伺服器（port 3000，自動 proxy 至 localhost:8000）
npm run dev

# 型別檢查
npm run typecheck

# 生產建置
npm run build
```

後端需在 `localhost:8000` 運行，Vite dev server 會自動將 `/api` 與 `/ws` 請求 proxy 過去。

## 專案結構

```
src/
├── core/                  # 純基礎設施，無業務邏輯
│   ├── api/               # HTTP 客戶端、WebSocket 管理器
│   ├── hooks/             # useApi、useWs
│   ├── i18n/              # 多語系（en/zh），按功能拆分 locale 檔
│   │   └── locales/
│   │       ├── en/        # common · dashboard · portfolio · ...
│   │       └── zh/
│   ├── types/             # 跨 feature 共用型別（Portfolio、Position、StrategyInfo）
│   └── utils/             # 格式化工具（fmtCurrency、fmtPct 等）
│
├── shared/                # 跨 feature 共用 UI
│   ├── ui/                # ErrorAlert · StatusBadge · InfoTooltip · MetricCard
│   └── layout/            # Sidebar
│
├── features/              # 業務功能模組，各自獨立
│   ├── dashboard/         # api · hooks/useDashboard · components/{NavChart,PositionTable}
│   ├── portfolio/         # api · PortfolioPage
│   ├── strategies/        # api · StrategiesPage
│   ├── orders/            # api · types · OrdersPage
│   ├── backtest/          # api · types · hooks/useBacktest · components/{AnimatedSelect,ResultChart}
│   ├── risk/              # api · types · RiskPage
│   └── settings/          # api · types · SettingsPage
│
├── App.tsx                # 路由 + I18nContext Provider
└── main.tsx
```

### 路徑別名

```
@core   →  src/core
@shared →  src/shared
@feat   →  src/features
```

## API 通訊

- **REST** — `GET /api/v1/...`，30s 逾時，`X-API-Key` header 認證
- **WebSocket** — `ws://host/ws/{channel}`，自動重連（指數退避，最大 60s），30s 心跳
- **Long polling** — Backtest 提交後每 2 秒輪詢任務狀態

## 認證

API Key 儲存於 `localStorage`（key: `quant_api_key`）。未設定時自動導向 `/settings`。開發用預設 Key：`dev-key`。
