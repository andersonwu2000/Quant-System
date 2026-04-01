# Phase N2：Web 前端重寫

> 狀態：🟡 Step 1-4 已完成，Step 5 待辦
> 架構文件：`docs/architecture/WEB_ARCHITECTURE_V2.md`
> 設計規範：`docs/architecture/WEB_DESIGN_SYSTEM.md`
> 目標：5 頁精簡 UI，dark-mode-first，shadcn/ui + Tremor

---

## 執行順序

```
Step 1: 骨架（Router + Providers + Sidebar + API client）
Step 2: 總覽頁（NAV + 持倉 + 系統狀態）
Step 3: 策略頁（選股 + 空頭偵測 + 再平衡）
Step 4: 風控頁 + 回測頁 + 設定頁
Step 5: 收尾（i18n + 測試 + 部署）
```

---

## Step 1：骨架 ✅

- Vite + React 18 + TypeScript（保留現有 `apps/web/` 位置，清空 `src/`）
- 安裝：`shadcn/ui` init + `@tremor/react` + `recharts` + `@tanstack/react-query` + `lucide-react`
- `tailwind.config.ts` 套用 Design System（surface 色 / profit-loss / tabular-nums / 動畫）
- Inter + JetBrains Mono 字型
- `app/App.tsx`：Router（5 頁）+ QueryClientProvider + ThemeProvider
- `shared/layout/Sidebar.tsx`：5 nav items + LiveDot 連線狀態 + dark mode toggle
- `lib/api.ts`：fetch wrapper（API key from localStorage）
- `lib/ws.ts`：WebSocket client（auto-reconnect）

> **完成**：`app/App.tsx`、`lib/api.ts`、`lib/format.ts`、`Sidebar.tsx` 已重寫。舊 v1 備份於 `src_v1_backup/`。

## Step 2：總覽頁 ✅

- 3 個 SparklineCard（NAV / 日損益 / 現金比）
- RegimeBadge + 再平衡倒數
- NAV AreaChart（1M/3M/6M/1Y 切換）
- 持倉 Table（前 5 檔 + 展開）
- Footer 系統狀態（3 個 LiveDot）

> **完成**：`pages/OverviewPage.tsx` 已建立。

## Step 3：策略頁 ✅

- 空頭偵測：左文字 + 右迷你圖
- 選股結果 Table（目標%/營收YoY/3M12M/持有?/偏差）
- 兩個按鈕：預覽再平衡 / 執行再平衡
- 歷史選股 BarList

> **完成**：`pages/StrategyPage.tsx` 已建立。

## Step 4：風控 + 回測 + 設定 ✅

- 風控：Drawdown GaugeChart + Kill Switch toggle + 告警列表
- 回測：表單（策略/期間）+ 結果展示
- 設定：API Key + 連線測試 + 語言/主題

> **完成**：`pages/RiskPage.tsx`、`pages/BacktestPage.tsx`、`pages/SettingsPage.tsx` 已建立。

## Step 5：收尾 🔵

- i18n（繁中 / English）
- Vitest 測試
- build 驗證
