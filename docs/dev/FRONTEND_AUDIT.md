# 前端系統全面審計報告

**日期**: 2026-03-24
**範圍**: `apps/web/`、`apps/mobile/`、`apps/shared/`
**審計方法**: 靜態程式碼分析、架構審查、測試覆蓋率分析

---

## 目錄

1. [資料即時性與正確性](#1-資料即時性與正確性)
2. [異常狀態處理](#2-異常狀態處理)
3. [操作安全性](#3-操作安全性)
4. [型別安全與程式碼品質](#4-型別安全與程式碼品質)
5. [測試覆蓋](#5-測試覆蓋)
6. [效能](#6-效能)
7. [無障礙性](#7-無障礙性)
8. [Mobile 特定問題](#8-mobile-特定問題)
9. [前端安全性](#9-前端安全性)
10. [UX 一致性](#10-ux-一致性)
11. [總結與優先級](#11-總結與優先級)

---

## 1. 資料即時性與正確性

### 1.1 WebSocket Channel 使用情況

**狀態: 全部接入** | 風險: 低

4 個 WS channel 皆已在前端使用：

| Channel | Web | Mobile | 使用位置 |
|---------|:---:|:------:|----------|
| `portfolio` | ✓ | ✓ | `useDashboard.ts`、`usePortfolio.ts` (mobile) |
| `alerts` | ✓ | ✓ | `RiskPage.tsx`、`useAlerts.ts` (mobile) |
| `orders` | ✓ | ✗ | `OrdersPage.tsx`（每秒 debounce 重整） |
| `market` | ✓ | ✗ | `MarketTicker.tsx` |

### 1.2 斷線狀態指示

**狀態: 缺失** | 風險: 嚴重

`WSManager`（`shared/src/api/ws.ts:65-71`）支援指數退避重連，但：

- `useWs` hook（`web/src/core/hooks/useWs.ts`）**無連線狀態追蹤**
- 使用者在 WS 斷線期間看到的是凍結數據，**無任何視覺提示**
- Mobile 的 `OfflineBanner` 僅偵測網路連線，不偵測 WS 狀態
- **風險情境**：使用者看到凍結的 NAV 認為市場平靜，實際上系統已斷線，持倉正在虧損

### 1.3 數字格式一致性

**狀態: 大致良好，有少量不一致** | 風險: 低

所有頁面使用共用 `fmtCurrency`、`fmtPct`、`fmtNum`。但以下位置直接使用 `.toFixed(2)`：

| 檔案 | 行 | 問題 |
|------|:--:|------|
| `MarketTicker.tsx` | 95-98 | `item.price.toFixed(2)` |
| `PositionTable.tsx` | 26 | `p.market_price?.toFixed(2)` |
| `PortfolioPage.tsx` | 70-71 | `$${p.market_price?.toFixed(2)}` |

### 1.4 快取與過時資料

**狀態: Mobile 有風險** | 風險: 中

- Web `useApi` 無快取層，無過時資料風險
- Mobile `useRealtimeData` 有 AsyncStorage 快取（TTL 5 分鐘），但顯示快取資料時**無視覺標記**

---

## 2. 異常狀態處理

### 2.1 ErrorBoundary 覆蓋

**狀態: 僅根層級** | 風險: 中

| 平台 | 覆蓋範圍 | 問題 |
|------|----------|------|
| Web | `App.tsx` 根節點一層 | 單一元件拋錯 → 整個 App 白屏，側邊欄也消失 |
| Mobile | `_layout.tsx` 根節點一層 | 同上，Tab 導航也會消失 |

**建議**：為每個路由/頁面加上獨立 ErrorBoundary，保留導航功能。

### 2.2 API 錯誤處理

**狀態: 良好** | 風險: 低

所有頁面使用 `useApi` hook 並處理三態：

| 頁面 | Loading | Error | Empty |
|------|:-------:|:-----:|:-----:|
| Dashboard | ✓ Skeleton | ✓ ErrorAlert + retry | N/A |
| Portfolio | ✓ Skeleton | ✓ ErrorAlert + retry | ✓ 空狀態訊息 |
| Orders | ✓ Skeleton | ✓ ErrorAlert + retry | ✓ ��狀態訊息 |
| Strategies | ✓ Skeleton | ✓ ErrorAlert + retry | ✓ 空狀態訊息 |
| Risk | ✓ Skeleton | ✓ ErrorAlert + retry | ✓ |
| Backtest | ✓ | ✓ | ✓ |
| Admin | ✓ | ✓ | ✓ |
| Settings | ✓ | ✓ | N/A |

`translateApiError` 工具函式將後端錯誤訊息對應至 i18n 字串，實作良好。

### 2.3 WS 重連邏輯

**狀態: 良好** | 風險: 低

`WSManager` 實作指數退避（基底 3 秒，最大 60 秒），成功連線後重置計數。`onerror` 正確關閉 socket 觸發 `onclose` 重連流程。

---

## 3. 操作安全性

### 3.1 策略啟停確認

**狀態: 缺失** | 風險: 嚴重

| 平台 | 位置 | 問題 |
|------|------|------|
| Web | `StrategiesPage.tsx:118` | 單擊即啟停，**無確認對話框** |
| Mobile | `StrategyRow.tsx:31` | 單擊即啟停，**無確認對話框** |

啟動或停止一個實盤策略應要求使用者明確確認。一次誤觸可能啟動未經測試的策略或中斷正在獲利的策略。

### 3.2 手動下單確認

**狀態: 缺失** | 風險: 嚴重

`OrderForm.tsx:21` 表單提交後直接呼叫 API，**無訂單預覽/確認步驟**。交易系統的下單流程應有：
1. 填寫表單
2. 預覽訂單摘要（標的、方向、數量、預估金額）
3. 確認送出

### 3.3 風控規則切換確認

**狀態: 缺失** | 風險: 重要

`RiskPage.tsx:44` 規則 toggle 即時生效，**無確認對話框、無影響說明**。關閉一條風控規則（如 `max_position_weight`）可能使組合暴露於過度集中風險。

### 3.4 Kill Switch 確認

**狀態: 良好** | 風險: 低

- Web：使用 `confirm()` 對話框（`RiskPage.tsx:58`）
- Mobile：使用 `Alert.alert` + 長按 1 秒才觸發（`alerts.tsx:19-37, 59`）

### 3.5 狀態更新模式

**狀態: 正確** | 風險: 低

所有變異操作（策略啟停、下單、規則切換）等待伺服器回應後才更新 UI。**無樂觀更新**。對交易系統而言這是正確做法。

---

## 4. 型別安全與程式碼品質

### 4.1 `any` 型別使用

**狀態: 優良** | 風險: 低

生產程式碼中**零個 `as any`**。僅 4 處在測試檔案中：
- `shared/src/api/ws.test.ts:50, 65`
- `shared/src/api/endpoints.test.ts:96, 105`

### 4.2 型別斷言

**狀態: 可接受但有改善空間** | 風險: 低

| 位置 | 斷言 | 風險 |
|------|------|------|
| `useDashboard.ts:14` | `msg as Partial<Portfolio>` | 前有 type guard，安全 |
| `MarketTicker.tsx:32` | `data as { symbol?: ... }` | 後有 null check，可接受 |
| `RiskPage.tsx:38` | `msg as RiskAlert` | 僅檢查 `typeof a.timestamp`，較弱 |
| `usePortfolio.ts:7` (mobile) | `update as Partial<Portfolio>` | 無 WS 訊息格式驗證 |

### 4.3 Import 模式違規

**狀態: 部分違反架構規範** | 風險: 中

CLAUDE.md 規定：「Feature code imports from `@core/*` — never directly from `@quant/shared`」。以下 runtime import 違反此規範：

| 檔案 | 違規 import |
|------|------------|
| `admin/AdminPage.tsx:8` | `import { fmtDate } from "@quant/shared"` |
| `admin/api.ts:1` | `import { get, post, put, del } from "@quant/shared"` |
| `settings/SettingsPage.tsx:10` | `import { auth as authApi } from "@quant/shared"` |
| `backtest/hooks/useBacktest.ts:4` | `import { pollBacktestResult } from "@quant/shared"` |

### 4.4 重複定義

| 問題 | 位置 |
|------|------|
| `ROLE_BADGE_COLORS` 重複 | `Sidebar.tsx:12-18` 與 `AdminPage.tsx:13-19` |
| Card 容器樣式 copy-paste | ~15 個檔案使用 `bg-slate-50 dark:bg-surface rounded-xl p-5 border...` |

### 4.5 硬編碼值

| 位置 | 問題 |
|------|------|
| `BacktestPage.tsx:25-35` | 回測預設值（策略、標的池、日期、初始資金）硬編碼 |
| `mobile/api/client.ts:13` | `baseUrl = "http://localhost:8000"` 硬編碼 |

---

## 5. 測試覆蓋

### 5.1 測試清單

**Shared (4 檔案)**:
- `client.test.ts` — ApiError、client 初始化
- `endpoints.test.ts` — 所有端點函式
- `ws.test.ts` — WSManager 連線、重連、退避、pong
- `format.test.ts` — 格式化工具

**Web (11 檔案, 71 tests)**:
- `useApi.test.ts` — loading/data/error/refresh/deps
- `format.test.ts` — fmtCurrency/fmtPct/pnlColor
- `ErrorAlert.test.tsx` — render/retry
- `MetricCard.test.tsx` — render/sub text
- `Skeleton.test.tsx` — animation class
- `StatusBadge.test.tsx` — 狀態樣式
- `DashboardPage.test.tsx` — loading/data/error/positions
- `PortfolioPage.test.tsx` — loading/data/empty/error
- `OrdersPage.test.tsx` — loading/data/filters/empty/error
- `StrategiesPage.test.tsx` — loading/data/start-stop/error/empty
- `SettingsPage.test.tsx` — title/login hint

**Mobile (13 檔案)**:
- 元件：AlertItem、ErrorBoundary、MetricCard、OrderRow、PositionRow、Skeleton、StrategyRow
- Hooks：useAlerts、useAuth、useBacktest、useOrders、usePortfolio、useRealtimeData

### 5.2 未測試的關鍵模組

**Web（高優先）**:

| 模組 | 複雜度 | 風險 |
|------|:------:|:----:|
| `BacktestPage` + 10 個子元件 | 極高 | 高 — 最複雜的頁面，完全未測試 |
| `RiskPage` | 高 | 高 — kill switch、規則切換、WS 整合 |
| `AdminPage` | 高 | 中 — 使用者 CRUD、Modal、密碼重設 |
| `useWs` hook | 中 | 高 — 即時資料核心 |
| `DataTable` 元件 | 高 | 中 — 虛擬化、排序、分頁 |
| `Modal` 元件 | 中 | 中 |
| `AuthContext` | 中 | 高 — 認證核心 |
| `OrderForm` | 中 | 高 — 交易安全相關 |
| `MarketTicker` | 中 | 中 |
| `translateApiError` | 低 | 低 |
| `Toast` / `ToastProvider` | 低 | 低 |

### 5.3 測試品質

現有測試覆蓋了基本的三態（loading/data/error）+ 使用者互動。但缺少：

- WS 整合測試（斷線、重連、資料合併）
- 變異操作失敗測試（API 回 500 時 UI 行為）
- 無障礙測試
- 鍵盤導航測試

---

## 6. 效能

### 6.1 Code Splitting

**狀態: 已實作** | 風險: 低

`App.tsx:10-18` 使用 `React.lazy` + `Suspense` 延遲載入所有頁面元件。

### 6.2 Bundle 大小

**狀態: 合理** | 風險: 低

- `recharts` 為最大依賴，但僅在使用圖表的路由載入
- `lucide-react` 支援 tree-shaking（個別 icon import）
- `@tanstack/react-virtual` ~5KB

### 6.3 重渲染風險

| 位置 | 問題 | 嚴重度 |
|------|------|:------:|
| `useDashboard.ts:16-21` | 每次 WS 訊息 append `navHistory` → `NavChart` 重渲染 | 中 |
| `useWs.ts:6` | 正確使用 `useRef` 避免重建 WS 連線 | ✓ |
| `OrdersPage.tsx:24-39` | WS 觸發 refresh debounce 1 秒 | ✓ |
| `AuthContext` / `I18nContext` | 正確使用 `useMemo` | ✓ |

### 6.4 列表渲染

| 元件 | 機制 | 狀態 |
|------|------|------|
| Web `DataTable` | 分頁(25/頁) + 虛擬化(100+行) | ✓ |
| Mobile `FlatList` | `getItemLayout` 固定高度 | ✓ |
| Web `PositionTable` | `positions.slice(0, 10)` **硬編碼截斷，無分頁** | ⚠️ |

---

## 7. 無障礙性

### 7.1 ARIA 標籤

**狀態: 良好** | 風險: 低

| 元件 | ARIA 屬性 |
|------|----------|
| `ErrorAlert` | `role="alert" aria-live="assertive"` |
| `DashboardPage` | `aria-live="polite"` 指標區 |
| `RiskPage` | `role="switch" aria-checked`、`role="alert" aria-live` |
| `OrdersPage` | `role="tablist"`、`role="tab"`、`aria-selected` |
| `DataTable` | `role="columnheader"`、`aria-sort` |
| `Modal` | Escape 鍵處理 |
| `OrderForm` | `aria-pressed` BUY/SELL、`aria-label` |
| `Sidebar` | `role="navigation" aria-label` |
| `Toast` | `role="status" aria-live="polite"` |

### 7.2 色彩對比度

**狀態: 暗色模式良好，亮色模式不足** | 風險: 中

| 顏色 | 暗色背景 (#1E293B) | 亮色背景 (#F8FAFC) | WCAG AA (4.5:1) |
|------|:-:|:-:|:-:|
| `emerald-400` (#34D399) 正收益 | 7.3:1 ✓ | **2.5:1 ✗** | 亮色失敗 |
| `red-400` (#F87171) 負收益 | 5.5:1 ✓ | **3.7:1 ✗** | 亮色失敗 |

### 7.3 缺失項

| 項目 | 狀態 |
|------|------|
| Modal focus trap | ✗ — 無 `aria-modal`、無焦點捕獲 |
| Skip-to-content 連結 | ✗ — 無 |
| ErrorBoundary 本地化 | ✗ — 硬編碼英文（在 I18nContext 外層） |

---

## 8. Mobile 特定問題

### 8.1 功能對等差異

| 功能 | Web | Mobile | 差距 |
|------|:---:|:------:|------|
| 使用者管理 (Admin) | ✓ | ✗ | Web-only |
| 手動下單 (OrderForm) | ✓ | ✗ | Mobile 訂單頁為唯讀 |
| 行情 Ticker | ✓ | ✗ | 使用 `market` WS channel |
| 風控規則說明 | ✓ InfoTooltip | ✗ | 僅顯示規則名稱 |
| 回測歷史/比較 | ✓ | ✗ | Mobile 為簡化版 |
| 明暗主題切換 | ✓ | ✗ | Mobile 僅暗色 |
| 密碼登入 | ✓ | ✗ | Mobile 僅 API Key |
| 角色權限 UI 控管 | ✓ | ✗ | Mobile 所有功能對所有角色可見 |

### 8.2 導航結構

**狀態: 正確** | Expo Router file-based 導航，Tab Layout，`_layout.tsx` 中有 auth redirect。

### 8.3 平台特定處理

**狀態: 良好** | `KeyboardAvoidingView`、`expo-secure-store`、`expo-network`（OfflineBanner），皆正確使用。

---

## 9. 前端安全性

### 9.1 憑證存儲

| 平台 | 機制 | 安全性 |
|------|------|:------:|
| Web | JWT 透過 httpOnly cookie（後端設定）；`localStorage` 存登入旗標和角色 | ✓ |
| Mobile | `expo-secure-store` 存 JWT token 和 API key | ✓ |

### 9.2 角色存儲於 localStorage

**狀態: 有風險** | 風險: 中

`AuthContext.tsx:28-30` 將使用者角色存於 `localStorage`（`quant_user_role`）。使用者可手動修改此值以在 UI 層面看到 Admin 功能。雖然後端會拒絕未授權請求，但允許未授權使用者看到管理介面是不理想的。

### 9.3 XSS 防護

**狀態: 安全** | 風險: 低

- 無 `dangerouslySetInnerHTML` 使用
- 所有使用者輸入透過 React 預設 escaping 渲染
- `ExportButton.tsx:13` CSV 匯出有正確 escape

### 9.4 API Key 暴露

**狀態: 安全** | 無硬編碼 API Key。Web 透過 cookie，Mobile 透過 SecureStore 取得憑證。

---

## 10. UX 一致性

### 10.1 設計系統

| 項目 | 狀態 |
|------|------|
| 共用 UI 元件 | MetricCard、ErrorAlert、StatusBadge、DataTable、Modal、Toast、Skeleton、InfoTooltip、ExportButton |
| Tailwind 自訂色盤 | `tailwind.config.ts` — surface 顏色 |
| Mobile 色盤 | `theme/colors.ts` — 集中管理 |
| Card 容器 | **未抽象** — `bg-slate-50 dark:bg-surface rounded-xl p-5 border...` 在 ~15 個檔案中 copy-paste |

### 10.2 響應式設計

**狀態: 基本** | 風險: 低

- Grid 使用 `grid-cols-2 lg:grid-cols-4` 等響應式
- Sidebar 在 767px 以下自動收合
- 表格有 `overflow-x-auto`

### 10.3 i18n

| 平台 | 狀態 |
|------|------|
| Web | ✓ 完整 zh/en，含 `translateApiError` 錯誤本地化 |
| Mobile | ✓ zh/en（鍵值較少，對應功能較少） |

**硬編碼英文殘留**:

| 檔案 | 行 | 內容 |
|------|:--:|------|
| `ErrorBoundary.tsx` (web) | 29-34 | "Something went wrong", "Reload" |
| `ErrorBoundary.tsx` (mobile) | 21-22 | "Something went wrong", "Try Again" |
| `AdminPage.tsx` | 174 | `"Status"` 欄位名 |
| `AdminPage.tsx` | 252 | `"Loading..."` |
| `StrategyRow.tsx` (mobile) | 33 | `"Stop"` / `"Start"` |

---

## 11. 總結與優先級

### 嚴重（必須處理）

| # | 問題 | 面向 | 影響 |
|---|------|------|------|
| F1 | WS 斷線無狀態指示 | 資料即時性 | 使用者在凍結數據上做交易決策 |
| F2 | 策略啟停無確認對話框 | 操作安全 | 誤觸啟動/停止實盤策略 |
| F3 | 手動下單無確認步驟 | 操作安全 | 無預覽直接送出市價單 |

### 重要（應規劃處理）

| # | 問題 | 面向 | 影響 |
|---|------|------|------|
| F4 | 風控規則切換無確認 | 操作安全 | 誤關風控規則無提示 |
| F5 | 每路由缺獨立 ErrorBoundary | 穩定性 | 單一元件錯誤 → 全 App 白屏 |
| F6 | Mobile 缺角色權限控管 | 安全 | 所有使用者可見 Kill Switch |
| F7 | Mobile 缺手動下單 | 功能缺口 | 無法從手機下單 |
| F8 | BacktestPage 全未測試 | 測試 | 最複雜頁面零覆蓋 |
| F9 | RiskPage / AdminPage 未測試 | 測試 | 高風險頁面零覆蓋 |
| F10 | 亮色模式 PnL 色彩對比不足 | 無障礙 | WCAG AA 不合規 |
| F11 | `@quant/shared` 直接 import | 架構 | 違反平台適配器模式 |
| F12 | localStorage 角色可竄改 | 安全 | UI 層級權限繞過 |

### 改善（可逐步推進）

| # | 問題 | 面向 |
|---|------|------|
| F13 | Card 容器樣式未抽象為元件 | 程式碼品質 |
| F14 | `ROLE_BADGE_COLORS` 重複定義 | 程式碼品質 |
| F15 | Modal 缺 focus trap / `aria-modal` | 無障礙 |
| F16 | 缺 skip-to-content 連結 | 無障礙 |
| F17 | ErrorBoundary 硬編碼英文 | i18n |
| F18 | NavChart 每次 WS 訊息重渲染 | 效能 |
| F19 | PositionTable 硬編碼截斷 10 筆 | UX |
| F20 | 數字格式不一致（.toFixed vs fmtCurrency） | 資料正確性 |
| F21 | 回測預設值硬編碼 | 可配置性 |

---

## 附錄：關鍵檔案索引

| 模組 | 檔案 | 說明 |
|------|------|------|
| WS 管理 | `shared/src/api/ws.ts` | WSManager 重連邏輯 |
| WS Hook | `web/src/core/hooks/useWs.ts` | 無連線狀態暴露 |
| API Hook | `web/src/core/hooks/useApi.ts` | 統一 loading/error 處理 |
| 認證上下文 | `web/src/core/auth/AuthContext.tsx` | 角色存 localStorage |
| 路由 | `web/src/App.tsx` | lazy loading + ErrorBoundary |
| 下單表單 | `web/src/features/orders/components/OrderForm.tsx` | 無確認步驟 |
| 策略頁 | `web/src/features/strategies/StrategiesPage.tsx` | 啟停無確認 |
| 風控頁 | `web/src/features/risk/RiskPage.tsx` | toggle 無確認 |
| 回測頁 | `web/src/features/backtest/BacktestPage.tsx` | 最複雜，未測試 |
| Mobile 佈局 | `mobile/app/_layout.tsx` | Auth redirect |
| Mobile 離線 | `mobile/src/components/OfflineBanner.tsx` | 僅偵測網路 |
