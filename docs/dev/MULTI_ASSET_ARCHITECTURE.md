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

現有的 `Instrument` dataclass 只有 symbol + name + asset_class。需要擴展為完整的金融工具模型：

```python
@dataclass(frozen=True)
class Instrument:
    symbol: str                         # 唯一識別碼 (e.g., "2330.TW", "ES=F", "TLT")
    name: str
    asset_class: AssetClass             # EQUITY, ETF, FUTURES
    sub_class: str                      # "stock", "etf_equity", "etf_bond", "etf_commodity", "future"
    market: Market                      # TW, US
    currency: Currency                  # TWD, USD

    # 合約規格（期貨專用，股票/ETF 可忽略）
    contract_size: Decimal = Decimal(1) # 期貨合約乘數
    tick_size: Decimal = Decimal("0.01")
    margin_rate: Decimal | None = None  # 保證金比率（期貨）
    expiry: date | None = None          # 到期日（期貨）
    lot_size: int = 1                   # 最小交易單位

    # 交易成本
    commission_rate: Decimal = Decimal("0.001425")
    tax_rate: Decimal = Decimal("0.003")  # 賣出稅（台股）
    slippage_model: str = "fixed"       # "fixed", "sqrt", "percentage"

class AssetClass(Enum):
    EQUITY = "equity"           # 個股
    ETF = "etf"                 # ETF（含債券/商品 ETF 代理）
    FUTURES = "futures"         # 期貨

class Market(Enum):
    TW = "tw"
    US = "us"

class Currency(Enum):
    TWD = "TWD"
    USD = "USD"
```

**InstrumentRegistry** — 集中管理所有可交易標的的 metadata：

```python
class InstrumentRegistry:
    def get(self, symbol: str) -> Instrument
    def search(self, query: str, asset_class: AssetClass | None) -> list[Instrument]
    def by_market(self, market: Market) -> list[Instrument]
    def by_asset_class(self, cls: AssetClass) -> list[Instrument]
    def register(self, instrument: Instrument) -> None
    def load_from_config(self, path: str) -> None  # YAML/JSON 配置檔
```

#### Multi-Market DataFeed (`src/data/`)

現有的 `DataFeed` ABC 只回傳 OHLCV DataFrame。不同資產需要不同的數據 schema：

```python
class DataFeed(ABC):
    """通用數據介面 — 所有市場共用。"""
    @abstractmethod
    def get_ohlcv(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """OHLCV 數據（所有資產皆有）。"""

    def get_futures_chain(self, root: str, date: str) -> list[FuturesContract]:
        """期貨合約鏈。"""
        raise NotImplementedError

    def get_fx_rate(self, base: str, quote: str, date: str) -> Decimal:
        """匯率（TWD/USD 轉換）。"""
        raise NotImplementedError
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
├── regime.py                          # 市場狀態識別（擴展現有 src/alpha/regime.py）
├── cross_asset_signals.py             # 跨資產信號：動量、利差、波動率
├── views.py                           # 投資觀點生成 (Black-Litterman 的 views)
├── strategic.py                       # 戰略配置（長期目標比例）
├── tactical.py                        # 戰術配置（短期偏離）
└── __init__.py
```

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
├── optimizer.py                       # 跨資產最佳化器
├── risk_model.py                      # 多資產風險模型（相關矩陣、因子風險）
├── currency.py                        # 幣別暴露管理、對沖決策
├── constraints.py                     # 約束：槓桿、保證金、流動性、監管限制
├── rebalance.py                       # 再平衡觸發邏輯（閾值、日曆、信號驅動）
└── __init__.py
```

**組合建構流程**：

```
第一步：戰略配置 (Strategic Asset Allocation)
    長期目標比例：股票 60% / 債券 30% / 商品 10%
    ↓
第二步：戰術偏離 (Tactical Overlay)
    宏觀信號 → 短期調整：股票 50% / 債券 35% / 商品 15%
    ↓
第三步：資產內選擇 (Within-Asset Selection)
    股票 50% 中 → Alpha Pipeline 選出具體個股權重
    債券ETF 35% 中 → TLT/IEF/LQD/HYG 配比
    商品 15% 中 → GLD/期貨 動量/基差選擇
    ↓
第四步：組合最佳化 (Portfolio Optimization)
    • 合併所有標的權重
    • 幣別對沖決策
    • 槓桿/保證金檢查
    • 交易成本最佳化
    • 最終目標持倉
```

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
@dataclass
class Position:
    instrument: Instrument              # 替代原本的 symbol: str
    quantity: Decimal
    avg_cost: Decimal
    currency: Currency                  # 持倉幣別
    margin_used: Decimal = Decimal(0)   # 佔用保證金

@dataclass
class Portfolio:
    positions: dict[str, Position]
    cash: dict[Currency, Decimal]       # 多幣別現金（替代單一 cash）
    base_currency: Currency = Currency.TWD

    @property
    def nav(self) -> Decimal:
        """計算 NAV 需要即時匯率。"""

    def currency_exposure(self) -> dict[Currency, Decimal]:
        """各幣別暴露（用於對沖決策）。"""

    def asset_class_weights(self) -> dict[AssetClass, float]:
        """各資產類別的權重。"""
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

| 任務 | 說明 |
|------|------|
| Instrument Registry | 統一標的模型，支援各資產類型 metadata |
| Multi-Currency Portfolio | 多幣別現金、匯率轉換、幣別暴露計算 |
| 擴展 DataFeed | 增加期貨合約鏈、匯率 (TWD/USD) 數據 |
| FRED 數據源 | 美國宏觀經濟數據 (GDP, CPI, 利率) |

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
│   ├── regime.py            #   市場狀態 (擴展自 alpha/regime.py)
│   ├── cross_asset.py       #   跨資產動量/carry/value 信號
│   ├── views.py             #   Black-Litterman 觀點
│   ├── strategic.py         #   戰略配置 (長期目標)
│   └── tactical.py          #   戰術配置 (短期偏離)
│
├── portfolio/               # [NEW] 多資產組合管理
│   ├── optimizer.py         #   Risk Parity, BL, HRP, MVO
│   ├── risk_model.py        #   因子風險模型 + 相關矩陣
│   ├── currency.py          #   幣別暴露 + 對沖決策
│   ├── constraints.py       #   槓桿/保證金/流動性約束
│   └── rebalance.py         #   再平衡邏輯
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
| 開發順序建議？ | 先做 Instrument Registry 和多幣別 Portfolio（基礎設施），再做 Allocation（Alpha 能力），最後做 Optimizer（組合建構） |
