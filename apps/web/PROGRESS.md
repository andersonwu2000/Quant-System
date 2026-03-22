# quant-web 開發進度

## 2026-03-23

### 環境建置
- 確認 quant-web（前端 Vite/React port 3000）與 Portfolio（後端 FastAPI port 8000）的啟動流程
- Portfolio 缺少虛擬環境，使用 Anaconda Python 3.12 建立 `.venv` 並安裝所有依賴（uvicorn、fastapi、sqlalchemy 等）
- 後端不依賴 Docker 即可啟動（AppState 為 in-memory，DB 僅特定路由使用）

### 風控管理頁（RiskPage）
- 研讀後端 `src/risk/rules.py` 六條規則的邏輯與閾值
- 每條規則名稱後加入 **ⓘ 圖標**，hover 顯示說明 tooltip
- Tooltip 內容支援中英文 i18n，新增 `risk.ruleDescriptions` 至 `en.ts` / `zh.ts`
- 抽出共用元件 `src/components/InfoTooltip.tsx`

### 策略管理頁（StrategiesPage）
- 研讀 `strategies/momentum.py`、`strategies/mean_reversion.py` 實作細節
- 策略名稱旁加入 **ⓘ 圖標（點擊展開）**，展開後在卡片下方以 maxHeight 動畫推出說明文字
- ⓘ 展開時變藍色（`text-blue-400`）表示已展開狀態
- 卡片佈局重構：名稱固定寬度（`w-44`）+ 垂直分隔線，確保 StatusBadge 對齊
- 新增 `strategies.strategyDescriptions` 至 i18n

### 回測頁（BacktestPage）
- 策略欄位從 `<input>` 改為自訂 **AnimatedSelect** 下拉元件（選項：momentum、mean_reversion）
- 再平衡頻率從原生 `<select>` 同樣改為 AnimatedSelect
- 動畫：`scaleY` + `translateY` + `opacity` 三軸過渡，`origin-top` 從按鈕下緣展開；chevron 同步旋轉 180°
- 點選範圍外自動關閉（`mousedown` 事件監聽）

## 2026-03-23（續）

### 專案整理
- 刪除 `projects/quant-web/` 根目錄下所有截圖 PNG（fix-*、screenshot-*、ss-*，共 20 張）及未追蹤的閒置 SVG 素材（information-circle、triangle-down-filled）

### 方案三：完整模組化重構（core / shared / features）

**動機**：舊結構以技術層（api/、hooks/、components/、pages/）分組，隨功能增加難以維護。方案三改以業務功能為主軸，搭配路徑別名消除相對路徑地獄。

**新目錄結構**

```
src/
├── core/          純基礎設施（api、hooks、i18n、types、utils）
├── shared/        跨 feature 共用 UI（ui/、layout/）
└── features/      業務模組，各自獨立
    ├── dashboard/   · hooks/useDashboard · components/{NavChart,PositionTable}
    ├── portfolio/
    ├── strategies/
    ├── orders/      · types（OrderInfo）
    ├── backtest/    · hooks/useBacktest · components/{AnimatedSelect,ResultChart} · types
    ├── risk/        · types（RiskRule、RiskAlert）
    └── settings/    · types（SystemStatus）
```

**路徑別名**（vite.config.ts + tsconfig.json）
- `@core` → `src/core`
- `@shared` → `src/shared`
- `@feat` → `src/features`

**主要拆分**
- i18n 從單一 `en.ts`/`zh.ts` 拆成 8 個 locale 檔（common、dashboard、portfolio、strategies、orders、backtest、risk、settings），透過各語系 `index.ts` 合併，型別結構不變
- 共用型別（Portfolio、Position、StrategyInfo）移至 `core/types`；僅單一 feature 使用的型別移至各 feature 的 `types.ts`
- `DashboardPage` 邏輯抽成 `useDashboard` hook；圖表與持倉表抽成 `NavChart`、`PositionTable` 子元件
- `BacktestPage` 輪詢邏輯抽成 `useBacktest` hook；`AnimatedSelect`、`ResultChart` 抽成獨立元件
- 舊目錄（src/api、src/hooks、src/components、src/pages、src/i18n、src/types、src/utils）全數刪除
- `tsc --noEmit` 零錯誤

### 文件
- 新增 `README.md`，包含 Tech Stack、功能頁面對照表、快速開始指令、專案結構說明、路徑別名、API 通訊模式、認證說明
