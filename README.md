# Quant Trading System

量化交易系統平台 — 採用 Monorepo 架構，整合 Python 後端、React 網頁儀表板與 React Native 行動應用程式。預設對接台灣股市（手續費 0.1425%、證交稅 0.3%），透過 Yahoo Finance 支援全球市場。

## 功能特色

- **策略引擎** — 以目標權重驅動，內建 Momentum / Mean Reversion 策略，可自訂擴充
- **回測引擎** — 嚴格時間因果律，模擬滑點、手續費、稅金，產出 Sharpe / Sortino / Max Drawdown 等績效指標
- **風險管理** — 6 條宣告式規則（持倉上限、單筆限額、日回撤、肥手指偵測…）+ Kill Switch 緊急停損
- **即時監控** — WebSocket 推送投組、警報、訂單、行情四頻道
- **多端應用** — Web 儀表板（中/英雙語）+ 行動 App，共用 `@quant/shared` 型別與 API Client
- **REST API** — FastAPI 非同步框架，JWT 認證，五層角色權限（viewer → admin）
- **CLI 工具** — 回測執行、啟動服務、系統狀態查詢、因子列表

## 技術棧

| 層級 | 技術 |
|------|------|
| 後端 | Python 3.12、FastAPI、SQLAlchemy、Alembic |
| 資料庫 | PostgreSQL 16 |
| 網頁前端 | React 18、Vite、Tailwind CSS、TypeScript |
| 行動應用 | React Native 0.76、Expo 52、TypeScript |
| 共用套件 | `@quant/shared`（bun workspace） |
| 資料來源 | Yahoo Finance（含本地檔案快取） |
| 部署 | Docker、Docker Compose、GitHub Actions CI |

## 專案結構

```
├── src/                  # Python 後端核心
│   ├── api/              #   FastAPI 路由、認證、WebSocket
│   ├── backtest/         #   回測引擎與績效分析
│   ├── strategy/         #   策略基底類別、因子庫、最佳化器
│   ├── risk/             #   風險引擎與宣告式規則
│   ├── execution/        #   模擬券商（SimBroker）、訂單管理系統
│   ├── data/             #   資料來源（Yahoo Finance）與儲存
│   ├── domain/           #   領域模型（Position, Order, Portfolio...）
│   └── cli/              #   命令列介面（Typer）
├── strategies/           # 使用者自訂策略
├── tests/                # 單元測試與整合測試（pytest）
├── migrations/           # 資料庫遷移（Alembic）
├── apps/
│   ├── shared/           # @quant/shared — 共用型別、API Client、WebSocket、工具函式
│   ├── web/              # React 網頁儀表板
│   └── mobile/           # React Native 行動應用
└── doc/                  # 專案文件
```

## 快速開始

### 環境需求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（Python 套件管理器）
- [bun](https://bun.sh/)（前端套件管理器）
- PostgreSQL 16（或使用 Docker）

### 安裝

```bash
# 取得原始碼
git clone https://github.com/andersonwu2000/Portfolio.git
cd Portfolio

# 安裝後端依賴
uv sync
uv sync --extra dev   # 包含開發工具（pytest, ruff, mypy）

# 安裝前端依賴
make install-apps

# 設定環境變數
cp .env.example .env
# 編輯 .env，設定 QUANT_DATABASE_URL、QUANT_API_KEY 等

# 資料庫遷移（本地 PostgreSQL）
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

# 或分別啟動：
make dev                # 後端 API，支援熱重載（port 8000）
make web                # 網頁前端開發伺服器（port 3000）
make mobile             # Expo 行動端開發伺服器

# Windows 使用者
scripts/start.bat       # 在獨立視窗中啟動後端與前端
```

## 使用方式

### 執行回測

```bash
# 透過 CLI
python -m src.cli.main backtest \
  --strategy momentum \
  -u AAPL -u MSFT -u GOOGL \
  --start 2023-01-01 --end 2024-12-31

# 透過 Make（台股範例）
make backtest ARGS="--strategy mean_reversion -u 2330.TW -u 2317.TW --start 2023-01-01 --end 2024-12-31"
```

### CLI 指令

```bash
python -m src.cli.main backtest   # 執行回測
python -m src.cli.main server     # 啟動 API 伺服器
python -m src.cli.main status     # 查詢系統狀態
python -m src.cli.main factors    # 列出可用因子
```

### API 端點

基礎路徑：`http://localhost:8000/api/v1`

| 端點 | 說明 |
|------|------|
| `POST /auth/login` | 登入取得 JWT Token |
| `POST /auth/logout` | 登出並撤銷 Token |
| `GET /portfolio` | 投資組合概覽 |
| `GET /portfolio/positions` | 所有持倉明細 |
| `GET /strategies` | 策略列表 |
| `POST /strategies/{id}/start` | 啟動策略 |
| `POST /strategies/{id}/stop` | 停止策略 |
| `POST /backtest` | 提交非同步回測任務 |
| `GET /backtest/{task_id}` | 查詢回測結果 |
| `GET /risk/rules` | 風控規則列表 |
| `PUT /risk/rules/{name}` | 啟用/停用規則 |
| `POST /risk/kill-switch` | 緊急停損開關 |
| `GET /orders` | 訂單紀錄（支援分頁與篩選） |
| `GET /system/health` | 健康檢查（免認證） |
| `GET /system/status` | 系統狀態 |
| `GET /system/metrics` | 系統指標 |
| `WS /ws/{channel}` | 即時推送（portfolio / alerts / orders / market） |

## 新增策略

1. 在 `strategies/` 目錄建立新檔案：

```python
from src.strategy.base import Strategy, Context

class MyStrategy(Strategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        # 回傳目標權重，例如 {"AAPL": 0.5, "MSFT": 0.5}
        prices = ctx.get_prices()
        # ... 你的策略邏輯 ...
        return weights
```

2. 在 `src/api/routes/backtest.py` 與 `src/cli/main.py` 的 `_resolve_strategy()` 中註冊新策略。

## 環境變數設定

所有設定透過 `QUANT_` 前綴環境變數或 `.env` 檔案管理，詳見 `.env.example`。

| 變數名稱 | 預設值 | 說明 |
|----------|--------|------|
| `QUANT_MODE` | `backtest` | 運行模式：`backtest` / `paper` / `live` |
| `QUANT_DATABASE_URL` | — | PostgreSQL 連線字串 |
| `QUANT_DATA_SOURCE` | `yahoo` | 資料來源：`yahoo` / `fubon` / `twse` |
| `QUANT_API_PORT` | `8000` | API 伺服器埠號 |
| `QUANT_API_KEY` | — | API 認證金鑰 |
| `QUANT_COMMISSION_RATE` | `0.001425` | 券商手續費率 |
| `QUANT_MAX_POSITION_PCT` | `0.05` | 單一持倉權重上限（5%） |
| `QUANT_MAX_DAILY_DRAWDOWN_PCT` | `0.03` | 日內回撤上限（3%） |
| `QUANT_DEFAULT_SLIPPAGE_BPS` | `5.0` | 滑點（基點） |
| `QUANT_LOG_LEVEL` | `INFO` | 日誌等級 |
| `QUANT_LOG_FORMAT` | `text` | 日誌格式：`text` / `json` |

## 開發指引

### 常用指令

```bash
make test              # 執行全部測試
make lint              # 程式碼檢查（ruff + mypy strict）
make web-typecheck     # 網頁前端 TypeScript 型別檢查
make mobile-typecheck  # 行動端 TypeScript 型別檢查
```

### 架構設計

```
DataFeed → Strategy.on_bar() → 目標權重 → RiskEngine → SimBroker → Trade → Portfolio 更新
```

核心設計原則：

- **策略回傳權重字典**（`dict[str, float]`），不直接產生訂單
- **風控規則為純函式工廠** — 無繼承，循序評估，首條 REJECT 即中止
- **時間因果律** — 回測中 `Context` 將資料截斷至當前時間點，防止未來資訊洩漏
- **金額一律使用 `Decimal`** — 禁止 `float` 處理金融數據
- **平台適配器模式** — 各平台注入自身的 `ClientAdapter`，共用邏輯集中在 `@quant/shared`

### 風控規則

| 規則 | 說明 | 預設閾值 |
|------|------|----------|
| `max_position_weight` | 單一標的持倉權重上限 | 5% |
| `max_order_notional` | 單筆訂單占 NAV 比例上限 | 2% |
| `daily_drawdown_limit` | 日內回撤警戒線 | 3% |
| `fat_finger_check` | 價格異常偏離偵測 | 5% |
| `max_daily_trades` | 每日交易次數上限 | 100 筆 |
| `max_order_vs_adv` | 訂單量占日均成交量比例 | 10% |

### CI/CD

GitHub Actions 自動化流程包含：

- **backend-lint** — ruff 檢查 + mypy 嚴格模式
- **backend-test** — pytest 單元測試
- **web-typecheck** — TypeScript 型別檢查
- **web-build** — 正式環境建置（依賴 typecheck 通過）
- **mobile-typecheck** — 行動端 TypeScript 型別檢查

## 授權

私有專案，保留所有權利。
