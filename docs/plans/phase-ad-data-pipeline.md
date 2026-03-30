# Phase AD：數據平台 — 從散落 Parquet 到生產級數據基礎設施

> 狀態：🚧 Phase 1-3 實作完成，Phase 4 待做
> 前置：Phase K（數據品質基礎）✅、Phase T（Paper Trading）✅
> 日期：2026-03-30（v2 重寫 + 實作）

---

## 1. 背景與問題

### 1.1 現狀盤點

系統目前的數據架構是在回測研究期間自然生長的，沒有統一設計：

```
data/
├── market/          # 1,099 個 {symbol}_1d.parquet — Yahoo/FinMind 混合來源
├── fundamental/     # 3,500+ 個 {symbol}_{type}.parquet — 11 種類型，覆蓋率 5%~80% 不等
├── research/        # universe.txt, baseline — 手動維護
├── paper_trading/   # portfolio state, trades — 無版本控制
└── all_tw_stock_ids.txt  # 靜態檔案，上市/下市不會更新
```

### 1.2 核心問題

| 類別 | 問題 | 影響 |
|------|------|------|
| **可觀測性** | 不知道有什麼數據、覆蓋多少支、最後更新時間 | 每次手動 `ls \| wc -l` |
| **完整性** | 11 種數據類型覆蓋率從 5%（daytrading）到 80%（revenue）不等 | 因子研究受限於最差維度 |
| **新鮮度** | Parquet 永不過期，營收 cache 不過期（M-07） | Paper trading 可能用半年前收盤價下單 |
| **正確性** | 無 look-ahead bias 防護（除 evaluate.py 40 天延遲） | 財報在公告前就被使用 |
| **來源單一** | 幾乎完全依賴 FinMind（覆蓋有限、rate limit 嚴格） | 單點故障 |
| **可攜性** | 數據不在 git，無 manifest，換機器要手動猜 | 無法重現研究環境 |
| **消費介面** | autoresearch agent 用 `data["xxx"][symbol]`，新增數據需改 evaluate.py | 數據擴充和消費者緊耦合 |

### 1.3 將被取代的現有模組

本計畫是完全重構，以下模組將在遷移完成後退役：

| 現有模組 | 位置 | 被什麼取代 |
|----------|------|-----------|
| **DataFeed** (ABC) | `src/data/feed.py` | DataCatalog 統一存取層 |
| **LocalMarketData** | `src/data/sources/parquet_cache.py` | Registry + Refresh Engine |
| **FundamentalsProvider** (ABC) | `src/data/fundamentals.py` | DataCatalog.get() |
| **YahooFeed / FinMindFeed** | `src/data/sources/` | 新 Provider 架構（§3.1） |
| **quality.py** | `src/data/quality.py` | Quality Gate（§4.2） |
| **download_finmind_data.py** | `scripts/` | `catalog refresh` CLI |
| **_async_price_update()** | `src/scheduler/jobs.py:886` | Refresh Engine（§3.5） |

> **注意**：`src/data/store.py`（SQLAlchemy ORM，管理用戶/交易紀錄）**不在取代範圍**。新的統一存取層命名為 `DataCatalog` 避免衝突。

### 1.4 目標

建立三層數據平台：

```
┌─────────────────────────────────────────────────┐
│  Layer 3: Data Serving & Quality                │
│  統一消費介面 + Quality Gate + Freshness 監控    │
├─────────────────────────────────────────────────┤
│  Layer 2: Data Acquisition & Enrichment         │
│  多源採集 + 增量更新 + PIT 標注 + 交叉驗證      │
├─────────────────────────────────────────────────┤
│  Layer 1: Data Catalog & Storage                │
│  統一 Registry + Schema 定義 + 血緣追蹤         │
└─────────────────────────────────────────────────┘
```

---

## 2. Layer 1：Data Catalog & Storage

### 2.1 Securities Master

目前系統沒有統一的股票資訊庫。symbol 散落在 parquet 檔名、`all_tw_stock_ids.txt`、config 中。

**設計：`data/securities_master.parquet`**

| 欄位 | 類型 | 說明 |
|------|------|------|
| `symbol` | str | 主鍵，如 `2330.TW` |
| `bare_id` | str | 不含後綴，如 `2330` |
| `name` | str | 台積電 |
| `exchange` | str | `TWSE` / `TPEX` |
| `industry_code` | str | 兩碼產業代碼 |
| `industry_name` | str | 半導體業 |
| `listed_date` | date | 上市日 |
| `delisted_date` | date \| null | 下市日（null = 仍上市） |
| `status` | str | `active` / `delisted` / `suspended` |
| `lot_size` | int | 交易單位（1000 for TW） |
| `last_updated` | datetime | 最後更新時間 |

**來源**：TWSE OpenAPI `/v1/exchangeReport/STOCK_DAY_ALL`（上市）+ TPEX（上櫃）+ FinMind `taiwan_stock_info()`

**用途**：
- 回測時用 `universe_at(date)` 取得 PIT universe（避免倖存者偏差）
- 產業分類用於因子中性化
- 上市/下市追蹤自動化

### 2.2 Data Registry

統一描述所有數據集的 metadata：

**設計：`src/data/registry.py`**

```python
@dataclass
class DatasetDef:
    name: str                    # "revenue", "institutional", ...
    suffix: str                  # parquet 檔名後綴
    frequency: str               # "daily", "monthly", "quarterly", "event"
    storage_dir: str             # "data/fundamental" or "data/market"
    schema: pa.Schema            # Pandera schema 定義
    providers: list[ProviderDef] # 可用的數據源（按優先順序）
    pit_delay_days: int          # PIT 延遲（營收=40, 季報=按公告日, 日頻=0）
    min_coverage: float          # 最低覆蓋率門檻（低於此值發出警告）
    refresh_cron: str            # 自動刷新排程

REGISTRY: dict[str, DatasetDef] = {
    "price": DatasetDef(
        name="price", suffix="1d", frequency="daily",
        storage_dir="data/market",
        providers=[yahoo_provider, finmind_provider, twse_provider],
        pit_delay_days=0, min_coverage=0.90,
        refresh_cron="0 8 * * 1-5",
    ),
    "revenue": DatasetDef(
        name="revenue", suffix="revenue", frequency="monthly",
        storage_dir="data/fundamental",
        providers=[finmind_provider, mops_provider],
        pit_delay_days=40, min_coverage=0.70,
        refresh_cron="0 8 11 * *",
    ),
    # ... 所有數據類型
}
```

### 2.3 Dataset Manifest

每台機器上實際有什麼數據的快照：

**設計：`data/manifest.json`**（自動生成，不手動維護）

```json
{
  "generated_at": "2026-03-30T20:00:00+08:00",
  "datasets": {
    "price": {
      "count": 1099,
      "total_size_mb": 107,
      "date_range": ["2015-01-05", "2026-03-28"],
      "freshest_bar": "2026-03-28",
      "stalest_bar": "2026-03-15",
      "coverage_vs_master": 0.95
    },
    "revenue": {
      "count": 874,
      "total_size_mb": 12,
      "date_range": ["2013-01-01", "2026-02-28"],
      "coverage_vs_master": 0.76
    }
  }
}
```

**用途**：
- `python -m src.data.catalog status` 一行命令看全局數據狀態
- 換機器時比對 manifest 知道缺什麼
- CI/CD 可驗證數據完整性

### 2.4 Schema 定義（Pandera）

為每種數據類型定義嚴格的 schema：

```python
# src/data/schemas.py
import pandera as pa

ohlcv_schema = pa.DataFrameSchema({
    "open":   pa.Column(float, pa.Check.gt(0)),
    "high":   pa.Column(float, pa.Check.gt(0)),
    "low":    pa.Column(float, pa.Check.gt(0)),
    "close":  pa.Column(float, pa.Check.gt(0)),
    "volume": pa.Column(float, pa.Check.ge(0)),
}, index=pa.Index(pa.DateTime, name="date"))

revenue_schema = pa.DataFrameSchema({
    "date":    pa.Column(pa.DateTime),
    "revenue": pa.Column(float, pa.Check.ge(0)),
    "yoy":     pa.Column(float, nullable=True),
})

institutional_schema = pa.DataFrameSchema({
    "date":        pa.Column(pa.DateTime),
    "foreign_net": pa.Column(float),
    "trust_net":   pa.Column(float),
    "dealer_net":  pa.Column(float),
})
```

每次寫入 parquet 前自動驗證 schema，fail-closed。

### 2.5 Parquet Metadata 血緣

利用 PyArrow 的 parquet metadata 記錄每個檔案的來源：

```python
import pyarrow.parquet as pq

metadata = {
    b"source": b"finmind",
    b"fetch_time": b"2026-03-30T08:00:00+08:00",
    b"api_method": b"taiwan_stock_daily",
    b"row_count": b"2500",
    b"date_range": b"2015-01-05/2026-03-28",
}
# 寫入 parquet 的 schema metadata
table = table.replace_schema_metadata({**table.schema.metadata, **metadata})
```

讀取時可查：
```python
meta = pq.read_metadata("data/market/2330.TW_1d.parquet")
print(meta.schema.metadata)  # → {b"source": b"finmind", ...}
```

---

## 3. Layer 2：Data Acquisition & Enrichment

### 3.1 多源 Provider 架構

擺脫 FinMind 單點依賴，建立多源採集：

```python
# src/data/providers/base.py
class DataProvider(ABC):
    name: str
    rate_limit: RateLimit  # 統一 rate limit 管理

    @abstractmethod
    def fetch(self, symbol: str, dataset: str,
              start: date, end: date) -> pd.DataFrame: ...

    @abstractmethod
    def fetch_bulk(self, symbols: list[str], dataset: str,
                   date: date) -> pd.DataFrame: ...
        """單日全市場快照（適用 TWSE OpenAPI）"""

    @abstractmethod
    def supported_datasets(self) -> list[str]: ...
```

### 3.2 Provider 清單

| Provider | 模組 | 涵蓋數據 | 成本 | 優先順序 |
|----------|------|---------|------|---------|
| **TWSE OpenAPI** | `src/data/providers/twse.py` | 上市股：OHLCV、三大法人、融資融券、PER/PBR | 免費 | 日頻首選 |
| **TPEX OpenAPI** | `src/data/providers/tpex.py` | 上櫃股：同 TWSE | 免費 | 上櫃首選 |
| **FinMind** | `src/data/providers/finmind.py` | 全市場：75 種數據集 | 免費 (600/hr) | 歷史回填、特殊數據 |
| **MOPS 爬蟲** | `src/data/providers/mops.py` | 月營收、財報、股利 | 免費 | 財報交叉驗證 |
| **Yahoo Finance** | `src/data/providers/yahoo.py` | 全球：OHLCV、基本面 | 免費 | 國際標的、fallback |

**Fallback 策略**：

```
Daily OHLCV:  TWSE/TPEX → FinMind → Yahoo
三大法人:      TWSE/TPEX → FinMind
月營收:        FinMind → MOPS
財報:          FinMind → MOPS
融資融券:      TWSE/TPEX → FinMind
```

### 3.3 TWSE/TPEX Provider 設計

TWSE OpenAPI 是台股最重要的免費數據源，但有兩種 endpoint 模式：

**A. OpenAPI（RESTful，僅最新快照）：**
- `GET /v1/exchangeReport/STOCK_DAY_ALL` → 全市場當日行情
- `GET /v1/fund/T86` → 三大法人當日買賣超
- 優點：免認證、結構穩定、JSON
- 缺點：只有最新一天，無歷史

**B. 傳統 endpoint（帶日期參數，可回溯）：**
- `GET /exchangeReport/STOCK_DAY?date=20260328&stockNo=2330`
- `GET /fund/T86?date=20260328`
- 優點：可回溯歷史
- 缺點：rate limit 嚴格（建議 5 秒/request），HTML/JSON 混合

**建議策略**：
- 每日增量用 OpenAPI（一次取全市場，1 個 request）
- 歷史回填用傳統 endpoint（per-date，慢但完整）
- 兩者共用 `src/data/providers/twse.py` 模組

### 3.4 Rate Limit 管理

```python
# src/data/providers/rate_limit.py
@dataclass
class RateLimit:
    max_requests: int      # e.g. 600
    period_seconds: int    # e.g. 3600
    min_interval: float    # e.g. 0.7 秒/request

class RateLimiter:
    """Token bucket rate limiter with multi-token rotation."""

    def __init__(self, tokens: list[str], limit: RateLimit):
        self._tokens = tokens
        self._limit = limit
        self._current_idx = 0
        self._request_times: deque[float] = deque()

    def get_token(self) -> str:
        """取得可用 token，自動輪轉避免 rate limit。"""
        ...

    async def throttle(self) -> None:
        """等待直到可以發送下一個 request。"""
        ...
```

支援多 token 輪轉（如你的兩個 FinMind token），自動在接近 rate limit 時切換。

### 3.5 增量更新引擎

```python
# src/data/refresh.py

@dataclass
class RefreshReport:
    dataset: str
    total_symbols: int
    updated: int            # 成功追加新資料的 symbol 數
    skipped: int            # 已是最新的
    failed: list[str]       # 下載失敗的 symbol（含原因）
    stale: list[str]        # 更新後仍缺最新交易日的
    new_rows: int           # 新增資料筆數
    duration_seconds: float
    provider_used: str

async def refresh_dataset(
    dataset: str,
    symbols: list[str] | None = None,  # None = securities_master 全部 active
    force: bool = False,
    providers: list[str] | None = None,  # None = registry 預設順序
) -> RefreshReport:
    """增量更新單一數據集。

    流程：
    1. 從 registry 取得 dataset 定義
    2. 讀取每個 symbol 的本地 parquet 最後日期
    3. 只下載 last_date+1 到今天
    4. Pandera schema 驗證新資料
    5. concat + drop_duplicates + 寫回（原子寫入）
    6. 更新 parquet metadata
    7. 回報 RefreshReport
    """
```

**原子寫入**：先寫 `{symbol}.tmp.parquet`，驗證通過後 `rename` 覆蓋。失敗不會損壞現有檔案。

### 3.6 Point-in-Time (PIT) 標注

防止 look-ahead bias 的核心機制：

| 數據類型 | PIT 規則 | 實作方式 |
|----------|---------|---------|
| 日線 OHLCV | 收盤後即可用 | `pit_delay_days=0` |
| 月營收 | 每月 10 日前公布上月 | `pit_delay_days=40`（已有） |
| Q1 季報 | 5/15 前公布 | `announcement_date` 欄位 |
| Q2 半年報 | 8/14 前 | 同上 |
| Q3 季報 | 11/14 前 | 同上 |
| Q4 年報 | 次年 3/31 前 | 同上 |
| 三大法人 | 收盤後 ~16:00 | `pit_delay_days=0` |
| 融資融券 | 收盤後 ~20:00 | `pit_delay_days=0` |

**財報 PIT 實作**：

```python
# 每筆財報記錄加入 announcement_date
# announcement_date = 實際公告日（從 MOPS 爬取）或保守估計（截止日）
# 回測時：只能使用 announcement_date <= current_date 的記錄

QUARTERLY_DEADLINES = {
    "Q1": (5, 15),   # 5/15 前
    "Q2": (8, 14),   # 8/14 前
    "Q3": (11, 14),  # 11/14 前
    "Q4": (3, 31),   # 次年 3/31 前
}

def conservative_announcement_date(report_date: date, quarter: str) -> date:
    """保守估計公告日 = 截止日（最遲可用日期）。"""
    month, day = QUARTERLY_DEADLINES[quarter]
    year = report_date.year + (1 if quarter == "Q4" else 0)
    return date(year, month, day)
```

### 3.7 跨源交叉驗證

同一筆數據從多源取得後比對：

```python
# src/data/reconcile.py

@dataclass
class ReconcileResult:
    symbol: str
    field: str              # "close", "volume", etc.
    source_a: str
    source_b: str
    match_rate: float       # 一致率（0-1）
    max_deviation: float    # 最大偏差百分比
    anomaly_dates: list[date]  # 不一致的日期

async def cross_validate(
    symbol: str,
    dataset: str,
    date_range: tuple[date, date],
    sources: list[str] = ("twse", "finmind"),
) -> ReconcileResult:
    """比對兩個數據源的同一筆資料。"""
```

**使用場景**：
- 每日增量更新後，抽樣 10% 的 symbol 做交叉驗證
- 發現偏差 > 1% 自動告警
- 月營收、三大法人等關鍵數據做 100% 交叉驗證

---

## 4. Layer 3：Data Serving & Quality

### 4.1 統一數據消費介面

取代目前散落各處的 parquet 讀取邏輯：

```python
# src/data/store.py

class DataCatalog:
    """統一數據存取層 — 所有消費者（回測、paper trading、autoresearch）共用。

    注意：不叫 DataStore（已被 src/data/store.py ORM 佔用）。
    無 in-memory cache — 遵循本地優先原則，每次從 parquet 讀取。
    """

    def __init__(self, base_dir: str = "data"):
        self._registry = load_registry()
        self._master = load_securities_master()

    def get(
        self,
        dataset: str,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        pit_date: date | None = None,  # PIT 查詢：只回傳此日前公告的資料
    ) -> pd.DataFrame:
        """取得單一 symbol 的數據。"""

    def get_cross_section(
        self,
        dataset: str,
        date: date,
        symbols: list[str] | None = None,  # None = active universe
    ) -> pd.DataFrame:
        """取得某日全市場截面數據（因子計算用）。"""

    def get_panel(
        self,
        dataset: str,
        symbols: list[str],
        start: date,
        end: date,
    ) -> pd.DataFrame:
        """取得面板數據（index=date, columns=symbols）。"""

    def available_datasets(self) -> list[str]:
        """列出所有可用數據集。"""

    def coverage(self, dataset: str) -> dict:
        """回傳數據集覆蓋率統計。"""
```

**Autoresearch 整合**：
evaluate.py 的 `data["xxx"][symbol]` 介面不變（READ-ONLY 檔案）。只改 `_load_all_data()` 內部實作，從直接讀 parquet 改為透過 `DataCatalog.get()`。消費者介面（`data["xxx"][symbol]`）維持不動。

### 4.2 Pre-Trade Quality Gate

交易前的數據品質閘門（fail-closed）：

```python
# src/data/quality_gate.py

@dataclass
class GateResult:
    passed: bool
    timestamp: datetime
    checks: dict[str, CheckResult]
    blocking: list[str]       # 導致 gate 失敗的 check
    warnings: list[str]
    universe_coverage: float  # 有最新數據的比例
    freshest_date: date
    stale_symbols: list[str]

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str

def pre_trade_quality_gate(
    universe: list[str],
    reference_date: date | None = None,
) -> GateResult:
```

**四層檢查**：

| Level | 名稱 | 檢查內容 | 失敗動作 |
|-------|------|---------|---------|
| L1 | Completeness | Universe 中所有 symbol 都有 price parquet | 缺失 >5% → BLOCK |
| L2 | Freshness | 最新 bar >= 上一個交易日 | 過期 >10% → BLOCK |
| L3 | Sanity | close 漲跌 <11%, high≥low, volume>0 | 異常 >10% → BLOCK |
| L4 | Consistency | 新 bar open vs 前日 close 差距合理 | 僅 warning |

**整合**：`execute_pipeline()` 開頭呼叫 gate，失敗則停止交易 + 發通知。

### 4.3 自動刷新排程

**台股每日時間線**：

```
07:30  universe_sync       — 同步上市/下市清單（每月 1 日）
08:00  data_refresh_daily  — TWSE/TPEX OpenAPI 取前日全市場 OHLCV + 法人 + 融券
08:10  data_refresh_fund   — 增量更新持股部位的基本面（只更新持倉 symbol）
08:20  quality_gate        — Pre-trade 品質閘門
08:30  health_check        — 系統健康檢查
09:03  pipeline            — 策略計算 + 下單
13:30  eod_processing      — 對帳 + 績效記錄
14:30  data_refresh_eod    — 收盤後完整刷新（含融資融券延遲數據）
```

**基本面刷新日曆**：

```python
FUNDAMENTAL_SCHEDULE = {
    "revenue":    "0 8 11 * *",     # 每月 11 日
    "financial":  "0 8 16 5,8,11 *", # 季報截止日隔天（5/16, 8/16, 11/16）
    "annual":     "0 8 1 4 *",      # 年報（4/1）
}
```

### 4.4 Freshness 監控

**Phase 1-2 用 Discord 通知（現有機制）**：

Quality Gate 和 Refresh Engine 的結果透過現有 Discord notifier 報告，不引入新依賴。

| 事件 | 動作 |
|------|------|
| Quality Gate 失敗 | Halt trading + Discord 通知（P0） |
| Holdings 數據過期 >1 交易日 | Discord 通知（P0） |
| 覆蓋率 < 90% | Discord 通知 + 排除缺失 symbol（P1） |
| Refresh 失敗（任何 provider） | 記錄到 log + Discord（P2） |

**Phase 4+ 才考慮 Prometheus**：

當系統規模需要時（多策略並行、多台機器），再引入 Prometheus metrics。目前是單人系統，Discord 通知足夠。屆時可加入：`quant_data_freshness_days`, `quant_quality_gate_pass`, `quant_symbol_coverage_ratio` 等 gauge。

---

## 5. 數據集完整清單

### 5.1 目標數據集

| 數據集 | 頻率 | 目標覆蓋 | 當前覆蓋 | 主要來源 | 備援來源 | PIT 延遲 |
|--------|------|---------|---------|---------|---------|---------|
| **price** (OHLCV) | 日 | 1700+ | 1099 | TWSE/TPEX | Yahoo, FinMind | 0 |
| **revenue** (月營收) | 月 | 1700+ | 874 | FinMind | MOPS | 40 天 |
| **financial_statement** (損益表) | 季 | 800+ | 499 | FinMind | MOPS | 按公告日 |
| **cash_flows** (現金流量表) | 季 | 800+ | 299 | FinMind | MOPS | 按公告日 |
| **balance_sheet** (資產負債表) | 季 | 800+ | 7 | FinMind | MOPS | 按公告日 |
| **per** (PER/PBR/殖利率) | 日 | 1000+ | 472 | FinMind | TWSE | 0 |
| **institutional** (三大法人) | 日 | 1700+ | 227 | TWSE/TPEX | FinMind | 0 |
| **margin** (融資融券) | 日 | 1700+ | 456 | TWSE/TPEX | FinMind | 0 |
| **securities_lending** (借券) | 日 | 500+ | 266 | FinMind | — | 0 |
| **shareholding** (外資持股) | 週 | 1000+ | 199 | FinMind | TWSE | 0 |
| **daytrading** (當沖) | 日 | 500+ | 57 | FinMind | — | 0 |
| **dividend** (股利) | 事件 | 1000+ | 51 | FinMind | TWSE, MOPS | 0 |

### 5.2 未來擴展候選

| 數據集 | 頻率 | 來源 | 因子潛力 | 優先級 |
|--------|------|------|---------|--------|
| **holding_shares_per** (股權分散表) | 週 | FinMind (付費) | 大戶/散戶持股變化 — 強訊號 | P1 |
| **government_bank** (八大官股買賣) | 日 | FinMind (付費) | 官股護盤指標 | P2 |
| **ptt_sentiment** (PTT 股票版情緒) | 日 | 爬蟲 + NLP | 散戶情緒 — 學術已驗證 | P2 |
| **news_sentiment** (新聞情緒) | 日 | 鉅亨網爬蟲 + NLP | 事件驅動 alpha | P3 |
| **etf_flows** (ETF 申贖) | 日 | TWSE | 資金流向 | P3 |

---

## 6. CLI 工具

所有數據操作統一入口：

```bash
# 查看數據狀態
python -m src.data.catalog status              # 所有數據集覆蓋率 + 新鮮度
python -m src.data.catalog status --dataset revenue  # 單一數據集明細
python -m src.data.catalog gaps                # 覆蓋率低於門檻的數據集

# 增量更新
python -m src.data.catalog refresh --dataset price          # 更新價格
python -m src.data.catalog refresh --dataset all            # 更新全部
python -m src.data.catalog refresh --dataset institutional --force  # 強制重下

# 批量回填
python -m src.data.catalog backfill --dataset institutional --start 2020-01-01
python -m src.data.catalog backfill --dataset all --symbols-from-master

# 品質檢查
python -m src.data.catalog validate --dataset price         # Schema + 合理性檢查
python -m src.data.catalog cross-validate --dataset price --sources twse,finmind

# Manifest
python -m src.data.catalog manifest --export manifest.json  # 生成可攜 manifest
python -m src.data.catalog manifest --diff other_manifest.json  # 比對兩台機器差異

# Securities Master
python -m src.data.catalog sync-universe                    # 同步上市/下市清單
```

---

## 7. 執行計畫

### Phase 1a：Paper Trading 直接受益（P0，本週）

| 步驟 | 內容 | 新增/修改檔案 |
|------|------|-------------|
| 1a-1 | 增量更新引擎（取代 `_async_price_update`） | `src/data/refresh.py` |
| 1a-2 | Quality Gate（fail-closed，交易前閘門） | 擴展 `src/data/quality.py` |
| 1a-3 | 排程整合（refresh → gate → pipeline） | 修改 `src/scheduler/jobs.py` |
| 1a-4 | 測試 | `tests/unit/test_data_refresh.py`, `test_quality_gate.py` |

### Phase 1b：研究基礎（P1，下週）

| 步驟 | 內容 | 新增/修改檔案 |
|------|------|-------------|
| 1b-1 | Securities Master（SQLite，非 parquet） | `src/data/master.py` + 遷移到 `quant.db` |
| 1b-2 | Registry 定義（數據集 metadata） | `src/data/registry.py` |
| 1b-3 | TWSE/TPEX Provider（僅 OpenAPI 日增量） | `src/data/sources/twse.py` |
| 1b-4 | CLI 工具（status + refresh） | `src/data/cli.py`（避免與 DataCatalog 混淆） |

### Phase 2：品質強化（P1，兩週內）

| 步驟 | 內容 | 新增/修改檔案 |
|------|------|-------------|
| 2a | Schema 驗證（先用 pandas assert，規模需要時再引入 Pandera） | `src/data/schemas.py` |
| 2b | PIT 標注（財報公告日） | 修改 refresh pipeline |
| 2c | Parquet metadata 血緣 | 修改 refresh pipeline |
| 2d | Manifest CLI（`catalog status` 即時掃描，不持久化 JSON） | 修改 `src/data/cli.py` |

### Phase 3：數據消費統一（P2，漸進遷移）

| 步驟 | 內容 | 新增/修改檔案 |
|------|------|-------------|
| 3a | DataCatalog 統一存取層（擴展現有 DataFeed） | `src/data/data_catalog.py`（**不是** `store.py`） |
| 3b | evaluate.py `_load_all_data()` 內部改用 DataCatalog | 修改 `scripts/autoresearch/evaluate.py` |
| 3c | 回測引擎漸進切換 | 修改 `src/backtest/engine.py` |
| 3d | Paper trading 漸進切換 | 修改 `src/scheduler/jobs.py` |

> **遷移策略**：Phase 3 逐模組切換。DataCatalog 內部仍讀相同 parquet 路徑（不改儲存格式），
> 但消費者從舊介面（DataFeed/FundamentalsProvider）切換到 DataCatalog。
> 每個模組單獨切換 + 回歸測試。全部切換完成後，刪除 §1.3 列出的退役模組。

### Phase 3e：按來源分離儲存（P1，Phase 3a-3d 後立即執行）

**動機**：現有 `data/market/` 和 `data/fundamental/` 混合了 Yahoo、FinMind、TWSE 等不同來源的數據，無法區分來源、無法跨源比對、新增來源時路徑混亂。從長遠角度，按來源分離是正確的架構。

**目標目錄結構**：

```
data/
├── yahoo/              # Yahoo Finance — OHLCV（國際標的 + TW fallback）
│   └── {sym}_1d.parquet
├── finmind/            # FinMind API — TW 股價 + 12 種基本面/籌碼面
│   ├── {sym}_1d.parquet
│   ├── {sym}_revenue.parquet
│   ├── {sym}_institutional.parquet
│   └── ...
├── twse/               # TWSE/TPEX OpenAPI — 每日全市場快照
│   ├── {sym}_1d.parquet
│   └── {sym}_institutional.parquet
├── paper_trading/      # 不變
└── research/           # 不變
```

**刪除**：`data/market/` 和 `data/fundamental/`（遷移到 `data/finmind/` 後刪除）。

**消費者不變**：DataCatalog 按 Registry 定義的優先級讀取，消費者只呼叫 `catalog.get("price", "2330.TW")`，不關心底層來源。

**實作步驟**：

| 步驟 | 內容 | 修改檔案 |
|------|------|---------|
| 3e-1 | Registry 加入 `providers` 優先級欄位 | `src/data/registry.py` |
| 3e-2 | DataCatalog 路徑解析改為按來源優先級查找 | `src/data/data_catalog.py` |
| 3e-3 | refresh.py 寫入路徑改為 `data/{source}/` | `src/data/refresh.py` |
| 3e-4 | download_finmind_data.py 輸出改為 `data/finmind/` | `scripts/download_finmind_data.py` |
| 3e-5 | quality_gate.py 透過 DataCatalog 讀，不直接讀 `market/` | `src/data/quality_gate.py` |
| 3e-6 | CatalogFeed 路徑跟隨 DataCatalog | `src/data/sources/catalog_feed.py` |
| 3e-7 | 一次性遷移：`market/` → `data/yahoo/`（注意：舊檔案缺 metadata，無法精確區分 Yahoo/FinMind 來源，以 Yahoo 為主歸類），`fundamental/` → `data/finmind/` | 遷移腳本 |
| 3e-8 | 退役 `parquet_cache.py`（LocalMarketData） | `src/data/sources/parquet_cache.py` |
| 3e-9 | 更新 evaluate.py 的 DataCatalog base_dir | `scripts/autoresearch/evaluate.py` |
| 3e-10 | 測試全量回歸 | 既有測試 + 新測試 |

**來源優先級**（DataCatalog 查找順序）：

| 數據集 | 第一優先 | 第二優先 | 第三優先 |
|--------|---------|---------|---------|
| price (OHLCV) | `twse/` | `yahoo/` | `finmind/` |
| institutional | `twse/` | `finmind/` | — |
| revenue | `finmind/` | — | — |
| 其他 fundamental | `finmind/` | — | — |

### Phase 4：擴充覆蓋（P3，持續進行）

| 步驟 | 內容 | 備註 |
|------|------|------|
| 4a | TWSE/TPEX 傳統 endpoint 歷史回填 | 三大法人、融資融券回溯到 2015。rate limit 2s/req |
| 4b | Securities Master 自動維護 | 上市/下市追蹤，月度同步 |
| 4c | 跨源交叉驗證 | `data/yahoo/` vs `data/twse/` 直接比對。同來源（FinMind vs TWSE）驗證價值有限 |
| 4d | MOPS 爬蟲 | 低優先 — ToS 不明確、HTML 頻繁變動、FinMind 數據本身來自 MOPS |
| 4e | 評估 TEJ 學術方案 | 長歷史 + PIT 因子庫 |
| 4f | Prometheus 監控 | 當系統規模需要時（多策略/多機器）再引入 |

---

## 8. 架構圖

```
                    ┌──────────────────────────────────────┐
                    │          Data Consumers               │
                    │  Backtest · Paper Trading · Research   │
                    │  Autoresearch Agent · API Dashboard    │
                    └───────────────┬──────────────────────┘
                                    │
                    ┌───────────────▼──────────────────────┐
                    │         DataStore (統一介面)           │
                    │  get() · get_cross_section() · panel  │
                    │  PIT filtering · schema validation    │
                    └───────────────┬──────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
    ┌─────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
    │  Quality Gate     │  │  Cross-Validate  │  │  Freshness Mon  │
    │  L1-L4 checks     │  │  Multi-source    │  │  Prometheus     │
    │  fail-closed      │  │  reconciliation  │  │  alerts         │
    └─────────┬────────┘  └────────┬────────┘  └────────┬────────┘
              │                     │                     │
    ┌─────────▼─────────────────────▼─────────────────────▼────────┐
    │                    Parquet Storage                            │
    │  data/market/*.parquet · data/fundamental/*.parquet           │
    │  + Pandera schema · + PyArrow metadata (lineage)             │
    │  + securities_master.parquet · + manifest.json               │
    └─────────────────────────┬────────────────────────────────────┘
                              │
    ┌─────────────────────────▼────────────────────────────────────┐
    │                  Refresh Engine                               │
    │  Incremental update · Atomic write · Rate limit management   │
    └────┬──────────┬──────────┬──────────┬──────────┬─────────────┘
         │          │          │          │          │
    ┌────▼───┐ ┌───▼────┐ ┌──▼─────┐ ┌──▼────┐ ┌──▼────┐
    │ TWSE   │ │ TPEX   │ │FinMind │ │ MOPS  │ │ Yahoo │
    │OpenAPI │ │OpenAPI │ │  API   │ │ 爬蟲  │ │Finance│
    └────────┘ └────────┘ └────────┘ └───────┘ └───────┘
```

---

## 9. 設計原則

1. **Fail-closed** — Quality Gate 失敗 → 不交易，絕不用 fallback 數據繼續
2. **本地優先不變** — 增量更新是追加本地 parquet，不改變核心設計
3. **多源冗餘** — 任何單一來源故障不影響交易
4. **PIT 嚴格** — 所有基本面數據標注公告日，回測時不可提前使用
5. **Schema 強制** — 每次寫入前 Pandera 驗證，拒絕不合格數據
6. **原子寫入** — 寫入失敗不損壞現有檔案
7. **可觀測** — 每個環節都有 Prometheus 指標和日誌
8. **冪等** — 任何操作重複執行不產生副作用
9. **可攜** — Manifest 追蹤數據狀態，換機器有清晰的遷移路徑

---

## 10. 參考資料

### 架構設計
- [Securities Master Databases for Algorithmic Trading (QuantStart)](https://www.quantstart.com/articles/Securities-Master-Databases-for-Algorithmic-Trading/)
- [Point-In-Time Data Discussion (Calcbench)](https://www.calcbench.com/blog/post/684461837001097216/a-discussion-on-point-in-time-data)
- [Advanced Look-Ahead Bias Prevention (QuantJourney)](https://quantjourney.substack.com/p/advanced-look-ahead-bias-prevention)
- [Open Source Data Lineage with OpenLineage and Hamilton](https://medium.com/@stefan.krawczyk/open-source-python-data-lineage-with-openlineage-and-hamilton)

### 數據品質
- [Data Validation Landscape 2025 (Aeturrell)](https://aeturrell.com/blog/posts/the-data-validation-landscape-in-2025/)
- [Pandera vs Great Expectations (Endjin)](https://endjin.com/blog/2023/03/a-look-into-pandera-and-great-expectations-for-data-validation)
- [Survivorship Bias Primer (QuantRocket)](https://www.quantrocket.com/blog/survivorship-bias/)
- [Creating a Survivorship Bias-Free Dataset (Teddy Koker)](https://teddykoker.com/2019/05/creating-a-survivorship-bias-free-sp-500-dataset-with-python/)

### 台灣數據源
- [TWSE OpenAPI](https://openapi.twse.com.tw/)
- [TPEX OpenAPI](https://www.tpex.org.tw/openapi/)
- [MOPS 公開資訊觀測站](https://mops.twse.com.tw/)
- [FinMind 官方文件](https://finmind.github.io/)
- [FinMind 籌碼面教學](https://finmind.github.io/tutor/TaiwanMarket/Chip/)
- [TEJ 台灣經濟新報](https://www.tejwin.com/en/)
- [Fugle Developer API](https://developer.fugle.tw/)

### 儲存與格式
- [Why Parquet Matters for Time Series and Finance (QuestDB)](https://questdb.com/blog/why-parquet-matters-for-time-series-and-finance/)
- [Incrementally Loading Data into Parquet (Red Gate)](https://www.red-gate.com/simple-talk/development/python/incrementally-loading-data-into-parquet-with-python/)
- [DuckDB Tutorial for Traders (MarketCalls)](https://www.marketcalls.in/python/duckdb-tutorial-for-traders-a-python-guide.html)
- [DVC vs Git-LFS vs lakeFS (lakeFS)](https://lakefs.io/blog/dvc-vs-git-vs-dolt-vs-lakefs/)

### Pipeline 工具
- [Airflow vs Prefect vs Dagster (ZenML)](https://www.zenml.io/blog/orchestration-showdown-dagster-vs-prefect-vs-airflow)
- [Python Data Pipeline Tools 2026](https://ukdataservices.co.uk/blog/articles/python-data-pipeline-tools-2025)

---

## 11. 審批

### 11.1 第一次審批（2026-03-30，v2 初稿）

判定：✅ 設計品質高。3 個事實修正 + 2 個風險提醒。

<details>
<summary>展開第一次審批細節</summary>

v2 重寫比 v1 好非常多 — 從散列的「加增量更新 + quality gate」升級為完整的三層數據平台設計。

**事實修正**：
1. TWSE 傳統 endpoint `min_interval` 應為 2.0s（不是 0.7s）— `twstock` Issue #39 實測
2. Q2 半年報 8/14 是保守估計，法規允許最遲 9/14 — 需在 `QUARTERLY_DEADLINES` 註解
3. Pandera 不直接和 parquet writer 整合 — 需在 `refresh_dataset()` 明確呼叫 `schema.validate(df)`

**風險提醒**：
1. evaluate.py 是 READ-ONLY — Phase 3b 只改 `_load_all_data()` 內部，不改消費介面
2. MOPS 爬蟲 ToS 不明確 + HTML 頻繁變動 — 降為 Phase 4 低優先

</details>

### 11.2 第二次審批（2026-03-30，獨立驗證）

判定：⚠️ 設計方向正確，但有 6 個結構性問題需修正（已在文件中直接修正）。

#### 已修正的問題

**1. 計畫未列出將被取代的現有模組**

代碼庫有完整的數據抽象層（DataFeed、LocalMarketData、FundamentalsProvider 等），計畫是完全重構但未說明遷移邊界。

**修正**：新增 §1.3 列出將被取代的模組和對應的新設計，明確 `src/data/store.py`（ORM）不在取代範圍。

**2. `DataStore` 命名衝突 + in-memory cache 違反設計哲學**

`src/data/store.py` 已存在（SQLAlchemy ORM）。計畫的 `DataStore._cache: dict` 是 in-memory cache，但用戶設計原則是「本地優先讀本地檔案，不用 in-memory cache」。

**修正**：重命名為 `DataCatalog`，移除 `_cache`，存放於 `src/data/data_catalog.py`。

**3. Phase 1 範圍不現實（7 子任務 = 「P0 立即需要」）**

原 Phase 1 包含 Securities Master、兩個新 Provider、refresh engine、quality gate、CLI、排程整合、測試 — 至少 2-3 週工作量，不是「立即」。

**修正**：拆為 Phase 1a（本週：refresh + gate + 排程，paper trading 直接受益）和 Phase 1b（下週：Securities Master + TWSE Provider + CLI）。

**4. Prometheus 監控過度設計**

單人/家庭系統。5 個 Prometheus metrics + 4 條告警規則引入 Prometheus 依賴，但現有 Discord notifier 已能通知異常。

**修正**：Phase 1-2 用 Discord 通知，Prometheus 降為 Phase 4+ 考慮項。

**5. 跨源交叉驗證效益有限**

FinMind 的三大法人/融資融券/月營收數據上游來自 TWSE/MOPS。TWSE vs FinMind 交叉驗證 = 同源比對。只有 Yahoo vs TWSE（真正不同上游）才有驗證價值。

**修正**：Phase 4c 加註「僅 Yahoo vs TWSE 有意義」。

**6. 缺少遷移策略**

代碼庫中至少 20+ 處直接讀 parquet。從散落直讀切換到 DataCatalog 沒有遷移計畫。

**修正**：Phase 3 加註漸進遷移策略 — DataCatalog 內部仍讀相同 parquet 路徑，模組逐一切換 + 驗證。

#### 額外觀察（未修正，供實作時參考）

**Securities Master 用 SQLite 比 parquet 更適合**：Master 是頻繁更新的 registry（上市/下市），不是時間序列。現有 `quant.db`（SQLite）已存在，加一張 `securities` 表比獨立 `securities_master.parquet` 更自然。實作時決定。

**Schema 驗證不一定需要 Pandera**：目前規模（~1,100 支股票、11 種數據），pandas 的 `assert` + `DataFrame.dtypes` 檢查就夠。Pandera 是額外依賴。可以先用簡單 assert，規模需要時再引入。

**TWSE/TPEX Provider 應只做 OpenAPI 日增量**：傳統 endpoint 歷史回填（2s/req × 1,700 支 × 多年）極慢且有 IP 封鎖風險。歷史數據繼續用 FinMind，TWSE/TPEX 只做每日全市場快照（1 個 request 取全部）。

**Manifest 不需要持久化 JSON**：`catalog status` CLI 每次即時掃描 `data/` 目錄就能產出相同資訊，且永遠準確。持久化 JSON 會過時。只在需要跨機器比對時才 export。

#### 計畫做得好的部分

1. **三層架構**概念清晰 — Catalog & Storage → Acquisition → Serving & Quality
2. **Securities Master** 解決 symbol 散落問題，`universe_at(date)` 是 PIT 正確做法
3. **多源 Fallback** — TWSE/TPEX → FinMind → Yahoo 優先順序合理
4. **PIT 標注**設計完整 — 月營收 40 天 + 季報按公告日 + 保守截止日
5. **原子寫入** — `.tmp.parquet` → `rename` 防止損壞
6. **9 條設計原則**全部合理，特別是 fail-closed + 本地優先不變
