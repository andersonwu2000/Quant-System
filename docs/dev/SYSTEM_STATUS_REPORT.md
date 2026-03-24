# 系統現況追蹤報告書

> **專案名稱**: 多資產投資組合研究與優化系統
> **報告日期**: 2026-03-24
> **報告版本**: v2.0
> **目標定位**: 涵蓋台股、美股、ETF、期貨的投資組合研究與優化平台（債券/商品透過 ETF 代理），面向個人投資者與家族資產管理
> **當前階段**: Phase B 進行中（跨資產 Alpha：宏觀因子 + 跨資產信號 + 戰術配置）
> **代碼庫起始日期**: 2026-03-22
> **總提交次數**: 44 commits
> **當前分支**: master

---

## 目錄

1. [專案總覽](#1-專案總覽)
2. [架構概覽](#2-架構概覽)
3. [模組清單與程式碼統計](#3-模組清單與程式碼統計)
4. [後端模組盤點](#4-後端模組盤點)
5. [前端模組盤點](#5-前端模組盤點)
6. [基礎設施](#6-基礎設施)
7. [測試覆蓋](#7-測試覆蓋)
8. [CI/CD](#8-cicd)
9. [安全機制](#9-安全機制)
10. [已知缺陷](#10-已知缺陷)
11. [功能完成度](#11-功能完成度)
12. [差距分析](#12-差距分析)
13. [開發路線圖](#13-開發路線圖)

---

## 1. 專案總覽

### 1.1 產品定位

本系統的目標是成為**涵蓋多資產類別的投資組合研究與優化平台**，最終面向個人投資者與家族資產管理。

**可交易市場**：台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
**不納入**：直接債券交易（OTC）、實體商品、零售外匯（台灣法規限制）

**系統演進路線：**

```
[已完成] 股票交易系統          [已完成] Alpha 研究層        [進行中] 多資產擴展
────────────────────        ──────────────────        ─────────────────
✅ 回測引擎 + 7 策略          ✅ 因子中性化/正交化          • Instrument Registry
✅ 風控 + SimBroker            ✅ 分位數回測                 • 資產間配置 (Allocation)
✅ REST API + WebSocket        ✅ 成本感知組合建構            • 多資產組合最佳化
✅ Web + Mobile 前端           ✅ Alpha Pipeline             • 多幣別 Portfolio
✅ 通知 + 排程                 ✅ AlphaStrategy              • 跨資產風控
```

### 1.2 技術棧

| 層級 | 技術 |
|------|------|
| 後端 | Python 3.12, mypy strict, FastAPI + Uvicorn |
| 資料庫 | PostgreSQL 16 / SQLite, SQLAlchemy 2.0 + Alembic |
| 前端 | React 18 + Vite 5 + Tailwind (Web), React Native + Expo 52 (Mobile) |
| 共享 | @quant/shared (TypeScript 型別、API 客戶端、WebSocket) |
| 基建 | Docker, GitHub Actions (9 jobs), Prometheus + structlog |

### 1.3 專案結構

```
src/                         # Python 後端 (79 檔, ~12,200 LOC)
├── alpha/                   #   Alpha 研究層 (11 檔, ~2,200 LOC)
├── domain/                  #   領域模型與持久化
├── strategy/                #   策略引擎、因子庫、研究工具
├── risk/                    #   風險引擎與規則
├── execution/               #   模擬券商與訂單管理
├── backtest/                #   回測引擎與分析
├── data/                    #   數據源與快取
├── api/                     #   REST API + WebSocket (含 /alpha 端點)
├── notifications/           #   多渠道通知
├── scheduler/               #   排程任務
└── cli/                     #   命令列工具
tests/                       # 測試 (38 檔, ~6,700 LOC)
strategies/                  # 策略插件 (8 檔, ~615 LOC)
apps/                        # 前端 monorepo
├── shared/                  #   @quant/shared
├── web/                     #   React Web (含 Alpha Research 頁面)
└── mobile/                  #   React Native (含 Alpha tab)
```

---

## 2. 架構概覽

### 2.1 現有架構

```
Alpha 研究層 (src/alpha/)
  因子 Pipeline → 中性化 → 正交化 → 合成 → 分位數驗證 → 組合建構
      ↓
  AlphaStrategy → dict[str, float] 權重
      ↓
交易系統
  DataFeed → Strategy.on_bar() → weights_to_orders()
  → RiskEngine → SimBroker → Trade → Portfolio
```

### 2.2 目標架構（多資產）

```
第三層：Multi-Asset Portfolio Optimizer
  跨資產風險預算 │ 幣別對沖 │ 槓桿約束 │ 再平衡
      ↑
第二層：雙軌 Alpha
  ┌──────────────────┐  ┌──────────────────────┐
  │ 資產內 Alpha      │  │ 資產間 Alpha (NEW)    │
  │ (現有 src/alpha/) │  │ src/allocation/       │
  │ 股票/期貨/債券選標的│  │ 宏觀因子 + 跨資產信號 │
  └──────────────────┘  └──────────────────────┘
      ↑
第一層：Instrument Registry + Multi-Market DataFeed
  台股 │ 美股 │ ETF (債券/商品代理) │ 期貨 (台/美)
```

詳見 `docs/dev/MULTI_ASSET_ARCHITECTURE.md`。

### 2.3 關鍵設計決策

| 決策 | 說明 |
|------|------|
| 策略回傳權重而非訂單 | `on_bar()` → `dict[str, float]`，解耦策略與執行 |
| 風險規則為純函式工廠 | 無繼承，`RiskRule` dataclass，可組合 |
| 金額使用 `Decimal` | 禁止 `float` |
| 時區正規化 | tz-naive UTC |
| 時間因果性 | Context 截斷至 `current_time` |
| Alpha 層獨立於 strategy/ | `src/alpha/` 為獨立模組 |
| Alpha 層保留不重做 | 橫截面因子研究是多資產中的資產內選擇能力 |
| 兩層配置架構 | 資產間（allocation）+ 資產內（alpha）分離 |

---

## 3. 模組清單與程式碼統計

### 3.1 後端

| 模組 | 檔案 | LOC | 說明 |
|------|------|-----|------|
| `src/alpha/` | 11 | ~2,200 | Alpha 研究層 (Pipeline, 中性化, 組合建構, regime, attribution) |
| `src/allocation/` | 4 | ~550 | 戰術資產配置 (宏觀因子, 跨資產信號, 戰術引擎) |
| `src/api/` | 18 | ~2,700 | REST API + WebSocket + Alpha + Allocation 端點 |
| `src/backtest/` | 6 | ~2,100 | 回測引擎、分析、報表、驗證 |
| `src/data/` | 12 | ~1,700 | 數據源、快取、品質檢查 |
| `src/strategy/` | 7 | ~1,500 | 策略引擎、因子庫 (含新增因子)、研究工具 |
| `src/domain/` | 3 | ~530 | 領域模型、持久化倉庫 |
| `src/risk/` | 4 | ~480 | 風險引擎、規則、監控 |
| `src/execution/` | 4 | ~370 | 模擬券商、OMS |
| `src/cli/` | 2 | ~300 | CLI 命令 (含 alpha 研究命令) |
| `src/notifications/` | 6 | ~250 | 通知渠道 |
| 其他 | 7 | ~470 | config, logging, scheduler |
| **後端合計** | **84** | **~12,950** | |

### 3.2 前端

| 套件 | 說明 |
|------|------|
| `apps/web/` | React Web — 9 頁 (含 Alpha Research)、18+ 共用元件 |
| `apps/mobile/` | React Native — 元件 + hooks (含 Alpha tab) |
| `apps/shared/` | @quant/shared — 型別、API 客戶端、WebSocket |

### 3.3 測試

| 分類 | 檔案 | 框架 |
|------|------|------|
| Python 單元/整合 | 39 | pytest (~7,100 LOC) |
| Web 單元 | 18 | Vitest + jsdom |
| Mobile 單元 | 14 | Jest |
| Shared 單元 | 4 | Vitest |
| Web E2E | 3 | Playwright |

### 3.4 總計

| 類別 | LOC |
|------|-----|
| 後端 + 策略 | ~12,800 |
| 前端 | ~11,000 |
| 測試 | ~10,000 |
| **總計** | **~34,000** |

---

## 4. 後端模組盤點

### 4.1 Alpha 研究層 (`src/alpha/`)

| 檔案 | 功能 |
|------|------|
| `universe.py` | 股票池篩選：流動性/市值/上市天數/數據完整性 |
| `neutralize.py` | 因子中性化：市場/行業/規模/行業+規模 + winsorize + standardize |
| `cross_section.py` | 分位數回測：N 分位收益、多空價差、單調性 |
| `turnover.py` | 換手率分析：成本侵蝕、盈虧平衡、淨 IC |
| `orthogonalize.py` | 正交化：Sequential (Gram-Schmidt) + Symmetric (PCA/ZCA) |
| `construction.py` | 成本感知組合建構：換手率懲罰、衰減混合 |
| `pipeline.py` | 端到端 Pipeline：研究報告 + 即時權重生成 + rolling IC 合成 |
| `strategy.py` | AlphaStrategy 適配器，已註冊至 registry |
| `regime.py` | 市場狀態識別與條件 IC |
| `attribution.py` | 因子歸因分析 |

### 4.2 戰術配置層 (`src/allocation/`) — Phase B NEW

| 檔案 | 功能 |
|------|------|
| `macro_factors.py` | 宏觀因子模型：成長/通膨/利率/信用 四因子 z-score |
| `cross_asset.py` | 跨資產信號：動量/波動率/均值回歸 per AssetClass |
| `tactical.py` | 戰術引擎：戰略配置 + 宏觀 + 跨資產 + regime → 資產類別權重 |

API 端點：`POST /api/v1/allocation` → `TacticalResponse`

### 4.3 策略引擎 (`src/strategy/`)

因子庫 (10+ 因子)：momentum, mean_reversion, volatility, rsi, ma_cross, vpt, reversal, illiquidity, ivol, skewness, max_ret + 基本面 (PE, PB, ROE)

最佳化器：equal_weight, signal_weight, risk_parity

策略註冊：7 預建策略 + alpha 策略，集中 registry

### 4.4 其他後端模組

| 模組 | 功能 |
|------|------|
| `domain/` | Instrument, Bar, Position, Order, Trade, Portfolio (T+N 交割) |
| `risk/` | RiskEngine (宣告式規則)、kill_switch (5% 熔斷)、RiskMonitor |
| `execution/` | SimBroker (滑點/手續費/稅)、OMS (訂單生命週期) |
| `backtest/` | 回測引擎 (7 輔助方法)、40+ 績效指標、HTML/CSV 報表、步進分析、驗證 |
| `data/` | Yahoo + FinMind 數據源、Parquet 快取、數據品質檢查 |
| `api/` | 9 路由模組 (含 alpha)、JWT/API Key 認證、WebSocket 4 頻道、Prometheus |
| `notifications/` | Discord / LINE / Telegram |
| `scheduler/` | APScheduler：每日快照、每週再平衡 |

---

## 5. 前端模組盤點

### 5.1 Web 頁面 (9 頁)

Dashboard, **Alpha Research**, Backtest, Portfolio, Orders, Strategies, Risk, Settings, Admin

**Alpha Research 頁面**：因子選擇 + 標的池選取 (230 支：美股/台股/ETF) + 研究配置 → IC 表格、IC 時序圖、分位數收益圖、合成 Alpha

### 5.2 Mobile

元件 12+、hooks 6、Victory Native 圖表、Expo SecureStore、離線偵測、Alpha tab

### 5.3 共享

TypeScript 型別 (含 Alpha 型別)、API 客戶端、WebSocket Manager、格式化工具

---

## 6. 基礎設施

| 項目 | 說明 |
|------|------|
| 資料庫 | PostgreSQL 16 / SQLite, Alembic 4 migrations |
| Docker | 多階段 Dockerfile, docker-compose (api + db) |
| 配置 | Pydantic Settings, `QUANT_` 前綴環境變數 |

---

## 7. 測試覆蓋

**後端**: 39 檔 — 含 9 個 Alpha 測試檔 + 1 個 Allocation 測試檔 (macro_factors, cross_asset, tactical)

**前端**: 18 Web + 14 Mobile + 4 Shared + 3 E2E

**缺口**: 無覆蓋率追蹤、無效能測試、無安全測試

---

## 8. CI/CD

9 jobs: backend-lint, backend-test, web-typecheck, web-test, web-build, shared-test, mobile-typecheck, mobile-test, e2e-test

**缺口**: 無覆蓋率上報、無 Docker 建置驗證、無 CD、無安全掃描

---

## 9. 安全機制

**已實作**: JWT + API Key 認證、5 級角色授權、PBKDF2 密碼、Token 撤銷、帳號鎖定、限流、CORS、審計日誌、非 root 容器、Expo SecureStore

**缺口**: HS256 → RS256、HTTPS、CSP、依賴掃描

---

## 10. 已知缺陷

### 10.1 架構設計缺陷

| 編號 | 嚴重度 | 狀態 | 說明 |
|------|--------|------|------|
| ~~D-01~~ | ~~致命~~ | ✅ 已修復 | `weights_to_orders()` 已支援合約乘數 (`multiplier`) |
| ~~D-02~~ | ~~致命~~ | ✅ 已修復 | `Portfolio.nav_in_base(fx_rates)` 支援多幣別 NAV |
| ~~D-03~~ | ~~致命~~ | ✅ 已修復 | BacktestEngine 偵測混幣別，載入 FX，建構 InstrumentRegistry |
| ~~D-04~~ | ~~高~~ | ✅ 已修復 | SimBroker 使用 per-instrument commission_rate/tax_rate |
| ~~D-05~~ | ~~高~~ | ✅ Phase B | 戰術配置層已實作 (`src/allocation/`) |
| ~~D-06~~ | ~~高~~ | ✅ 已修復 | InstrumentRegistry 已整合進 BacktestEngine |
| ~~D-07~~ | ~~中~~ | ✅ 已修復 | YahooFeed 加入重試 (3 次) + 限流 (0.5s) |
| D-08 | **中** | 延後 | Alpha Pipeline GIL 限制 |
| ~~D-09~~ | ~~低~~ | ✅ | 前端標的列表已擴展至 230 支 (US/TW/ETF) |
| ~~D-10~~ | ~~高~~ | ✅ 已修復 | 雙重 Instrument/AssetClass 定義已統一為 domain/models.py |

### 10.2 其他缺陷

| 編號 | 說明 |
|------|------|
| B-01 | WebSocket market 頻道未接入即時數據源 |
| B-02 | `.env.example` 列出 `fubon`/`twse` 但未實作 |
| B-03 | 排程器依賴 API 進程，無獨立 worker |

---

## 11. 功能完成度

### 11.1 後端功能

| 領域 | 完成度 | 備註 |
|------|--------|------|
| 回測引擎 | ✅ 完整 | 單策略/步進/驗證/報表/40+ 指標 |
| 數據源 | ✅ Yahoo + FinMind + FRED | 缺即時行情 |
| 策略框架 | ✅ 完整 | 7 策略 + alpha + 插件式載入 |
| Alpha 研究 (資產內) | ✅ 完整 | 中性化/正交化/分位數/換手率/Pipeline/regime/attribution |
| 資產間配置 | ✅ Phase B | 宏觀因子模型 + 跨資產信號 + 戰術配置引擎 + API |
| 多資產組合最佳化 | ❌ Phase C | Risk Parity, BL, 幣別對沖 |
| Instrument Registry | ✅ 已整合 | 自動推斷標的屬性，回測引擎已接入 |
| 多幣別 Portfolio | ✅ 已整合 | `nav_in_base()`, `currency_exposure()`, `cash_by_currency` |
| 風控 | ✅ 基礎完整 | 缺跨資產規則 (幣別/槓桿/久期) |
| 執行 | ✅ SimBroker | 缺真實券商、期貨展期 |
| 用戶/通知/API | ✅ 完整 | |

### 11.2 前端功能

| 頁面 | Web | Mobile |
|------|-----|--------|
| Dashboard / Alpha / Backtest / Portfolio / Orders / Strategies / Risk | ✅ | ✅ |
| Settings | ✅ | ⚠️ |
| Admin | ✅ | ❌ |
| i18n (en/zh) / 深色模式 / 離線 | ✅ | ✅ |

---

## 12. 差距分析

### 12.1 多資產核心差距 (P0)

| 差距 | 狀態 | 說明 |
|------|------|------|
| ~~Instrument Registry~~ | ✅ | 統一 Instrument 模型，InstrumentRegistry 已整合進回測引擎 |
| ~~多幣別 Portfolio~~ | ✅ | `cash_by_currency`, `nav_in_base()`, `currency_exposure()` |
| ~~宏觀數據源~~ | ✅ | FRED 數據源 (7+ 系列) |
| ~~管線整合~~ | ✅ | weights_to_orders 乘數、SimBroker 費率、回測 FX |
| ~~資產間配置層~~ | ✅ | 宏觀因子模型 + 跨資產信號 + 戰術配置引擎 (Phase B) |
| 多資產最佳化器 | ❌ | 無 Risk Parity / Black-Litterman / HRP |

### 12.2 實盤交易差距 (P1)

| 差距 | 說明 |
|------|------|
| 券商對接 | 僅 SimBroker |
| 即時行情 | market 頻道空殼 |
| Paper Trading | 配置項存在但無完整流程 |

### 12.3 基礎設施差距 (P2)

測試覆蓋率、HTTPS、CD、備份、Grafana

---

## 13. 開發路線圖

### Phase A：多資產基礎設施 + 管線整合 ✅ 已完成

✅ A1~A4：Instrument Registry、多幣別 Portfolio、DataFeed 擴展、FRED 數據源
✅ A5：管線整合（weights_to_orders 乘數、SimBroker 費率、多幣別 NAV、回測引擎 FX + Registry）
✅ A6：YahooFeed 重試/限流
✅ 模型統一：雙重 Instrument/AssetClass 合併為單一定義
✅ 死碼清理：移除 `combine_factors()` (93 LOC)、`revenue_momentum()` (20 LOC)

### Phase B：跨資產 Alpha ✅ 已完成

✅ B1：宏觀因子模型 (`src/allocation/macro_factors.py`) — 成長/通膨/利率/信用 四因子
✅ B2：跨資產信號 (`src/allocation/cross_asset.py`) — 動量/波動率/均值回歸
✅ B3：戰術配置引擎 (`src/allocation/tactical.py`) — 戰略 + 宏觀 + 跨資產 + regime → 權重
✅ API：`POST /api/v1/allocation` + 前端型別定義

### Phase C：多資產組合最佳化

Risk Parity / BL / HRP → 幣別對沖 → 兩層配置整合 → 再平衡邏輯

### Phase D：回測 + 風控升級

多幣別回測 → 期貨展期 → 跨資產風控 → 績效歸因 (配置/選股/匯率)

### Phase E：實盤 + 商業化

券商對接 → Paper/Live Trading → 前端多資產 UI → 合規

詳細開發計畫見 `docs/dev/DEVELOPMENT_PLAN.md`。

---

> **文件維護說明**: 本報告應在每次重大功能變更、架構調整或里程碑完成後更新。
