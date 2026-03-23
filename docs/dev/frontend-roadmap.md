# 前端介面開發路線圖

**更新日期**: 2026-03-23
**範圍**: `apps/web/`、`apps/mobile/`、`apps/shared/`

---

## 現況總覽

| 類別 | 狀態 | 說明 |
|------|:----:|------|
| 核心功能 | ✅ | 8 個頁面、全部交易流程可用 |
| API 覆蓋 | ✅ | 18/19 端點已串接（僅 `/system/metrics` 未用） |
| WebSocket | ✅ | portfolio, orders, alerts 已用；market 未用 |
| i18n | ✅ | 中英文完整覆蓋（30+ 翻譯鍵） |
| Mobile | ✅ | 7 個 tab、基本功能對等 |
| 測試 | ✅ | Web 71+ unit + E2E、Mobile 20+、Shared 38+ |
| 無障礙 | ✅ | ARIA 標籤已補齊 |
| 主題 | ✅ | 深色/淺色切換已完成 |
| PWA | ❌ | 無 Service Worker、無離線支援 |
| 效能 | ✅ | 虛擬列表、exponential backoff 已完成 |

---

## 一、測試與品質（高優先）

### 1. Web E2E 測試 ✅

- Playwright 設定 + MSW mock API
- 核心旅程：登入 → Dashboard → 下單 → 查看訂單
- 回測流程：選策略 → 執行 → 檢視結果 → 比較
- 風控流程：切換規則 → Kill Switch
- 預計 3 個 spec 檔案

### 2. Mobile 測試建設 ✅

- Jest + React Native Testing Library 設定
- 元件單元測試（MetricCard, PositionRow, StrategyRow, OrderRow, AlertItem, Skeleton）
- Hook 測試（usePortfolio, useOrders, useBacktest, useRealtimeData）
- 目標：≥ 20 tests

### 3. Shared 測試補強 ✅

- WebSocket Manager 測試（連線、重連、backoff）
- API client 錯誤處理測試
- 所有 endpoint 函數測試
- 達成：38+ tests（目標 ≥ 15）

---

## 二、使用者體驗（高優先）

### 4. 深色/淺色主題切換 ✅

- ThemeContext + `useTheme()` hook
- 系統偏好偵測（`prefers-color-scheme`）
- Tailwind `dark:` class 雙主題支援
- localStorage 持久化
- Settings 頁面加入切換開關

### 5. 即時行情 Ticker（`market` WS channel）

- Dashboard 頂部顯示即時行情（目前 `market` channel 未使用）
- 價格跳動動畫（綠漲紅跌）
- 可選標的訂閱

### 6. 系統監控面板（`/system/metrics` 端點）

- 目前唯一未串接的後端端點
- 顯示 API 延遲、請求數、錯誤率
- 可整合至 Settings 或獨立 Admin 頁面

### 7. 通知系統

- Web：瀏覽器 Notification API（風控警報、訂單成交）
- Mobile：expo-notifications 推播（severity=CRITICAL）
- Toast 元件（操作成功/失敗回饋，目前缺少）

---

## 三、無障礙性（中優先）

### 8. ARIA 標籤補齊 ✅

- 所有互動元素加 `aria-label`
- 表格加 `role="table"` / `role="grid"`
- 錯誤訊息加 `aria-live="polite"` 即時播報
- Modal/Dialog 加 `role="dialog"` + focus trap

### 10. 色彩對比度

- WCAG AA 標準（≥ 4.5:1）
- 目前深色主題的 `text-slate-500` 在 `bg-surface-dark` 上可能不達標
- StatusBadge 已有圖示輔助（已完成）

---

## 四、Mobile 進階功能（中優先）

### 11. 圖表視覺化

- 整合 `react-native-svg` + `victory-native`
- Dashboard NAV 迷你折線圖（近 30 點、觸控查看）
- Backtest 結果 NAV 曲線
- Positions 持倉權重圓餅圖

### 13. 離線快取

- AsyncStorage 快取最近一次 API 回應
- 離線時顯示快取資料 +「離線」標示
- 恢復連線自動刷新

### 14. Mobile 色彩主題常數

- 目前 16+ 處硬編碼 `#0F172A`、`#1E293B` 等
- 抽取為 `colors.ts` 主題常數
- 為未來淺色主題做準備

---

## 五、效能最佳化（中優先）

### 15. 大型列表虛擬化 ✅

- `react-window` 或 `@tanstack/virtual`
- Orders、Positions、Alerts 表格 > 100 筆時自動啟用
- Mobile：FlatList `getItemLayout` + `windowSize` 調校

### 16. 回測輪詢 Exponential Backoff ✅

- 目前固定 2–3 秒輪詢，最多 900 次 API 呼叫
- 改為指數退避（2s → 4s → 8s → cap 30s）
- Web + Mobile 兩端都需修改

---

## 六、功能增強（低優先）

### 18. 進階回測分析

- 月度報酬熱力圖（heatmap）
- 回撤曲線圖（drawdown chart）
- 交易明細表 + CSV 匯出
- 因子貢獻分析圖表

### 19. 多使用者角色 UI

- 後端已有 5 級角色（viewer → admin）
- 前端根據角色隱藏/顯示功能（如 viewer 不能下單、risk_manager 才能 kill switch）
- 角色標示 badge

### 22. 跨平台程式碼整合

- `useBacktest` hook web / mobile 重複 → 抽至 `@quant/shared`
- i18n 翻譯字典重複 → 合併至 shared
- `ordersApi` / `backtestApi` 與 shared endpoints 重複 → 統一

---

## 七、CI/CD 強化（低優先）

### 23. 前端測試 CI Jobs ✅

- `web-test`、`shared-test` 已加入 ✅
- `mobile-test` 已加入 ✅
- Playwright `e2e-test` 已加入 ✅

---

## 建議執行順序

```
第一批（品質基礎）
  ├─ #1  Web E2E 測試
  ├─ #2  Mobile 測試
  └─ #4  深色/淺色主題

第二批（體驗提升）
  ├─ #5  即時行情 ticker
  ├─ #7  通知系統 / Toast
  ├─ #8  ARIA 補齊
  └─ #11 Mobile 圖表

第三批（效能 + 進階）
  ├─ #15 虛擬列表
  ├─ #16 輪詢 backoff
  └─ #22 跨平台程式碼整合

第四批（錦上添花）
  ├─ #18 進階回測分析
  ├─ #19 角色 UI
```

---

## 跨項目依賴

```
#4  主題切換 ──────→ #14 Mobile 色彩常數
#1  E2E 測試 ─────→ #23 CI Playwright job
#2  Mobile 測試 ──→ #23 CI mobile-test job
#8  ARIA 補齊 ────→ #10 色彩對比度
#22 程式碼整合 ───→ #16 輪詢 backoff（共用邏輯）
#11 Mobile 圖表 ──→ #18 進階回測分析
```
