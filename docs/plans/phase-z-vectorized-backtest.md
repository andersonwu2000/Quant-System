# Phase Z：向量化回測引擎

> 目標：將 Validator 的回測從 event-driven loop 改為 numpy 矩陣運算
> 預估加速：PBO 100x、Full backtest 5-10x、整體 Validator 10 分鐘 → 1-2 分鐘

## 1. 現狀分析

### 現有架構（event-driven）

```python
for bar_date in trading_dates:           # ~2000 days
    for symbol in universe:               # 150 stocks
        prices = feed.get_bars(symbol)    # per-stock lookup
    weights = strategy.on_bar(ctx)        # factor computation
    orders = weights_to_orders(weights)   # sequential
    for order in orders:
        risk_check(order, portfolio)      # state-dependent
        fill = simulate_fill(order)       # per-order
        apply_trade(portfolio, fill)      # mutate state
    record_nav(portfolio)
```

- 瓶頸：Python for-loop × 150 stocks × 2000 days
- 每次 `on_bar` 呼叫 `compute_factor`（pandas/numpy，但逐 stock 計算）
- 風控和下單是**狀態依賴的**，不能簡單向量化

### 目標架構（vectorized）

```python
# 1. 預建矩陣 (一次性)
price_matrix = build_price_matrix(universe, dates)        # (T × N)
volume_matrix = build_volume_matrix(universe, dates)      # (T × N)
revenue_matrix = build_revenue_matrix(universe, dates)    # (T × N)

# 2. 因子計算 (向量化，一次算完所有日期和股票)
factor_matrix = compute_factor_vectorized(
    price_matrix, volume_matrix, revenue_matrix
)                                                         # (T × N)

# 3. 選股 + 權重 (向量化)
weight_matrix = select_top_n(factor_matrix, n=15)         # (T × N)

# 4. 報酬計算
# 簡化版（PBO 用）：直接矩陣乘法
returns = (weight_matrix.shift(1) * daily_returns).sum(axis=1)

# 完整版（Validator 用）：加入成本、風控
returns = simulate_with_costs(weight_matrix, price_matrix, costs)
```

## 2. 分階段實作

### Phase Z1：PBO 向量化回測（高價值、低風險）

**範圍：** 只改 `_compute_pbo`，不動 BacktestEngine

**原理：** PBO 的 10 個變體只需要每日報酬序列，不需要完整的下單/風控模擬。等權 top-N 的報酬可以直接用矩陣計算。

**實作：**

```python
class VectorizedPBOBacktest:
    """Vectorized backtest for PBO — no orders, no risk rules."""

    def __init__(self, price_matrix, volume_matrix, revenue_matrix):
        self.prices = price_matrix      # (T × N) DataFrame
        self.returns = price_matrix.pct_change()
        self.volume = volume_matrix
        self.revenue = revenue_matrix

    def run_variant(self, compute_factor, top_n, weight_mode, rebal_skip=0):
        """Run one PBO variant, return daily returns Series."""
        # H-08 fix: 月度再平衡（對齊 event-driven）
        monthly_first = self.prices.groupby(
            self.prices.index.to_period("M")
        ).apply(lambda g: g.index[0])
        if rebal_skip > 0:
            monthly_first = monthly_first[::rebal_skip + 1]
        rebal_dates = monthly_first.values

        # H-05 fix: adapter — 用現有 compute_factor(symbols, as_of, data) 介面
        symbols = self.prices.columns.tolist()

        # 2. For each rebal date, compute factor values → select top_n
        weight_matrix = pd.DataFrame(np.nan, index=self.prices.index,
                                      columns=self.prices.columns)
        for date in rebal_dates:
            as_of = pd.Timestamp(date)
            data = {
                "bars": {s: self.prices[[s]].loc[:as_of].rename(
                    columns={s: "close"}).assign(
                    open=self.prices[s].loc[:as_of],
                    high=self.prices[s].loc[:as_of],
                    low=self.prices[s].loc[:as_of],
                    volume=self.volume[s].loc[:as_of],
                ) for s in symbols},
                "revenue": self.revenue,
                "institutional": {},
                "pe": {}, "pb": {}, "roe": {},
            }
            values = compute_factor(symbols, as_of, data)
            if not values:
                continue
            ranked = sorted(values, key=lambda s: values[s], reverse=True)
            selected = ranked[:top_n]
            if not selected:
                continue
            if weight_mode == "equal":
                for s in selected:
                    weight_matrix.loc[date, s] = 1.0 / len(selected)
            elif weight_mode == "signal":
                vals = {s: max(values[s], 0) for s in selected}
                total = sum(vals.values()) or 1.0
                for s in selected:
                    weight_matrix.loc[date, s] = vals[s] / total
            elif weight_mode == "inverse_rank":
                n = len(selected)
                total = n * (n + 1) / 2
                for i, s in enumerate(selected):
                    weight_matrix.loc[date, s] = (n - i) / total

        # H-01 fix: forward-fill 用 rebalance mask，不靠 replace(0, nan)
        is_rebal = pd.Series(False, index=weight_matrix.index)
        is_rebal.loc[rebal_dates] = True
        for col in weight_matrix.columns:
            weight_matrix[col] = weight_matrix[col].where(is_rebal).ffill().fillna(0)

        # H-02 fix: shift(1) 對齊 T+1 execution (close-to-close 近似)
        # M-03 fix: 加簡化成本
        weight_diff = weight_matrix.diff().fillna(0)
        sells = weight_diff.clip(upper=0).abs()
        buys = weight_diff.clip(lower=0)
        commission = 0.001425
        tax = 0.003
        cost_per_bar = (buys * commission + sells * (commission + tax)).sum(axis=1)

        gross_returns = (weight_matrix.shift(1) * self.returns).sum(axis=1)
        portfolio_returns = gross_returns - cost_per_bar
        return portfolio_returns
```

**預估：**
- 10 個變體：從 5 分鐘 → 5-10 秒
- 不改任何現有代碼（新增平行模組）
- 風險：低（PBO 只需要相對排名，精確成本模擬不重要）

**驗證：**
- 對比現有 event-driven PBO 和向量化版本的結果
- 允許 ±5% 的 PBO 差異（成本/滑點影響）

### Phase Z2：Validator 加速（shared feed + 並行化，不犧牲正確性）

**範圍：** WF、OOS、recent 保持 event-driven BacktestEngine，只加速數據載入和並行化

**原理：** WF/OOS/recent 決定 Validator 的 pass/fail 判定。簡化回測會犧牲正確性
（風控拒絕、lot size、滑點、除權息），導致 Sharpe 偏高 10-20%，足以改變 pass/fail。
不可接受。

**已實作的加速（保持完整引擎）：**
- shared feed（讀一次 parquet，所有子回測共用）→ ~3x
- ThreadPoolExecutor 並行 WF 各年份 → ~2x
- Validator universe 200 → 150 → ~1.3x
- 總計：~5x（已從 20 min 降到 ~5-10 min）

**可進一步加速的方向：**
- BacktestEngine 內部 per-bar 的 `ctx.bars()` 加快取（Phase Z3）
- 但不能省略風控、成本、lot size

**驗證：** 不需要 — 使用原始 BacktestEngine，結果完全一致

### Phase Z3：BacktestEngine 矩陣加速（高價值、高風險）

**範圍：** 現有 BacktestEngine 內部改用矩陣運算

**原理：** 不替換 BacktestEngine API，而是內部用矩陣預計算因子值和價格查表，減少 per-bar 的 Python overhead。

**不改的部分：**
- Strategy.on_bar() 介面不變
- 風控規則（state-dependent，保持 per-order）
- OMS（下單/成交模擬）

**改的部分：**
- `_build_matrices()` 預建價格/成交量矩陣（已有）
- `HistoricalFeed.get_bars()` 改為矩陣 slice（避免 per-symbol DataFrame copy）
- `Context.bars()` 快取 lookback window

**預估：**
- Full backtest：2-3x 加速（瓶頸從 data lookup 轉移到 strategy logic）
- 風險：高（改核心引擎，可能破壞精確的成本/風控模擬）

**驗證：**
- 現有 1700+ 測試必須全部通過
- 關鍵指標（Sharpe、CAGR、MDD）與舊版差異 < 0.1%
- 交易筆數必須完全一致

## 3. 實作順序與依賴

```
Phase Z1 (PBO 向量化)           ← 獨立，不動現有代碼
    ↓
Phase Z2 (shared feed + 並行)   ← 已實作，保持 event-driven 正確性
    ↓
Phase Z3 (BacktestEngine 加速)  ← 內部最佳化，不改 API
```

## 4. 檔案規劃

```
src/backtest/
├── engine.py              ← Phase Z3 改動（高風險）
├── vectorized.py          ← 新增：VectorizedBacktest + VectorizedPBOBacktest
├── validator.py           ← Z1: _compute_pbo 改用 vectorized; Z2: WF/OOS 改用 vectorized
└── analytics.py           ← 不改

tests/unit/
├── test_vectorized.py     ← 新增：向量化回測正確性驗證
└── test_validator.py      ← 更新：確保 Validator 結果一致
```

## 5. 驗證策略

### Z1 驗證（PBO）

```python
# 對同一個因子，跑兩種 PBO
pbo_event = _compute_pbo_event_driven(...)     # 現有
pbo_vector = _compute_pbo_vectorized(...)      # 新版
assert abs(pbo_event - pbo_vector) < 0.10      # 允許 10% 差異（成本模型不同）
```

### Z2 驗證

不需要 — Z2 保持 event-driven BacktestEngine，結果完全一致。

### Z3 驗證（全引擎）

```python
# 現有 1700+ 測試全部通過
pytest tests/ -v --timeout=120
# 關鍵回測指標 < 0.1% 差異
# 交易筆數允許 ±5% 差異（lot size/風控拒絕不模擬）
```

## 6. 風險管控

| 風險 | 緩解 |
|------|------|
| 向量化結果和 event-driven 不一致 | 允許範圍內差異 + 詳細 diff 報告 |
| 簡化成本模型漏掉重要成本 | Z2 可選擇回退到 event-driven |
| Z3 破壞現有測試 | Z3 每個小改動都跑完整測試 |
| 記憶體不足（150 stocks × 2000 days × 多矩陣） | ~300MB（6 矩陣 + 10 PBO 變體），仍在 8GB 限制內 |
| 向量化 factor 和原始 factor 行為不同 | Z1/Z2 用原始 compute_factor（不向量化因子本身） |

## 7. 時程

| Phase | 工作量 | 前置 |
|-------|--------|------|
| Z1: PBO 向量化 | 2-3 小時 | 無 |
| Z2: shared feed + 並行 | 已完成 | — |
| Z3: BacktestEngine 加速 | 8-12 小時 | Z2 驗證通過 |

## 8. 成功標準

| 指標 | Z1 完成 | Z2 完成 | Z3 完成 |
|------|---------|---------|---------|
| PBO 計算時間 | 5 min → 10 sec | — | — |
| WF 計算時間 | — | 已加速（shared feed） | — |
| Full backtest 時間 | — | — | 2 min → 30 sec |
| Validator 總時間 | 10 min → 5 min | 5 min（已達成） | 5 min → 2 min |
| 測試通過 | 1700+ | 1700+（不變） | 1700+ |
| PBO 精度 | ±10% | — | — |
| Sharpe 精度 | — | 完全一致（event-driven） | ±0.1% |

---

## 9. 審批意見（2026-03-28）

**審批結果：有條件通過 — Z1 可開工，Z2/Z3 需先解決設計問題。**

### 必須修正才能開工的問題（3 個 HIGH）

#### H-01: `replace(0, nan)` 誤殺合法 0 權重

```python
weight_matrix = weight_matrix.replace(0, np.nan).ffill().fillna(0)
```

如果某支股票在 rebalance 日被選中但恰好權重為 0，`replace(0, nan)` 會把它變成 NaN，被前一期的權重覆蓋。非 rebalance 日的 0 值是「未設定」而非「權重為零」，但代碼無法區分。

**修正方向**：用 rebalance 日 mask 而非靠 0 值判斷：
```python
# 標記哪些行是 rebalance 日
is_rebal = pd.Series(False, index=weight_matrix.index)
is_rebal.loc[rebal_dates] = True
# 只在非 rebalance 日 forward-fill
weight_matrix = weight_matrix.where(is_rebal, method=None).ffill()
```

#### H-02: `shift(1)` 與 event-driven engine 的 T+0/T+1 假設不一致

```python
portfolio_returns = (weight_matrix.shift(1) * self.returns).sum(axis=1)
```

`shift(1)` 代表「用昨天的權重算今天的報酬」= T+1 執行。但 event-driven engine 的 `execution_delay` 可以是 0（同日收盤）或 1（隔日開盤）。如果 Validator 的 `_make_bt_config` 用 `execution_delay=1, fill_on="open"`，那 `shift(1)` 只是近似（真正的 T+1 open 價格和 close return 不同）。

**修正方向**：明確對齊 event-driven 的 `execution_delay` 和 `fill_on` 設定。如果 `execution_delay=1`，向量化版應用 `shift(1)` 且 returns 用 open-to-open（而非 close-to-close）。

#### H-05: factor_fn 簽名與現有因子不相容

Z1 期望 `factor_fn(date, prices, volume, revenue)` — 4 個參數，接收矩陣。
現有因子是 `compute_factor(symbols, as_of, data)` — 3 個參數，接收 dict。

**修正方向**：在 `VectorizedPBOBacktest` 內部加 adapter：
```python
def _adapt_factor(self, factor_fn, date):
    """Wrap vectorized call to match autoresearch factor interface."""
    symbols = self.prices.columns.tolist()
    data = {
        "bars": {s: self.prices[[s]].rename(columns={s: "close"}) for s in symbols},
        "revenue": ...,
    }
    return factor_fn(symbols, date, data)
```
或反過來，要求 Z1 的因子函數接受矩陣介面，由 caller 提供 adapter。

### 需改善的設計問題（4 個 MEDIUM）

#### M-03: PBO 完全不含成本

PBO 比較 IS/OOS 的 Sharpe 排名。如果 10 個變體的 turnover 差異大（top-8 vs top-20），加入成本後排名可能反轉。建議至少加 `weight_diff * (commission * 2 + tax)` 的簡化成本。

#### M-04: Z2 的 ±15% Sharpe 容差太寬

Sharpe=0.75 的策略在 ±15% 容差下可能顯示為 0.64（低於 0.7 門檻）或 0.86。這個差距**足以改變 Validator 的 pass/fail 判定**。建議收緊到 ±5%。

#### M-06: turnover cost 公式把稅加在買入

```python
cost_per_bar = weight_diff * (config.commission_rate * 2 + config.tax_rate)
```

`tax_rate` 只在賣出時收取，但 `weight_diff` 包含買賣兩側。正確做法：
```python
sells = weight_diff.clip(upper=0).abs()  # 減少的權重 = 賣出
buys = weight_diff.clip(lower=0)          # 增加的權重 = 買入
cost = buys * commission + sells * (commission + tax)
```

#### M-08: 固定間隔 vs 月度再平衡

```python
rebal_dates = self.prices.index[::rebal_freq]
```

Event-driven 用月度再平衡（每月第一個交易日），但 Z1 用固定 N-bar 間隔。1 月 21 個交易日、2 月 18 個 → 兩者在不同日期觸發再平衡。

**修正方向**：改為按月份分組取第一個交易日：
```python
rebal_dates = self.prices.groupby(self.prices.index.to_period("M")).first().index
```

### 可接受的取捨（2 個 LOW）

#### L-07: Z3「交易筆數完全一致」不可能

向量化版不模擬 lot size、最低交易金額、風控拒絕。「完全一致」改為「允許 ±5% 差異 + 關鍵指標 ±0.1%」更實際。

#### L-09: 記憶體估算偏低

50MB → 實際 ~300MB（6 個矩陣 + 10 個 PBO 變體）。仍在安全範圍內，但文件中的估算應更新。

### 建議的執行順序

1. **先修 H-01, H-02, H-05** — 這三個不修，Z1 的結果會跟 event-driven 系統性偏差
2. **Z1 開工** — 修完後開始實作，跑驗證
3. **Z1 驗證通過後**，修 M-03, M-04, M-06, M-08，再開工 Z2
4. **Z3 最後做** — 風險最高、收益相對最低（Z1+Z2 已經把 10 分鐘降到 2 分鐘）

### 回覆（2026-03-28）

所有 HIGH 和 MEDIUM 問題已在計畫偽代碼中修正：

| # | 問題 | 修正 |
|---|------|------|
| H-01 | replace(0, nan) 誤殺 | 改用 rebalance mask + where().ffill() |
| H-02 | shift(1) 對齊 | 保持 shift(1) close-to-close 近似，文件標註 |
| H-05 | factor_fn 簽名不相容 | 內建 adapter，用現有 compute_factor(symbols, as_of, data) 介面 |
| M-03 | PBO 不含成本 | 加入 commission + tax（賣出才收稅） |
| M-04 | ±15% 容差太寬 | 收緊到 ±5% |
| M-06 | 稅加在買入 | sells × (commission + tax) + buys × commission |
| M-08 | 固定間隔 | 改為 groupby month 取第一個交易日 |
| L-07 | 交易筆數完全一致 | 改為 ±5% |
| L-09 | 記憶體估算 | 50MB → 300MB |

### 覆核（2026-03-28）

**修正後通過。** 以下是覆核結論和補充事項。

#### 正確性判斷

| Phase | 正確性犧牲 | 可接受? | 理由 |
|-------|-----------|---------|------|
| Z1 (PBO) | close-to-close 近似 T+1、簡化成本 → Sharpe 偏差 ~2-5% | **可接受** | PBO 比較的是變體間**相對排名**，偏差是系統性的（全部偏高），排名不受影響 |
| Z2 (shared feed) | **零犧牲** — 保持 event-driven engine | **正確** | 最佳決策：直接避開簡化回測的正確性問題 |
| Z3 (engine 加速) | 取決於實作 — 內部加速不改 API 可達 ±0.1% | **待驗證** | 交易筆數和 Sharpe 精度目標需統一 |

#### 補充限制（需標註在實作中）

**Z1-L1: bars adapter 只有 close**

```python
open=self.prices[s].loc[:as_of],   # = close
high=self.prices[s].loc[:as_of],   # = close
low=self.prices[s].loc[:as_of],    # = close
```

open/high/low 全部等於 close。使用 `(close - open)` 或 `(high - low)` 的因子（如 Kakushadze alpha_101、intraday range）在 Z1 中結果全為 0。

**影響**：Z1 的 PBO 只跑 Validator 內部的 `_VariantStrategy`，不跑這類因子。但如果未來擴展 PBO 到任意因子，需要傳入完整 OHLV 矩陣。

**Z1-L2: revenue 不做 40 天截斷**

```python
"revenue": self.revenue,  # 未截斷
```

autoresearch 的 evaluate.py 在呼叫 compute_factor 前截斷 revenue 到 `as_of - 40 天`。Z1 的 adapter 直接傳完整 revenue → 因子可能看到未來營收 → look-ahead bias。

**為什麼 PBO 仍有效**：所有 10 個變體共用同一份 revenue → bias 一致 → 排名不受影響。但 Z1 計算的 Sharpe 絕對值不能用來評估因子本身的表現——只能用於 PBO 的相對比較。

**Z1-L3: Z3 的精度目標矛盾**

計畫要求「交易筆數 ±5%」但同時「Sharpe ±0.1%」。交易筆數差 5% → 成本差異 → Sharpe 偏差 > 0.1%。

**建議**：Z3 保留完整的 lot size + 風控（不簡化），目標交易筆數**完全一致** + Sharpe ±0.1%。如果要省略 lot size，Sharpe 容差應放寬到 ±1%。

---

## 10. 實作進度（2026-03-28）

### Z1 已完成

**新增檔案：** `src/backtest/vectorized.py` — `VectorizedPBOBacktest`

**修改檔案：** `src/backtest/validator.py` — `_compute_pbo` 改用向量化版

**實測結果：**
- 10 支股票 × 10 變體：6.7 秒（event-driven 原需 5+ 分鐘）
- 150 支股票預估：30-60 秒

**Z1 審批後額外修復（8 個 review items）：**

| # | 問題 | 嚴重度 | 修復 |
|---|------|--------|------|
| 1 | compute_fn 在非 autoresearch 場景失敗 → PBO=1.0 | HIGH | 加 event-driven fallback，任何 strategy 都能跑 PBO |
| 2 | `__import__("time")` 反模式 | LOW | 改為 `import time as _time` |
| 3 | 沒有 fallback 到 event-driven | MEDIUM | `_compute_pbo` 分拆為 `_vectorized` + `_event_driven`，vectorized 失敗自動 fallback |
| 4 | `_build_factor_data` 每月重建 12,000 個 DataFrame | MEDIUM | 快取完整 bars dict，只做 `.loc[:as_of]` slice |
| 5 | `pct_change(fill_method=None)` deprecated | LOW | 改為 `ffill().pct_change()` |
| 6 | `df.index.date` 精度丟失 | LOW | 已知，暫不改（PBO 只用日期級別） |
| 7 | revenue 不截斷 | OK | 已知且文件標註，PBO 排名不受影響 |
| 8 | 第一次 rebalance 前全 0 | OK | 正確行為 |

**架構決策：**
- `_compute_pbo` 不再猜 compute_fn 來源 — 所有 caller 明確傳入 `compute_fn` 參數
- `validate()` 新增 `compute_fn` 參數，透傳到 `_compute_pbo`
- watchdog + evaluate.py + API 三個 caller 都已更新

### Z2 已完成

shared feed + ThreadPoolExecutor 並行化已在先前實作。保持 event-driven，零正確性犧牲。

### Z3 待開工

待 Z1 在生產環境驗證通過後再開始。

### 數據路徑一致性確認（2026-03-28）

| 路徑 | revenue 載入 | symbol 格式 | 狀態 |
|------|-------------|-----------|:----:|
| evaluate.py | 直接讀 parquet | 先 sym 再 bare | ✅ |
| strategy_builder.py | ctx.get_revenue(sym) | sym 含 .TW | ✅ |
| vectorized.py | 直接讀 parquet | 先 sym 再 bare | ✅ |
| watchdog.py | ctx.get_revenue(s) | s 含 .TW | ✅ |
| Context.get_revenue | 讀 {symbol}_revenue.parquet | caller 決定 | ✅ |
