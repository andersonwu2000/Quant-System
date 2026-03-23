# 外部資料源評估報告

**日期**: 2026-03-24
**範圍**: 替代/補充 Yahoo Finance 的資料源方案
**目標**: 解決存活者偏差、補齊基本面數據、支援台股 + 美股

---

## 目錄

1. [現況分析](#1-現況分析)
2. [台股資料源](#2-台股資料源)
3. [全球/美股資料源](#3-全球美股資料源)
4. [去存活者偏差專用源](#4-去存活者偏差專用源)
5. [比較矩陣](#5-比較矩陣)
6. [建議方案](#6-建議方案)

---

## 1. 現況分析

### 現行架構

```
YahooFeed (src/data/sources/yahoo.py)
  └→ DataFeed ABC (src/data/feed.py)
       └→ get_bars(), get_latest_price(), get_universe()
            └→ DataFrame [open, high, low, close, volume] + DatetimeIndex (tz-naive UTC)
```

**優點**:
- 介面抽象良好，新增資料源只需子類化 `DataFeed`
- 雙層快取（記憶體 + Parquet 磁碟，TTL 24h）
- 品質檢查（`src/data/quality.py`）已整合

### 現行問題

| 問題 | 嚴重度 | 影響 |
|------|:------:|------|
| 存活者偏差 | 高 | 僅含目前上市標的，長期回測報酬率高估 2-5% |
| 無基本面數據 | 高 | `multi_factor` 策略缺 P/E、P/B、ROE |
| 無產業分類 | 中 | `sector_rotation` 策略缺產業權重 |
| 未模擬股利現金流 | 中 | 高殖利率標的回測低估 1-3%/年 |
| 無下市公司數據 | 高 | 回測標的池有偏差 |
| 無日內數據 | 低 | 目前策略為日頻，暫不需要 |
| API 限流風險 | 中 | Yahoo 無官方 API，可能被封鎖 |

---

## 2. 台股資料源

### 2.1 TWSE OpenAPI（免費，官方）

| 項目 | 內容 |
|------|------|
| 數據範圍 | 日 OHLCV、指數、法人買賣超、Put/Call ratio |
| 基本面 | ✗ |
| 下市公司 | ✗ |
| API 品質 | REST，Swagger 文件，無需 API Key |
| 費用 | 免費（政府開放資料） |
| Python SDK | 社群套件（非官方） |
| 限流 | 未文件化，過度存取會被 IP 封鎖 |

**評價**: 基礎台股日資料和法人進出的免費補充，但歷史深度和涵蓋範圍不足以單獨使用。

### 2.2 FinMind（免費/低成本）

| 項目 | 內容 |
|------|------|
| 數據範圍 | 日 OHLCV、5 秒 tick（2019 起）、財報三表、月營收、法人買賣超、持股分布、美股日/分鐘 |
| 基本面 | ✓ P/E、P/B、ROE、股利、月營收 |
| 下市公司 | ✗（僅含目前上市） |
| API 品質 | REST + Swagger，JSON 格式 |
| 費用 | **免費**（註冊後 600 req/hr） |
| Python SDK | 官方 `finmind` (PyPI) |
| 資料品質 | 每日自動更新，tick 僅 2019 起 |

**評價**: **台股免費選項中最佳**。覆蓋 `multi_factor` 策略所需的基本面數據（P/E、P/B、ROE），有法人進出數據和月營收。600 req/hr 足夠日頻回測。**主要弱點**：無下市公司、tick 僅從 2019 起。

### 2.3 TEJ 台灣經濟新報（付費，機構級）

| 項目 | 內容 |
|------|------|
| 數據範圍 | 市場數據、財務會計、公司行動、ESG、信用風險、產業分類、策略數據 |
| 基本面 | ✓ 台股最完整 — 30+ 年財報 |
| 下市公司 | **✓ 提供 point-in-time 數據** |
| 台股覆蓋 | 定義性資料源（學術界和機構標準） |
| API 品質 | REST (JSON/XML)，單次 10,000 筆 + 分頁 |
| 費用 | 企業定價（估 NT$50,000-200,000+/年），學術另議 |
| Python SDK | 官方 `tejapi` (PyPI) |
| 附加價值 | TQuant Lab（回測+因子分析平台） |

**評價**: **台股數據的黃金標準**。唯一正式解決存活者偏差的台股來源（提供 point-in-time 歷史成分股資料）。產業分類完整，解決 `sector_rotation` 需求。**主要障礙**：價格高，適合有學術關係或機構預算的團隊。

### 2.4 Fugle API

| 項目 | 內容 |
|------|------|
| 數據範圍 | 日內即時/歷史、快照、台股個股報價 |
| 基本面 | ✗ |
| 下市公司 | ✗ |
| API 品質 | REST + WebSocket，SDK 多語言 |
| 費用 | 免費層可用（需券商帳戶） |
| Python SDK | 官方 `fugle-marketdata-python` |

**評價**: **即時行情最佳**，適合實盤交易整合。歷史數據深度不及 FinMind/TEJ，**不適合作為回測主要資料源**。

### 2.5 CMoney

**評價**: 零售投資者工具平台，**無公開開發者 API**，不適合程式化整合。不建議。

---

## 3. 全球/美股資料源

### 3.1 Alpha Vantage

| 項目 | 內容 |
|------|------|
| 數據範圍 | 美股/全球 OHLCV（日/週/月/分）、基本面（三表+EPS）、外匯、加密貨幣、經濟指標 |
| 台股 | ✗（部分 ETF/ADR） |
| 下市公司 | ✗ |
| 費用 | 免費：25 req/日。付費：$49.99/月（75 req/min） |
| Python SDK | 官方 `alpha_vantage` |

**評價**: 美股基本面的入門級選擇。免費層太少（25 次/日），$50/月層級可用但性價比不如 Tiingo/EODHD。

### 3.2 Polygon.io

| 項目 | 內容 |
|------|------|
| 數據範圍 | 美股/選擇權/外匯/加密 — 即時+歷史 OHLCV、trades、quotes、reference |
| 台股 | ✗ |
| 下市公司 | 部分（高階方案） |
| 費用 | 免費：5 req/min。Starter：~$29/月（無限、5 年歷史） |
| Python SDK | 官方 `polygon` |
| 特色 | WebSocket 串流強、開發者體驗佳 |

**評價**: **美股即時/高頻的最佳選擇**。$29/月的 Starter 方案性價比高。但無台股、基本面有限。

### 3.3 Tiingo

| 項目 | 內容 |
|------|------|
| 數據範圍 | 82,000+ 全球證券 EOD、IEX 即時、基本面（美/ADR/中國）、加密、外匯 |
| 台股 | 有限（需驗證） |
| 下市公司 | 未明確聲明 |
| 費用 | 免費層可用。Starter：$7/月。Pro：$29/月 |
| Python SDK | 官方 `tiingo` |
| 特色 | 30+ 年歷史，自有 EOD Price Engine 驗證 |

**評價**: **獨立開發者性價比最高**。$7-29/月涵蓋廣泛全球數據 + 基本面 + 30 年歷史。中國股票覆蓋是額外加分。

### 3.4 IEX Cloud

**狀態: 已於 2024 年 8 月關閉**。不再可用。

### 3.5 Nasdaq Data Link（前 Quandl）

| 項目 | 內容 |
|------|------|
| 數據範圍 | 250+ 付費資料集（金融、經濟、另類數據） |
| 台股 | 有限 |
| 費用 | 免費資料集可用。付費資料集 $100-1,000+/月 |
| Python SDK | 官方 `nasdaqdatalink` |

**評價**: 適合另類數據和經濟指標的補充。付費資料集對個人使用者偏貴。

### 3.6 EODHD

| 項目 | 內容 |
|------|------|
| 數據範圍 | 150,000+ tickers，70+ 交易所。EOD、日內、基本面（30 年）、股利、拆股、選擇權、總經 |
| 台股 | **✓ 有 TW 交易所覆蓋** |
| 下市公司 | **✓ 明確支援**（2018 前有 EOD，2018 後完整數據） |
| 費用 | EOD：$19.99/月。EOD+日內：$29.99/月。基本面：$59.99/月。**全包：$99.99/月（年繳 $83.33/月）** |
| Python SDK | 官方 `eodhd` |

**評價**: **綜合性價比最高的付費選項**。全包方案 ~$83/月 解決：全球 OHLCV、基本面、**下市公司（去存活者偏差）**、台股交易所覆蓋、日內數據。在此價位提供去偏差數據非常罕見。

### 3.7 Financial Modeling Prep (FMP)

| 項目 | 內容 |
|------|------|
| 數據範圍 | 即時/歷史價格、基本面、SEC filings、篩選器、DCF |
| 台股 | 有限 |
| 費用 | 免費(500MB)。Starter ~$19/月。按流量計費 |

**評價**: 美股基本面價格合理，但按流量計費不可預測。不適合台股。

### 3.8 Alpaca Markets

| 項目 | 內容 |
|------|------|
| 數據範圍 | 美股/選擇權/加密 — 即時+歷史 |
| 台股 | ✗ |
| 費用 | 免費 Basic。Algo Trader Plus：$99/月 |
| 特色 | 數據+免佣執行一體化 |

**評價**: 適合美股實盤（數據+交易整合），但純數據使用 $99/月偏貴。

### 3.9 Interactive Brokers API

| 項目 | 內容 |
|------|------|
| 數據範圍 | 60+ 交易所，股票/選擇權/期貨/外匯/債券 |
| 台股 | **✓ 支援 TWSE** |
| 下市公司 | ✗ |
| 費用 | 需開戶（$500+ 最低資金）。市場數據每交易所 $1-10/月 |
| Python SDK | `ib_insync`（社群）/ `ibapi`（官方） |
| 特色 | **唯一同時支援台股+美股+執行的 API** |

**評價**: **實盤交易的終極方案** — 一個 API 覆蓋台美兩市場的數據+執行。但需要 TWS/Gateway 常駐，歷史數據深度有限，不適合作為純回測資料源。

---

## 4. 去存活者偏差專用源

### 4.1 Norgate Data

| 項目 | 內容 |
|------|------|
| 覆蓋 | 美/澳/加股票，30+ 年歷史 |
| 台股 | ✗ |
| 特色 | **歷史指數成分股 point-in-time 數據** — 去偏差的黃金標準 |
| 費用 | 訂閱制（估 $20-50/月） |
| Python SDK | 官方 `norgatedata` |

**評價**: 美股去偏差最佳選擇，但不覆蓋台股。

### 4.2 QuantRocket

| 項目 | 內容 |
|------|------|
| 覆蓋 | 美股（含 IB 整合可擴展至全球） |
| 特色 | 完整平台（數據+回測引擎+部署）|
| 費用 | 免費（5 年美股數據，僅研究）。付費 $19.99/月起 |

**評價**: 本身是完整回測平台，與本專案功能重疊。**不建議** — 只需資料源，不需另一個回測引擎。

---

## 5. 比較矩陣

| 提供者 | OHLCV | 基本面 | 台股 | 下市股 | 日內 | 月費 | SDK |
|--------|:-----:|:------:|:----:|:------:|:----:|-----:|:---:|
| Yahoo Finance（現行）| ✓ | 基本 | ✓ | ✗ | 有限 | 免費 | ✓ |
| TWSE OpenAPI | ✓ | ✗ | ✓✓ | ✗ | ✗ | 免費 | △ |
| **FinMind** | ✓ | **✓** | **✓✓** | ✗ | 5s | **免費** | ✓ |
| **TEJ** | ✓ | **✓✓** | **✓✓** | **✓** | ✓ | $$$ | ✓ |
| Fugle | ✓ | ✗ | ✓✓ | ✗ | 即時 | 免費+ | ✓ |
| Alpha Vantage | ✓ | ✓ | ✗ | ✗ | ✓ | $0-50 | ✓ |
| **Polygon.io** | ✓ | △ | ✗ | △ | ✓ | $0-29 | ✓ |
| **Tiingo** | ✓ | ✓ | △ | ✗ | IEX | $7-29 | ✓ |
| **EODHD** | ✓ | **✓** | **✓** | **✓** | ✓ | $20-100 | ✓ |
| FMP | ✓ | ✓ | △ | ✗ | ✓ | $19-29 | △ |
| Alpaca | ✓ | ✗ | ✗ | ✗ | ✓ | $0-99 | ✓ |
| IB API | ✓ | ✗ | **✓** | ✗ | 即時 | $1-10 | ✓ |
| Norgate | ✓ | ✗ | ✗ | **✓** | ✗ | ~$30 | ✓ |

✓✓ = 原生/完整支援　✓ = 支援　△ = 有限/部分　✗ = 不支援

---

## 6. 建議方案

### 策略：多源分層

本專案同時面向台股和美股，無單一資料源可涵蓋所有需求。建議分層整合：

```
Layer 0 — 現有（免費，零遷移成本）
└── Yahoo Finance (YahooFeed) — 基礎 OHLCV，已有快取和品質檢查

Layer 1 — 台股基本面（免費，低整合成本）
└── FinMind — P/E、P/B、ROE、月營收、法人買賣超、財報三表
    → 新增 FinMindFeed 或 FundamentalsProvider 介面

Layer 2 — 去存活者偏差 + 全球覆蓋（~$83/月）
└── EODHD All-in-One — 下市公司數據、30 年基本面、70+ 交易所含台股
    → 新增 EODHDFeed，可逐步取代 YahooFeed 作為主要價格源

Layer 3（未來）— 機構級台股研究
└── TEJ — 需學術/機構預算時升級
    → point-in-time 成分股、最完整台股財報

Layer 4（未來）— 實盤交易
└── Interactive Brokers — 數據+執行一體化（台+美）
    → 實盤階段再整合
```

### 遷移成本評估

**低**。現有架構已良好抽象：

1. `DataFeed` ABC 定義清晰介面
2. 新增資料源 = 在 `src/data/sources/` 建新檔案，子類化 `DataFeed`
3. 輸出約定簡單：`DataFrame[open, high, low, close, volume]` + `DatetimeIndex`
4. 基本面數據需新介面（`DataFeed` 目前僅處理 OHLCV）

### 各策略對資料源的需求

| 策略 | Yahoo | +FinMind | +EODHD | +TEJ |
|------|:-----:|:--------:|:------:|:----:|
| `momentum_12_1` | ✓ 足夠 | — | — | — |
| `mean_reversion` | ✓ 足夠 | — | — | — |
| `rsi_oversold` | ✓ 足夠 | — | — | — |
| `ma_crossover` | ✓ 足夠 | — | — | — |
| `pairs_trading` | ✓ 基本 | ✓ 產業配對 | — | — |
| **`multi_factor`** | **✗ 缺基本面** | **✓ P/E、P/B、ROE** | ✓ 全球基本面 | ✓✓ 最完整 |
| **`sector_rotation`** | **✗ 缺產業分類** | **✓ 產業分類** | ✓ 產業分類 | ✓✓ 細分產業 |

### 立即可行方案（免費）

**Yahoo Finance + FinMind + TWSE OpenAPI** — 零成本解決基本面和產業分類需求。

### 最佳單一付費升級

**EODHD All-in-One ~$83/月** — 一次解決：去存活者偏差 + 全球基本面 + 台股覆蓋 + 日內數據。

### 最低成本美股強化

**Tiingo $7-29/月** 或 **Polygon $29/月** — 高品質美股數據，但不覆蓋台股。

---

## 附錄：整合程式碼示意

### 新增 FinMind 資料源

```python
# src/data/sources/finmind.py
from finmind.data import DataLoader
from src.data.feed import DataFeed

class FinMindFeed(DataFeed):
    def __init__(self, universe: list[str], token: str = ""):
        self._dl = DataLoader()
        if token:
            self._dl.login_by_token(api_token=token)
        self._universe = universe

    def get_bars(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        df = self._dl.taiwan_stock_daily(
            stock_id=symbol, start_date=start, end_date=end
        )
        # 轉換欄位名至標準格式 ...
```

### 新增基本面介面

```python
# src/data/fundamentals.py
from abc import ABC, abstractmethod

class FundamentalsProvider(ABC):
    @abstractmethod
    def get_financials(self, symbol: str) -> dict:
        """取得最新財報數據（P/E、P/B、ROE、EPS 等）。"""

    @abstractmethod
    def get_sector(self, symbol: str) -> str:
        """取得產業分類。"""

    @abstractmethod
    def get_dividends(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """取得股利歷史。"""
```
