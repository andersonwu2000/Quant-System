# Quant-System 完整系統說明

> **日期**：2026-03-29
> **版本**：v15.0
> **階段**：Phase A~AC 完成，Paper Trading 運行中，Phase 2 乾淨研究準備中

---

## 一、系統定位

**多資產量化投資研究與交易平台**，服務對象為個人投資者和家族資產管理。

- **主要市場**：台股（佣金 0.1425%，賣出稅 0.3%）
- **資產類別**：台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
- **當前階段**：Alpha 研究層完成，Paper Trading 運行中，等待永豐金 CA 憑證後進入 Live Mode
- **架構**：Python 後端 + React Web + Android App（Monorepo）

---

## 二、架構總覽

### 資料流

```
DataFeed → Strategy.on_bar() → 目標權重 dict
  → weights_to_orders() → RiskEngine（12 規則）
  → SimBroker/PaperBroker/SinopacBroker → Trade
  → Portfolio 更新 → save_portfolio()
  → 通知（Discord/LINE/Telegram）
```

### 代碼規模

| 項目 | 數值 |
|------|------|
| 後端 Python 檔案 | 153 |
| 後端 LOC | 35,870 |
| 測試檔案 | 114 |
| 測試函式 | 1,544 |
| API 端點 | 117（16 路由模組）|
| 策略 | 13（11 standalone + alpha + multi_asset） |
| Alpha 因子 | 83（66 技術 + 17 基本面）|
| 組合最佳化方法 | 14 |
| 風控規則 | 12 |
| 本地價格 Parquet | 895 支台股 + 408 基本面 |

### 模組架構

```
src/
├── core/           (7)   模型、設定、日誌、交易日曆、交易流程
├── alpha/          (31)  Alpha 研究管線 + Auto-Alpha 自動因子挖掘（9 子模組）
├── strategy/       (19)  83 因子 + 3 最佳化器 + Registry
├── portfolio/      (4)   14 種組合最佳化 + 5 種風險模型 + 匯率避險
├── allocation/     (4)   戰術資產配置（4 總經因子）
├── risk/           (5)   12 規則 + Kill Switch + RealtimeRiskMonitor
├── execution/      (14)  SimBroker + PaperBroker + SinopacBroker + TWAP + OMS + 對帳
├── backtest/       (13)  BacktestEngine + 40+ 指標 + Walk-Forward/PBO/DSR + Validator 15 項
├── data/           (15)  Yahoo/FinMind/FRED/Shioaji + Parquet 快取
├── api/            (25)  FastAPI REST + WebSocket + JWT/RBAC + Prometheus
├── scheduler/      (2)   APScheduler（統一交易管線 + 每日對帳）
├── notifications/  (6)   Discord / LINE / Telegram
├── instrument/     (3)   InstrumentRegistry + 自動推斷資產類型
└── cli/            (2)   CLI 工具

strategies/         (11)  9 內建 + revenue_momentum_hedged + multi_strategy_combo
apps/web/                 React 18 + Vite + Tailwind（11 頁面）
apps/android/             Kotlin + Jetpack Compose + Material 3
apps/shared/              TypeScript 共用套件
```

### 核心設計決策

| 決策 | 說明 |
|------|------|
| 策略回傳權重 | `on_bar() → dict[str, float]`，不是訂單。`weights_to_orders()` 負責轉換 |
| 風控是純函式工廠 | `src/risk/rules.py`，無繼承。第一個 REJECT 即停止 |
| 所有金額用 Decimal | 不用 float，避免精度問題 |
| 時區 tz-naive | 所有 DatetimeIndex 移除時區，台股判斷用 UTC+8 |
| 本地優先數據 | 先讀 `data/market/*.parquet`，不存在才下載 |
| 原子寫入 | portfolio 持久化用 tmp+rename，防 crash 損壞 |

---

## 三、13 個策略

| # | 策略 | 類型 | 說明 |
|---|------|------|------|
| 1 | Momentum | 規則型 | 12-1 月動量 |
| 2 | Mean Reversion | 規則型 | Z-score 均值回歸 |
| 3 | RSI Oversold | 規則型 | RSI < 30 |
| 4 | MA Crossover | 規則型 | 均線交叉 |
| 5 | Multi-Factor | 規則型 | 動量+價值+品質 |
| 6 | Pairs Trading | 規則型 | 共整合 + Kalman |
| 7 | Sector Rotation | 規則型 | 板塊動量輪動 |
| 8 | **Revenue Momentum** | 條件篩選 | revenue_acceleration 排序，ICIR 0.476 |
| 9 | **Revenue Momentum Hedged** | 條件篩選 | **主策略** — #8 + 空頭避險，Validator 14/15 |
| 10 | Trust Follow | 條件篩選 | 投信跟單 + 營收成長 |
| 11 | Multi-Strategy Combo | 組合型 | 多策略等權 |
| 12 | Alpha Pipeline | 管線型 | 可配置因子 + 中性化 + 成本感知 |
| 13 | Multi-Asset | 管線型 | 戰術配置 → Alpha → 組合最佳化 |

**核心結論**：台股 Alpha 在營收，不在價格。`revenue_acceleration` 是修正後最強因子（ICIR 0.476）。

---

## 四、三條獨立執行管線

### 1. 統一交易管線（Trading Pipeline）

```bash
# 啟用排程
QUANT_SCHEDULER_ENABLED=true
QUANT_ACTIVE_STRATEGY=revenue_momentum_hedged
QUANT_TRADING_PIPELINE_CRON="30 8 11 * *"  # 每月 11 日 08:30

# 手動啟動
make api  # 或 make dev
```

**流程**：冪等性檢查 → 數據更新 → strategy.on_bar() → weights_to_orders → RiskEngine → ExecutionService → 持久化 → 通知

### 2. Autoresearch（自動因子挖掘）

```bash
# Docker 模式（推薦）
cd scripts/autoresearch
docker compose up -d
./loop-docker.ps1

# 非 Docker
claude -p scripts/autoresearch/program.md
```

**架構**：Karpathy 3 檔案（`evaluate.py` READ-ONLY + `factor.py` Agent 可改 + `program.md` 協議）

**閘門**：L1-L4 in-sample → L5 OOS holdout → 大規模 IC → Validator 15 項

### 3. Auto-Alpha API

```bash
POST /api/v1/auto-alpha/start
```

L5 通過 → 自動提交 → Validator ≥13/15 → Paper Deploy

---

## 五、使用方法

### 後端

```bash
# 安裝
pip install -e ".[dev]"

# 測試
make test                    # 1,725 tests
make lint                    # ruff + mypy

# 開發 API（port 8000）
make dev

# 回測
make backtest ARGS="--strategy revenue_momentum_hedged -u 2330.TW --start 2020-01-01 --end 2025-12-31"

# CLI
python -m src.cli.main backtest --strategy momentum -u AAPL --start 2023-01-01
python -m src.cli.main server
python -m src.cli.main status
python -m src.cli.main factors

# Docker
docker compose up -d         # API + PostgreSQL
```

### 前端

```bash
make install-apps            # bun install
make web                     # Web dev server (port 3000)
make web-typecheck           # TypeScript 檢查
cd apps/android && ./gradlew assembleDebug  # Android APK
```

### Paper Trading

```bash
# .env 設定
QUANT_MODE=paper
QUANT_SINOPAC_API_KEY=...
QUANT_SINOPAC_SECRET_KEY=...
QUANT_SCHEDULER_ENABLED=true

# 啟動
make api
# Portfolio 自動持久化到 data/paper_trading/portfolio_state.json
# Kill switch 5% 日回撤自動清倉
# 每日 14:30 自動對帳（reconcile）
```

### 關鍵 API 端點

| 端點 | 用途 |
|------|------|
| `POST /api/v1/auth/login` | JWT 登入 |
| `POST /api/v1/backtest` | 執行回測 |
| `POST /api/v1/strategy/rebalance` | 一鍵再平衡 |
| `GET /api/v1/execution/paper-trading/status` | Paper trading 狀態 |
| `POST /api/v1/auto-alpha/start` | 啟動自動因子研究 |
| `GET /api/v1/risk/realtime` | 即時風控狀態 |
| `POST /api/v1/risk/kill-switch/reset` | 手動重置 kill switch |
| `POST /api/v1/execution/reconcile` | 手動對帳 |
| `GET /metrics` | Prometheus 指標 |

---

## 六、風控與安全

### Kill Switch（雙路徑）

- **路徑 A**：`app.py` 每 5 秒輪詢 `daily_drawdown > 5%`（`mutation_lock` 保護）
- **路徑 B**：`realtime.py` 每 tick 監控 `intraday_drawdown > 5%`（`mutation_lock` + `kill_switch_fired` 雙重檢查）
- **觸發後**：停策略 → 清倉 → 持久化 → WebSocket + Discord/LINE/Telegram 通知
- **重置**：`POST /risk/kill-switch/reset`

### 12 條風控規則

- **個股**：5% 最大持倉、2% NAV 最大單筆、10% ADV 量限、±10% 漲跌停
- **組合**：3% 日回撤、100 筆日交易上限
- **跨資產**：40% 資產類別、60% 幣別、1.5x 槓桿

### 安全

JWT + API Key 雙認證、5 級角色、PBKDF2 密碼、帳號鎖定、限流、稽核日誌、非 root Docker

---

## 七、Prometheus Metrics

集中模組 `src/metrics.py`，透過 `/metrics` 端點暴露：

| Metric | 類型 | 說明 |
|--------|------|------|
| `kill_switch_triggers_total` | Counter | Kill switch 觸發次數（label: path=poll/tick）|
| `risk_alerts_total` | Counter | 風控告警次數（label: severity）|
| `intraday_drawdown_pct` | Gauge | 日內回撤百分比（每 tick 更新）|
| `nav_current` | Gauge | 當前 NAV |
| `reconcile_runs_total` | Counter | 對帳執行次數（label: status）|
| `reconcile_mismatches` | Gauge | 最近一次對帳差異數 |
| `pipeline_runs_total` | Counter | 交易管線執行次數 |
| `pipeline_duration_seconds` | Histogram | 管線執行時間 |
| `orders_submitted_total` | Counter | 下單次數（label: side）|
| `orders_rejected_total` | Counter | 被拒絕訂單數 |
| `backtest_duration_seconds` | Histogram | 回測執行時間 |

---

## 八、因子研究結論

基於 17 次實驗、40 天營收延遲修正、大規模驗證（865+ 支）：

| 結論 | 證據 |
|------|------|
| **台股 alpha 在營收，不在價格** | 4 營收因子 ICIR > 0.15；66 price-volume 全 < 0.3 |
| **revenue_acceleration 是最強因子** | ICIR 0.476（20d）/ 0.646（60d） |
| **revenue_yoy 被高估** | 修正前 0.674 → 修正後 0.188（-72%，40 天延遲）|
| **營收因子不衰減** | 5d→60d ICIR 持續增強 |
| **成本是台股瓶頸** | 換手率 > 10% 的因子全部虧損 |
| **1/N 等權極難打敗** | DeMiguel 2009 在台股完全驗證 |

---

## 九、代辦事項

### HIGH — 阻塞 Live Trading

| 項目 | 說明 | 阻塞原因 |
|------|------|---------|
| **永豐金 CA 憑證** | 申請中 | 阻塞 live mode（非 simulation）|
| **Shioaji async fill callback** | 非 simulation 的異步成交回報未接線 | Live mode 成交確認 |
| **Paper trade vs 券商比對** | 需實際帳戶驗證 | 確認系統持倉與券商一致 |

### MEDIUM — 功能完善

| 項目 | Phase | 說明 |
|------|-------|------|
| **Phase N2 Step 5** | N2 | Web 重寫剩餘步驟 |
| **Phase Q2-Q3** | Q | 策略精煉（Q1 代碼 12/13 完成）|
| **存活者偏差不完整** | — | 有 40 支已下市，但缺歷史時點完整上市清單 |
| **`compute_forward_returns` 日期交集** | — | 大 universe 時用交集為空，核心函式待改用聯集 |
| **Pipeline metrics 埋點** | — | `src/metrics.py` 已定義，但 `execute_pipeline` 尚未埋入 |
| **Orders metrics 埋點** | — | `ORDERS_SUBMITTED/REJECTED` 已定義，尚未在 `execution/` 埋入 |
| **4 個 pre-existing test failures** | — | `test_auto_alpha_scheduler` / `test_auto_alpha_ws` 長期失敗 |

### LOW — 改善項目

| 項目 | 說明 |
|------|------|
| 跨市場驗證 | 只有台股，無法確認因子跨市場有效性 |
| 衝擊成本模型 | sqrt 滑點近似，未用 Almgren-Chriss 學術模型 |
| 獨立壓力情境 | 無獨立 stress scenario（如 2008 模擬）|
| SYSTEM_STATUS_REPORT 更新 | Phase V 改動後未更新 |
| BUG_HISTORY 更新 | 雙重清倉 race condition 應記錄 |

---

## 十、Phase 完成度

| 階段 | 狀態 | 核心內容 |
|------|:----:|---------|
| A~I | ✅ | 基礎建設 → Alpha 擴充 |
| K | ✅ | 數據品質 |
| L | ✅ | 策略轉型（6/7 驗證通過）|
| M | ✅ | 下行保護 |
| P | ✅ | 自動因子挖掘（Karpathy 3 檔案）|
| S | ✅ | 管線統一 |
| U | ✅ | Autoresearch 重構 |
| V | ✅ | Kill Switch debug + 對帳 + 通知 + metrics |
| X | ✅ | 防過擬合（L5 OOS holdout）|
| N | 🟢 | Paper Trading（持久化、kill switch、mutation lock）|
| N2 | 🟡 | Web 重寫（Step 1-4 完成）|
| Q | 🟡 | 策略精煉（Q1 完成）|
| R | 🟢 | 代碼審計（7 輪 88+ bug）|
| Y | 🟢 | Docker 容器化（已部署）|

---

## 十一、相關文件索引

| 文件 | 用途 |
|------|------|
| `CLAUDE.md` | 行為規範和開發規則 |
| `docs/claude/ARCHITECTURE.md` | 系統架構詳細描述 |
| `docs/claude/EXPERIMENT_STANDARDS.md` | 實驗方法論標準 |
| `docs/claude/SYSTEM_STATUS_REPORT.md` | 模組清單、測試覆蓋、功能矩陣 |
| `docs/claude/BUG_HISTORY.md` | 60+ 已修復 bug 分類 |
| `docs/plans/` | 27 個 Phase 獨立計畫書（A~Z）|
| `docs/research/` | 17 份實驗報告 + 研究總結 |
| `docs/guides/autoresearch-guide-zh.md` | Autoresearch 操作指南 |
| `.env.example` | 環境變數範本 |
