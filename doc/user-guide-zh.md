# 量化交易系統 — 用戶指南

## 1. 簡介

量化交易系統是一個基於 Python 的量化交易平台，支援回測、模擬交易與實盤交易。系統採用模組化架構，內建風控管理、因子庫以及 REST/WebSocket API。

**核心功能：**
- 事件驅動回測引擎，具備真實的滑價、手續費與稅金模擬
- 內建技術因子庫（動量、均值回歸、RSI、均線交叉等）
- 宣告式風控管理，含盤前檢查與緊急熔斷機制
- REST API + WebSocket 即時監控
- CLI 命令列工具：回測、因子分析、系統管理

## 2. 安裝

### 環境需求

- Python 3.12+
- PostgreSQL（選用，用於持久化儲存）
- Docker（選用，用於資料庫設定）

### 安裝步驟

```bash
# 安裝專案
cd Finance
pip install -e ".[dev]"

# 複製並編輯配置檔
cp .env.example .env
# 編輯 .env 中的設定

# （選用）啟動資料庫
docker compose up -d db
make migrate
```

### 系統配置

所有設定透過 `QUANT_` 前綴的環境變數控制。複製 `.env.example` 並依需求編輯：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `QUANT_MODE` | `backtest` | 運行模式：`backtest`（回測）、`paper`（模擬）、`live`（實盤） |
| `QUANT_DATABASE_URL` | `postgresql://...` | 資料庫連線字串 |
| `QUANT_DATA_SOURCE` | `yahoo` | 數據源：`yahoo`、`fubon`、`twse` |
| `QUANT_API_KEY` | `dev-key` | API 認證金鑰 |
| `QUANT_LOG_LEVEL` | `INFO` | 日誌等級 |
| `QUANT_COMMISSION_RATE` | `0.001425` | 券商手續費（0.1425%） |
| `QUANT_DEFAULT_SLIPPAGE_BPS` | `5.0` | 滑價（基點） |
| `QUANT_MAX_POSITION_PCT` | `0.05` | 單一持倉權重上限 |
| `QUANT_MAX_DAILY_DRAWDOWN_PCT` | `0.03` | 日回撤上限 |

## 3. 快速上手

### 執行回測

```bash
# 動量策略，美國科技股，週再平衡
python -m src.cli.main backtest \
    --strategy momentum \
    -u AAPL -u MSFT -u GOOGL -u AMZN -u META \
    --start 2023-01-01 \
    --end 2024-12-31 \
    --rebalance weekly \
    --validate
```

**參數說明：**

| 參數 | 簡寫 | 預設值 | 說明 |
|------|------|--------|------|
| `--strategy` | `-s` | `momentum` | 策略名稱 |
| `--universe` | `-u` | AAPL, MSFT, GOOGL, AMZN, META | 股票代碼（可重複指定） |
| `--start` | | `2020-01-01` | 開始日期 |
| `--end` | | `2024-12-31` | 結束日期 |
| `--cash` | `-c` | `10000000` | 初始資金 |
| `--rebalance` | `-r` | `weekly` | 再平衡頻率：`daily`（每日）、`weekly`（每週）、`monthly`（每月） |
| `--slippage` | | `5.0` | 滑價（基點） |
| `--validate` | `-v` | `False` | 是否執行回測驗證 |
| `--log-level` | `-l` | `INFO` | 日誌等級 |

### 輸出範例

```
═══ momentum_12_1 Backtest Result ═══
Period:        2023-01-03 ~ 2024-12-30
Initial Cash:  $10,000,000
Final NAV:     $11,694,031

Total Return:  +16.94%
Annual Return: +8.19%
Volatility:    7.73%
Sharpe Ratio:  1.06
Sortino Ratio: 0.99
Calmar Ratio:  1.02

Max Drawdown:  8.04%
Max DD Days:   87

Total Trades:  54
Win Rate:      64.7%
Total Comm.:   $25,962
```

### 查看因子值

```bash
python -m src.cli.main factors AAPL
```

顯示指定股票的當前因子值：動量、均值回歸（Z 分數）、波動率、RSI 及均線交叉。

### 查看系統狀態

```bash
python -m src.cli.main status
```

顯示當前配置：運行模式、數據源、API 端點、手續費率及風控限制。

## 4. 內建策略

### 動量策略（12-1）

經典的橫截面動量策略。

- **邏輯：** 買入過去 12 個月漲幅最大的股票，跳過最近 1 個月（避免短期反轉效應）。
- **參數：** `lookback=252`、`skip=21`、`max_holdings=10`
- **配置方式：** 信號加權，單檔上限 10%，總曝險 95%。
- **策略名稱：** `momentum` 或 `momentum_12_1`

### 均值回歸策略

統計型均值回歸策略。

- **邏輯：** 買入價格顯著偏離 20 日均線下方的股票（Z 分數 > 1.5 個標準差）。
- **參數：** `lookback=20`、`z_threshold=1.5`
- **配置方式：** 信號加權，單檔上限 8%，總曝險 90%，僅做多。
- **策略名稱：** `mean_reversion`

## 5. 啟動 API 伺服器

```bash
# 開發模式（含熱重載）
make dev

# 生產模式
make api

# 或透過 CLI
python -m src.cli.main server --host 0.0.0.0 --port 8000
```

啟動後：
- Swagger UI：`http://localhost:8000/docs`
- ReDoc：`http://localhost:8000/redoc`

### 認證方式

除健康檢查外，所有 API 請求皆需認證：

```bash
# API Key 認證
curl -H "X-API-Key: dev-key" http://localhost:8000/api/v1/system/status
```

## 6. 風控管理

系統在每筆訂單執行前強制執行以下風控規則：

| 規則 | 預設值 | 說明 |
|------|--------|------|
| 單檔權重上限 | 10% | 單一持倉不可超過 NAV 的 10% |
| 單筆金額上限 | 10% | 單筆訂單金額不可超過 NAV 的 10% |
| 日回撤限制 | 3% | 日虧損超過 3% 時禁止新下單 |
| 胖手指檢查 | 5% | 拒絕價格偏離市價超過 5% 的訂單 |
| 每日交易上限 | 100 次 | 每日最多 100 筆交易 |
| 訂單量 vs ADV | 10% | 下單量不可超過平均日成交量的 10% |

**緊急熔斷：** 日回撤達 5% 時自動觸發 — 取消所有掛單並停止所有策略。

## 7. 績效指標

回測引擎計算以下績效指標：

| 指標 | 說明 |
|------|------|
| 總報酬（Total Return） | 回測期間的累積報酬 |
| 年化報酬（Annual Return） | 年化報酬率（假設每年 252 個交易日） |
| Sharpe Ratio | 風險調整後報酬（年化報酬 / 波動率） |
| Sortino Ratio | 下行風險調整後報酬 |
| Calmar Ratio | 年化報酬 / 最大回撤 |
| 最大回撤（Max Drawdown） | 最大峰谷跌幅 |
| 最大回撤天數 | 最長回撤持續天數 |
| 波動率（Volatility） | 日報酬的年化標準差 |
| 勝率（Win Rate） | 盈利交易佔比 |
| 換手率（Turnover） | 年化投資組合換手率 |

### 回測驗證

啟用 `--validate` 時，系統會執行以下檢查：

- **非零交易：** 至少執行 1 筆交易
- **NAV 連續性：** 單日 NAV 變動未超過合理閾值
- **報酬合理性：** 年化報酬在可信範圍內
- **Sharpe 合理性：** Sharpe 比率在可信範圍內
- **成本影響：** 交易成本相對於報酬是合理的

## 8. 因子庫

可用於策略開發的技術因子：

| 因子 | 函式 | 主要參數 | 輸出 |
|------|------|----------|------|
| 動量 | `momentum()` | `lookback=252, skip=21` | 12-1 月報酬比率 |
| 均值回歸 | `mean_reversion()` | `lookback=20` | Z 分數（反轉：低值 = 買入訊號） |
| 波動率 | `volatility()` | `lookback=20` | 年化波動率 |
| RSI | `rsi()` | `period=14` | 相對強弱指標（0-100） |
| 均線交叉 | `moving_average_crossover()` | `fast=10, slow=50` | 快線/慢線比值 - 1 |
| 量價趨勢 | `volume_price_trend()` | `lookback=20` | 價格與成交量相關性 |

## 9. 交易成本模型

模擬引擎預設使用台灣股票市場的成本參數：

| 成本類型 | 預設值 | 說明 |
|----------|--------|------|
| 手續費 | 0.1425% | 買賣雙向收取 |
| 證交稅 | 0.3% | 僅賣出時收取（台灣證券交易稅） |
| 滑價 | 5 基點 | 買入價格上調，賣出價格下調 |

所有成本參數均可透過 CLI 參數或環境變數自訂。
