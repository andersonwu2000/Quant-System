# 開發計畫書

> **版本**: v1.2
> **日期**: 2026-03-24
> **對應追蹤報告**: `docs/dev/SYSTEM_STATUS_REPORT.md` v1.2
> **目標**: 建立真實的 Alpha 研究能力與實盤交易能力
> **第一階段狀態**: ⚠️ 部分完成 — Tasks 1–6 完整通過 (56 測試)；Tasks 7–8 因 `attribution.py` / `regime.py` 尚未實作導致 import 失敗，pipeline 測試無法執行；Tasks 9–10 為新增待辦

---

## 目錄

1. [開發策略](#1-開發策略)
2. [第一階段：Alpha 研究層](#2-第一階段alpha-研究層)
3. [第二階段：實盤交易能力](#3-第二階段實盤交易能力)
4. [第三階段：穩固與商業化](#4-第三階段穩固與商業化)
5. [技術規格](#5-技術規格)
6. [風險與決策紀錄](#6-風險與決策紀錄)
   - 6.1 技術風險
   - 6.2 已知架構缺陷
   - 6.3 架構決策紀錄

---

## 1. 開發策略

### 1.1 核心原則

**先有 Alpha → 再有實盤 → 最後商業化。**

系統需要先能系統化地發現有效因子、驗證其在扣除交易成本後仍然有效，才有實盤的意義。實盤交易能力是第二步，商業化是遠期目標。

### 1.2 現有基礎

系統已具備完整的回測 + 策略 + 風控框架，以及初步的因子研究工具：

| 已有能力 | 位置 | 說明 |
|---------|------|------|
| 因子函式庫 | `src/strategy/factors.py` | 6 技術因子 + 4 基本面因子，皆為純函式 |
| IC 分析 | `src/strategy/research.py` | Spearman/Pearson IC、IC 時序、hit rate |
| 因子衰減 | `src/strategy/research.py` | 多週期 IC 對比 (1/5/10/20/40/60 日) |
| 因子合成 | `src/strategy/research.py` | 等權 / IC 加權，含橫截面 Z-score |
| 因子註冊表 | `src/strategy/research.py` | `FACTOR_REGISTRY`，6 因子可插拔 |
| 組合最佳化 | `src/strategy/optimizer.py` | 等權重 / 信號加權 / 風險平價 |
| 基本面數據 | `src/data/sources/finmind_fundamentals.py` | PE/PB/ROE/營收/股利/產業分類 |
| 回測引擎 | `src/backtest/engine.py` | 完整回測循環 + 40+ 績效指標 |

### 1.3 缺失環節

| 缺失 | 影響 |
|------|------|
| 無因子中性化 | 因子收益可能來自市場/行業/規模暴露而非真正的 Alpha |
| 無分位數回測 | 無法驗證因子的單調性和多空價差 — 這是因子有效性的金標準 |
| 無換手率分析 | 不知道因子換手率多高、交易成本會吃掉多少 Alpha |
| 無成本感知最佳化 | 現有 optimizer 追求信號最大化，不考慮換倉成本 |
| 無股票池篩選 | 回測可能包含不可交易的標的（流動性不足、剛上市等） |
| 無因子正交化 | 多因子合成時可能重複計算相同信息 |

---

## 2. 第一階段：Alpha 研究層

### 2.1 總覽

在 `src/alpha/` 建立 10 個模組（原計劃 8 個 + 擴充 2 個），形成從因子發現到組合建構的完整 pipeline。

**完成狀態**:

| Task | 模組 | 狀態 | 測試 |
|------|------|------|------|
| 1 | `universe.py` | ✅ 完成 | 8 通過 |
| 2 | `neutralize.py` | ✅ 完成 | 9 通過 |
| 3 | `cross_section.py` | ✅ 完成 | 7 通過 |
| 4 | `turnover.py` | ✅ 完成 | 10 通過 |
| 5 | `orthogonalize.py` | ✅ 完成 | 9 通過 |
| 6 | `construction.py` | ✅ 完成 | 11 通過 |
| 7 | `pipeline.py` | ⚠️ import 失敗 | 18 無法收集 |
| 8 | `strategy.py` | ⚠️ import 失敗（依賴 pipeline） | — |
| 9 | `regime.py` | ❌ 尚未實作 | — |
| 10 | `attribution.py` | ❌ 尚未實作 | — |

> **根本原因**: `pipeline.py` 在頂層引用了 `src.alpha.regime` 與 `src.alpha.attribution`，但這兩個模組尚未建立，導致整個 pipeline import 鏈斷裂。`AlphaStrategy` 與 `registry.py` 中的 `"alpha"` 策略在呼叫時同樣會崩潰。

**依賴關係圖：**

```
                         ┌────────────────────┐
                         │  #1 universe.py    │  ✅
                         │  股票池篩選         │
                         └────────┬───────────┘
                                  │
                         ┌────────▼───────────┐
                         │  #2 neutralize.py  │  ✅
                         │  因子中性化         │
                         └──┬─────┬────────┬──┘
                            │     │        │
                   ┌────────▼─┐ ┌─▼──────┐ ┌▼────────────┐
                   │#3 cross_ │ │#4 turn-│ │#5 orthog-   │
                   │section.py│ │over.py │ │onalize.py   │  ✅✅✅
                   │分位數回測 │ │換手率   │ │因子正交化    │
                   └──────────┘ └───┬────┘ └─────────────┘
                                    │
                           ┌────────▼────────┐
                           │#6 construction. │  ✅
                           │py 成本感知建構   │
                           └────────┬────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
      ┌────────▼────────┐  ┌────────▼────────┐          │
      │ #9 regime.py    │  │ #10 attribution │  ❌ 待實作
      │ 市場狀態分類     │  │ .py 因子歸因     │
      └────────┬────────┘  └────────┬────────┘
               └────────────────────┘
                                    │
                           ┌────────▼────────┐
                           │ #7 pipeline.py  │  ⚠️ 依賴缺失
                           │ Alpha Pipeline  │
                           └────────┬────────┘
                                    │
                           ┌────────▼────────┐
                           │ #8 strategy.py  │  ⚠️ 依賴缺失
                           │ AlphaStrategy   │
                           └─────────────────┘
```

---

### Task 1: 股票池篩選框架

**檔案**: `src/alpha/universe.py`
**依賴**: 無（第一個開發）

**目的**: 定義可投資股票池，排除不可交易或不適合量化策略的標的。沒有乾淨的股票池，所有後續分析的結論都不可靠。

**介面設計**:

```python
@dataclass
class UniverseConfig:
    min_market_cap: float | None = None        # 最低市值（元）
    min_avg_volume: float | None = None        # 最低日均成交量（股）
    min_avg_turnover: float | None = None      # 最低日均成交額（元）
    min_listing_days: int = 252                 # 最少上市天數
    exclude_sectors: list[str] = field(...)     # 排除的產業
    volume_lookback: int = 60                   # 流動性計算的回望天數
    max_missing_pct: float = 0.1               # 最大允許缺值比例

class UniverseFilter:
    def __init__(self, config: UniverseConfig): ...

    def filter(
        self,
        data: dict[str, pd.DataFrame],
        date: pd.Timestamp,
        fundamentals: FundamentalsProvider | None = None,
    ) -> list[str]:
        """回傳在指定日期通過所有篩選條件的標的列表。"""

    def filter_timeseries(
        self,
        data: dict[str, pd.DataFrame],
        dates: list[pd.Timestamp],
        fundamentals: FundamentalsProvider | None = None,
    ) -> dict[pd.Timestamp, list[str]]:
        """回傳每個日期的可投資標的，用於回測。"""
```

**篩選規則**:
1. 流動性篩選：日均成交量 / 日均成交額低於閾值 → 排除
2. 上市天數篩選：上市未滿 N 天 → 排除（避免 IPO 異常波動）
3. 數據完整性：缺值比例超過閾值 → 排除
4. 產業篩選：可排除特定產業（如金融、ETF）
5. 市值篩選：市值低於閾值 → 排除（需基本面數據）

**測試要點**:
- 空數據 / 單一標的 / 大量標的
- 邊界條件：剛好在閾值上
- 時序篩選的結果隨日期變化（標的進出股票池）

---

### Task 2: 因子中性化

**檔案**: `src/alpha/neutralize.py`
**依賴**: Task 1 (股票池篩選)

**目的**: 從原始因子值中移除市場、行業、規模等系統性暴露，隔離出純 Alpha 信號。

一個「看起來有效」的動量因子，可能 80% 的收益來自做多大盤——中性化後才能看到它是否真的能選股。

**介面設計**:

```python
class NeutralizeMethod(Enum):
    MARKET = "market"          # 去市場均值
    INDUSTRY = "industry"      # 行業內去均值
    SIZE = "size"              # 回歸去規模暴露
    INDUSTRY_SIZE = "ind_size" # 行業 + 規模雙重中性化

def neutralize(
    factor_values: pd.DataFrame,         # index=date, columns=symbols
    method: NeutralizeMethod,
    industry_map: dict[str, str] | None = None,  # symbol → 行業
    market_caps: pd.DataFrame | None = None,     # index=date, columns=symbols
) -> pd.DataFrame:
    """回傳中性化後的因子值，同形狀的 DataFrame。"""

def winsorize(
    factor_values: pd.DataFrame,
    lower: float = 0.01,        # 下界百分位
    upper: float = 0.99,        # 上界百分位
) -> pd.DataFrame:
    """極端值處理：截尾到指定百分位。"""

def standardize(
    factor_values: pd.DataFrame,
    method: str = "zscore",     # "zscore" | "rank" | "rank_zscore"
) -> pd.DataFrame:
    """橫截面標準化。"""
```

**中性化方法**:

| 方法 | 數學 | 用途 |
|------|------|------|
| 市場中性 | `f_i - mean(f)` | 去除因子的市場平均暴露 |
| 行業中性 | `f_i - mean(f_industry)` | 去除行業效應，只看業內選股能力 |
| 規模中性 | `residual(f ~ log_cap)` | 回歸去除規模暴露 |
| 行業+規模 | 行業 dummy + log_cap 回歸殘差 | 最嚴格的中性化 |

**處理流程**: 原始因子 → winsorize (去極端值) → standardize (Z-score) → neutralize (去暴露) → 輸出

**測試要點**:
- 中性化後因子的行業/規模暴露應接近 0
- winsorize 正確截尾
- 單一行業 / 少量標的不會崩潰

---

### Task 3: 分位數組合回測

**檔案**: `src/alpha/cross_section.py`
**依賴**: Task 2 (中性化後的因子)

**目的**: 因子有效性的金標準測試。按因子值排序分組，觀察各組收益是否呈現單調遞增/遞減。如果 Q1（最低分位）到 Q5（最高分位）的收益沒有明顯的單調關係，這個因子就不值得用。

**介面設計**:

```python
@dataclass
class QuantileResult:
    factor_name: str
    n_quantiles: int
    quantile_returns: pd.DataFrame    # index=date, columns=Q1..Qn
    mean_returns: pd.Series           # 各分位的平均報酬
    long_short_return: pd.Series      # Qn - Q1 (多空組合) 時序
    long_short_sharpe: float
    monotonicity_score: float         # Spearman rank corr(分位序號, 平均報酬)
    turnover_by_quantile: pd.Series   # 各分位的平均換手率

def quantile_backtest(
    factor_values: pd.DataFrame,    # 中性化後的因子值
    forward_returns: pd.DataFrame,  # 未來 N 天報酬
    n_quantiles: int = 5,           # 分位數 (5=五分位, 10=十分位)
    holding_period: int = 5,        # 持倉週期 (天)
    weight: str = "equal",          # "equal" | "factor"
) -> QuantileResult:
    """執行分位數組合回測。"""

def long_short_analysis(
    result: QuantileResult,
) -> dict:
    """多空組合深入分析：年化報酬、Sharpe、最大回撤、勝率。"""
```

**分析輸出**:
- 各分位數的累積收益曲線
- 多空組合 (Q5 - Q1) 的績效指標
- 單調性分數 (monotonicity)：分位序號 vs 平均報酬的 Spearman 相關
- 各分位的換手率（預備 Task 4）

**驗收標準**: 對已知有效的動量因子跑分位數回測，Q5 應明顯優於 Q1，monotonicity > 0.8。

---

### Task 4: 換手率分析

**檔案**: `src/alpha/turnover.py`
**依賴**: Task 2 (中性化因子)

**目的**: 一個因子即使 IC 很高，如果換手率太高，交易成本會吃掉大部分 Alpha。這個模組量化「因子信號的穩定性」和「交易成本的侵蝕程度」。

**介面設計**:

```python
@dataclass
class TurnoverResult:
    factor_name: str
    avg_turnover: float                  # 平均單邊換手率 (0~1)
    turnover_series: pd.Series           # 每期換手率時序
    cost_drag: float                     # 年化成本侵蝕 (bps)
    net_ic: float                        # 成本調整後的 IC
    breakeven_cost: float                # 盈虧平衡交易成本 (bps)

def compute_turnover(
    weights_t: pd.DataFrame,     # index=date, columns=symbols, values=weight
    weights_t1: pd.DataFrame,    # 下一期權重
) -> pd.Series:
    """逐期計算單邊換手率 = sum(|w_new - w_old|) / 2。"""

def analyze_factor_turnover(
    factor_values: pd.DataFrame,
    n_quantiles: int = 5,
    holding_period: int = 5,
    cost_bps: float = 30.0,      # 單邊交易成本 (bps)，台股預設含手續費+稅
) -> TurnoverResult:
    """完整的因子換手率分析。"""

def cost_adjusted_returns(
    gross_returns: pd.Series,
    turnover: pd.Series,
    cost_bps: float = 30.0,
) -> pd.Series:
    """從毛報酬扣除交易成本，得到淨報酬。"""
```

**關鍵指標**:
- **平均換手率**: 低頻因子 (如價值) 通常 < 20%/月，高頻因子 (如短期反轉) 可能 > 80%/月
- **成本侵蝕**: `avg_turnover × cost_bps × 12 × 2`（年化、雙邊）
- **盈虧平衡成本**: IC 為 0 時的成本，`gross_alpha / (turnover × 12 × 2)`
- **淨 IC**: 扣除成本後的因子信息係數

**台股預設成本模型**: 買入手續費 0.1425% + 賣出手續費 0.1425% + 證交稅 0.3% = 單邊約 30 bps

---

### Task 5: 因子正交化

**檔案**: `src/alpha/orthogonalize.py`
**依賴**: Task 2 (中性化因子)

**目的**: 多因子合成時，如果動量和 RSI 高度相關 (ρ=0.7)，等權合成就相當於動量加倍權重。正交化確保每個因子帶來獨立的信息。

**介面設計**:

```python
def orthogonalize_sequential(
    factor_dict: dict[str, pd.DataFrame],
    priority: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    逐步正交化（改良 Gram-Schmidt）。

    按 priority 順序，每個因子回歸去除前面所有因子的影響，保留殘差。
    priority[0] 保持原樣，priority[1] 去除 [0] 的影響，以此類推。
    """

def orthogonalize_symmetric(
    factor_dict: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """
    對稱正交化（PCA 旋轉）。

    對所有因子做 PCA，旋轉回原空間，使因子兩兩正交但保持可解釋性。
    """

def factor_correlation_matrix(
    factor_dict: dict[str, pd.DataFrame],
    method: str = "spearman",
) -> pd.DataFrame:
    """計算因子間的平均橫截面相關矩陣（用於診斷共線性）。"""
```

**方法選擇指引**:
- **逐步正交化**: 當你有明確的因子優先級時（例如動量是核心因子，其他是輔助）
- **對稱正交化**: 當所有因子地位平等時

---

### Task 6: 成本感知組合建構

**檔案**: `src/alpha/construction.py`
**依賴**: Task 4 (換手率分析)

**目的**: 現有 `optimizer.py` 的 3 個最佳化器只看信號強度，不考慮換倉成本。本模組建立一個在 Alpha 信號和交易成本之間取得平衡的組合建構器。

**介面設計**:

```python
@dataclass
class ConstructionConfig:
    max_weight: float = 0.05              # 單一標的上限
    max_total_weight: float = 0.95        # 總投資比例上限
    min_weight: float = 0.001             # 低於此歸零
    long_only: bool = True
    turnover_penalty: float = 0.0005      # 換手率懲罰係數 (越高越傾向不換倉)
    max_turnover: float | None = None     # 單期最大換手率上限
    cost_bps: float = 30.0               # 單邊成本 (bps)
    half_life: int | None = None          # Alpha 衰減半衰期（天），用於混合新舊信號

def construct_portfolio(
    alpha_signal: pd.Series,              # 當期 Alpha 信號 (symbol → score)
    current_weights: pd.Series | None,    # 當前持倉權重 (None = 空倉)
    config: ConstructionConfig | None = None,
    volatilities: dict[str, float] | None = None,  # 用於風險預算
) -> pd.Series:
    """
    回傳目標權重。

    最佳化目標：max(alpha_exposure - turnover_penalty × turnover)
    約束：權重上限、投資比例、換手率上限
    """

def blend_with_decay(
    new_signal: pd.Series,
    old_signal: pd.Series,
    half_life: int,
) -> pd.Series:
    """以指數衰減混合新舊信號，減少不必要的換倉。"""
```

**與現有 optimizer 的關係**:
- `optimizer.py` 的 `equal_weight`, `signal_weight`, `risk_parity` 保留作為簡單場景使用
- `construction.py` 作為 Alpha 策略的專用建構器，取代 optimizer 成為 Alpha Pipeline 的默認選擇
- 兩者產出相同格式 (`dict[str, float]`)，對下游完全相容

---

### Task 7: Alpha Pipeline

**檔案**: `src/alpha/pipeline.py`
**依賴**: Task 1–6 (所有前置模組)

**目的**: 端到端的 Alpha 研究流水線。用一個配置檔定義完整的因子策略，自動串接所有步驟。

**介面設計**:

```python
@dataclass
class AlphaConfig:
    """Alpha Pipeline 配置。"""
    # 股票池
    universe: UniverseConfig

    # 因子定義
    factors: list[FactorSpec]         # 使用哪些因子 + 參數

    # 處理流程
    winsorize_bounds: tuple[float, float] = (0.01, 0.99)
    standardize_method: str = "zscore"
    neutralize_method: NeutralizeMethod = NeutralizeMethod.INDUSTRY_SIZE
    orthogonalize: bool = True
    orthogonalize_method: str = "sequential"  # "sequential" | "symmetric"

    # 合成
    combine_method: str = "ic"          # "equal" | "ic" | "custom"
    combine_weights: dict[str, float] | None = None  # custom 時使用
    ic_lookback: int = 60               # IC 加權的滾動窗口

    # 組合建構
    construction: ConstructionConfig = field(default_factory=ConstructionConfig)

    # 回測
    holding_period: int = 5             # 持倉週期 (天)
    rebalance_freq: str = "weekly"      # "daily" | "weekly" | "monthly"

@dataclass
class FactorSpec:
    """單因子規格。"""
    name: str                           # 因子名稱 (對應 FACTOR_REGISTRY)
    direction: int = 1                  # 1=越大越好, -1=越小越好
    kwargs: dict = field(default_factory=dict)  # 因子參數覆寫

@dataclass
class AlphaReport:
    """Alpha Pipeline 完整報告。"""
    config: AlphaConfig
    # 單因子分析
    factor_ics: dict[str, ICResult]
    factor_decays: dict[str, DecayResult]
    factor_turnovers: dict[str, TurnoverResult]
    factor_correlations: pd.DataFrame
    # 分位數回測
    quantile_results: dict[str, QuantileResult]
    # 合成 Alpha
    composite_ic: ICResult
    composite_quantile: QuantileResult
    # 組合績效
    backtest_result: BacktestResult      # 復用現有 BacktestResult

class AlphaPipeline:
    def __init__(self, config: AlphaConfig): ...

    def research(
        self,
        data: dict[str, pd.DataFrame],
        fundamentals: FundamentalsProvider | None = None,
    ) -> AlphaReport:
        """
        執行完整的 Alpha 研究流程（不進入回測引擎）：
        1. 股票池篩選
        2. 逐因子計算 + 中性化
        3. 單因子分析 (IC, 衰減, 分位數, 換手率)
        4. 因子正交化
        5. 因子合成
        6. 合成因子的分位數回測
        7. 成本感知組合建構 + 績效統計
        """

    def generate_weights(
        self,
        data: dict[str, pd.DataFrame],
        current_date: pd.Timestamp,
        current_weights: pd.Series | None = None,
        fundamentals: FundamentalsProvider | None = None,
    ) -> dict[str, float]:
        """
        生產模式：給定當前數據和日期，產出目標權重。
        供 AlphaStrategy.on_bar() 調用。
        """
```

**Pipeline 執行流程**:

```
AlphaConfig
    │
    ▼
[1] UniverseFilter.filter_timeseries()     → 每日可投資標的
    │
    ▼
[2] compute_factor_values() × N factors     → 原始因子矩陣
    │
    ▼
[3] winsorize() → standardize()             → 清洗後因子
    │
    ▼
[4] neutralize()                            → 中性化因子
    │
    ▼
[5] 單因子分析:
    ├── compute_ic()                        → IC / ICIR
    ├── factor_decay()                      → 衰減曲線
    ├── quantile_backtest()                 → 分位數收益
    └── analyze_factor_turnover()           → 換手率 + 成本侵蝕
    │
    ▼
[6] orthogonalize_sequential/symmetric()    → 正交化因子
    │
    ▼
[7] combine_factors() (IC 加權)             → 合成 Alpha 信號
    │
    ▼
[8] quantile_backtest(composite)            → 合成因子驗證
    │
    ▼
[9] construct_portfolio()                   → 成本感知的目標權重
    │
    ▼
[10] compute_analytics()                    → 績效報告
```

---

### Task 8: AlphaStrategy 適配器

**檔案**: `src/alpha/__init__.py` 中或獨立檔案
**依賴**: Task 7 (Pipeline)

**目的**: 將 AlphaPipeline 包裝為標準的 `Strategy` 子類，使其能直接被現有回測引擎和 API 執行。

**介面設計**:

```python
class AlphaStrategy(Strategy):
    """
    Alpha Pipeline 的 Strategy 適配器。

    使 AlphaPipeline 產出的權重能直接接入：
    - BacktestEngine.run() 回測
    - API /backtest 端點
    - 未來的 Paper/Live Trading
    """

    def __init__(self, config: AlphaConfig):
        self._pipeline = AlphaPipeline(config)
        self._current_weights: pd.Series | None = None

    def name(self) -> str:
        factor_names = [f.name for f in self._pipeline.config.factors]
        return f"alpha_{'_'.join(factor_names)}"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        data = {sym: ctx.bars(sym) for sym in ctx.universe()}
        weights = self._pipeline.generate_weights(
            data=data,
            current_date=pd.Timestamp(ctx.now()),
            current_weights=self._current_weights,
            fundamentals=...,
        )
        self._current_weights = pd.Series(weights)
        return weights
```

**註冊方式**: 在 `src/strategy/registry.py` 中加入 `alpha` 策略類型，接受 `AlphaConfig` 作為參數。

**驗收標準**: 能用以下方式執行 Alpha 策略回測：
```bash
# CLI
python -m src.cli.main backtest --strategy alpha --config alpha_config.yaml

# API
POST /api/v1/backtest { "strategy": "alpha", "config": { ... } }
```

**已知缺陷**: `on_bar()` 第 75 行直接存取 `ctx._fundamentals`（私有屬性），應改為公開 API `ctx.sector(sym)`。

---

### Task 9: 市場狀態分類（Regime Detection）

**檔案**: `src/alpha/regime.py`
**狀態**: ❌ 待實作（`pipeline.py` 已引用，必須先建立才能修復 import）
**依賴**: Task 2（中性化因子）、Task 3（分位數回測）

**目的**: 分析因子在不同市場狀態（多頭/空頭/震盪）下的表現差異。同一個因子在牛市和熊市的 IC 可能截然不同，Regime 分析幫助判斷何時應增減倉位。

**介面設計**:

```python
from enum import Enum

class MarketRegime(Enum):
    BULL = "bull"        # 多頭（月報酬 > 閾值）
    BEAR = "bear"        # 空頭（月報酬 < -閾值）
    SIDEWAYS = "sideways"  # 震盪

@dataclass
class RegimeICResult:
    factor_name: str
    ic_by_regime: dict[MarketRegime, ICResult]  # 各狀態的 IC
    regime_counts: dict[MarketRegime, int]      # 各狀態的樣本數

def classify_regimes(
    market_returns: pd.Series,       # 市場指數日報酬
    bull_threshold: float = 0.03,    # 月報酬 > 3% = 多頭
    bear_threshold: float = -0.03,   # 月報酬 < -3% = 空頭
) -> pd.Series:
    """回傳每日的市場狀態 (MarketRegime)。"""

def compute_regime_ic(
    factor_values: pd.DataFrame,
    forward_returns: pd.DataFrame,
    regime_series: pd.Series,
) -> RegimeICResult:
    """計算每個市場狀態下的條件 IC。"""
```

**測試要點**:
- Regime 分類邊界條件
- 空 Regime 時不崩潰
- IC 計算與無 Regime 版本一致

---

### Task 10: 因子報酬歸因（Factor Attribution）

**檔案**: `src/alpha/attribution.py`
**狀態**: ❌ 待實作（`pipeline.py` 已引用，必須先建立才能修復 import）
**依賴**: Task 3（分位數回測）、Task 6（組合建構）

**目的**: 分解組合報酬中各因子的貢獻度。當組合持有多個因子時，需要知道哪個因子貢獻了多少報酬，哪個因子在拖累績效。

**介面設計**:

```python
@dataclass
class AttributionResult:
    factor_contributions: dict[str, float]  # 各因子的報酬貢獻
    residual_return: float                  # 無法被因子解釋的殘差
    total_return: float                     # 組合總報酬

def attribute_returns(
    portfolio_returns: pd.Series,           # 組合日報酬
    factor_returns: dict[str, pd.Series],   # 各因子的日報酬
) -> AttributionResult:
    """以 OLS 回歸分解組合報酬至各因子貢獻。"""
```

**測試要點**:
- 各因子貢獻加上殘差 = 總報酬（數值精度）
- 單因子情況下驗證正確性
- 高共線因子不崩潰

---

## 3. 第二階段：實盤交易能力

**前置條件**: 第一階段全部完成（Tasks 1–10 通過），已有經過驗證的 Alpha 策略。

> **券商評估**: 詳細的券商 API 比較請參閱 `docs/dev/BROKER_API_EVALUATION.md`（2026-03-24 更新，涵蓋 10 家券商含台新證券）。

### Task 11: 券商 API 對接

**目標**: 實作 `BrokerAdapter` 介面 (`src/execution/broker.py`)，對接至少一家台灣券商。

**候選券商評估摘要**:

| 券商 | API | Python | 跨平台 | 模擬 | 整合難度 |
|------|-----|:------:|:------:|:----:|:-------:|
| **永豐 Shioaji** | `pip install shioaji` | ✅ 原生 | ✅ Win/Linux/Mac | ✅ `simulation=True` | 低 |
| **富邦 Neo API** | .whl 下載 | ✅ 原生 | ✅ Win/Linux/Mac | ❓ | 中 |
| 元富 MasterLink | 官網下載 | ✅ 原生 | ❌ Win only | ✅ | 中高 |
| 元大 Yuanta | COM/DLL | ⚠️ COM | ❌ Win only | ❓ | 高 |
| 台新 TSSCO | DLL | ❌ 無 | ❌ Win only | ❌ | 極高 |

**決定**: 以**永豐金 Shioaji** 為第一優先，富邦 Neo 作為備援。

**前置作業（需人工完成）**:
1. 開立永豐金證券帳戶
2. 線上簽署「API 服務申請暨委託交易風險預告書」
3. 匯出 CA 電子憑證（.pfx 格式）
4. `pip install shioaji`，`simulation=True` 確認連線

**實作範圍**:
- `ShioajiBroker(BrokerAdapter)`: 實作 `submit_order()`, `cancel_order()`, `query_positions()`, `query_account()`, `is_connected()`
- Shioaji callback 接入 Order 狀態機（SUBMITTED → FILLED/REJECTED）
- `AppState` 加入 mode-aware 路由（`QUANT_MODE=paper` → ShioajiBroker with `simulation=True`，`QUANT_MODE=live` → ShioajiBroker with `simulation=False`）
- 斷線重連機制
- 成交回報推送至 WebSocket `orders` 頻道

### Task 12: 即時行情串流

**目標**: 接入即時報價，填補 WebSocket `market` 頻道（目前為空殼，`ws.py:80` 有 TODO 標記）。

**實作方式**:
- Shioaji `api.quote.subscribe()` 訂閱 tick/quote
- 實作 `RealtimeFeed(DataFeed)` 介面，在 `market` WebSocket 頻道廣播
- 前端 `MarketTicker` 元件已就位，只需接入數據

**依賴**: Task 11（需要 Shioaji 連線）

### Task 13: Paper Trading

**目標**: 完整的紙上交易循環，使用真實行情 + 模擬撮合。

**流程**:
1. 排程器定時觸發（每日 08:55，台股開盤前）
2. 取得最新行情 → 呼叫 Alpha Strategy → 產出目標權重
3. `weights_to_orders()` → RiskEngine 檢查 → SimBroker 模擬執行（使用即時價格）
4. 更新 Portfolio → 推送通知 → 記錄交易日誌
5. 前端即時顯示持倉變化

**與 Live Trading 的差異**: `QUANT_MODE=paper` 使用 `ShioajiBroker(simulation=True)`，數據和信號流程與 live 完全一致。

**驗收標準**: 連跑 4 週 paper trading，持倉正確、NAV 追蹤無誤、通知正常發送。

### Task 14: 通知事件串接

**目標**: 將交易/再平衡/風控事件接入已建好的通知系統（Discord/LINE/Telegram 已實作，尚未與事件串接）。

**事件觸發點**:
- 策略產出新權重 → 通知「再平衡建議」
- 訂單成交 → 通知「成交回報」
- Kill Switch 觸發 → 通知「熔斷告警」
- 每日收盤 → 通知「持倉快照 + 日損益」

### Task 15: HTTPS + 安全

**目標**: 生產環境安全配置。

**內容**:
- Nginx/Caddy 反向代理 + Let's Encrypt TLS
- docker-compose 增加 proxy 服務
- CSP 標頭配置

---

## 4. 第三階段：穩固與商業化

遠期任務，視第一、二階段完成後的需求調整。

| 任務 | 說明 |
|------|------|
| 測試覆蓋率 | pytest-cov + istanbul，Alpha 層需 >80% 覆蓋 |
| Alpha 研究前端 | IC 時序圖、分位數收益圖、因子相關矩陣、Pipeline 配置 UI |
| 多帳戶 | 家族資產管理的帳戶隔離 |
| PDF 報表 | 商業級 Alpha 研究 + 績效報表 |
| 訂閱授權 | 用戶方案管理 |
| 合規 | 使用條款、免責聲明 |

---

## 5. 技術規格

### 5.1 Alpha 層設計原則

| 原則 | 說明 |
|------|------|
| 純函式優先 | 中性化、正交化、標準化皆為無狀態純函式，方便測試和組合 |
| DataFrame in / DataFrame out | 所有分析函式的輸入輸出統一為 `pd.DataFrame(index=date, columns=symbols)` |
| 橫截面操作 | 所有變換在每個日期的橫截面上獨立執行，保證時間因果性 |
| 配置驅動 | AlphaConfig dataclass 定義完整 Pipeline，可序列化為 YAML/JSON |
| 向後相容 | AlphaStrategy 產出 `dict[str, float]`，對回測引擎和 API 透明 |

### 5.2 數據格式約定

```
因子值 / 報酬 / 權重：
    pd.DataFrame
    index  = pd.DatetimeIndex (tz-naive, 交易日)
    columns = str (symbol)
    values  = float

行業映射：
    dict[str, str]  # symbol → industry

市值：
    pd.DataFrame (同因子值格式)
```

### 5.3 測試策略

每個 Alpha 模組需要：
1. **單元測試**: 純函式的數學正確性（已知輸入 → 預期輸出）
2. **性質測試**: 中性化後市場暴露 ≈ 0、正交化後相關 ≈ 0
3. **整合測試**: Pipeline 端到端跑通
4. **回歸測試**: 固定數據集上的結果不變（防止重構引入 bug）

### 5.4 效能考量

| 場景 | 預估規模 | 策略 |
|------|---------|------|
| 台股全市場 | ~1,800 標的 × 5 年 × 5 因子 | 向量化 pandas 操作，避免逐行迴圈 |
| IC 計算 | ~1,200 交易日 × 1,800 標的 | `DataFrame.rank()` + `corr()`，不手動排序 |
| 最佳化 | 單期 ~200 標的 | scipy.optimize 足夠，不需 CVXPY |

---

## 6. 風險與決策紀錄

### 6.1 技術風險

| 風險 | 影響 | 緩解 |
|------|------|------|
| 台股基本面數據不完整 | 行業/市值中性化效果打折 | FinMindFundamentals 已有產業分類，市值可從股價×股數估算 |
| 因子在台股樣本太少 | 橫截面標的不夠（vs 美股 3000+） | 放寬分位數到 5 組（非 10 組），使用 Spearman 而非 Pearson |
| 存活者偏差 | 回測只看到活下來的股票 | UniverseFilter 按日期篩選，不使用未來股票池 |
| 前瞻偏差 | 基本面數據可能有發佈延遲 | FinMindFundamentals 的 point-in-time 查詢已考慮發佈日 |

### 6.2 已知架構缺陷

| 位置 | 問題 | 嚴重度 | 修法 |
|------|------|:------:|------|
| `src/alpha/pipeline.py:15–19` | import `attribution` / `regime` 但模組未建立，整條 pipeline import 鏈斷裂 | 🔴 P0 | 先實作 Task 9/10，再解鎖 Task 7/8 |
| `src/alpha/strategy.py:75` | `ctx._fundamentals` 直接存取私有屬性，繞過 Context 公開介面 | 🟡 P2 | 改為 `ctx.sector(sym)` 公開 API |
| `src/api/ws.py:80` | `market` 頻道 TODO 標記，無任何即時資料輸入 | 🔴 P0 | Task 12 實作後解決 |

### 6.3 架構決策紀錄

| 日期 | 決策 | 原因 | 替代方案 |
|------|------|------|---------|
| 2026-03-24 | Alpha 層建為 `src/alpha/`，不合併入 `src/strategy/` | Alpha 研究是獨立關注點，不應污染策略引擎的簡潔性 | 擴展 `src/strategy/research.py` — 否決，因為 research.py 會膨脹到不可維護 |
| 2026-03-24 | 保留現有 `optimizer.py`，新增 `construction.py` | 簡單策略仍可用等權重/信號加權，不強制所有策略走 Alpha Pipeline | 替換 optimizer — 否決，避免破壞現有策略 |
| 2026-03-24 | AlphaStrategy 作為 Strategy 的子類 | 零成本接入現有回測/API/風控 | 獨立的 Alpha 回測引擎 — 否決，重複造輪子 |
| 2026-03-24 | 券商首選永豐金 Shioaji | Python 原生 SDK、跨平台、simulation=True 無縫切換、社群最活躍；詳見 `BROKER_API_EVALUATION.md` | 富邦 Neo — 保留為備援 |
| 2026-03-24 | Paper Trading 使用 `ShioajiBroker(simulation=True)` 而非 SimBroker | 與 live 流程完全一致，僅切換 simulation flag，減少「模擬環境通過但實盤出問題」的風險 | SimBroker paper — 否決，流程分歧過大 |

---

> **文件維護說明**: 本計畫書隨開發進展更新。每完成一個 Task，標注完成日期並記錄實際與計畫的差異。
