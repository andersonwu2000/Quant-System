# Phase K：數據品質提升 + 基本面因子驗證

> 狀態：✅ 完成 2026-03-26
> 完成摘要：K1 品質基礎（16 tests）+ K2 FinMind 8 dataset × 51 支（408 parquet）+ K3 因子 6→14（21 tests）+ K4 IC 分析（revenue_yoy ICIR 0.317 突破）+ K5 Walk-Forward（三因子 Sharpe 1.19）
> 前置：Phase I（因子庫擴展）✅ 完成
> 依據：實驗 1-15 總結 — 75 個 price-volume 因子天花板 ~3-6%/年超額，需要基本面突破
> 目標：補齊數據缺口、提升品質、驗證基本面因子

---

## 背景

經過 15 次實驗、75 個因子的全面分析，核心發現：

1. **基本面因子從未被測試** — 6 個基本面因子已註冊（value_pe, value_pb, quality_roe, size, investment, gross_profit），但 15 次實驗全部只跑 price-volume
2. **FinMind 數據未充分利用** — 已接通 6 個 dataset，但還有 6+ 個有價值的 dataset 未用
3. **數據品質有盲區** — 除權息靠啟發式判斷、基本面無異常值過濾、無跨源交叉驗證
4. **基本面因子天然低換手率** — 正好克服台股成本瓶頸（實驗結論：換手率 > 10% 的因子全部虧損）

---

## 階段總覽

| 階段 | 內容 | 預估工作量 |
|:----:|------|:---------:|
| K1 | 數據品質基礎設施 | 中 |
| K2 | FinMind 新數據集下載 + 本地存儲 | 中 |
| K3 | 基本面因子數據接通 + 新因子 | 中 |
| K4 | 基本面因子全面 IC 分析 | 小 |
| K5 | 最佳因子組合 Walk-Forward 驗證 | 小 |

---

## K1：數據品質基礎設施

### K1.1 除權息精確比對

**現狀**：`src/data/quality.py` 第 98-107 行用啟發式判斷（-1%~-10% 下跌 + 正常量 = 疑似除權息），會誤判。

**改進**：

```python
# src/data/quality.py — 新增
def load_dividend_dates(symbol: str) -> set[str]:
    """從本地 Parquet 讀取已下載的除權息日期。"""
    # 讀取 data/market/{symbol}_dividends.parquet（YahooFeed 已存）
    # 或 FinMind TaiwanStockDividend
    # 返回 ISO 日期 set
```

在 `check_bars()` 的 5σ 跳變檢查中，先查真實除權息日期表，只有不在表中的跳變才標記為 suspect。

**檔案**：
- 修改 `src/data/quality.py`：`check_bars()` 加入 `dividend_dates` 參數
- 新增 `src/data/quality.py`：`load_dividend_dates()` 函式

### K1.2 基本面異常值過濾

**現狀**：`get_financials()` 返回原始值，PE=9999 或 ROE=-500% 會扭曲因子排名。

**改進**：

```python
# src/data/quality.py — 新增
FUNDAMENTAL_BOUNDS = {
    "pe_ratio": (0, 200),      # PE 0~200，超過 clip
    "pb_ratio": (0, 50),       # PB 0~50
    "roe": (-100, 100),        # ROE -100%~100%
    "eps": (-50, 500),         # EPS
    "revenue_growth": (-100, 500),  # 營收成長率 %
}

def check_fundamentals(data: dict[str, float]) -> dict[str, float]:
    """過濾基本面異常值。超出範圍的值 clip 到邊界。"""
```

**檔案**：
- 修改 `src/data/quality.py`：新增 `check_fundamentals()`
- 修改 `src/data/sources/finmind_fundamentals.py`：`get_financials()` 返回前過濾

### K1.3 停牌日偵測

**現狀**：停牌股（volume=0 或連續 N 天價格相同）仍參與因子排名。

**改進**：

```python
# src/data/quality.py — 新增
def detect_halted_dates(df: pd.DataFrame, max_unchanged_days: int = 3) -> set[str]:
    """偵測停牌日：volume=0 或連續 N 天收盤價完全相同。"""
```

**用途**：因子計算前排除停牌日的截面數據。

**檔案**：
- 修改 `src/data/quality.py`：新增 `detect_halted_dates()`
- 修改 `src/strategy/research.py`：`compute_factor_values()` 排除停牌股

### K1.4 測試

新增 `tests/unit/test_data_quality_enhanced.py`：
- `test_dividend_date_exact_match` — 真實除權息日不標記 suspect
- `test_fundamentals_clip` — PE=9999 clip 到 200
- `test_halted_detection` — volume=0 連續 3 天偵測為停牌
- `test_negative_pe_filtered` — 負 PE 返回 0

---

## K2：FinMind 新數據集下載 + 本地存儲

### K2.1 新數據集列表

| 優先級 | Dataset | 用途 | 存儲格式 |
|:------:|---------|------|---------|
| P0 | **TaiwanStockBalanceSheet** | 補齊 investment + gross_profit 的實際數據（total_assets, revenue, cogs） | `data/fundamental/{symbol}_balance_sheet.parquet` |
| P0 | **TaiwanStockInstitutionalInvestors** | 外資/投信/自營商買賣超（實驗 11 ICIR 0.15，但需正規化後重測） | `data/fundamental/{symbol}_institutional.parquet` |
| P1 | **TaiwanStockShareholding** | 董監持股比例變化 — 內部人交易信號 | `data/fundamental/{symbol}_shareholding.parquet` |
| P1 | **TaiwanStockMarginPurchaseShortSale** | 融資融券餘額 — 散戶情緒 | `data/fundamental/{symbol}_margin.parquet` |
| P2 | **TaiwanStockDayTrading** | 當沖比率 — 投機度指標 | `data/fundamental/{symbol}_daytrading.parquet` |
| P2 | **TaiwanStockTotalReturnIndex** | 含息報酬指數 — 回測精度驗證 | `data/fundamental/{symbol}_tri.parquet` |

### K2.2 本地存儲架構

```
data/
├── market/          # 已有：OHLCV parquet（149 檔）
├── fundamental/     # 新增：基本面 + 籌碼面 parquet
│   ├── {symbol}_balance_sheet.parquet
│   ├── {symbol}_institutional.parquet
│   ├── {symbol}_shareholding.parquet
│   ├── {symbol}_margin.parquet
│   └── ...
└── tw50_5yr.pkl     # 已有：回測用打包數據
```

### K2.3 下載腳本

新增 `scripts/download_finmind_data.py`：
- 參數：`--dataset`, `--symbols`（預設 TW50），`--start`, `--end`
- 本地優先：先檢查 `data/fundamental/` 是否已有，有就跳過
- Rate limit：FinMind 免費 600 req/hr，每次請求間隔 0.5s
- 輸出：下載進度 + 存儲路徑

### K2.4 FundamentalsProvider 擴展

修改 `src/data/fundamentals.py` ABC，新增方法：

```python
class FundamentalsProvider(ABC):
    # 已有
    def get_financials(self, symbol, date=None) -> dict[str, float]: ...
    def get_sector(self, symbol) -> str: ...
    def get_revenue(self, symbol, start, end) -> pd.DataFrame: ...
    def get_dividends(self, symbol, start, end) -> pd.DataFrame: ...

    # 新增
    def get_institutional(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """法人買賣超。columns: [date, foreign_buy, foreign_sell, trust_buy, trust_sell, dealer_buy, dealer_sell]"""
        return pd.DataFrame()  # 預設空（非 abstract，向後相容）

    def get_margin(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """融資融券。columns: [date, margin_balance, short_balance]"""
        return pd.DataFrame()

    def get_shareholding(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """董監持股。columns: [date, director_ratio, major_ratio]"""
        return pd.DataFrame()
```

### K2.5 FinMindFundamentals 實作

修改 `src/data/sources/finmind_fundamentals.py`：
- 實作 `get_institutional()`：呼叫 `taiwan_stock_institutional_investors()`，正規化為淨買金額
- 實作 `get_margin()`：呼叫 `taiwan_stock_margin_purchase_short_sale()`
- 實作 `get_shareholding()`：呼叫 `taiwan_stock_shareholding()`
- 所有新方法都先讀 `data/fundamental/` 本地快取

### K2.6 測試

- `tests/unit/test_finmind_fundamentals.py`：新增 3 個方法的 mock 測試
- `tests/unit/test_download_script.py`：下載腳本的 dry-run 測試

---

## K3：基本面因子數據接通 + 新因子

### K3.1 現有因子數據接通

**問題**：6 個基本面因子已註冊但部分沒有實際數據：

| 因子 | metric_key | FinMind 有嗎 | 狀態 |
|------|-----------|:----------:|------|
| value_pe | pe_ratio | ✅ | 已接通 |
| value_pb | pb_ratio | ✅ | 已接通 |
| quality_roe | roe | ✅ | 已接通 |
| size | market_cap | ❌ | **缺數據** — 用 price×volume proxy |
| investment | total_assets_current/prev | ❌ | **缺數據** — 需 BalanceSheet |
| gross_profit | revenue, cogs, total_assets | ❌ | **缺數據** — 需 BalanceSheet |

**修復**：K2 下載 TaiwanStockBalanceSheet 後，在 `get_financials()` 中解析並返回 `total_assets`, `revenue`, `cogs` 欄位。

### K3.2 新增基本面因子

| 因子 | Registry Key | 定義 | 數據源 | 學術依據 |
|------|-------------|------|--------|---------|
| 營收動能 | `revenue_momentum` | 連續 N 月營收 YoY > 0 的月數（0~12） | TaiwanStockMonthRevenue | 台股實證研究常用 |
| 營收 YoY | `revenue_yoy` | 最新月營收 YoY 成長率 | TaiwanStockMonthRevenue | — |
| 股利殖利率 | `dividend_yield` | 近 12 月現金股利 / 股價 | TaiwanStockDividend + price | Fama-French HML 的成分 |
| 外資淨買超 | `foreign_net` | 外資 N 日累計淨買金額（正規化） | TaiwanStockInstitutionalInvestors | 台股籌碼面文獻 |
| 投信淨買超 | `trust_net` | 投信 N 日累計淨買金額（正規化） | TaiwanStockInstitutionalInvestors | 台股籌碼面文獻 |
| 董監持股變化 | `director_chg` | 董監持股比例 N 日變化 | TaiwanStockShareholding | 內部人交易文獻 |
| 融資餘額變化 | `margin_chg` | 融資餘額 N 日變化率（反向：融資增=散戶追漲=負） | TaiwanStockMarginPurchaseShortSale | 台股散戶行為 |
| 當沖比率 | `daytrading_ratio` | 當沖成交量 / 總成交量（反向：高當沖=投機=負） | TaiwanStockDayTrading | 投機度指標 |

### K3.3 實作位置

- `src/strategy/factors/fundamental.py`：新增 8 個因子函式
- `src/strategy/research.py`：`FUNDAMENTAL_REGISTRY` 新增 8 個條目
- `src/data/sources/finmind_fundamentals.py`：確保所有新 metric_key 能從 `get_financials()` 或專用方法取得

### K3.4 因子計算管道

修改 `compute_fundamental_factor_values()` 使其支援本地 parquet 讀取：

```python
def compute_fundamental_factor_values(
    symbols: list[str],
    factor_name: str,
    provider: FundamentalsProvider | None = None,  # None = 本地讀取
    dates: list[pd.Timestamp] | None = None,
    data_dir: str = "data/fundamental",  # 本地優先
) -> pd.DataFrame:
```

對於頻繁調用的因子分析，避免每次都走 API，改為批量讀本地 parquet 面板。

### K3.5 測試

- `tests/unit/test_fundamental_factors.py`：新增 8 個因子的單元測試
- 每個因子 2-3 個 test：正常值、邊界值、缺數據回傳空

---

## K4：基本面因子全面 IC 分析

### K4.1 分析腳本

新增 `scripts/run_fundamental_analysis.py`：
- 讀取本地 `data/fundamental/` parquet 數據
- 對 14 個基本面因子（6 舊 + 8 新）× TW50 計算 IC/ICIR
- 持有期：5 天 / 20 天 / 60 天
- 分層：全市場 / 大型股 / 小型股
- 輸出：`docs/research/fundamental_factor_analysis.csv`

### K4.2 與 price-volume 因子對比

將基本面因子結果與已有的 66 因子結果合併，比較：

| 維度 | 比較項 |
|------|--------|
| IC 絕對值 | 基本面 vs 技術面最佳因子 |
| 換手率 | 基本面因子天然低換手 → 成本優勢 |
| 淨 Alpha | 扣除成本後，基本面是否超越 momentum |
| 相關性 | 基本面 vs momentum 的相關性（低相關 = 組合價值高） |

### K4.3 預期

根據學術文獻和台股特性：
- **revenue_momentum** 和 **revenue_yoy** 最有可能突破（台股營收月報是最即時的基本面數據）
- **foreign_net** 之前 ICIR 0.15，正規化後可能改善
- **dividend_yield** 在台股高股息文化下可能有效
- **基本面因子換手率預估 < 5%**，成本優勢明顯

---

## K5：最佳因子組合 Walk-Forward 驗證

### K5.1 組合策略

根據 K4 結果，挑選 ICIR > 0.1 的基本面因子，與已驗證的 momentum 組合：

候選組合：
1. momentum + revenue_momentum（動量 + 基本面動量）
2. momentum + dividend_yield（動量 + 價值）
3. momentum + foreign_net（動量 + 籌碼）
4. 以上三者等權組合

### K5.2 Walk-Forward 設定

- Universe：142 支台股（寬 universe，避免 Selection Bias）
- 持有期：20 天
- Train window：120 天
- 成本：50 bps 單邊
- DD control：10%
- 期間：2020-01 ~ 2025-12（~5.5 年）
- 分層：全市場 + 大型股

### K5.3 成功標準

| 指標 | 門檻 | 說明 |
|------|------|------|
| 超額 Sharpe vs 1/N | > 0.3 | 高於之前最佳的 0.20 |
| 超額報酬 | > 5%/年 | 高於之前最佳的 3.1% |
| 穩定性 | ≥ 4/6 年正超額 | 高於之前最佳的 4/6 |
| MaxDD | < 25% | 合理範圍 |

### K5.4 輸出

- `docs/research/fundamental_walkforward_report.md` — 實驗報告
- `docs/research/fundamental_walkforward.csv` — 完整結果

---

## 關鍵檔案變更

| 檔案 | 變更類型 | 階段 |
|------|---------|:----:|
| `src/data/quality.py` | 修改：除權息精確比對、基本面過濾、停牌偵測 | K1 |
| `src/data/fundamentals.py` | 修改：新增 3 個方法（institutional/margin/shareholding） | K2 |
| `src/data/sources/finmind_fundamentals.py` | 修改：實作新方法 + 本地快取讀取 | K2 |
| `data/fundamental/` | **新目錄**：基本面 + 籌碼面 parquet 存儲 | K2 |
| `scripts/download_finmind_data.py` | **新檔案**：FinMind 數據批量下載腳本 | K2 |
| `src/strategy/factors/fundamental.py` | 修改：新增 8 個因子函式 | K3 |
| `src/strategy/research.py` | 修改：FUNDAMENTAL_REGISTRY 新增 8 個條目 | K3 |
| `scripts/run_fundamental_analysis.py` | **新檔案**：基本面因子分析腳本 | K4 |
| `tests/unit/test_data_quality_enhanced.py` | **新檔案**：品質檢查測試 | K1 |
| `tests/unit/test_fundamental_factors.py` | 修改：新增因子測試 | K3 |

---

## 執行順序與依賴

```
K1（品質基礎）──→ K2（下載數據）──→ K3（因子接通）──→ K4（IC 分析）──→ K5（Walk-Forward）
     │                  │                  │
     │                  │                  └── 依賴 K2 的本地數據
     │                  └── 依賴 K1 的品質過濾
     └── 獨立，可先做
```

**K1 和 K2 可部分並行**：K1 的品質過濾不依賴 K2 的新數據，但 K2 下載的數據需要通過 K1 的品質檢查。

---

## 驗證

```bash
make test && make lint    # 後端：pytest + ruff + mypy strict
```

每階段完成後：
- K1：品質測試全過 + 現有 1214 tests 不退化
- K2：`python scripts/download_finmind_data.py --dataset balance_sheet --symbols TW50` 成功，本地有 parquet
- K3：`python -c "from src.strategy.research import FUNDAMENTAL_REGISTRY; print(len(FUNDAMENTAL_REGISTRY))"` → 14
- K4：`python scripts/run_fundamental_analysis.py` 產出 CSV
- K5：Walk-Forward 報告完成，與 price-volume 結果對比
