# Phase L：策略方向轉型 — 條件篩選 + 營收動能

> 狀態：🟡 進行中（L1 部分 + L2 + L3 已完成）
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

## L1：數據管線補齊

### L1.1 營收動能因子（已有部分基礎）

Phase K 已下載 `TaiwanStockMonthRevenue` 到 `data/fundamental/`（51 支），但需要：

1. **擴大 Universe** — 從 TW50 擴大到 data/market/ 所有 142 支
2. **新增營收衍生指標**：
   - `revenue_3m_avg` — 近 3 月平均營收
   - `revenue_12m_avg` — 近 12 月平均營收
   - `revenue_acceleration` — 3M avg / 12M avg（FinLab 核心指標）
   - `revenue_new_high` — 3M avg 是否創 12M 新高（boolean）
3. **營收發布日對齊** — 月營收每月 10 日前公布，確保回測不 look-ahead

**修改**：
- `scripts/download_finmind_data.py`：支援 `--symbols-from-market` 自動取 data/market/ 所有 symbol
- `scripts/run_fundamental_analysis.py`：加入新營收指標

### L1.2 投信買賣超分離

Phase K 已下載 `TaiwanStockInstitutionalInvestors`，且 `finmind_fundamentals.py` 已有 `get_institutional()` 方法（已被 linter 修改加入）。但需要：

1. **投信 10 日累計淨買超** — FinLab 核心指標
2. **外資 / 投信 / 自營商分開**（K2 的 parquet 已存有 name 欄位）
3. **正規化**：淨買金額 / 成交金額（cross-sectional 可比性）

**修改**：
- `src/strategy/factors/fundamental.py`：新增 `trust_cumulative_factor`（已被 linter 加入）
- `src/strategy/research.py`：FUNDAMENTAL_REGISTRY 新增 `trust_cumulative`

### L1.3 集保數據（P1，Strategy C 依賴）

| 數據 | Dataset | 說明 |
|------|---------|------|
| 散戶持股比例 | `TaiwanStockHoldingSharesPer` | 每週更新，< 10 張持股比例 |

**新增**：
- `scripts/download_finmind_data.py`：加入 `holding_shares` dataset
- `src/data/sources/finmind_fundamentals.py`：`get_holding_shares()` 方法
- 存儲：`data/fundamental/{symbol}_holding_shares.parquet`

### L1.4 市值數據

| 數據 | Dataset | 說明 |
|------|---------|------|
| 精確市值 | `TaiwanStockMarketValue` | 每日市值，取代 close × volume proxy |

**修改**：
- `scripts/download_finmind_data.py`：加入 `market_value` dataset
- `src/strategy/factors/fundamental.py`：`size_factor()` 改用真實 market_cap

---

## L2：Alpha Pipeline 條件篩選模式

### 現狀

目前 `AlphaPipeline` 只支援 cross-sectional ranking（每個因子算 z-score → 排名 → 取 top quintile）。

### 需求

新增 **boolean filter 模式**：每個因子定義一個閾值條件，通過所有條件的股票組成股票池，再用排序指標排名取前 N 檔。

### 設計

```python
# src/alpha/pipeline.py 新增

@dataclass
class FilterCondition:
    """單一篩選條件。"""
    factor_name: str          # 因子名稱
    operator: str             # "gt" | "lt" | "gte" | "lte" | "eq" | "between"
    threshold: float | tuple  # 閾值

@dataclass
class FilterStrategyConfig:
    """條件篩選策略配置。"""
    filters: list[FilterCondition]       # 篩選條件列表（AND 邏輯）
    rank_by: str                         # 排序依據的因子
    top_n: int = 15                      # 取前 N 檔
    rebalance: str = "monthly"           # 再平衡頻率
    max_weight: float = 0.15             # 單一持股上限
    min_volume_20d: int = 300            # 20 日均量最低門檻（張）

class FilterStrategy(Strategy):
    """條件篩選策略 — 替代 cross-sectional ranking。"""

    def __init__(self, config: FilterStrategyConfig): ...

    def on_bar(self, ctx: Context) -> dict[str, float]:
        # 1. 取得所有因子值
        # 2. 對每個 FilterCondition 篩選（AND）
        # 3. 通過的股票按 rank_by 排序
        # 4. 取前 top_n 檔，等權分配
        ...
```

### 檔案變更

| 檔案 | 變更 |
|------|------|
| `src/alpha/pipeline.py` | 新增 `FilterCondition`, `FilterStrategyConfig`, `FilterStrategy` |
| `src/strategy/base.py` | `FilterStrategy` 繼承 `Strategy` ABC |
| `src/strategy/registry.py` | 註冊 `filter_revenue`, `filter_trust` 等策略名 |
| `tests/unit/test_filter_strategy.py` | **新檔案** ~8 tests |

---

## L3：策略實作

### L3.1 Strategy A：營收動能 + 價格確認

```python
FilterStrategyConfig(
    filters=[
        FilterCondition("revenue_acceleration", "gt", 1.0),   # 3M avg > 12M avg
        FilterCondition("revenue_yoy", "gt", 15.0),           # YoY > 15%
        FilterCondition("price_vs_ma60", "gt", 0.0),          # 股價 > 60 日均線
        FilterCondition("momentum_60d", "gt", 0.0),           # 近 60 日漲幅 > 0
        FilterCondition("volume_20d_avg", "gt", 300),         # 20 日均量 > 300 張
    ],
    rank_by="revenue_yoy",
    top_n=15,
    rebalance="monthly",
    max_weight=0.10,
)
```

### L3.2 Strategy B：投信跟單 + 營收成長

```python
FilterStrategyConfig(
    filters=[
        FilterCondition("trust_10d_cumulative", "gt", 15000), # 投信 10 日買超 > 15,000 股
        FilterCondition("revenue_new_high", "eq", 1.0),       # 營收 3M avg 創 12M 新高
        FilterCondition("revenue_yoy", "gt", 20.0),           # YoY > 20%
        FilterCondition("volume_20d_avg", "gt", 300),         # 20 日均量 > 300 張
    ],
    rank_by="trust_10d_cumulative",
    top_n=10,
    rebalance="monthly",
    max_weight=0.15,
)
```

### L3.3 輔助因子計算

需新增的非註冊因子（直接在 FilterStrategy 中計算）：

| 因子 | 計算 | 數據源 |
|------|------|--------|
| price_vs_ma60 | close / SMA(close, 60) - 1 | 價格 |
| momentum_60d | close.pct_change(60) | 價格 |
| volume_20d_avg | volume.rolling(20).mean() / 1000 | 價格（轉為「張」）|
| trust_10d_cumulative | trust_net.rolling(10).sum() | 法人 parquet |
| revenue_acceleration | revenue_3m_avg / revenue_12m_avg | 營收 parquet |
| revenue_new_high | (revenue_3m_avg >= revenue_12m_max) ? 1 : 0 | 營收 parquet |

---

## L4：8 年回測驗證

### L4.1 回測設定

| 項目 | 設定 |
|------|------|
| 期間 | 2017-01 ~ 2025-12（8 年） |
| Universe | data/market/ 全部台股（需下載更長歷史） |
| 再平衡 | 月度（每月 10 日後，營收公布） |
| 交易成本 | 大型股 30 bps、中型 50 bps、小型 80 bps + 證交稅 30 bps |
| DD control | 10% |
| 基準 | 1/N 等權月度再平衡 |

### L4.2 驗證標準

| 指標 | 門檻 |
|------|------|
| CAGR（扣成本） | > 15% |
| Sharpe | > 0.7 |
| Max Drawdown | < 50% |
| vs 1/N 超額 | > 0% |
| Walk-Forward（3 年訓練 / 1 年測試） | OOS Sharpe > 0 |
| PBO（Bailey 2015） | < 50% |
| OOS 2025 H2 | 報酬 > 0 |
| 年化換手率 | < 80%（月度） |

### L4.3 風險警告

1. **回測 ≠ 實盤** — Quantopian 888 策略 R² < 0.025
2. **擁擠風險** — 動能因子擁擠度上升（FinLab centrality slope = 0.000093）
3. **營收延遲** — 月營收 T+10，極端市場效果打折
4. **倖存者偏差** — 需確認回測排除已下市股票

---

## 關鍵檔案變更

| 檔案 | 變更類型 | 階段 |
|------|---------|:----:|
| `scripts/download_finmind_data.py` | 修改：擴大 universe + 新 dataset | L1 |
| `src/strategy/factors/fundamental.py` | 修改：營收加速度、營收創新高、投信累計 | L1 |
| `src/strategy/research.py` | 修改：FUNDAMENTAL_REGISTRY 新增 | L1 |
| `src/data/sources/finmind_fundamentals.py` | 修改：get_holding_shares() | L1 |
| `src/alpha/pipeline.py` | 修改：FilterCondition + FilterStrategy | L2 |
| `strategies/revenue_momentum.py` | **新檔案**：Strategy A | L3 |
| `strategies/trust_following.py` | **新檔案**：Strategy B | L3 |
| `scripts/run_strategy_backtest.py` | **新檔案**：8 年回測腳本 | L4 |
| `tests/unit/test_filter_strategy.py` | **新檔案** | L2 |

---

## 執行順序

```
L1（數據管線）──→ L2（條件篩選 Pipeline）──→ L3（策略實作）──→ L4（8 年回測）
     │                     │
     ├── L1.1 營收擴展      └── 可與 L1 並行開發
     ├── L1.2 投信分離
     ├── L1.3 集保（P1）
     └── L1.4 市值
```
