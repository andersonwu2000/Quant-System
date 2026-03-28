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

    def run_variant(self, factor_fn, top_n, weight_mode, rebal_freq):
        """Run one PBO variant, return daily returns Series."""
        # 1. Compute factor for all rebalance dates
        rebal_dates = self.prices.index[::rebal_freq]

        # 2. For each rebal date, compute factor values → select top_n
        weight_matrix = pd.DataFrame(0.0, index=self.prices.index,
                                      columns=self.prices.columns)
        for date in rebal_dates:
            values = factor_fn(date, self.prices, self.volume, self.revenue)
            selected = values.nlargest(top_n).index
            if weight_mode == "equal":
                weight_matrix.loc[date, selected] = 1.0 / top_n
            elif weight_mode == "signal":
                vals = values[selected].clip(lower=0)
                weight_matrix.loc[date, selected] = vals / vals.sum()
            elif weight_mode == "inverse_rank":
                ranks = range(top_n, 0, -1)
                weight_matrix.loc[date, selected] = [r/sum(range(1,top_n+1)) for r in ranks]

        # Forward-fill weights between rebalance dates
        weight_matrix = weight_matrix.replace(0, np.nan).ffill().fillna(0)

        # 3. Daily returns = sum(weight * stock_return)
        portfolio_returns = (weight_matrix.shift(1) * self.returns).sum(axis=1)
        return portfolio_returns
```

**預估：**
- 10 個變體：從 5 分鐘 → 5-10 秒
- 不改任何現有代碼（新增平行模組）
- 風險：低（PBO 只需要相對排名，精確成本模擬不重要）

**驗證：**
- 對比現有 event-driven PBO 和向量化版本的結果
- 允許 ±5% 的 PBO 差異（成本/滑點影響）

### Phase Z2：Validator 簡化回測（中價值、中風險）

**範圍：** 為 WF、OOS、recent 提供快速回測路徑

**原理：** 這些 check 需要 Sharpe/CAGR/MDD，但不需要完整的風控模擬。用向量化回測 + 簡化成本模型。

**實作：**

```python
class VectorizedBacktest:
    """Fast vectorized backtest with simplified cost model."""

    def run(self, weight_matrix, price_matrix, config):
        returns = price_matrix.pct_change()

        # Turnover cost
        weight_diff = weight_matrix.diff().abs().sum(axis=1)
        cost_per_bar = weight_diff * (config.commission_rate * 2 + config.tax_rate)

        # Portfolio returns (after costs)
        gross_returns = (weight_matrix.shift(1) * returns).sum(axis=1)
        net_returns = gross_returns - cost_per_bar

        # NAV series
        nav = (1 + net_returns).cumprod() * config.initial_cash

        # Compute metrics
        return BacktestResult(
            nav_series=nav,
            daily_returns=net_returns,
            total_return=float(nav.iloc[-1] / nav.iloc[0] - 1),
            ...
        )
```

**預估：**
- WF 6 年：從 1-2 分鐘 → 10-20 秒
- 包含簡化成本（佣金 + 稅 + 固定滑點）
- 不含風控規則（Validator 用寬鬆風控，影響小）

**驗證：**
- Sharpe/CAGR/MDD 與 event-driven 版本對比
- 允許 ±10% 差異（成本模型簡化）
- 如果差異太大，加入更精確的成本模型

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
Phase Z1 (PBO 向量化)        ← 獨立，不動現有代碼
    ↓
Phase Z2 (Validator 簡化回測) ← 依賴 Z1 的矩陣建構
    ↓
Phase Z3 (BacktestEngine 加速) ← 依賴 Z2 驗證方法論
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

### Z2 驗證（WF/OOS）

```python
# 對同一個策略，比較 Sharpe
sharpe_event = run_event_driven(strategy, config)
sharpe_vector = run_vectorized(strategy, config)
assert abs(sharpe_event - sharpe_vector) / max(abs(sharpe_event), 0.01) < 0.15
```

### Z3 驗證（全引擎）

```python
# 現有 1700+ 測試全部通過
pytest tests/ -v --timeout=120
# 關鍵回測指標 < 0.1% 差異
```

## 6. 風險管控

| 風險 | 緩解 |
|------|------|
| 向量化結果和 event-driven 不一致 | 允許範圍內差異 + 詳細 diff 報告 |
| 簡化成本模型漏掉重要成本 | Z2 可選擇回退到 event-driven |
| Z3 破壞現有測試 | Z3 每個小改動都跑完整測試 |
| 記憶體不足（150 stocks × 2000 days × 多矩陣） | ~50MB，遠低於 8GB 限制 |
| 向量化 factor 和原始 factor 行為不同 | Z1/Z2 用原始 compute_factor（不向量化因子本身） |

## 7. 時程

| Phase | 工作量 | 前置 |
|-------|--------|------|
| Z1: PBO 向量化 | 2-3 小時 | 無 |
| Z2: Validator 簡化回測 | 3-4 小時 | Z1 完成 |
| Z3: BacktestEngine 加速 | 8-12 小時 | Z2 驗證通過 |

## 8. 成功標準

| 指標 | Z1 完成 | Z2 完成 | Z3 完成 |
|------|---------|---------|---------|
| PBO 計算時間 | 5 min → 10 sec | — | — |
| WF 計算時間 | — | 2 min → 20 sec | — |
| Full backtest 時間 | — | — | 2 min → 30 sec |
| Validator 總時間 | 10 min → 6 min | 6 min → 2 min | 2 min → 1 min |
| 測試通過 | 1700+ | 1700+ | 1700+ |
| PBO 精度 | ±10% | ±10% | ±10% |
| Sharpe 精度 | — | ±15% | ±0.1% |
