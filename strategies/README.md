# 策略開發指南

本文件說明如何在此系統中開發自訂交易策略。完整的架構原理與進階主題（自訂因子、風控規則、資料層擴充等）請參考 [開發者指南](../doc/developer-guide-zh.md)。

## 快速上手

建立一支新策略只需三步：

### 第一步：建立策略檔案

在 `strategies/` 目錄下新增 Python 檔案，繼承 `Strategy` 並實作兩個方法：

```python
# strategies/my_strategy.py

from src.strategy.base import Strategy, Context
from src.strategy.factors import momentum
from src.strategy.optimizer import signal_weight, OptConstraints

class MyStrategy(Strategy):
    def __init__(self, lookback: int = 60):
        self.lookback = lookback

    def name(self) -> str:
        return "my_strategy"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        signals = {}
        for symbol in ctx.universe():
            bars = ctx.bars(symbol, lookback=self.lookback)
            if len(bars) < self.lookback:
                continue

            factor = momentum(bars, lookback=self.lookback, skip=5)
            if not factor.empty and factor["momentum"] > 0:
                signals[symbol] = factor["momentum"]

        return signal_weight(
            signals,
            OptConstraints(max_weight=0.10, max_total_weight=0.95),
        )
```

**重點**：`on_bar()` 回傳 `dict[str, float]` — key 是標的代碼，value 是目標權重（佔 NAV 的比例）。你只需決定「持有什麼、佔多少」，系統自動處理差異計算、風控檢查、訂單生成與執行。

### 第二步：註冊策略

使用 `@register_strategy` decorator 自動註冊，不需手動修改其他檔案：

```python
# strategies/my_strategy.py
from src.strategy.registry import register_strategy

@register_strategy("my_strategy")
class MyStrategy(Strategy):
    ...
```

策略會自動被 CLI、API、scheduler 識別。確認註冊成功：
```bash
python -m src.cli.main factors  # 列出所有已註冊策略
```

### 第三步：執行回測

```bash
python -m src.cli.main backtest \
  --strategy my_strategy \
  -u AAPL -u MSFT -u GOOGL \
  --start 2023-01-01 --end 2024-12-31
```

---

## 現有策略參考

| 策略 | 檔案 | 因子 | 最佳化器 | 核心邏輯 |
|------|------|------|----------|----------|
| 動量 12-1 | `momentum.py` | `momentum` | `signal_weight` | 買入過去 12 月漲幅最大、跳過近 1 月的標的 |
| 均值回歸 | `mean_reversion.py` | `mean_reversion` | `signal_weight` | 買入 Z-score 超過閾值（價格偏低）的標的 |
| RSI 超賣 | `rsi_oversold.py` | `rsi` | `signal_weight` | 買入 RSI < 30 的超賣標的 |
| 均線交叉 | `ma_crossover.py` | `moving_average_crossover` | `signal_weight` | 快線上穿慢線時買入 |
| 多因子 | `multi_factor.py` | `momentum` + `mean_reversion` + `rsi` | `signal_weight` | 三因子百分位排名加權的複合評分 |
| 配對交易 | `pairs_trading.py` | 自算價格比率 Z-score | `equal_weight` | 買入配對中相對被低估的一方 |
| 板塊輪動 | `sector_rotation.py` | `volatility` | `risk_parity` | 短期動量 Top N + 風險平價配置 |

建議從 `momentum.py` 或 `rsi_oversold.py` 開始閱讀，這兩支結構最簡單。

---

## 常見模式

### 模式一：單因子 + 信號加權

最常見的策略結構，適合大多數因子策略。參考 `momentum.py`、`rsi_oversold.py`、`ma_crossover.py`。

```python
def on_bar(self, ctx: Context) -> dict[str, float]:
    signals = {}
    for symbol in ctx.universe():
        bars = ctx.bars(symbol, lookback=self.lookback)
        if len(bars) < self.lookback:
            continue
        factor = some_factor(bars)
        if not factor.empty and factor["value"] > self.threshold:
            signals[symbol] = factor["value"]

    return signal_weight(signals, OptConstraints(max_weight=0.10))
```

### 模式二：多因子複合評分

結合多個因子，適合更穩健的策略。參考 `multi_factor.py`。

```python
def on_bar(self, ctx: Context) -> dict[str, float]:
    signals = {}
    for symbol in ctx.universe():
        bars = ctx.bars(symbol, lookback=300)
        mom = momentum(bars)
        rev = mean_reversion(bars)
        score = 0.6 * mom["momentum"] + 0.4 * rev["z_score"]
        if score > 0:
            signals[symbol] = score

    return signal_weight(signals, OptConstraints(max_weight=0.08))
```

### 模式三：風險平價配置

按波動率倒數分配，使每個標的貢獻相等的風險。參考 `sector_rotation.py`。

```python
def on_bar(self, ctx: Context) -> dict[str, float]:
    signals, vols = {}, {}
    for symbol in ctx.universe():
        bars = ctx.bars(symbol, lookback=100)
        signals[symbol] = some_score
        vol = volatility(bars)
        if not vol.empty:
            vols[symbol] = vol["volatility"]

    return risk_parity(signals, vols, OptConstraints(max_weight=0.20))
```

---

## 注意事項

1. **不要直接產生訂單** — `on_bar()` 只回傳目標權重，系統自動處理後續流程
2. **不要存取未來資料** — `ctx.bars()` 已保證時間因果律，但自行載入外部資料需自行確保
3. **lookback 要留餘量** — 請求的 `lookback` 應大於因子所需的最少 bar 數
4. **處理空值** — 因子函式在資料不足時回傳空 `Series`，務必檢查 `factor.empty`
5. **權重語義** — 正值 = 做多，負值 = 做空（需 `long_only=False`），不在 dict 中 = 平倉

---

## 深入了解

- **Context API、因子庫、最佳化器詳細說明** → [開發者指南 §4-7](../doc/developer-guide-zh.md)
- **自訂因子寫法** → [開發者指南 §5](../doc/developer-guide-zh.md)
- **自訂風控規則** → [開發者指南 §6](../doc/developer-guide-zh.md)
- **回測引擎原理** → [開發者指南 §8](../doc/developer-guide-zh.md)
- **使用者操作指南（CLI 參數、結果解讀）** → [用戶指南](../doc/user-guide-zh.md)
