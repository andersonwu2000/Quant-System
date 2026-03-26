# Phase L+：FinLab 差距修復 — 下行保護 + 數據修復 + 事件時機

> 狀態：🟡 進行中（L+.1 ✅ 完成、L+.2 部分完成）
> 前置：Phase L（策略轉型，6/7 驗證通過）✅
> 依據：FinLab 差距分析 — 純多頭策略在 2025 H1 失敗（-7.4%）、Yahoo 倖存者偏差、月度再平衡 Sharpe 落後 2x
> 目標：解決 P0 缺口後進入 Phase N Paper Trading

---

## 背景：FinLab 差距分析

### 績效差距

| 指標 | 我們 (revenue_momentum) | FinLab 最佳 | 差距 |
|------|------------------------|------------|------|
| CAGR | +30.5% | +60% | -29.5pp |
| Sharpe | 1.51 | Sharpe(D) > 3 | ~2x |
| Sortino | 2.16 | 3.02 | -0.86 |
| Beta | ≈ 1.0（純多頭） | **-0.43** | 根本差異 |
| OOS 2025 H1 | **-7.4%** | 負 Beta 應正 | 致命 |

### 架構差距

| 差距 | 等級 | Phase |
|------|:----:|:-----:|
| 純多頭，無下行保護 | 🔴 致命 | L+.1 |
| Yahoo 倖存者偏差 | 🔴 致命 | L+.2 |
| 月度再平衡，無事件時機 | 🟡 重要 | L+.3 |
| 單策略集中風險 | 🟡 重要 | L+.4 |

### 我們的優勢（vs FinLab 公開展示）

- Walk-Forward 7/7 年正 Sharpe — FinLab 未公開
- PBO 0% — FinLab 未提及
- t = 3.50, p = 0.013 — FinLab 未公開
- StrategyValidator 11 項強制閘門 — 與 `verify_strategy()` 同等

---

## L+.1：空頭市場偵測 + 現金避險（🔴 P0）

### 問題

revenue_momentum 是純多頭策略（Beta ≈ 1），市場下跌時完全暴露。
- 2022 年：+3.4%（勉強正，但 MDD 26%）
- 2025 H1：**-7.4%**（OOS 唯一失敗項）
- FinLab 的最佳策略 Beta = -0.43，下跌時反而賺

### 方案：Regime-Aware Position Sizing

```python
# 在 on_bar() 開頭加入：
def _market_regime(self, ctx: Context) -> str:
    """偵測市場環境：bull / bear / sideways"""
    # 用 0050.TW（或大盤指數）作為 proxy
    market_bars = ctx.bars("0050.TW", lookback=252)
    close = market_bars["close"]

    ma200 = close.rolling(200).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    current = close.iloc[-1]

    if current < ma200 and ma50 < ma200:
        return "bear"   # 空頭：價格在 MA200 以下，MA50 死亡交叉
    elif current > ma200 and ma50 > ma200:
        return "bull"   # 多頭
    else:
        return "sideways"

# 根據 regime 調整倉位：
regime = self._market_regime(ctx)
if regime == "bear":
    # 空頭：降到 30% 倉位，70% 現金
    weights = {k: v * 0.3 for k, v in weights.items()}
elif regime == "sideways":
    # 盤整：降到 60% 倉位
    weights = {k: v * 0.6 for k, v in weights.items()}
```

### 預期效果

| 情境 | 原始 | 加入空頭偵測後 |
|------|------|---------------|
| 2022 (熊市) | +3.4%, MDD 26% | +2%~5%, MDD ~10% |
| 2025 H1 | -7.4% | ~-2% (70% 現金保護) |
| 2023 (牛市) | +94% | +94%（bull mode 不變） |

### 檔案變更

| 檔案 | 變更 |
|------|------|
| `strategies/revenue_momentum.py` | 加入 `_market_regime()` + 倉位調整 |
| `strategies/trust_follow.py` | 同上 |
| `src/alpha/filter_strategy.py` | `FilterStrategy` 加入 regime 支援 |
| `tests/unit/test_revenue_strategies.py` | 新增 regime 測試 |

### 驗證

- 重跑 2018-2024 全期回測 + Walk-Forward
- 特別驗證 2022、2018 H2（熊市段）的 MDD 改善
- OOS 2025 H1 是否從 -7.4% 改善

---

## L+.2：FinMind 價格數據源（🔴 P0）

### 問題

Yahoo Finance 不含已下市股票，導致倖存者偏差 — 回測只看到「活下來」的贏家，CAGR 可能過度樂觀 3-8pp。

FinLab 創辦人明確說：「量化交易比的是誰能清洗最乾淨的資料，做歷史上幾乎無誤差的回測。」

### 方案

```
1. 用 FinMind TaiwanStockPrice 下載全台股歷史價格
   - 含已下市股票（FinMind 保留歷史記錄）
   - 2015-01-01 ~ 2025-12-31
   - 存到 data/market/{symbol}_1d.parquet（與 Yahoo 格式相同）

2. 修改 download_finmind_data.py 加入 price dataset
   - 使用 FinMind API: dl.taiwan_stock_daily(stock_id=..., start_date=..., end_date=...)
   - 欄位對應：Trading_Volume → volume, close → close, etc.

3. 比較 Yahoo vs FinMind 回測差異
   - 預期：FinMind 回測 CAGR 下降 3-8pp（更真實）
```

### 檔案變更

| 檔案 | 變更 |
|------|------|
| `scripts/download_finmind_data.py` | 新增 `price` dataset |
| `src/data/sources/finmind.py` | 確保讀取 FinMind 格式 parquet |

### 驗證

- FinMind 價格 vs Yahoo 價格對比（現存股票應一致）
- 用 FinMind 價格重跑 revenue_momentum 全期回測
- 記錄 CAGR 差異（= 倖存者偏差大小）

---

## L+.3：事件時機層（🟡 P1）

### 問題

我們的策略是固定月度再平衡。FinLab 的策略有事件驅動時機：
- 月營收公布後 T+1 進場（不等月底）
- 法人異常買超觸發
- ChatGPT vs Claude 比拼發現「跳過前 3 天，第 4-7 天進場」

結果：FinLab Sharpe(D) > 3 vs 我們 Sharpe(M) 1.51

### 方案

```python
class EventDrivenRebalancer:
    """事件驅動再平衡 — 取代固定月度。"""

    def should_rebalance(self, ctx: Context) -> bool:
        """月營收公布日 + T+1 觸發。"""
        # 台股月營收每月 10 日前公布
        day = ctx.now().day
        if 11 <= day <= 13:  # 營收公布後 T+1~T+3
            return True

        # 法人異常買超事件
        # trust_10d > historical_3σ → 觸發
        return False
```

### 檔案變更

| 檔案 | 變更 |
|------|------|
| `src/alpha/event_rebalancer.py` | **新檔案**：事件驅動再平衡邏輯 |
| `strategies/revenue_momentum.py` | 整合 EventDrivenRebalancer |
| `src/backtest/engine.py` | 支援 event-driven rebalance mode |

---

## L+.4：多策略組合（🟡 P1）

### 問題

單策略集中風險。FinLab 有 54 個策略可輪動/組合。

### 方案

組合 3-4 個低相關策略，inverse-volatility 加權：

| 策略 | 類型 | 相關性預期 |
|------|------|-----------|
| revenue_momentum_hedged | 營收動能 + 空頭偵測 | 核心 |
| trust_follow | 投信跟單（中小型股） | 低相關 |
| momentum_12_1 | 價格動量 | 中等相關 |
| mean_reversion | 均值回歸 | 負相關 |

```python
class MultiStrategyCombo(Strategy):
    """多策略 inverse-volatility 加權組合。"""

    def __init__(self, strategies: list[Strategy]):
        self.strategies = strategies

    def on_bar(self, ctx: Context) -> dict[str, float]:
        all_weights = [s.on_bar(ctx) for s in self.strategies]
        # Inverse-vol 加權合併
        ...
```

### 檔案變更

| 檔案 | 變更 |
|------|------|
| `strategies/multi_strategy_combo.py` | **新檔案** |
| `src/strategy/registry.py` | 註冊 combo 策略 |

---

## 執行順序

```
L+.1（空頭偵測）──→ 重新驗證 ──→ L+.2（FinMind 價格）──→ 重新驗證
                                          │
                                    L+.3（事件時機）
                                          │
                                    L+.4（多策略組合）
                                          │
                                    Phase N（Paper Trading）
```

L+.1 和 L+.2 是 P0，必須在 Paper Trading 前完成。
L+.3 和 L+.4 是 P1，可以在 Paper Trading 期間並行開發。

---

## 驗證標準

### 現有閘門：StrategyValidator 11 項（`src/backtest/validator.py`）

所有策略上線前必須通過此閘門（`validator.validate()` 全部 pass）：

| # | 檢查 | 門檻 | 方法 |
|---|------|------|------|
| 1 | CAGR | > 15% | Full backtest |
| 2 | Sharpe | > 0.7 | Full backtest |
| 3 | Max Drawdown | < 50% | Full backtest |
| 4 | Walk-Forward | ≥ 60% 年正 Sharpe | 滾動 3yr/1yr |
| 5 | PBO | < 50% | Bailey 2015 CSCV |
| 6 | Deflated Sharpe | > 0.95 | Bailey & López de Prado 2014 |
| 7 | Bootstrap P(SR>0) | > 80% | 1,000 次重抽 |
| 8 | OOS holdout | return > 0 | 2025 H2 |
| 9 | vs 1/N 超額 | > 0 | DeMiguel 2009 |
| 10 | 成本佔比 | < 50% × gross | 成本/報酬比 |
| 11 | Factor decay | 近 1 年 SR > 0 | 最近期有效性 |
| + | Universe ≥ 50 | ≥ 50 支 | Selection bias |
| + | Worst regime | > -30% | 最差年度 |

### Phase L+ 額外檢查

| # | 檢查 | 門檻 |
|---|------|------|
| 12 | 2022 年 MDD | < 15%（空頭保護有效） |
| 13 | OOS 2025 H1 | > -3%（從 -7.4% 改善） |
| 14 | FinMind vs Yahoo CAGR 差 | < 5pp（倖存者偏差可控） |
| 15 | 多策略 Sharpe | > 單策略 Sharpe |

---

## 關鍵檔案

| 檔案 | 階段 | 狀態 |
|------|:----:|:----:|
| `strategies/revenue_momentum.py` | L+.1 | 🔵 |
| `strategies/trust_follow.py` | L+.1 | 🔵 |
| `src/alpha/filter_strategy.py` | L+.1 | 🔵 |
| `scripts/download_finmind_data.py` | L+.2 | 🔵 |
| `src/alpha/event_rebalancer.py` | L+.3 | 🔵 |
| `strategies/multi_strategy_combo.py` | L+.4 | 🔵 |
| `src/backtest/engine.py` | L+.3 | 🔵 |
| `tests/unit/test_regime_hedge.py` | L+.1 | 🔵 |
