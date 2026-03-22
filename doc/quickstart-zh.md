# 快速上手指南

本指南將帶你從零開始，完成安裝、執行第一次回測、理解回測結果，並撰寫你自己的交易策略。

## 目錄

1. [什麼是回測](#1-什麼是回測)
2. [安裝與設定](#2-安裝與設定)
3. [執行你的第一次回測](#3-執行你的第一次回測)
4. [看懂回測結果](#4-看懂回測結果)
5. [調整回測參數](#5-調整回測參數)
6. [內建策略介紹](#6-內建策略介紹)
7. [撰寫你自己的策略](#7-撰寫你自己的策略)
8. [進階：使用因子庫與優化器](#8-進階使用因子庫與優化器)
9. [其他實用指令](#9-其他實用指令)
10. [常見問題](#10-常見問題)

---

## 1. 什麼是回測

回測（Backtest）是用歷史數據模擬一套交易策略的過程，目的是在投入真金白銀之前，先了解這套策略在過去的表現如何。

本系統的回測流程每天重複以下步驟：

1. **取得歷史資料** — 從 Yahoo Finance 自動下載股票的開高低收、成交量等數據
2. **策略運算** — 你的策略根據歷史資料，決定「我想持有哪些股票、各佔多少比例」
3. **風控檢查** — 系統自動檢查這些持倉是否符合風控規則（例如單檔不超過 10%）
4. **模擬交易** — 系統模擬真實下單，包含手續費、滑價、證交稅等成本
5. **更新持倉與淨值** — 記錄每天的資產淨值，最後計算績效指標

你只需要負責第 2 步：告訴系統你想怎麼分配資金。其他的事系統會幫你處理。

---

## 2. 安裝與設定

### 環境需求

- Python 3.12 以上

### 安裝

```bash
cd Portfolio
pip install -e .
```

### 設定（選用）

系統開箱即可使用，不需要額外配置。如果你想調整預設參數（例如手續費率），可以複製配置範本：

```bash
cp .env.example .env
```

然後編輯 `.env` 中的對應欄位。常見的配置項：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `QUANT_COMMISSION_RATE` | `0.001425` | 手續費率（預設為台灣的 0.1425%） |
| `QUANT_DEFAULT_SLIPPAGE_BPS` | `5.0` | 滑價（基點） |
| `QUANT_MAX_POSITION_PCT` | `0.05` | 單一持倉上限 |
| `QUANT_MAX_DAILY_DRAWDOWN_PCT` | `0.03` | 日回撤上限 |

---

## 3. 執行你的第一次回測

在終端機中執行以下指令：

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

---

## 4. 看懂回測結果

回測完成後，你會看到類似這樣的輸出：

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

各項指標的意義：

| 指標 | 說明 | 怎樣算好？ |
|------|------|-----------|
| **Total Return** | 整個回測期間賺了多少 | 正值就是賺錢 |
| **Annual Return** | 年化報酬率 | 長期而言 > 8% 算不錯 |
| **Volatility** | 波動率 — 報酬的不確定程度 | 越低越穩定 |
| **Sharpe Ratio** | 每承受一單位風險，賺到多少報酬 | > 1.0 算好，> 2.0 很好 |
| **Sortino Ratio** | 類似 Sharpe，但只考慮下跌風險 | > 1.0 算好 |
| **Max Drawdown** | 從最高點到最低點，最多跌了多少 | 越小越好，< 10% 算穩健 |
| **Max DD Days** | 最大回撤持續了幾天 | 越短表示回復越快 |
| **Win Rate** | 盈利交易的比例 | > 50% 但不是唯一指標 |
| **Total Comm.** | 總交易成本（手續費 + 稅） | 注意成本是否侵蝕獲利 |

你也可以加上 `--validate` 參數，讓系統自動檢查結果是否合理（例如報酬是否異常、是否有交易、淨值是否連續）：

```bash
python -m src.cli.main backtest -s momentum -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31 --validate
```

---

## 5. 調整回測參數

所有可用的參數：

| 參數 | 簡寫 | 預設值 | 說明 |
|------|------|--------|------|
| `--strategy` | `-s` | `momentum` | 策略名稱（`momentum` 或 `mean_reversion`） |
| `--universe` | `-u` | AAPL, MSFT, GOOGL, AMZN, META | 股票代碼，可重複指定多檔 |
| `--start` | | `2020-01-01` | 回測起始日 |
| `--end` | | `2024-12-31` | 回測結束日 |
| `--cash` | `-c` | `10,000,000` | 初始資金 |
| `--rebalance` | `-r` | `weekly` | 再平衡頻率：`daily`（每天）、`weekly`（每週一）、`monthly`（每月初） |
| `--slippage` | | `5.0` | 滑價，單位為基點（1 基點 = 0.01%） |
| `--validate` | `-v` | 關閉 | 啟用結果驗證 |
| `--log-level` | `-l` | `INFO` | 日誌等級（`DEBUG` 可看到更多細節） |

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

---

## 6. 內建策略介紹

### 動量策略（momentum）

**核心概念**：過去漲得多的股票，未來可能繼續漲。

具體做法：
- 計算每檔股票過去 252 個交易日（約 12 個月）的報酬率，但跳過最近 21 天（約 1 個月），因為短期內可能有反轉
- 選出報酬最高的前 10 檔
- 按報酬率的強弱分配權重，單檔上限 10%，總持倉不超過 95%

```bash
python -m src.cli.main backtest -s momentum -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

### 均值回歸策略（mean_reversion）

**核心概念**：股價偏離均線太遠時，傾向回歸。

具體做法：
- 計算每檔股票的 Z-score：目前價格偏離 20 日均線多少個標準差
- 只買入 Z-score 超過 1.5 的標的（也就是價格顯著低於均線的）
- 按 Z-score 強弱分配權重，單檔上限 8%，總持倉不超過 90%

```bash
python -m src.cli.main backtest -s mean_reversion -u AAPL -u MSFT -u GOOGL -u AMZN -u META
```

---

## 7. 撰寫你自己的策略

這是最有趣的部分。撰寫策略只需要三步：

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

打開 `src/cli/main.py`，找到 `_resolve_strategy` 函式，加入你的策略：

```python
def _resolve_strategy(name: str):
    from strategies.momentum import MomentumStrategy
    from strategies.mean_reversion import MeanReversionStrategy
    from strategies.my_strategy import MyStrategy  # 加這行

    mapping = {
        "momentum": MomentumStrategy,
        "momentum_12_1": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
        "my_strategy": MyStrategy,                  # 加這行
    }
    # ...
```

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

---

## 8. 進階：使用因子庫與優化器

### 因子庫

系統內建了多個技術因子，可以直接在策略中使用。它們都在 `src/strategy/factors.py` 裡：

| 因子 | 函式 | 說明 | 回傳值 |
|------|------|------|--------|
| 動量 | `momentum(bars, lookback=252, skip=21)` | 過去 N 天報酬（跳過最近幾天） | `{"momentum": float}` |
| 均值回歸 | `mean_reversion(bars, lookback=20)` | 價格偏離均線的 Z-score | `{"z_score": float}` |
| 波動率 | `volatility(bars, lookback=20)` | 年化波動率 | `{"volatility": float}` |
| RSI | `rsi(bars, period=14)` | 相對強弱指標（0-100） | `{"rsi": float}` |
| 均線交叉 | `moving_average_crossover(bars, fast=10, slow=50)` | 快線/慢線比值 - 1 | `{"ma_cross": float}` |
| 量價趨勢 | `volume_price_trend(bars, lookback=20)` | 價格與成交量的相關性 | `{"vpt": float}` |

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

---

## 9. 其他實用指令

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

---

## 10. 常見問題

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

---

## 延伸閱讀

- [用戶指南](user-guide-zh.md) — 完整功能說明、風控規則、績效指標的詳細解釋
- [開發者指南](developer-guide-zh.md) — 系統架構、模組設計、擴充方式
- [API 參考](api-reference-zh.md) — REST / WebSocket API 端點文件
