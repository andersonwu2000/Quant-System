# Quant Trading System

多資產投資組合研究與最佳化平台 — Monorepo 架構，整合 Python 後端、React 網頁儀表板與 Android 原生應用。預設對接台灣股市（手續費 0.1425%、證交稅 0.3%），透過 Yahoo Finance / FinMind 支援全球市場。

## 功能特色

### 策略與因子
- **83 個 Alpha 因子** — 66 技術因子（動量、均值回歸、RSI、Kakushadze 101 精選等）+ 17 基本面因子（PE/PB/ROE/營收動能/殖利率/法人籌碼）
- **9 種策略** — Momentum、MA Crossover、Mean Reversion、RSI Oversold、Multi-Factor、Pairs Trading、Sector Rotation、Alpha Pipeline、Multi-Asset
- **條件篩選策略** — 營收動能 + 投信跟單，支援 boolean filter 模式

### 投資組合最佳化
- **14 種最佳化方法** — 等權、反波動、風險平價、MVO、Black-Litterman、HRP、Robust、Resampled、CVaR、MaxDrawdown、MaxSharpe、全域最小變異、指數追蹤、半變異數
- **風險模型** — 歷史/EWM/Ledoit-Wolf 收縮/GARCH/PCA 因子模型共變異數 + VaR/CVaR + 邊際風險貢獻
- **幣別對沖** — 分層對沖比率 + 建議

### 回測與研究
- **回測引擎** — 嚴格時間因果律，模擬滑點、手續費、稅金（含最低手續費 NT$20）、T+N 交割
- **Alpha Pipeline** — IC/ICIR 分析、中性化、正交化、Rolling IC 加權、分位數回測、成本感知建構
- **實驗框架** — 平行 grid backtest（256+ 配置 × 5 期間）、Walk-Forward、CSCV/PBO 過擬合檢測
- **自動化 Alpha** — 排程執行、動態因子池、安全閘門、因子績效追蹤

### 風險管理
- **10 條宣告式規則** — 持倉上限、單筆限額、日回撤、肥手指偵測、Kill Switch + 冷靜期恢復
- **即時風控** — 2%/3%/5% 分級預警、WebSocket 推送

### 執行層
- **Shioaji 券商整合** — 永豐金 API（下單/帳務/Scanner/即時行情）
- **TWAP 拆單** — 大單自動分割
- **Paper Trading** — 模擬交易完整循環

### 數據
- **多源接入** — Yahoo Finance、FinMind（8 種台股數據集）、FRED 宏觀數據、Shioaji 即時行情
- **本地優先** — data/market/ Parquet 永久存儲，避免重複下載
- **數據品質** — 7 項 OHLCV 檢查 + 除權息精確比對 + 基本面異常值過濾 + 停牌偵測

### 平台
- **103 個 API 端點** — FastAPI 非同步框架，JWT + API Key 雙模認證，五層角色權限
- **WebSocket** — portfolio / alerts / orders / market 四頻道即時推送
- **Web 儀表板** — React 18 + Vite + Tailwind，11 頁面，中/英雙語
- **Android App** — Kotlin + Jetpack Compose + Material 3
- **CLI 工具** — 回測、服務啟動、狀態查詢、因子列表
- **通知** — Discord / LINE / Telegram

## 技術棧

| 層級 | 技術 |
|------|------|
| 後端 | Python 3.12、FastAPI、SQLAlchemy、Alembic |
| 資料庫 | PostgreSQL 16（開發用 SQLite） |
| 網頁前端 | React 18、Vite、Tailwind CSS、TypeScript |
| Android | Kotlin、Jetpack Compose、Material 3、Hilt DI |
| 共用套件 | `@quant/shared`（bun workspace） |
| 資料來源 | Yahoo Finance、FinMind、FRED、Shioaji |
| 券商 | Shioaji（永豐金證券 API） |
| 部署 | Docker、Docker Compose、GitHub Actions CI（9 jobs） |
| 測試 | pytest（1,298 tests）、Vitest、Playwright E2E |

## 專案結構

```
├── src/                      # Python 後端（~150 檔，~27K LOC）
│   ├── api/                  #   FastAPI 路由（15 模組，103 端點）、認證、WebSocket
│   ├── alpha/                #   Alpha 研究：Pipeline、Regime、Attribution、自動化
│   ├── allocation/           #   戰術配置：宏觀因子、跨資產信號
│   ├── portfolio/            #   最佳化（14 方法）、風險模型、幣別對沖
│   ├── strategy/             #   策略基底、因子庫（83 因子）、研究工具
│   ├── backtest/             #   回測引擎、實驗框架、報告產生
│   ├── risk/                 #   風險引擎、即時監控
│   ├── execution/            #   SimBroker、SinopacBroker、TWAP、OMS
│   ├── data/                 #   DataFeed ABC、Yahoo/FinMind/FRED/Shioaji
│   ├── core/                 #   模型、設定、日誌、交易日曆、Trading Pipeline
│   ├── notifications/        #   Discord / LINE / Telegram
│   └── scheduler/            #   APScheduler 排程
├── strategies/               # 使用者自訂策略（9 個內建）
├── tests/                    # 單元測試（1,298 tests）
├── scripts/                  # 工具腳本（因子分析、數據下載、回測實驗）
├── migrations/               # 資料庫遷移（Alembic）
├── data/
│   ├── market/               # 本地 OHLCV Parquet（149 檔）
│   └── fundamental/          # 基本面 + 籌碼面 Parquet（408 檔）
├── apps/
│   ├── shared/               # @quant/shared — 共用型別、API Client、WebSocket
│   ├── web/                  # React 網頁儀表板（11 頁面）
│   └── android/              # Android 原生應用（Kotlin + Compose）
└── docs/                     # 文件 + 實驗報告 + 開發計畫
```

## 快速開始

### 環境需求

- Python 3.12+
- [bun](https://bun.sh/)（前端套件管理器）
- PostgreSQL 16（或使用 Docker / SQLite 開發）

### 安裝

```bash
# 取得原始碼
git clone https://github.com/andersonwu2000/Quant-System.git
cd Quant-System

# 安裝後端依賴
pip install -r requirements.txt

# 安裝前端依賴
make install-apps

# 設定環境變數
cp .env.example .env
# 編輯 .env，設定 QUANT_API_KEY、QUANT_FINMIND_TOKEN 等

# 資料庫遷移
make migrate
```

### 使用 Docker

```bash
docker compose up -d    # 啟動 API（port 8000）+ PostgreSQL
```

### 啟動服務

```bash
# 全端啟動（後端 + 網頁前端）
make start

# 或分別啟動
make dev                # 後端 API，熱重載（port 8000）
make web                # 網頁前端（port 3000）

# Windows
scripts/start.bat       # 在獨立視窗中啟動後端與前端
```

## 使用方式

### 執行回測

```bash
# CLI
python -m src.cli.main backtest \
  --strategy momentum \
  -u 2330.TW -u 2317.TW -u 2454.TW \
  --start 2023-01-01 --end 2024-12-31

# Make
make backtest ARGS="--strategy mean_reversion -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31"
```

### 因子分析

```bash
# 全因子 IC 分析（66 技術因子 × TW50）
python -m scripts.run_factor_analysis

# 基本面因子 IC 分析（17 因子 × 142 台股）
python -m scripts.run_fundamental_analysis

# FinMind 數據下載
python -m scripts.download_finmind_data --dataset all --start 2019-01-01
```

### CLI 指令

```bash
python -m src.cli.main backtest   # 執行回測
python -m src.cli.main server     # 啟動 API 伺服器
python -m src.cli.main status     # 查詢系統狀態
python -m src.cli.main factors    # 列出可用因子
```

## API 端點

基礎路徑：`http://localhost:8000/api/v1`（共 103 個端點）

### 認證與管理

| 端點 | 說明 |
|------|------|
| `POST /auth/login` | 登入（帳密 / API Key） |
| `POST /auth/logout` | 登出撤銷 Token |
| `GET /admin/users` | 使用者列表 |
| `POST /admin/users` | 建立使用者 |

### 投資組合

| 端點 | 說明 |
|------|------|
| `GET /portfolio` | 投組概覽 |
| `GET /portfolio/positions` | 持倉明細 |
| `POST /portfolio/saved` | 建立持久化投組 |
| `POST /portfolio/optimize` | **14 種最佳化方法** |
| `POST /portfolio/risk-analysis` | VaR/CVaR/風險貢獻 |
| `POST /portfolio/hedge-recommendations` | 幣別對沖建議 |

### Alpha 研究

| 端點 | 說明 |
|------|------|
| `POST /alpha` | 提交 Alpha 研究任務 |
| `POST /alpha/ic-analysis` | 單因子 IC/ICIR 分析 |
| `POST /alpha/turnover-analysis` | 換手率 + 成本拖累 |
| `POST /alpha/attribution` | 報酬歸因分解 |
| `GET /alpha/regime` | 市場狀態分類 |

### 回測

| 端點 | 說明 |
|------|------|
| `POST /backtest` | 提交回測 |
| `POST /backtest/walk-forward` | Walk-Forward 分析 |
| `POST /backtest/grid-search` | 平行 Grid Backtest |
| `POST /backtest/kfold` | K-Fold 交叉驗證 |
| `POST /backtest/pbo` | PBO 過擬合檢測 |

### 風險管理

| 端點 | 說明 |
|------|------|
| `GET /risk/rules` | 風控規則列表 |
| `PUT /risk/config` | 更新風控閾值 |
| `POST /risk/kill-switch` | 緊急停損 |
| `GET /risk/realtime` | 即時風控狀態 |

### 策略

| 端點 | 說明 |
|------|------|
| `GET /strategies` | 策略列表 |
| `GET /strategies/factors` | **83 個因子 Registry** |
| `POST /strategies/{id}/start` | 啟動策略 |

### 執行

| 端點 | 說明 |
|------|------|
| `GET /execution/status` | 執行狀態 |
| `POST /execution/smart-order` | TWAP 拆單 |
| `GET /execution/market-hours` | 交易時段 |

### 數據

| 端點 | 說明 |
|------|------|
| `POST /data/quality-check` | 數據品質檢查 |
| `GET /data/fundamentals/{symbol}` | 基本面指標 |
| `GET /data/cache-status` | 本地快取狀態 |
| `GET /data/macro/{indicator}` | FRED 宏觀數據 |

### 配置與戰術

| 端點 | 說明 |
|------|------|
| `POST /allocation` | 戰術資產配置 |
| `GET /allocation/macro-factors` | 宏觀因子 z-scores |
| `GET /allocation/cross-asset-signals` | 跨資產信號 |

### 自動化 Alpha

| 端點 | 說明 |
|------|------|
| `GET /auto-alpha/status` | 運行狀態 |
| `POST /auto-alpha/run-now` | 立即執行 |
| `GET /auto-alpha/factor-pool` | 動態因子池 |
| `GET /auto-alpha/safety-gates` | 安全閘門 |

### 掃描器

| 端點 | 說明 |
|------|------|
| `GET /scanner/top-volume` | 成交量排行 |
| `GET /scanner/active-universe` | 活躍股票池 |

### 系統

| 端點 | 說明 |
|------|------|
| `GET /system/health` | 健康檢查 |
| `GET /system/alerts` | 系統告警 |
| `GET /scheduler/jobs` | 排程任務 |
| `POST /scheduler/notify` | 手動通知 |
| `WS /ws/{channel}` | WebSocket 即時推送 |

## 新增策略

```python
# strategies/my_strategy.py
from src.strategy.base import Strategy, Context

class MyStrategy(Strategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        # 回傳目標權重
        return {"2330.TW": 0.5, "2317.TW": 0.5}
```

在 `src/api/routes/backtest.py` 與 `src/cli/main.py` 的 `_resolve_strategy()` 中註冊。

## 環境變數

所有設定透過 `QUANT_` 前綴環境變數或 `.env` 檔案管理，詳見 `.env.example`。

| 變數 | 預設 | 說明 |
|------|------|------|
| `QUANT_MODE` | `backtest` | 運行模式：`backtest` / `paper` / `live` |
| `QUANT_DATA_SOURCE` | `yahoo` | 資料來源：`yahoo` / `finmind` / `shioaji` |
| `QUANT_FINMIND_TOKEN` | — | FinMind API Token（提高速率限制） |
| `QUANT_API_KEY` | — | API 認證金鑰 |
| `QUANT_COMMISSION_RATE` | `0.001425` | 券商手續費率 |
| `QUANT_MAX_POSITION_PCT` | `0.05` | 單一持倉權重上限 |
| `QUANT_MAX_DAILY_DRAWDOWN_PCT` | `0.03` | 日內回撤上限 |
| `QUANT_DEFAULT_SLIPPAGE_BPS` | `5.0` | 滑點（基點） |
| `QUANT_LOG_LEVEL` | `INFO` | 日誌等級 |

## 開發指引

```bash
make test              # 執行全部測試（1,298 tests）
make lint              # ruff + mypy strict
make web-typecheck     # TypeScript 型別檢查
make web-test          # Vitest
```

### 角色權限

| 角色 | 權限 |
|------|------|
| `viewer` | 唯讀 |
| `researcher` | + 回測、因子分析 |
| `trader` | + 下單、啟停策略 |
| `risk_manager` | + 風控規則、Kill Switch |
| `admin` | 全部 + 使用者管理 |

### 架構設計

```
DataFeed → Strategy.on_bar() → 目標權重 → RiskEngine → Broker → Trade → Portfolio
```

- **策略回傳權重字典**（`dict[str, float]`），不直接產生訂單
- **風控規則為純函式工廠** — 循序評估，首條 REJECT 即中止
- **時間因果律** — `Context` 截斷資料至當前時間點
- **金額一律 `Decimal`** — 禁止 `float` 處理金融數據
- **本地優先** — data/market/ Parquet 永久存儲，有就用本地

### CI/CD

GitHub Actions 9 jobs：backend-lint、backend-test、web-typecheck、web-test、web-build、shared-test、android-build、e2e-test、release（含 APK）

## 文件

| 文件 | 說明 |
|------|------|
| `docs/dev/DEVELOPMENT_PLAN.md` | 開發計畫 v10（Phase A~N） |
| `docs/dev/SYSTEM_STATUS_REPORT.md` | 系統狀態報告 |
| `docs/dev/plans/` | 各階段詳細計畫書 |
| `docs/dev/test/` | 實驗報告（15+ 次因子分析） |
| `docs/api-reference-zh.md` | API 參考（繁中） |
| `docs/developer-guide-zh.md` | 開發者指南（繁中） |
| `docs/user-guide-zh.md` | 使用者指南（繁中） |

## 授權

私有專案，保留所有權利。
