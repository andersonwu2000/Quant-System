# Phase L：策略方向轉型 — 條件篩選 + 營收動能

> 狀態：✅ 完成（6/7 檢驗通過，p=0.013，PBO=0%）
> 前置：Phase K（數據品質 + 基本面因子）✅ 完成
> 依據：15 次 price-volume 實驗（alpha 不顯著）+ FinLab 54 策略研究（營收動能 = 台股最強因子）+ K4 基本面 IC 分析（revenue_yoy ICIR 0.317）
> 目標：建立條件篩選 Pipeline + 實作營收動能 / 投信跟單策略 + 8 年回測驗證

---

## 背景

### 方向轉變

從「cross-sectional factor ranking」轉向「多條件篩選 + 營收動能 + 投信籌碼」。

三方面交叉驗證支持此轉變：

| 來源 | 結論 |
|------|------|
| 自有 15 次實驗 | 75 個 price-volume 因子在 142 支寬 universe 全 < ICIR 0.5，淨超額 +0.7% 不顯著 |
| Phase K 基本面分析 | revenue_yoy ICIR 0.317（首次突破 0.3），但 Walk-Forward 超額 +2.7% 仍有限 |
| FinLab 54 策略 | 年化 > 30% 的 16 策略中 **100% 包含營收動能**；投信 > 外資；低 PE/低波動無效 |

### 核心策略方向

| 策略 | FinLab 對標 | 核心因子 | 目標 CAGR |
|------|-----------|---------|----------|
| **A: 營收動能 + 價格確認** | 月營收動能策略 CAGR 33.5% | 營收 3M > 12M、YoY > 15%、價 > MA60 | > 20% |
| **B: 投信跟單 + 營收成長** | 法人跟單 CAGR 31.7% | 投信 10 日買超、營收創新高 | > 20% |

---

## L1：數據管線補齊 ✅

### L1.1 營收數據擴展 ✅

- 從 TW50（51 支）擴大到全 universe（143 支）
- `scripts/download_finmind_data.py` 新增 `--symbols-from-market` + `--force`
- 下載期間：2015-01-01 ~ 2025-12-31

### L1.2 投信買賣超分離 ✅

- 146 支 institutional parquet（外資/投信/自營商分開）
- `src/data/sources/finmind_fundamentals.py` 新增 `get_institutional()` 方法
- 回傳 DataFrame[date, trust_net, foreign_net, dealer_net]

### L1.3 本地 parquet 優先讀取 ✅

- `get_revenue()` / `get_institutional()` 優先讀 `data/fundamental/{symbol}_*.parquet`
- 找不到才呼叫 FinMind API
- Symbol-level cache：同一 symbol 只解析一次 parquet，按日期範圍 filter（避免每日重複讀檔）

### L1.4 Yahoo mode 啟用 FinMind fundamentals ✅

- `create_fundamentals("yahoo")` 自動偵測 FinMind token，有 token 就啟用
- 回測引擎用 Yahoo 價格 + FinMind 基本面，不需切換 data_source

### L1.5 集保數據（⏳ Phase M 依賴）

| 數據 | Dataset | 說明 |
|------|---------|------|
| 散戶持股比例 | `TaiwanStockHoldingSharesPer` | 每週更新，< 10 張持股比例 |

### L1.6 市值數據（⏳ 暫用 close × volume 代理）

---

## L2：條件篩選 Pipeline ✅

### 實作

建立獨立模組 `src/alpha/filter_strategy.py`（非修改 pipeline.py），包含：

```
FilterCondition     — 單一篩選條件（6 運算子：gt/lt/gte/lte/eq/between）
FilterStrategyConfig — 策略配置（filters + rank_by + top_n + max_weight）
FilterStrategy      — Strategy 子類，通用條件篩選邏輯
PRICE_FACTORS       — 8 個價格因子計算器（MA ratio/momentum/volume/RSI）
FUNDAMENTAL_FACTORS — 5 個基本面因子計算器（revenue YoY/acceleration/new_high/trust cumulative）
```

### 預設策略工廠

- `revenue_momentum_filter()` — Strategy A 的 FilterStrategy 版本
- `trust_follow_filter()` — Strategy B 的 FilterStrategy 版本

### 測試

- `tests/unit/test_filter_strategy.py` — 21 tests

---

## L3：策略實作 ✅

### Strategy A：營收動能 + 價格確認

**檔案**：`strategies/revenue_momentum.py`（Standalone）+ `src/alpha/filter_strategy.py`（FilterStrategy 版）

```
條件：
1. 營收 3M avg > 12M avg（營收動能）
2. 營收 YoY > 15%（成長確認）
3. 股價 > 60 日均線（趨勢確認）
4. 近 60 日漲幅 > 0（動能確認）
5. 20 日均量 > 300 張（流動性）
排序：營收 YoY 取前 15 檔
再平衡：月度
```

### Strategy B：投信跟單 + 營收成長

**檔案**：`strategies/trust_follow.py`（Standalone）+ `src/alpha/filter_strategy.py`（FilterStrategy 版）

```
條件：
1. 投信 10 日累計買超 > 15,000 股
2. 營收 3M avg 創 12M 新高
3. 營收 YoY > 20%
4. 20 日均量 > 300 張
排序：投信買超金額取前 10 檔
再平衡：月度
單一持股上限：15%
```

### 效能優化

- 月度 cache：策略只在月份變更時重新計算（`_last_month` + `_cached_weights`），避免每日重複讀取營收/法人 parquet
- 回測配置建議 `rebalance_freq='monthly'`（引擎層面只在月底呼叫 on_bar）

### 新增因子函式

| 因子 | 函式 | 來源 |
|------|------|------|
| `revenue_new_high_factor` | 3M avg 營收達 12M 新高 → 1.0 | FinLab 最強單因子 |
| `revenue_acceleration_factor` | 3M avg / 12M avg 比率 | FinLab 核心指標 |
| `trust_cumulative_factor` | 10 日投信累計淨買超 | FinLab 法人跟單 |

### 策略註冊

- `src/strategy/registry.py`：新增 `revenue_momentum` + `trust_follow`（共 11 策略）
- FilterStrategy 版本透過工廠函式實例化（不走 registry）

### 測試

- `tests/unit/test_revenue_strategies.py` — 29 tests

---

## L4：回測驗證 ⏳

### 初步結果（TW50 × 20 支, 2020-2024, 月度再平衡）

| 策略 | CAGR | Sharpe | MDD | 交易次數 | 耗時 |
|------|------|--------|-----|---------|------|
| momentum_12_1（基線） | +31.6% | 1.57 | 33.1% | 364 | 2s |
| **revenue_momentum** | **+23.8%** | **1.42** | **25.1%** | **163** | **54s** |
| trust_follow | +0.4% | 0.17 | 3.8% | 5 | 28s |

### 觀察

1. **Revenue Momentum 可行**：CAGR +23.8% 超過 §L4.2 門檻（> 15%），Sharpe 1.42 > 0.7，MDD 25.1% < 50%
2. **Trust Follow 需要中小型股**：TW50 大型股中滿足投信買超 + 營收創新高的太少（5 次交易）。FinLab 研究也指出投信主要買中小型股
3. **Momentum 在 TW50 表現最好**：但 MDD 33% 較高

### 待完成

| 項目 | 說明 |
|------|------|
| Trust Follow 閾值調整 | 降低 trust_threshold / 加入中小型股 |
| 交易成本分層 | 大型 30 bps / 中型 50 bps / 小型 80 bps |
| OOS 2025 H2 下行保護 | Kill Switch / 空頭偵測 |

### 驗證標準（StrategyValidator 11 項強制閘門）

所有策略上線前必須通過 `src/backtest/validator.py` 的完整驗證：

| # | 檢查 | 門檻 | 方法 |
|---|------|------|------|
| 1 | CAGR | > 15% | Full backtest |
| 2 | Sharpe | > 0.7 | Full backtest |
| 3 | Max Drawdown | < 50% | Full backtest |
| 4 | Walk-Forward | ≥ 60% 年正 | 滾動 3yr/1yr |
| 5 | PBO | < 50% | Bailey 2015 CSCV |
| 6 | Deflated Sharpe | > 0.95 | Bailey & López de Prado 2014 |
| 7 | Bootstrap P(SR>0) | > 80% | 1,000 次重抽 |
| 8 | OOS holdout | return > 0 | 2025 H2 |
| 9 | vs 1/N 超額 | > 0 | DeMiguel 2009 |
| 10 | 成本佔比 | < 50% × gross | 成本/報酬比 |
| 11 | Factor decay | 近 1 年 SR > 0 | 最近期有效性 |
| + | Universe ≥ 50 | ≥ 50 支 | Selection bias |
| + | Worst regime | > -30% | 最差年度 |

**整合**：`backtest_gate.full_validation()` + `POST /backtest/full-validation` API

### 風險警告

1. **回測 ≠ 實盤** — Quantopian 888 策略 R² < 0.025
2. **擁擠風險** — 動能因子擁擠度上升（FinLab centrality slope = 0.000093）
3. **營收延遲** — 月營收 T+10，極端市場效果打折
4. **倖存者偏差** — Yahoo Finance 僅含現存股票，已下市者不可見

---

## 關鍵檔案

| 檔案 | 變更類型 | 階段 | 狀態 |
|------|---------|:----:|:----:|
| `scripts/download_finmind_data.py` | 修改：`--symbols-from-market` + `--force` | L1 | ✅ |
| `src/data/sources/finmind_fundamentals.py` | 修改：本地 parquet 優先 + `get_institutional()` + symbol-level cache | L1 | ✅ |
| `src/data/sources/__init__.py` | 修改：Yahoo mode 啟用 FinMind fundamentals | L1 | ✅ |
| `src/data/fundamentals.py` | 修改：新增 `get_institutional()` 預設實作 | L1 | ✅ |
| `src/strategy/factors/fundamental.py` | 修改：+3 因子函式 | L1 | ✅ |
| `src/strategy/factors/__init__.py` | 修改：re-export 新因子 | L1 | ✅ |
| `src/strategy/research.py` | 修改：FUNDAMENTAL_REGISTRY +3 條目 | L1 | ✅ |
| `src/alpha/filter_strategy.py` | **新檔案**：FilterStrategy 框架 | L2 | ✅ |
| `strategies/revenue_momentum.py` | **新檔案**：Strategy A | L3 | ✅ |
| `strategies/trust_follow.py` | **新檔案**：Strategy B | L3 | ✅ |
| `src/strategy/registry.py` | 修改：+2 策略 | L3 | ✅ |
| `scripts/run_strategy_backtest.py` | **新檔案**：回測腳本 | L4 | ✅ |
| `tests/unit/test_filter_strategy.py` | **新檔案**：21 tests | L2 | ✅ |
| `tests/unit/test_revenue_strategies.py` | **新檔案**：29 tests | L3 | ✅ |
