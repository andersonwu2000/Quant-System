# 量化交易系統 — 用戶指南

## 1. 簡介

量化交易系統是一個基於 Python 的量化交易平台，支援回測、模擬交易與實盤交易。Monorepo 架構包含 Python 後端、React Web 儀表板與 Android 原生 App。系統採用模組化設計，內建風控管理、因子庫以及 REST/WebSocket API。

**核心功能：**
- 事件驅動回測引擎，具備真實的滑價、手續費與稅金模擬
- 83 個內建因子（66 價量 + 17 基本面），含 Alpha 研究 pipeline
- 戰術資產配置（宏觀因子 + 跨資產動能 + 市場體制判斷）
- 投資組合優化（14 種方法：等權、風險平價、MVO、Black-Litterman、HRP 等）
- 宣告式風控管理，含盤前檢查與緊急熔斷機制
- REST API + WebSocket 即時監控 + React Web 儀表板
- CLI 命令列工具：回測、因子分析、系統管理

### 什麼是回測

回測（Backtest）是用歷史數據模擬一套交易策略的過程，目的是在投入真金白銀之前，先了解這套策略在過去的表現如何。

本系統的回測流程每天重複以下步驟：

1. **取得歷史資料** — 從 Yahoo Finance 自動下載股票的開高低收、成交量等數據
2. **策略運算** — 你的策略根據歷史資料，決定「我想持有哪些股票、各佔多少比例」
3. **風控檢查** — 系統自動檢查這些持倉是否符合風控規則（例如單檔不超過 10%）
4. **模擬交易** — 系統模擬真實下單，包含手續費、滑價、證交稅等成本
5. **更新持倉與淨值** — 記錄每天的資產淨值，最後計算績效指標

你只需要負責第 2 步：告訴系統你想怎麼分配資金。其他的事系統會幫你處理。

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
| `QUANT_DATA_SOURCE` | `yahoo` | 數據源：`yahoo`、`finmind` |
| `QUANT_API_KEY` | `dev-key` | API 認證金鑰 |
| `QUANT_LOG_LEVEL` | `INFO` | 日誌等級 |
| `QUANT_COMMISSION_RATE` | `0.001425` | 券商手續費（0.1425%） |
| `QUANT_DEFAULT_SLIPPAGE_BPS` | `5.0` | 滑價（基點） |
| `QUANT_MAX_POSITION_PCT` | `0.05` | 單一持倉權重上限 |
| `QUANT_MAX_DAILY_DRAWDOWN_PCT` | `0.03` | 日回撤上限 |

## 3. 快速上手

### 執行你的第一次回測

```bash
python -m src.cli.main backtest \
    --strategy momentum \
    -u AAPL -u MSFT -u GOOGL \
    --start 2023-01-01 \
    --end 2024-12-31
```

這會做以下事情：
- 從 Yahoo Finance 下載 AAPL、MSFT、GOOGL 三檔股票在 2023-01-01 到 2024-12-31 間的歷史數據
- 使用「動量策略」：買入近期表現最強的股票
- 以 1,000 萬元初始資金、每週再平衡的方式模擬交易
- 計算完成後，輸出完整的績效報告

### 台股範例

系統預設的手續費和證交稅就是台灣的費率。台股在 Yahoo Finance 的代碼格式為 `代號.TW`：

```bash
python -m src.cli.main backtest \
    -s momentum \
    -u 2330.TW -u 2317.TW -u 2454.TW \
    --start 2023-01-01 \
    --end 2024-12-31
```

這會回測台積電（2330）、鴻海（2317）、聯發科（2454）的動量策略組合。

### CLI 參數

| 參數 | 簡寫 | 預設值 | 說明 |
|------|------|--------|------|
| `--strategy` | `-s` | `momentum` | 策略名稱（見[內建策略](#5-內建策略)） |
| `--universe` | `-u` | AAPL, MSFT, GOOGL, AMZN, META | 股票代碼，可重複指定多檔 |
| `--start` | | `2020-01-01` | 回測起始日 |
| `--end` | | `2024-12-31` | 回測結束日 |
| `--cash` | `-c` | `10,000,000` | 初始資金 |
| `--rebalance` | `-r` | `weekly` | 再平衡頻率：`daily`（每天）、`weekly`（每週一）、`monthly`（每月初） |
| `--slippage` | | `5.0` | 滑價，單位為基點（1 基點 = 0.01%） |
| `--validate` | `-v` | 關閉 | 啟用結果驗證 |
| `--log-level` | `-l` | `INFO` | 日誌等級（`DEBUG` 可看到更多細節） |

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

### 範例：不同配置的比較

```bash
# 每日再平衡、更高滑價假設
python -m src.cli.main backtest \
    -s momentum -u AAPL -u MSFT -u GOOGL \
    --start 2023-01-01 --end 2024-12-31 \
    --rebalance daily --slippage 10

# 均值回歸策略、每月再平衡、較少初始資金
python -m src.cli.main backtest \
    -s mean_reversion -u AAPL -u MSFT -u GOOGL -u AMZN -u META \
    --start 2022-01-01 --end 2024-12-31 \
    --rebalance monthly --cash 1000000
```

## 4. 看懂回測結果

| 指標 | 說明 | 怎樣算好？ |
|------|------|-----------|
| **Total Return** | 整個回測期間賺了多少 | 正值就是賺錢 |
| **Annual Return** | 年化報酬率 | 長期而言 > 8% 算不錯 |
| **Volatility** | 波動率 — 報酬的不確定程度 | 越低越穩定 |
| **Sharpe Ratio** | 每承受一單位風險，賺到多少報酬 | > 1.0 算好，> 2.0 很好 |
| **Sortino Ratio** | 類似 Sharpe，但只考慮下跌風險 | > 1.0 算好 |
| **Calmar Ratio** | 年化報酬 / 最大回撤 | > 1.0 算好 |
| **Max Drawdown** | 從最高點到最低點，最多跌了多少 | 越小越好，< 10% 算穩健 |
| **Max DD Days** | 最大回撤持續了幾天 | 越短表示回復越快 |
| **Win Rate** | 盈利交易的比例 | > 50% 但不是唯一指標 |
| **Total Comm.** | 總交易成本（手續費 + 稅） | 注意成本是否侵蝕獲利 |
| **換手率（Turnover）** | 年化投資組合換手率 | 越低代表交易成本越少 |

### 回測驗證

啟用 `--validate` 時，系統會執行以下檢查：

- **非零交易：** 至少執行 1 筆交易
- **NAV 連續性：** 單日 NAV 變動未超過合理閾值
- **報酬合理性：** 年化報酬在可信範圍內
- **Sharpe 合理性：** Sharpe 比率在可信範圍內
- **成本影響：** 交易成本相對於報酬是合理的

## 5. 內建策略

### 動量策略（momentum）

**核心概念**：過去漲得多的股票，未來可能繼續漲。

具體做法：
- 計算每檔股票過去 252 個交易日（約 12 個月）的報酬率，但跳過最近 21 天（約 1 個月），因為短期內可能有反轉
- 選出報酬最高的前 10 檔
- 按報酬率的強弱分配權重，單檔上限 10%，總持倉不超過 95%

```bash
python -m src.cli.main backtest -s momentum -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

**策略名稱：** `momentum` 或 `momentum_12_1`

### 均值回歸策略（mean_reversion）

**核心概念**：股價偏離均線太遠時，傾向回歸。

具體做法：
- 計算每檔股票的 Z-score：目前價格偏離 20 日均線多少個標準差
- 只買入 Z-score 超過 1.5 的標的（也就是價格顯著低於均線的）
- 按 Z-score 強弱分配權重，單檔上限 8%，總持倉不超過 90%

```bash
python -m src.cli.main backtest -s mean_reversion -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

### RSI 超賣策略（rsi_oversold）

**核心概念**：RSI 低於 30 代表超賣，股價可能反彈。

具體做法：
- 計算每檔股票的 14 日 RSI
- 只買入 RSI < 30 的標的（超賣區間）
- 信號強度 = 100 - RSI（RSI 越低，配置越多）

```bash
python -m src.cli.main backtest -s rsi_oversold -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

### 均線交叉策略（ma_crossover）

**核心概念**：短期均線上穿長期均線時，代表趨勢轉多。

具體做法：
- 計算 10 日快線與 50 日慢線的比值
- 快線 > 慢線時買入（比值 > 0）
- 按交叉強度分配權重

```bash
python -m src.cli.main backtest -s ma_crossover -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

### 多因子策略（multi_factor）

**核心概念**：結合動量、均值回歸、RSI 三個因子，綜合評分選股。

具體做法：
- 對每檔股票計算三個因子的百分位排名
- 加權合成（動量 40%、價值 30%、品質 30%）
- 只買入複合分數為正的標的

```bash
python -m src.cli.main backtest -s multi_factor -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

### 配對交易策略（pairs_trading）

**核心概念**：兩檔相關股票的價格比率會回歸均值，偏離時買入被低估的一方。

具體做法：
- 對每一對股票計算價格比率的 Z-score
- Z-score 超過閾值時，買入相對弱勢（被低估）的標的
- 等權重配置

```bash
python -m src.cli.main backtest -s pairs_trading -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

### 板塊輪動策略（sector_rotation）

**核心概念**：買入短期動量最強的標的，用風險平價分配權重。

具體做法：
- 計算 60 日短期動量，選出前 5 名
- 按波動率的倒數分配權重（波動低的配置多），使風險貢獻相等

```bash
python -m src.cli.main backtest -s sector_rotation -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

### 月營收動能策略（revenue_momentum）

**核心概念**：台股上市公司每月公布營收，營收加速成長的公司股價通常有延續性。

具體做法：
- 計算月營收年增率（rev_yoy）作為主要排序因子（ICIR 0.037（修正前 0.674）））
- 使用營收加速度（3 個月 / 12 個月營收比率）排序
- 搭配價格趨勢確認，過濾假信號

```bash
python -m src.cli.main backtest -s revenue_momentum -u 2330.TW -u 2317.TW -u 2454.TW
```

### 月營收動能避險策略（revenue_momentum_hedged）

**核心概念**：在月營收動能策略的基礎上，加入空頭偵測機制，避免在熊市中持倉。這是系統的 Paper Trading 主策略。

具體做法：
- 核心邏輯與 `revenue_momentum` 相同
- 加入複合空頭偵測：當指數跌破 200 日均線（MA200）**或**出現波動率飆升（vol_spike）時判定為空頭
- 空頭期間持倉降至 0%，避開系統性風險

```bash
python -m src.cli.main backtest -s revenue_momentum_hedged -u 2330.TW -u 2317.TW -u 2454.TW
```

### 投信跟單策略（trust_follow）

**核心概念**：追蹤投信（共同基金）的買超行為，結合營收成長篩選。

具體做法：
- 篩選投信連續買超的標的
- 搭配營收成長率作為品質過濾條件
- 買入同時符合投信買超 + 營收成長的股票

```bash
python -m src.cli.main backtest -s trust_follow -u 2330.TW -u 2317.TW -u 2454.TW
```

### 多策略組合（multi_strategy_combo）

**核心概念**：結合多個策略的信號，用反波動率加權，降低單一策略的風險。

具體做法：
- 同時運行多個子策略
- 按各策略的波動率倒數分配權重（波動低的策略配置更多）
- 達到分散風險的效果

```bash
python -m src.cli.main backtest -s multi_strategy_combo -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

### Alpha 因子策略（alpha）

**核心概念**：可配置的量化因子 pipeline，支援因子中性化與成本感知的投組建構。

具體做法：
- 自訂宇宙篩選 → 因子計算 → 中性化 → 正交化 → 複合信號 → 分位回測
- 支援成本感知的投組建構，考慮換手率對績效的影響
- 適合進階用戶進行因子研究

### 多資產策略（multi_asset）

**核心概念**：兩層式架構，先做跨資產配置，再做類別內選股，最後進行投組優化。

具體做法：
- 第一層：戰術配置 — 根據宏觀因子與跨資產動能決定各資產類別的配置比例
- 第二層：類別內選股 — 在每個資產類別中選出最佳標的
- 最終透過投組優化器（14 種方法可選）產生目標權重

## 6. 撰寫你自己的策略

撰寫策略只需要三步：

### Step 1：建立策略檔案

在 `strategies/` 目錄下新增一個 Python 檔案，例如 `strategies/my_strategy.py`：

```python
from src.strategy.base import Context, Strategy


class MyStrategy(Strategy):

    def name(self) -> str:
        return "my_strategy"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        """
        這是策略的核心：根據當前數據，回傳你想持有的股票和比例。

        回傳格式：{"股票代碼": 權重, ...}
        權重代表佔總資產的比例，例如 0.2 = 20%
        沒出現在 dict 裡的股票 = 不持有（如果之前有持倉會自動賣出）
        """
        weights = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=50)
            if len(bars) < 50:
                continue

            close = bars["close"]

            # 範例邏輯：如果目前價格高於 50 日均線，就買入
            if close.iloc[-1] > close.mean():
                weights[symbol] = 0.2  # 配置 20%

        return weights
```

`ctx`（Context）是你與系統互動的唯一介面，它提供：

| 方法 | 說明 |
|------|------|
| `ctx.universe()` | 取得所有可交易的股票代碼 |
| `ctx.bars(symbol, lookback=252)` | 取得歷史 K 線（包含 open、high、low、close、volume） |
| `ctx.portfolio()` | 取得目前的持倉資訊 |
| `ctx.now()` | 取得當前日期 |
| `ctx.latest_price(symbol)` | 取得最新收盤價 |
| `ctx.log(msg)` | 輸出日誌 |

回測時 `ctx.bars()` 會自動截斷未來的數據，確保你的策略不會「偷看」到未來的資訊。

### Step 2：註冊策略

打開 `src/cli/main.py` 和 `src/api/routes/backtest.py`，找到 `_resolve_strategy` 函式，加入你的策略：

```python
from strategies.my_strategy import MyStrategy  # 加這行

mapping = {
    # ... 現有策略 ...
    "my_strategy": MyStrategy,                  # 加這行
}
```

> 詳細的策略開發說明（因子庫、最佳化器、常見模式）請參考 [strategies/README.md](../strategies/README.md) 或[開發者指南](developer-guide-zh.md)。

### Step 3：執行回測

```bash
python -m src.cli.main backtest -s my_strategy -u AAPL -u MSFT -u GOOGL --start 2023-01-01 --end 2024-12-31
```

### 更多策略範例

**RSI 超賣策略**：RSI 低於 30 時買入

```python
from src.strategy.base import Context, Strategy
from src.strategy.factors import rsi


class RSIStrategy(Strategy):

    def name(self) -> str:
        return "rsi_oversold"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        weights = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=30)
            if len(bars) < 15:
                continue

            factor = rsi(bars, period=14)
            if not factor.empty and factor["rsi"] < 30:
                weights[symbol] = 0.1

        return weights
```

**雙均線交叉策略**：短期均線突破長期均線時買入

```python
from src.strategy.base import Context, Strategy
from src.strategy.factors import moving_average_crossover


class MACrossStrategy(Strategy):

    def name(self) -> str:
        return "ma_cross"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        weights = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=60)
            if len(bars) < 50:
                continue

            factor = moving_average_crossover(bars, fast=10, slow=50)
            if not factor.empty and factor["ma_cross"] > 0:
                weights[symbol] = 0.15

        return weights
```

## 7. 因子庫與優化器

### 因子庫

系統內建 83 個因子，分佈在 `src/strategy/factors/` 套件中：

| 模組 | 檔案 | 因子數量 | 說明 |
|------|------|----------|------|
| 價量因子 | `technical.py` | 66 個 | 動量、均值回歸、波動率、RSI、均線交叉、量價趨勢等 |
| 基本面因子 | `fundamental.py` | 17 個 | 營收成長、獲利能力、估值等 |
| Kakushadze | `kakushadze.py` | 子集 | Kakushadze 101 Alphas 論文中的因子子集 |

常用因子範例：

| 因子 | 函式 | 主要參數 | 回傳值 |
|------|------|----------|--------|
| 動量 | `momentum(bars, lookback=252, skip=21)` | 回溯天數、跳過天數 | `{"momentum": float}` |
| 均值回歸 | `mean_reversion(bars, lookback=20)` | 回溯天數 | `{"z_score": float}` |
| 波動率 | `volatility(bars, lookback=20)` | 回溯天數 | `{"volatility": float}` |
| RSI | `rsi(bars, period=14)` | 計算週期 | `{"rsi": float}` |
| 均線交叉 | `moving_average_crossover(bars, fast=10, slow=50)` | 快線/慢線週期 | `{"ma_cross": float}` |
| 量價趨勢 | `volume_price_trend(bars, lookback=20)` | 回溯天數 | `{"vpt": float}` |

使用方式：

```python
from src.strategy.factors import momentum, rsi, volatility

factor = momentum(bars, lookback=252, skip=21)
if not factor.empty:
    signal = factor["momentum"]  # 取出數值
```

### 優化器

當你有了每檔股票的信號後，需要決定「信號要怎麼轉換成權重」。系統提供三種優化器（`src/strategy/optimizer.py`）：

| 優化器 | 函式 | 說明 |
|--------|------|------|
| 等權重 | `equal_weight(signals, constraints)` | 所有有信號的標的平均分配 |
| 信號加權 | `signal_weight(signals, constraints)` | 信號越強，權重越高 |
| 風險平價 | `risk_parity(signals, volatilities, constraints)` | 讓每檔股票貢獻相等的風險 |

搭配 `OptConstraints` 控制約束條件：

```python
from src.strategy.optimizer import signal_weight, OptConstraints

weights = signal_weight(
    signals={"AAPL": 0.8, "MSFT": 0.5, "GOOGL": 0.3},
    constraints=OptConstraints(
        max_weight=0.10,         # 單檔最多 10%
        max_total_weight=0.95,   # 總持倉最多 95%（留 5% 現金）
        long_only=True,          # 只做多
    ),
)
```

### 完整範例：結合因子與優化器

```python
from src.strategy.base import Context, Strategy
from src.strategy.factors import momentum, volatility
from src.strategy.optimizer import risk_parity, OptConstraints


class MomentumRiskParity(Strategy):
    """動量選股 + 風險平價配置"""

    def name(self) -> str:
        return "momentum_rp"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals = {}
        vols = {}

        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=280)
            if len(bars) < 252:
                continue

            mom = momentum(bars)
            vol = volatility(bars)

            if not mom.empty and not vol.empty and mom["momentum"] > 0:
                signals[symbol] = mom["momentum"]
                vols[symbol] = vol["volatility"]

        if not signals:
            return {}

        return risk_parity(
            signals=signals,
            volatilities=vols,
            constraints=OptConstraints(max_weight=0.15, max_total_weight=0.90),
        )
```

## 8. 啟動 API 伺服器

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

## 9. 風控管理

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

## 10. 交易成本模型

模擬引擎預設使用台灣股票市場的成本參數：

| 成本類型 | 預設值 | 說明 |
|----------|--------|------|
| 手續費 | 0.1425% | 買賣雙向收取 |
| 證交稅 | 0.3% | 僅賣出時收取（台灣證券交易稅） |
| 滑價 | 5 基點 | 買入價格上調，賣出價格下調 |

所有成本參數均可透過 CLI 參數或環境變數自訂。

## 11. 其他實用指令

### 查看系統狀態

```bash
python -m src.cli.main status
```

顯示目前的運行模式、資料來源、手續費率、風控限制等配置。

### 查看個股因子

```bash
python -m src.cli.main factors AAPL
python -m src.cli.main factors 2330.TW
```

顯示指定股票的各項技術因子數值，可以幫助你判斷策略邏輯是否合理。

### 使用 Makefile

```bash
# 執行回測（用 ARGS 傳入參數）
make backtest ARGS="-s momentum -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31"

# 啟動 API 伺服器（開發模式）
make dev

# 執行測試
make test
```

## 12. 常見問題

### 下載數據時出錯？

系統透過 Yahoo Finance 取得數據，需要網路連線。如果下載失敗，請確認：
- 網路是否正常
- 股票代碼是否正確（台股要加 `.TW`）
- Yahoo Finance 是否能存取（部分地區可能需要 VPN）

### 回測結果沒有交易？

可能原因：
- 回測期間太短，策略需要足夠的歷史資料來運算（例如動量策略需要至少 252 天）
- 策略的條件太嚴格，沒有任何標的符合
- 可以加 `--log-level DEBUG` 查看詳細日誌

### 怎麼比較不同策略的好壞？

用相同的標的、相同的時間區間、相同的初始資金分別跑兩個策略，比較 Sharpe Ratio 和 Max Drawdown。Sharpe 越高代表風險調整後報酬越好，Max Drawdown 越低代表承受的最大損失越小。
