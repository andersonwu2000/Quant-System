# 多資產架構設計

> **目標**: 從單一股票系統演進為涵蓋多個可自動交易市場的投資組合研究與優化系統
> **可交易市場**: 台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
> **不納入**: 直接債券交易（OTC，零售不可行）、實體商品、零售外匯（台灣法規限制）
> **原則**: 忽略中間開發成本，以最終資產管理能力為目標

---

## 1. 現有架構 vs 目標架構

### 現有架構的限制

| 模組 | 限制 | 說明 |
|------|------|------|
| `Instrument` | 只有 symbol + asset_class | 缺少合約規格（到期日、合約乘數、保證金、票息率、幣別） |
| `DataFeed` | 假設 OHLCV 股票數據 | 期貨有到期日/展期、債券有殖利率曲線、商品有現貨/期貨基差 |
| `Portfolio` | 單幣別、無保證金 | 多幣別資產需要匯率轉換、期貨需要保證金計算 |
| `Strategy` | 回傳個股權重 | 無「先決定股債商品比例，再在每類中選標的」的兩層框架 |
| `Alpha 層` | 橫截面選股 | 缺少時間序列信號（宏觀因子、利差、匯率動量）做資產配置 |
| `RiskEngine` | 個股層級規則 | 缺少跨資產相關性、幣別暴露、利率敏感度 |
| `SimBroker` | 台股手續費/稅模型 | 不同市場的費率、保證金、交割制度完全不同 |

### 目標架構總覽

```
┌─────────────────────────────────────────────────────────────────┐
│                     投資組合研究平台                               │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              第三層：投資組合建構與優化                       │   │
│  │                                                          │   │
│  │  Multi-Asset Optimizer                                   │   │
│  │  • 跨資產風險預算 (Risk Parity / Black-Litterman)         │   │
│  │  • 幣別對沖決策                                           │   │
│  │  • 槓桿/保證金約束                                        │   │
│  │  • 交易成本感知（各市場不同）                               │   │
│  │  • 再平衡頻率最佳化                                       │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                       │
│  ┌──────────────────────┼───────────────────────────────────┐   │
│  │              第二層：Alpha 信號                              │   │
│  │                                                          │   │
│  │  ┌─────────────────┐  ┌──────────────────────────────┐   │   │
│  │  │ 資產內 Alpha     │  │ 資產間 Alpha (NEW)            │   │   │
│  │  │ (現有 Alpha 層)  │  │                              │   │   │
│  │  │                 │  │ • 宏觀因子模型                │   │   │
│  │  │ • 因子中性化     │  │   (成長/通膨/利率/信用)       │   │   │
│  │  │ • 分位數回測     │  │ • 跨資產動量/價值/利差        │   │   │
│  │  │ • 正交化/合成    │  │ • 波動率狀態 (VIX regime)    │   │   │
│  │  │ • 成本感知建構   │  │ • 宏觀預測信號               │   │   │
│  │  │                 │  │ • 戰術配置時序信號            │   │   │
│  │  └─────────────────┘  └──────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                         │                                       │
│  ┌──────────────────────┼───────────────────────────────────┐   │
│  │              第一層：數據 + 標的                             │   │
│  │                                                          │   │
│  │  Instrument Registry   Multi-Market DataFeed             │   │
│  │  (統一標的模型)         (各市場數據適配器)                   │   │
│  │                                                          │   │
│  │  台股 │ 美股 │ ETF (含債券/商品代理) │ 期貨             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ╔══════════════════════════════════════════════════════════╗   │
│  ║  基礎設施（現有，擴展）                                     ║   │
│  ║  回測引擎 │ 風險引擎 │ 執行層 │ API │ 前端                  ║   │
│  ╚══════════════════════════════════════════════════════════╝   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 模組設計

### 2.1 第一層：Instrument Registry + Multi-Market DataFeed

#### Instrument Registry (`src/instrument/`)

✅ **已完成**：統一 Instrument 定義在 `src/domain/models.py`，`src/instrument/` 提供 Registry + 預設模板。

```python
# src/domain/models.py（唯一定義，src/instrument/model.py 只做 re-export）

class AssetClass(Enum):
    EQUITY = "equity"           # 個股
    ETF = "etf"                 # ETF（含債券/商品 ETF 代理）
    FUTURE = "future"           # 期貨（注意：FUTURE 非 FUTURES）
    OPTION = "option"

class SubClass(Enum):
    STOCK = "stock"
    ETF_EQUITY = "etf_equity"
    ETF_BOND = "etf_bond"
    ETF_COMMODITY = "etf_commodity"
    ETF_MIXED = "etf_mixed"
    FUTURE = "future"

class Market(Enum):
    TW = "tw"
    US = "us"

# currency 為 str（"TWD" / "USD"），不是 enum

@dataclass(frozen=True)
class Instrument:
    symbol: str                              # 唯一識別碼 (e.g., "2330.TW", "ES=F", "TLT")
    name: str = ""
    asset_class: AssetClass = AssetClass.EQUITY
    sub_class: SubClass = SubClass.STOCK
    market: Market = Market.US
    currency: str = "USD"                    # "TWD" | "USD"（string，非 enum）
    multiplier: Decimal = Decimal("1")       # 期貨合約乘數（股票/ETF 為 1）
    tick_size: Decimal = Decimal("0.01")
    lot_size: int = 1
    margin_rate: Decimal | None = None       # 保證金比率（期貨專用）
    commission_rate: Decimal = Decimal("0.001425")
    tax_rate: Decimal = Decimal("0")
    sector: str = ""
```

**InstrumentRegistry** — 集中管理所有可交易標的的 metadata：

```python
class InstrumentRegistry:
    def get(self, symbol: str) -> Instrument | None
    def get_or_create(self, symbol: str) -> Instrument   # 自動推斷 symbol pattern
    def search(self, query: str, asset_class: AssetClass | None) -> list[Instrument]
    def by_market(self, market: Market) -> list[Instrument]
    def by_asset_class(self, cls: AssetClass) -> list[Instrument]
    def register(self, instrument: Instrument) -> None
    def load_from_yaml(self, path: str) -> None          # YAML 配置檔
```

#### Multi-Market DataFeed (`src/data/`)

現有的 `DataFeed` ABC 只回傳 OHLCV DataFrame。不同資產需要不同的數據 schema：

```python
class DataFeed(ABC):
    """通用數據介面 — 所有市場共用。（實際介面在 src/data/feed.py）"""

    @abstractmethod
    def get_bars(self, symbol: str, start: str | None, end: str | None) -> pd.DataFrame:
        """OHLCV 數據（所有資產皆有）。"""

    @abstractmethod
    def get_latest_price(self, symbol: str) -> Decimal: ...

    def get_fx_rate(self, base: str, quote: str, date: str | None = None) -> Decimal:
        """匯率（預設實作：下載 {base}{quote}=X）。"""
        ...

    def get_futures_chain(self, root_symbol: str) -> list[str]:
        """期貨合約鏈（預設回傳空 list）。"""
        ...
```

**新增數據源**：

| 數據源 | 覆蓋 | 用途 |
|--------|------|------|
| Yahoo Finance (現有) | 美股、ETF、期貨、外匯 | 免費，覆蓋廣 |
| FinMind (現有) | 台股、台灣期貨 | 台灣市場專用 |
| FRED (NEW) | 美國利率、GDP、CPI、失業率 | 宏觀因子 |
| 台灣央行 (NEW) | 台灣利率、匯率 | 台灣宏觀 |

### 2.2 第二層：雙軌 Alpha 系統

#### 資產內 Alpha（保留現有 `src/alpha/`）

現有的橫截面因子研究框架**完全保留**，它回答的問題是：

> 在台股 / 美股 / 商品期貨中，哪些標的應該超配、哪些應該低配？

這是多資產系統中「單一資產類別內的選股/選標的」能力，仍然是核心。

**小幅擴展**：
- 讓因子庫支援期貨因子（基差 backwardation/contango、展期收益 roll yield）
- ETF 分類因子（根據 sub_class 區分 etf_equity / etf_bond / etf_commodity）

#### 資產間 Alpha（新增 `src/allocation/`）

這是全新的模組，回答的問題是：

> 現在應該把多少比例放在股票、債券ETF、商品ETF/期貨、現金？

```
src/allocation/                        # 戰術資產配置
├── macro_factors.py                   # 宏觀因子：成長、通膨、利率、信用
├── cross_asset.py                     # 跨資產信號：動量、carry、value、波動率
├── tactical.py                        # 戰術配置引擎（輸出 dict[AssetClass, float]）
└── __init__.py
```

> **注意**：
> - **市場狀態識別 (regime)** 保留在 `src/alpha/regime.py`（唯一一份），`allocation` 模組直接 import 使用，不重複實作。
> - **戰略配置**（長期目標比例，如股 60%/債 30%）是靜態設定值，透過 `AlphaConfig` 或 YAML 設定檔管理，不單獨建立 `strategic.py` 模組。
> - **Black-Litterman views** 在 Phase C 實作時併入 `src/portfolio/optimizer.py`，與最佳化器緊密耦合，不在 allocation 層單獨放 `views.py`。

**宏觀因子模型**：

| 因子 | 數據來源 | 信號邏輯 |
|------|---------|---------|
| 經濟成長 | GDP、PMI、就業 | 成長加速 → 超配股票 |
| 通膨 | CPI、PPI、油價 | 通膨上升 → 超配商品、TIPS |
| 利率 | 央行利率、殖利率曲線 | 利率下降 → 超配長債 |
| 信用 | 信用利差、違約率 | 利差收窄 → 超配高收益債 |
| 波動率 | VIX、隱含波動率 | 高波動 → 降低股票配置 |

**跨資產因子**：

| 因子 | 定義 | 適用資產 |
|------|------|---------|
| 時間序列動量 | 過去 12 個月報酬 | 所有資產 |
| Carry | 利差 / 股息率 / 展期收益 | 債券、外匯、期貨 |
| Value | 長期均值回歸 (CAPE, 殖利率偏離) | 股票、債券 |
| 防禦性 | 低波動率、高品質 | 股票 |

### 2.3 第三層：Multi-Asset Portfolio Optimizer

現有的 `src/alpha/construction.py` 處理單一資產類別的組合建構。多資產需要一個上層的跨資產最佳化器：

```
src/portfolio/                         # 多資產組合管理（新增）
├── optimizer.py                       # 跨資產最佳化器（MVO/Risk Parity/BL/HRP）
├── risk_model.py                      # 多資產風險模型（相關矩陣、因子風險）
├── currency.py                        # 幣別暴露管理、對沖決策
└── __init__.py
```

> **邊界說明**：
> - **約束 (constraints)**：「拒絕/批准」型的執行期約束（槓桿上限、保證金不足）擴展到 `src/risk/rules.py`；最佳化器的「軟約束」（目標函數懲罰項）內嵌在 `optimizer.py`，不另建 `constraints.py`。
> - **再平衡邏輯**：觸發邏輯（閾值、日曆）保留在 `src/backtest/engine.py`（`_is_rebalance_day`），實盤時由 Scheduler 觸發，不另建 `rebalance.py`。

**組合建構流程與層間資料契約**：

```
第一步：戰略配置（靜態設定）
    輸入：YAML / AlphaConfig
    輸出：strategic_weights: dict[AssetClass, float]
          e.g. {EQUITY: 0.60, ETF: 0.30, FUTURE: 0.10}
    ↓
第二步：戰術偏離（tactical.py）
    輸入：strategic_weights + macro_signals: dict[str, float]
    輸出：tactical_weights: dict[AssetClass, float]
          e.g. {EQUITY: 0.50, ETF: 0.35, FUTURE: 0.15}
    ↓
第三步：資產內選擇（alpha/pipeline.py，per asset class）
    輸入：tactical_weights[cls] + universe_per_class: list[str]
    輸出：symbol_weights: dict[str, float]  ← 各 symbol 的最終分配比例
          e.g. {"AAPL": 0.12, "MSFT": 0.08, "TLT": 0.20, "GC=F": 0.10, ...}
    ↓
第四步：組合最佳化（portfolio/optimizer.py）
    輸入：symbol_weights + covariance_matrix + fx_rates + constraints
    輸出：final_weights: dict[str, float]  ← 送進 weights_to_orders()
```

> **宏觀資料頻率問題**：CPI/GDP/PMI 為月度/季度發布，與每日 Alpha 信號頻率不符。
> 處理策略：以**最新發布值前向填補（forward-fill）**到每日，填補上限 66 個交易日（約 3 個月）。
> 宏觀信號的再計算頻率建議設為月度（`rebalance_freq="monthly"`），而非每日。

**最佳化方法**：

| 方法 | 用途 | 複雜度 |
|------|------|--------|
| Mean-Variance (Markowitz) | 基礎最佳化 | 低 |
| Risk Parity | 等風險貢獻配置 | 中 |
| Black-Litterman | 結合市場均衡 + 主觀觀點 | 中 |
| Hierarchical Risk Parity | 不需要預期報酬估計 | 中 |
| CVaR Optimization | 尾部風險控制 | 高 |

### 2.4 擴展現有模組

#### Portfolio (`src/domain/models.py`)

```python
# 現狀（src/domain/models.py，已實作）

@dataclass
class Portfolio:
    positions: dict[str, Position]
    cash: Decimal                           # 主幣別現金（向後相容）
    cash_by_currency: dict[str, Decimal]    # 多幣別現金 {"TWD": ..., "USD": ...}
    base_currency: str = "TWD"             # str，非 enum

    @property
    def nav(self) -> Decimal:
        """單幣別 NAV（向後相容）。"""

    def nav_in_base(self, fx_rates: dict[tuple[str,str], Decimal] | None) -> Decimal:
        """多幣別 NAV，以 base_currency 計價（回測 _snap_nav 使用此方法）。"""

    def currency_exposure(self) -> dict[str, Decimal]: ...
    def asset_class_weights(self) -> dict[AssetClass, float]: ...
    def total_cash(self, fx_rates: ...) -> Decimal: ...

# Phase D 待擴展：Position 加入 margin_used 欄位（期貨保證金追蹤）
```

#### RiskEngine (`src/risk/`)

新增跨資產風險規則：

```python
# 現有規則（保留）
max_position_weight()       # 單一標的上限
max_sector_weight()         # 板塊上限
max_daily_drawdown()        # 日回撤上限

# 新增規則
max_asset_class_weight()    # 資產類別上限 (e.g., 期貨 ≤ 20%)
max_currency_exposure()     # 單一幣別暴露上限 (e.g., USD ≤ 60%)
max_leverage()              # 總槓桿上限（期貨保證金）
correlation_limit()         # 新增持倉不得使組合相關性超過閾值
stress_test_limit()         # 壓力測試情境下最大虧損
```

#### BacktestEngine (`src/backtest/`)

- 支援多幣別 NAV 計算 (TWD/USD)
- 支援期貨合約展期 (roll)
- 支援保證金追繳 (margin call) 模擬

---

## 3. 開發路線建議

### Phase A：基礎設施升級

✅ **已完成**：Instrument Registry、多幣別 Portfolio、DataFeed 擴展、FRED 數據源、管線整合 (D-01~D-07)、模型統一。

### Phase B：跨資產 Alpha

| 任務 | 說明 |
|------|------|
| 宏觀因子模型 | 成長/通膨/利率/信用 四因子框架 |
| 跨資產信號 | 時序動量、carry、value 在各資產上的表現 |
| 市場狀態識別 | 擴展 regime.py，支援宏觀狀態 |
| 戰術配置引擎 | 從宏觀信號生成資產類別偏離 |

### Phase C：組合建構

| 任務 | 說明 |
|------|------|
| 多資產最佳化器 | Risk Parity + Black-Litterman |
| 幣別對沖決策 | 根據暴露和成本自動決定對沖比例 |
| 兩層組合建構 | 資產間配置 + 資產內選擇 的整合 |
| 再平衡邏輯 | 閾值觸發 + 日曆觸發 + 信號觸發 |

### Phase D：回測 + 風控升級

| 任務 | 說明 |
|------|------|
| 多幣別回測 | NAV 以基準幣別計價，含匯率影響 |
| 期貨展期模擬 | 自動 roll 近月到遠月 |
| 跨資產風控規則 | 幣別/槓桿/久期/壓力測試限制 |
| 績效歸因 | 資產配置歸因 + 選股歸因 + 匯率歸因 |

---

## 4. 對現有 Alpha 層的影響

### 保留不變的

| 模組 | 原因 |
|------|------|
| `universe.py` | 股票池篩選邏輯通用，加個 asset_class 參數即可 |
| `neutralize.py` | 因子中性化是跨市場通用的技術 |
| `orthogonalize.py` | 正交化是數學操作，與資產類型無關 |
| `cross_section.py` | 分位數回測在任何資產上都有效 |
| `turnover.py` | 換手率分析通用 |
| `pipeline.py` | 端到端流水線架構保留，擴展 FactorSpec 支援更多因子 |

### 需要擴展的

| 模組 | 擴展內容 |
|------|---------|
| `factors.py` | 新增期貨因子（基差 backwardation/contango、展期收益 roll yield） |
| `construction.py` | 增加保證金約束、多幣別權重、槓桿限制 |
| `strategy.py` | AlphaStrategy 接受 asset_class 參數，產出特定資產類別的權重 |
| `pipeline.py` | AlphaConfig 增加 asset_class 欄位，自動選用對應的因子集 |

### 全新增加的

| 模組 | 說明 |
|------|------|
| `src/allocation/` | 戰術資產配置（宏觀因子、跨資產信號、觀點生成） |
| `src/portfolio/optimizer.py` | 多資產最佳化器 (Risk Parity, Black-Litterman, HRP) |
| `src/portfolio/risk_model.py` | 跨資產風險模型 |
| `src/portfolio/currency.py` | 幣別管理和對沖 |

---

## 5. 目錄結構（目標狀態）

```
src/
├── instrument/              # [NEW] 統一標的模型
│   ├── model.py             #   Instrument, AssetClass, Market, Currency
│   └── registry.py          #   InstrumentRegistry
│
├── alpha/                   # [KEEP+EXTEND] 資產內 Alpha（橫截面選股/選標的）
│   ├── pipeline.py          #   AlphaPipeline (擴展 asset_class 支援)
│   ├── universe.py          #   UniverseFilter (擴展多資產)
│   ├── neutralize.py        #   (不變)
│   ├── orthogonalize.py     #   (不變)
│   ├── cross_section.py     #   (不變)
│   ├── turnover.py          #   (不變)
│   ├── construction.py      #   (擴展保證金/槓桿)
│   └── strategy.py          #   (不變)
│
├── allocation/              # [NEW] 資產間 Alpha（戰術配置）
│   ├── macro_factors.py     #   宏觀因子模型
│   ├── cross_asset.py       #   跨資產動量/carry/value 信號
│   └── tactical.py          #   戰術配置引擎 (輸出 dict[AssetClass, float])
│   # regime.py 不在此：直接 import src/alpha/regime.py（唯一一份）
│   # strategic 配置不建模組：改用 AlphaConfig / YAML 設定
│
├── portfolio/               # [NEW] 多資產組合管理
│   ├── optimizer.py         #   Risk Parity, BL, HRP, MVO
│   ├── risk_model.py        #   因子風險模型 + 相關矩陣
│   └── currency.py          #   幣別暴露 + 對沖決策
│   # constraints → 擴展 src/risk/rules.py（不另建模組）
│   # rebalance → 保留在 backtest/engine.py + scheduler（不另建模組）
│
├── strategy/                # [KEEP] 策略引擎 + 因子庫
│   ├── factors.py           #   (擴展期貨因子)
│   └── ...
│
├── data/                    # [EXTEND] 多市場數據
│   ├── sources/yahoo.py     #   (現有，已支援期貨/ETF/匯率)
│   ├── sources/finmind.py   #   (現有)
│   └── sources/fred.py      #   [NEW] 美國宏觀數據
│
├── domain/models.py         # [EXTEND] Portfolio → 多幣別, Position → Instrument
├── risk/                    # [EXTEND] 跨資產風控規則
├── execution/               # [EXTEND] 多市場執行 + 期貨展期
├── backtest/                # [EXTEND] 多幣別回測 + 績效歸因
└── ...                      # 其餘模組保留
```

---

## 6. 結論

| 問題 | 答案 |
|------|------|
| Alpha 研究層需要重做嗎？ | **不需要。** 保留並擴展。它做的「橫截面因子選股」在多資產中仍是資產內選擇的核心能力 |
| 最大的架構變更是什麼？ | **新增 Instrument Registry + Allocation 層 + Portfolio Optimizer**。這三者構成多資產的骨幹 |
| 現有哪些模組完全不用改？ | neutralize, orthogonalize, cross_section, turnover — 這些是純數學操作 |
| 開發順序建議？ | ✅ Phase A 已完成基礎設施，Phase B 做 Allocation（宏觀因子 + 跨資產信號），Phase C 做 Portfolio Optimizer |
