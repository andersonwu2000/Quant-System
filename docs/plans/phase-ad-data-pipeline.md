# Phase AD：生產級數據管線 — 從回測到實盤的數據基礎

> 狀態：📋 待開發
> 前置：Phase K（數據品質基礎）✅ 完成、Phase T（Paper Trading 基礎設施）✅ 完成
> 觸發：CODE_REVIEW_20260329 識別出數據管線是 paper trading 上線前的最大阻塞
> 日期：2026-03-29

---

## 背景與動機

### 現狀

系統的數據架構設計目標是**回測研究**，核心原則「本地有就用本地的，沒有才下載」（`parquet_cache.py` line 17）。這個設計在回測階段完全正確，但轉入 paper trading / 實盤時有結構性缺陷：

| 問題 | 影響 | 嚴重度 |
|------|------|:------:|
| 磁碟 parquet 永不過期 | 系統可能用半年前的收盤價下單 | **CRITICAL** |
| 沒有開盤前自動數據刷新 | 策略計算基於過時價格 | **CRITICAL** |
| `_revenue_cache` 全域不過期 | 長期運行用過時營收（M-07） | **HIGH** |
| 沒有增量更新 | 每次全量下載效率低 | **MEDIUM** |
| 沒有 freshness 警報 | 無法偵測「數據過期 N 天」 | **HIGH** |
| 沒有 data quality gate | 下載和下單之間無驗證閘門 | **HIGH** |

### 業界標準

研究來源：QuantRocket Schedule Live Trading、QuantConnect Scheduled Events、Exactpro Market Data Testing、MoldStud Caching for Trading Platforms

**生產級量化系統的數據管線標準架構：**

```
[收盤後] 下載昨日收盤數據
    ↓
[開盤前] Data Quality Gate（完整性 + 合理性 + 新鮮度 + 一致性）
    ↓
[Gate 通過] 觸發策略計算 → 生成訂單
    ↓
[Gate 失敗] Halt trading + 告警
```

關鍵原則：**數據下載和訂單生成之間必須有 validation gate，不能直接串接。**

### 目標

讓系統具備：
1. 每日自動刷新市場數據（增量更新）
2. 開盤前 data quality gate（不通過就不交易）
3. 營收等基本面按公布日曆刷新
4. Freshness 監控和告警
5. Cache 分層過期策略

---

## 階段總覽

| 階段 | 內容 | 優先級 | 複雜度 |
|:----:|------|:------:|:------:|
| AD1 | 增量數據更新機制 | P0 | 中 |
| AD2 | Data Quality Gate | P0 | 中 |
| AD3 | 排程整合（開盤前自動刷新） | P0 | 小 |
| AD4 | 基本面數據按日曆刷新 | P1 | 中 |
| AD5 | Cache 過期與 Freshness 監控 | P1 | 小 |
| AD6 | Universe 維護（上市/下市追蹤） | P2 | 中 |

---

## AD1：增量數據更新

### 現狀

`scripts/download_yahoo_prices.py`（line 34-41）：每次下載完整歷史，如果本地已有 >100 bars 就跳過。沒有「只追加新 bar」的功能。

### 設計

**方案：單檔 read-append-write**（符合現有 symbol-per-file 架構）

```python
# src/data/refresh.py — 新檔案

def refresh_market_data(
    symbols: list[str],
    source: str = "yahoo",
    data_dir: str = "data/market",
    force: bool = False,
) -> RefreshReport:
    """增量更新市場數據。

    每支股票：
    1. 讀取本地 parquet 的最後日期
    2. 只下載 last_date+1 到今天
    3. 驗證新數據 schema 一致
    4. concat + drop_duplicates + 寫回
    """
```

**關鍵細節：**
- 每個 parquet 旁記錄 metadata（`{symbol}_1d.meta.json`）：`last_updated`, `last_bar_date`, `source`, `row_count`
- 新 bar 合併前用 `check_bars()` 驗證品質
- Yahoo Finance rate limit：批次間 0.5s 延遲，50 symbol 一批
- 如果新 bar 數 = 0（非交易日），meta 中更新 `last_checked` 但不改 `last_bar_date`

**RefreshReport 結構：**
```python
@dataclass
class RefreshReport:
    total_symbols: int
    updated: int          # 成功追加新 bar 的 symbol 數
    skipped: int          # 已是最新的
    failed: list[str]     # 下載失敗的 symbol
    stale: list[str]      # 更新後仍缺最新交易日的
    duration_seconds: float
```

### 檔案變更
- **新增** `src/data/refresh.py`：增量更新核心邏輯
- **修改** `src/data/sources/yahoo.py`：新增 `download_since(symbol, since_date)` 方法
- **修改** `src/data/sources/finmind.py`：同上
- **新增** `tests/unit/test_data_refresh.py`

---

## AD2：Data Quality Gate

### 現狀

`src/data/quality.py` 已有 7 項 OHLCV 驗證 + 除權息偵測 + 停牌偵測（Phase K 完成）。但沒有**交易前的 gate 機制** — 品質檢查和交易決策是分離的。

### 設計

```python
# src/data/quality_gate.py — 新檔案

@dataclass
class GateResult:
    passed: bool
    checks: dict[str, bool]   # 每項 check 的結果
    blocking: list[str]       # 導致 gate 失敗的 check
    warnings: list[str]       # 通過但有疑慮
    coverage: float           # universe 中有最新數據的比例
    freshest_date: str        # 最新 bar 日期
    stale_symbols: list[str]  # 缺最新交易日的 symbol

def pre_trade_quality_gate(
    universe: list[str],
    data_dir: str = "data/market",
    reference_date: str | None = None,  # None = 上一個交易日
) -> GateResult:
    """開盤前 data quality gate。Fail-closed：任何 blocking check 失敗 → 不交易。"""
```

### 四層檢查

**Level 1 — 完整性（Completeness）：**
- Universe 中所有 symbol 都有 parquet 檔案
- 缺失比例 > 5% → **BLOCK**
- 個別 symbol 無資料 → 從當日 universe 排除（warning）

**Level 2 — 新鮮度（Freshness）：**
- 每支股票最新 bar 日期 >= 上一個交易日
- 超過 90% 的 symbol 滿足 → PASS
- 低於 90% → **BLOCK**
- 計算方式：用 `exchange_calendars` 或簡易台股交易日曆判斷上一個交易日

**Level 3 — 合理性（Sanity）：**
- 新 bar 的 close vs 前一日 close 變動幅度 < 11%（台股漲跌停 10% + 1% buffer）
- High >= Low, High >= Open, High >= Close
- Volume > 0（排除已知停牌）
- 任何 symbol 異常 → warning（不 block 個別股票）
- 異常比例 > 10% → **BLOCK**（可能是數據源出問題）

**Level 4 — 一致性（Consistency）：**
- 新 bar 的 open 和前一日 close 的差距 < 合理範圍
- 檢查是否有除權息跳空（查 dividend_dates）

### 整合點

```python
# src/scheduler/jobs.py — execute_pipeline 和 execute_rebalance 開頭加入

from src.data.quality_gate import pre_trade_quality_gate

gate = pre_trade_quality_gate(universe)
if not gate.passed:
    logger.critical("DATA QUALITY GATE FAILED: %s", gate.blocking)
    # 發告警通知
    return  # 不交易
```

### 檔案變更
- **新增** `src/data/quality_gate.py`：gate 邏輯
- **修改** `src/scheduler/jobs.py`：`execute_pipeline`, `execute_rebalance`, `monthly_revenue_rebalance` 加入 gate
- **新增** `tests/unit/test_quality_gate.py`

---

## AD3：排程整合

### 現狀

`src/alpha/auto/scheduler.py` 已有 cron 排程框架：
```python
SCHEDULES = {
    "health_check": "30 8 * * 1-5",   # 08:30
    "universe": "50 8 * * 1-5",       # 08:50
    "research": "52 8 * * 1-5",       # 08:52
    "decision": "55 8 * * 1-5",       # 08:55
    "execution": "00 9 * * 1-5",      # 09:00
    "eod_processing": "30 13 * * 1-5", # 13:30
}
```

缺少的：**數據刷新 job** 在 08:50 universe 之前。

### 設計

新增兩個排程 job：

```python
SCHEDULES = {
    # === 新增 ===
    "data_refresh":    "00 8 * * 1-5",   # 08:00 — 增量更新 OHLCV
    "quality_gate":    "20 8 * * 1-5",   # 08:20 — 品質閘門檢查
    # === 現有 ===
    "health_check":    "30 8 * * 1-5",   # 08:30
    "universe":        "50 8 * * 1-5",   # 08:50
    ...
}
```

**時間線（台股日常）：**

```
08:00  data_refresh  — 下載前日收盤 OHLCV（Yahoo Finance 約 06:00 UTC 更新完畢）
08:20  quality_gate  — 驗證數據完整性和新鮮度
08:30  health_check  — 系統健康檢查（含 gate 結果）
08:50  universe      — 根據通過 gate 的 symbol 組建 universe
08:55  decision      — 策略計算（確保用最新數據）
09:00  execution     — 開盤下單
13:30  eod_processing — 收盤後處理（reconcile、績效記錄）
```

**Gate 結果傳遞：**
- `data_refresh` 結果存入 `state.last_refresh_report`
- `quality_gate` 結果存入 `state.last_gate_result`
- `universe` job 讀取 gate 結果，只用通過的 symbol
- 如果 gate 失敗，`decision` 和 `execution` 跳過

### 檔案變更
- **修改** `src/scheduler/jobs.py`：新增 `job_data_refresh()`, `job_quality_gate()`
- **修改** `src/alpha/auto/scheduler.py`：SCHEDULES 加入新 job
- **修改** `src/api/state.py`：AppState 新增 `last_refresh_report`, `last_gate_result`

---

## AD4：基本面數據按日曆刷新

### 台股基本面數據公布時間

| 資料類型 | 公布規則 | 刷新時機 |
|----------|---------|---------|
| **月營收** | 每月 10 日前公布上月營收 | 每月 11 日 08:00 |
| Q1 季報 | 5/15 前 | 5/16 |
| Q2 半年報 | 8/14 前 | 8/15 |
| Q3 季報 | 11/14 前 | 11/15 |
| Q4 年報 | 次年 3/31 前 | 4/1 |
| 法人買賣超 | 每日收盤後 | 每日 EOD |
| 融資融券 | 每日收盤後 | 每日 EOD |

### 設計

```python
# src/data/refresh.py — 新增

FUNDAMENTAL_REFRESH_CALENDAR = {
    "revenue": {
        "cron": "0 8 11 * *",          # 每月 11 日 08:00
        "source": "finmind",
        "dataset": "TaiwanStockMonthRevenue",
    },
    "financial_statement": {
        "cron": "0 8 16 5,8,11 * | 0 8 1 4 *",  # 季報截止後 +1 天
        "source": "finmind",
        "dataset": "TaiwanStockBalanceSheet",
    },
    "institutional": {
        "cron": "0 14 * * 1-5",         # 每日 14:00（收盤後）
        "source": "finmind",
        "dataset": "TaiwanStockInstitutionalInvestors",
    },
    "margin": {
        "cron": "0 14 * * 1-5",
        "source": "finmind",
        "dataset": "TaiwanStockMarginPurchaseShortSale",
    },
}

def refresh_fundamental_data(
    dataset: str,
    symbols: list[str],
    data_dir: str = "data/fundamental",
) -> RefreshReport:
    """按日曆增量更新基本面數據。"""
```

### `_revenue_cache` 過期修復（M-07）

```python
# strategies/revenue_momentum.py

_revenue_cache: dict[str, pd.DataFrame] | None = None
_revenue_cache_date: str | None = None  # 新增：記錄載入日期

def _preload_revenue(...):
    global _revenue_cache, _revenue_cache_date
    today = pd.Timestamp.now().strftime("%Y-%m")
    # 每月刷新一次（營收 10 號公布後）
    if _revenue_cache is not None and _revenue_cache_date == today:
        return _revenue_cache
    # 重新載入...
    _revenue_cache_date = today
```

### 檔案變更
- **修改** `src/data/refresh.py`：新增 `refresh_fundamental_data()` + 日曆配置
- **修改** `src/scheduler/jobs.py`：新增 `job_refresh_revenue()`, `job_refresh_institutional()`
- **修改** `strategies/revenue_momentum.py`：`_revenue_cache` 按月過期

---

## AD5：Cache 過期與 Freshness 監控

### Cache 分層策略

| 資料類型 | 磁碟 TTL | 記憶體 TTL | 過期策略 |
|----------|:--------:|:--------:|---------|
| 日線 OHLCV | 到下次收盤 | 到下次收盤 | data_refresh job 觸發失效 |
| 即時報價（Shioaji） | N/A | 1-5 秒 | 事件驅動（每次 tick 更新） |
| 月營收 | 到下月 11 日 | 到下月 11 日 | 日曆驅動 |
| 季報 | 到下季截止日 | 7 天 | 日曆驅動 |
| 法人/融資券 | 到下次 EOD | 24 小時 | 每日 EOD 刷新 |
| 靜態資料（股票清單） | 24 小時 | 24 小時 | 定期刷新 |

### Prometheus 指標

系統已有 Prometheus metrics（commit d5b6490）。新增：

```python
# src/metrics.py — 新增

from prometheus_client import Gauge, Counter, Histogram

DATA_FRESHNESS_DAYS = Gauge(
    'quant_data_freshness_days',
    'Trading days since last bar',
    ['symbol_group']  # "universe", "tw50", "holdings"
)
REFRESH_DURATION = Histogram(
    'quant_refresh_duration_seconds',
    'Data refresh duration',
    ['stage']  # "download", "validate", "write"
)
QUALITY_GATE_PASS = Gauge(
    'quant_quality_gate_pass',
    'Whether pre-trade quality gate passed (1=pass, 0=fail)'
)
REFRESH_FAILURES = Counter(
    'quant_refresh_failures_total',
    'Data refresh failures',
    ['source', 'reason']  # source=yahoo/finmind, reason=timeout/rate_limit/parse_error
)
SYMBOL_COVERAGE = Gauge(
    'quant_symbol_coverage_ratio',
    'Fraction of universe with fresh data'
)
```

### 告警規則

| 指標 | 閾值 | 動作 |
|------|------|------|
| `DATA_FRESHNESS_DAYS{group="holdings"}` > 1 | P0 | Halt trading + 通知 |
| `QUALITY_GATE_PASS` == 0 | P0 | Halt trading + 通知 |
| `SYMBOL_COVERAGE` < 0.95 | P1 | 通知，允許交易（排除缺失 symbol） |
| `REFRESH_DURATION{stage="download"}` > 300s | P1 | 通知（可能 rate limited） |
| `REFRESH_FAILURES` > 5/小時 | P2 | 記錄觀察 |

### 告警整合

已有 `src/notifications/` 模組（Telegram/LINE）。Gate 失敗時呼叫：

```python
if not gate.passed:
    await notifier.send(
        "🚨 DATA QUALITY GATE FAILED",
        f"Blocking: {gate.blocking}\nStale: {len(gate.stale_symbols)} symbols\n"
        f"Coverage: {gate.coverage:.1%}",
        level="critical",
    )
```

### 檔案變更
- **修改** `src/metrics.py`：新增 5 個 Prometheus 指標
- **修改** `src/data/refresh.py`：刷新過程中更新指標
- **修改** `src/data/quality_gate.py`：gate 結果更新指標

---

## AD6：Universe 維護

### 現狀

`data/all_tw_stock_ids.txt` 是靜態檔案，上市/下市不會自動更新。

### 設計

```python
# src/data/universe.py — 新增

def sync_universe(
    source: str = "twse",
    output: str = "data/all_tw_stock_ids.txt",
    history_path: str = "data/universe_history.parquet",
) -> UniverseSyncReport:
    """同步上市櫃股票清單。

    1. 從 TWSE/TPEX 官網或 FinMind 取得最新上市櫃清單
    2. 比對本地 all_tw_stock_ids.txt
    3. 新增：加入清單 + 下載歷史數據
    4. 下市：標記 delisted_date，保留歷史數據（不刪除）
    5. 記錄到 universe_history.parquet（point-in-time universe）
    """
```

**Point-in-time universe：**
```
universe_history.parquet:
| date       | symbol  | status   |
|------------|---------|----------|
| 2026-01-02 | 1101.TW | active   |
| 2026-01-02 | 1102.TW | active   |
| 2026-03-15 | 9999.TW | delisted |
```

回測時可用 `universe_at(as_of_date)` 取得當時的 active symbol list，避免倖存者偏差。

### 排程

```python
# 每月 1 日同步一次（上市/下市頻率低）
"universe_sync": "0 7 1 * *"
```

### 檔案變更
- **新增** `src/data/universe.py`：universe 同步邏輯
- **新增** `data/universe_history.parquet`：歷史 universe 快照
- **修改** `src/scheduler/jobs.py`：新增 `job_sync_universe()`

---

## 執行順序與依賴

```
AD1（增量更新）───→ AD3（排程整合）───→ AD5（監控告警）
                      ↑
AD2（Quality Gate）──┘
                                        AD6（Universe）── 獨立
AD4（基本面日曆）────────────────────────┘
```

**Phase 1（Paper Trading 前置，P0）**：AD1 + AD2 + AD3
- 這三項完成後，系統可以每日自動刷新數據 + 驗證 + 安全交易
- 預估工作量：中等

**Phase 2（生產強化，P1）**：AD4 + AD5
- 基本面按日曆刷新 + Prometheus 監控
- 預估工作量：中等

**Phase 3（完整性，P2）**：AD6
- Universe 自動維護
- 預估工作量：小

---

## 驗證方式

### AD1 驗證
```bash
# 模擬增量更新（先刪最後 5 天，再 refresh）
python -c "
from src.data.refresh import refresh_market_data
report = refresh_market_data(['2330.TW', '2317.TW'])
print(f'Updated: {report.updated}, Failed: {len(report.failed)}, Stale: {len(report.stale)}')
"
```

### AD2 驗證
```bash
# Gate 應在有完整數據時通過
python -c "
from src.data.quality_gate import pre_trade_quality_gate
result = pre_trade_quality_gate(['2330.TW', '2317.TW'])
print(f'Passed: {result.passed}, Coverage: {result.coverage:.1%}')
"
```

### AD3 驗證
```bash
# 確認排程註冊
python -c "
from src.alpha.auto.scheduler import SCHEDULES
assert 'data_refresh' in SCHEDULES
assert 'quality_gate' in SCHEDULES
print('Schedules OK:', list(SCHEDULES.keys()))
"
```

### 回歸測試
```bash
make test  # 確保現有 1707 tests 不退化
```

---

## 與其他 Phase 的關係

| Phase | 關係 |
|-------|------|
| Phase K（數據品質） | AD2 建立在 K1 的 `check_bars()` 之上 |
| Phase T（Paper Trading） | AD1-AD3 是 Paper Trading 上線的前置條件 |
| Phase N（Paper Trading 完整性） | AD 為 N 提供可靠的數據基礎 |
| Phase Y（容器化 Autoresearch） | 容器內的數據刷新可復用 AD1 |
| Phase AB（Factor-Level PBO） | watchdog 需要 fresh data 才能計算正確的 OOS |
| Phase AC（Validator 強化） | Validator 的 OOS check 依賴 fresh holdout 數據 |

---

## 設計原則

1. **Fail-closed**：Quality Gate 失敗 → 不交易，不是用 fallback 數據繼續
2. **本地優先不變**：增量更新是追加本地 parquet，不改變「讀本地」的核心設計
3. **最小侵入**：不改現有數據源介面，只在上層加 refresh + gate 層
4. **可觀測性**：每個環節都有 Prometheus 指標和日誌
5. **冪等**：重複執行 refresh 不產生重複數據（drop_duplicates）

---

## 參考

- QuantRocket: Schedule Live Trading — cron-based pre-market data refresh
- QuantConnect: `before_trading_start()` — daily universe reconstitution
- Exactpro: Market Data Systems Testing — 4-level quality gate
- Pandera: DataFrame schema validation — lightweight quality checks
- MoldStud: Caching for Trading Platforms — tier-based TTL strategy
- EODHD: Survivorship Bias-Free Analysis — delisted stock handling
- Red-Gate: Incrementally Loading Data into Parquet — append strategies
- 永豐金證券: 台股月營收公布時間 — 每月 10 日前
- 公開資訊觀測站: 季報公布截止日
