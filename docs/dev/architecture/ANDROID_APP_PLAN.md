# Android 原生 APP 實作計畫 — Kotlin Jetpack Compose

## Context

使用 Kotlin Jetpack Compose 建構 100% Android 原生 APP，功能與 Web 版完全對齊。僅做 Android（不考慮 iOS）。由 Claude 主導實作，附詳細操作手冊。

---

## 現有架構（2026-03-25 git pull 後）

### 後端 API（12 個路由模組，50+ 端點）

| 路由 | 前綴 | 說明 |
|------|------|------|
| auth | `/api/v1/auth` | 登入/登出/改密碼 |
| admin | `/api/v1/admin` | 使用者 CRUD + 審計日誌（僅 admin） |
| portfolio | `/api/v1/portfolio` | 持倉 + 已保存組合 CRUD + 再平衡 + 交易歷史 |
| strategies | `/api/v1/strategies` | 策略列表/啟動/停止 |
| orders | `/api/v1/orders` | 訂單列表/建立 |
| backtest | `/api/v1/backtest` | 回測提交/狀態/結果/取消/Walk-forward |
| alpha | `/api/v1/alpha` | Alpha 研究管道（非同步） |
| allocation | `/api/v1/allocation` | 戰術資產配置 |
| execution | `/api/v1/execution` | **新增** 執行狀態/模擬交易/市場時段/對帳/排隊訂單 |
| scanner | `/api/v1/scanner` | **新增** 市場掃描/快照 |
| risk | `/api/v1/risk` | 風控規則/告警/Kill Switch |
| system | `/api/v1/system` | 健康檢查/狀態/指標 |

WebSocket：4 頻道（portfolio / alerts / orders / market）

### Web 前端（8 個頁面，經 Tab 整併）

| 路由 | 頁面 | 內容 |
|------|------|------|
| `/` | Dashboard | 持倉概覽、NAV 圖表、WebSocket 即時更新 |
| `/trading` | Trading | **Tab**: Portfolio ｜ Orders ｜ Paper Trading |
| `/strategies` | Strategies | 策略列表 + 啟停控制 |
| `/research` | Research | **Tab**: Backtest ｜ Alpha Research ｜ Allocation |
| `/risk` | Risk | 風控規則、告警、Kill Switch |
| `/guide` | Guide | 使用指南（7 個章節） |
| `/settings` | Settings | 認證、語言、主題、系統指標、Getting Started |
| `/admin` | Admin | 使用者管理、審計日誌（僅 admin） |

### 共享型別（`apps/shared/src/types/index.ts`，43 個型別）

核心：Portfolio, Position, StrategyInfo, OrderInfo, BacktestRequest/Summary/Result, RiskRule/Alert, UserInfo, AlphaRunRequest/Summary/Report, TacticalRequest/Response

新增：ExecutionStatus, PaperTradingStatus, MarketHoursStatus, ReconcileResult, ReconcileDiff, QueuedOrdersResponse, PortfolioListItem, SavedPortfolio, PortfolioCreateRequest, RebalancePreviewRequest/Response, SuggestedTrade

### API 端點（`apps/shared/src/api/endpoints.ts`，7 個模組）

auth / system / portfolio / strategies / orders / backtest / alpha / allocation / execution / risk

---

## Phase 1：專案初始化與基礎架構

### 1.1 建立 Android 專案結構

```
apps/android/
  app/
    src/main/
      java/com/quant/trading/
        QuantApp.kt                    # Application + Hilt DI
        MainActivity.kt                # Single-activity Compose host
      res/
        values/strings.xml             # 英文
        values-zh-rTW/strings.xml      # 繁體中文
    build.gradle.kts
  build.gradle.kts                     # Root build
  settings.gradle.kts
  gradle.properties
  gradle/libs.versions.toml            # 版本目錄
```

### 1.2 核心依賴

| 用途 | 依賴 | 版本 |
|------|------|------|
| UI | Jetpack Compose BOM | 2024.12+ |
| 導航 | Navigation Compose | 2.8+ |
| 網路 | Retrofit2 + OkHttp | 2.11+ / 4.12+ |
| JSON | kotlinx.serialization | 1.7+ |
| DI | Hilt | 2.51+ |
| 憑證 | EncryptedSharedPreferences | 1.1+ |
| 圖表 | Vico (Compose charting) | 2.0+ |
| WebSocket | OkHttp WebSocket | 4.12+ |
| 生命週期 | Lifecycle ViewModel Compose | 2.8+ |
| Material | Material 3 | Compose BOM 管理 |

### 1.3 基礎層檔案

- `navigation/Screen.kt` — Sealed class（Login + 8 頁面 = 9 個目的地）
- `navigation/NavGraph.kt` — Compose NavHost
- `navigation/BottomNavBar.kt` — 底部導航列（5 tab + More menu）
- `data/local/SecureStorage.kt` — EncryptedSharedPreferences 封裝
- `data/api/AuthInterceptor.kt` — OkHttp JWT interceptor
- `data/api/QuantApiService.kt` — Retrofit interface（所有 API 端點）
- `data/api/WebSocketManager.kt` — OkHttp WS（auto-reconnect + exponential backoff）
- `data/api/ApiModels.kt` — Kotlin data classes（對應 43 個 TypeScript 型別）
- `di/NetworkModule.kt` — Hilt：OkHttp / Retrofit / WS
- `di/StorageModule.kt` — Hilt：SecureStorage
- `ui/theme/Theme.kt` — Material 3 主題
- `ui/theme/Color.kt` — 色彩定義
- `util/Format.kt` — fmtCurrency, fmtPct, fmtDate

---

## Phase 2：認證與設定

- `ui/screens/login/LoginScreen.kt` + `LoginViewModel.kt`
  - 伺服器 URL 輸入 → SecureStorage
  - API Key 或帳密登入 → JWT 存入 EncryptedSharedPreferences
  - 登入成功 → 導航至 Dashboard

- `ui/screens/settings/SettingsScreen.kt` + `SettingsViewModel.kt`
  - Getting Started 引導（對應 Web 的 GettingStarted 元件）
  - 語言切換（en/zh-TW）
  - 主題切換（深色/淺色/系統）
  - 修改密碼
  - 系統指標顯示
  - 登出

- 認證守衛：NavGraph 檢查 JWT → 未認證導向 Login，AuthInterceptor 401 → 重新登入

---

## Phase 3：核心頁面（對齊 Web 8 頁面結構）

每頁遵循 **Screen + ViewModel + Repository** 模式。

### 3.1 Dashboard（`/`）
- `ui/screens/dashboard/DashboardScreen.kt` + `DashboardViewModel.kt`
- 持倉概覽 MetricCard、NAV 折線圖（Vico）、持倉列表
- API：`GET /portfolio`, `GET /portfolio/positions`
- WS：`portfolio` 頻道

### 3.2 Trading（`/trading`）— **Tab 結構**
- `ui/screens/trading/TradingScreen.kt` + Tab 切換
- **Tab 1: Portfolio**
  - `ui/screens/trading/portfolio/PortfolioTab.kt` + `PortfolioViewModel.kt`
  - 已保存組合 CRUD、再平衡預覽、交易歷史
  - API：portfolio.listSaved / createSaved / getSaved / deleteSaved / rebalancePreview / trades
- **Tab 2: Orders**
  - `ui/screens/trading/orders/OrdersTab.kt` + `OrdersViewModel.kt`
  - 下單表單、訂單歷史（篩選 open/filled）
  - API：orders.list / orders.create
  - WS：`orders` 頻道
- **Tab 3: Paper Trading**
  - `ui/screens/trading/paper/PaperTradingTab.kt` + `PaperTradingViewModel.kt`
  - 模擬交易狀態、市場時段、對帳、排隊訂單
  - API：execution.status / paperTradingStatus / marketHours / reconcile / autoCorrect / queuedOrders

### 3.3 Strategies（`/strategies`）
- `ui/screens/strategies/StrategiesScreen.kt` + `StrategiesViewModel.kt`
- 策略列表、啟動/停止
- API：strategies.list / start / stop

### 3.4 Research（`/research`）— **Tab 結構**
- `ui/screens/research/ResearchScreen.kt` + Tab 切換
- **Tab 1: Backtest**
  - `ui/screens/research/backtest/BacktestTab.kt` + `BacktestViewModel.kt`
  - 回測參數設定、非同步執行、結果圖表、歷史比較
  - API：backtest.submit / status / result
  - coroutine 輪詢進度
- **Tab 2: Alpha Research**
  - `ui/screens/research/alpha/AlphaTab.kt` + `AlphaViewModel.kt`
  - 因子分析、IC 圖表、分位數報酬
  - API：alpha.run / status / result
- **Tab 3: Allocation**
  - `ui/screens/research/allocation/AllocationTab.kt` + `AllocationViewModel.kt`
  - 戰術配置計算、宏觀因子視覺化
  - API：allocation.compute

### 3.5 Risk（`/risk`）
- `ui/screens/risk/RiskScreen.kt` + `RiskViewModel.kt`
- 風控規則管理、告警列表、Kill Switch
- API：risk.rules / toggleRule / alerts / killSwitch
- WS：`alerts` 頻道

### 3.6 Guide（`/guide`）
- `ui/screens/guide/GuideScreen.kt` + `GuideViewModel.kt`
- 7 個章節（Overview / Backtest / Alpha / Allocation / Risk / PaperTrading / FAQ）
- 純本地內容，無 API 呼叫
- 使用 Compose LazyColumn + 章節摺疊

### 3.7 Admin（`/admin`，僅 admin 角色）
- `ui/screens/admin/AdminScreen.kt` + `AdminViewModel.kt`
- 使用者 CRUD、角色管理、密碼重設、審計日誌
- API：admin 路由全部

---

## Phase 4：共用 UI 元件

- `ui/components/Card.kt` — 基礎卡片
- `ui/components/MetricCard.kt` — KPI 指標卡
- `ui/components/StatusBadge.kt` — 狀態標籤
- `ui/components/LoadingSkeleton.kt` — 載入骨架
- `ui/components/ErrorAlert.kt` — 錯誤提示 + 重試
- `ui/components/ConnectionBanner.kt` — WS 連線狀態
- `ui/components/ConfirmDialog.kt` — 確認對話框
- `ui/components/EmptyState.kt` — 空資料狀態
- `ui/components/HelpTip.kt` — 提示工具
- `ui/components/TabBar.kt` — Tab 切換列（Trading/Research 頁面使用）
- `ui/components/NavChart.kt` — NAV 折線圖（Vico）
- `ui/components/PnlText.kt` — 紅綠色損益文字

---

## Phase 5：i18n 多語系

- `res/values/strings.xml` — 英文（預設）
- `res/values-zh-rTW/strings.xml` — 繁體中文
- 翻譯內容參考 `apps/web/src/core/i18n/locales/en.ts` 和 `zh.ts`
- App 內語言切換使用 `AppCompatDelegate.setApplicationLocales()`

---

## Phase 6：CI 整合

在 `.github/workflows/ci.yml` 新增：

```yaml
android-lint:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-java@v4
      with: { java-version: '17' }
    - run: cd apps/android && ./gradlew lint

android-test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-java@v4
      with: { java-version: '17' }
    - run: cd apps/android && ./gradlew test

android-build:
  needs: [android-lint, android-test]
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-java@v4
      with: { java-version: '17' }
    - run: cd apps/android && ./gradlew assembleDebug
```

---

## Phase 7：操作手冊

產出 `docs/dev/ANDROID_SETUP.md`：
1. Android Studio 安裝與設定
2. 開啟專案（File → Open → `apps/android/`）
3. 設定後端 URL
4. 模擬器/實機執行
5. 建構 APK（Build → Build Bundle / APK）
6. 常見問題排解

同步更新 `docs/dev/ANDROID_APP_PLAN.md` 與 `docs/dev/SYSTEM_STATUS_REPORT.md`。

---

## 關鍵檔案參考

| 用途 | 路徑 |
|------|------|
| 後端 API 全部路由 | `src/api/routes/` (12 個模組) |
| 後端 Pydantic Schema | `src/api/schemas.py` |
| 後端 app 入口 | `src/api/app.py` |
| OpenAPI Spec | 執行時 `http://localhost:8000/openapi.json` |
| TS 型別（43 個） | `apps/shared/src/types/index.ts` |
| TS API 端點 | `apps/shared/src/api/endpoints.ts` |
| Web 路由結構 | `apps/web/src/App.tsx` |
| Web Trading 頁面 | `apps/web/src/features/trading/TradingPage.tsx` |
| Web Research 頁面 | `apps/web/src/features/alpha/AlphaPage.tsx` |
| Web Sidebar 導航 | `apps/web/src/shared/layout/Sidebar.tsx` |
| Web WS Manager | `apps/shared/src/api/ws.ts` |
| Web i18n (en) | `apps/web/src/core/i18n/locales/en.ts` |
| Web i18n (zh) | `apps/web/src/core/i18n/locales/zh.ts` |

---

## 驗證步驟

1. `make dev` 啟動後端 API（port 8000）
2. Android Studio → Run 在模擬器或實機
3. 登入（輸入 server URL + API key）
4. 逐一檢查 8 個頁面功能（含 Tab 子頁面）
5. 驗證 WebSocket 即時推送（portfolio / alerts / orders）
6. 切換語言（en ↔ zh-TW）
7. `./gradlew test` 通過單元測試
8. `./gradlew lint` 無錯誤
9. `./gradlew assembleRelease` 產出 APK

---

## 工作量預估

| Phase | 內容 | 檔案數 |
|-------|------|--------|
| 1 | 專案初始化 + 基礎架構 | ~15 |
| 2 | 認證 + 設定 | ~6 |
| 3 | 8 個頁面（含 6 個 Tab 子頁面） | ~24 |
| 4 | 共用 UI 元件 | ~12 |
| 5 | i18n | ~2 |
| 6 | CI | ~1 |
| 7 | 文件 | ~2 |
| **合計** | | **~62 檔案** |
