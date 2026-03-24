# 開發計畫書

> **版本**: v2.0
> **日期**: 2026-03-24
> **目標**: 建立涵蓋多個可自動交易市場的投資組合研究與優化系統
> **可交易市場**: 台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
> **不納入**: 直接債券交易（OTC）、實體商品、零售外匯（台灣法規限制）
> **架構設計**: `docs/dev/MULTI_ASSET_ARCHITECTURE.md`
> **已完成里程碑**: 股票交易系統 + Alpha 研究層 (2026-03-24)

---

## 目錄

1. [開發策略](#1-開發策略)
2. [Phase A：多資產基礎設施](#2-phase-a多資產基礎設施)
3. [Phase B：跨資產 Alpha](#3-phase-b跨資產-alpha)
4. [Phase C：多資產組合最佳化](#4-phase-c多資產組合最佳化)
5. [Phase D：回測與風控升級](#5-phase-d回測與風控升級)
6. [Phase E：實盤與商業化](#6-phase-e實盤與商業化)
7. [已完成的里程碑](#7-已完成的里程碑)

---

## 1. 開發策略

### 1.1 核心原則

**基礎設施 → Alpha 能力 → 組合最佳化 → 回測驗證 → 實盤執行**

每一層都建立在前一層之上。不跳過基礎設施直接做最佳化，因為沒有正確的標的模型和多幣別支援，最佳化結果不可靠。

### 1.2 階段概覽

```
Phase A                Phase B              Phase C               Phase D             Phase E
多資產基礎設施          跨資產 Alpha          組合最佳化             回測+風控            實盤+商業化
─────────────         ────────────         ─────────             ──────────          ──────────
Instrument Registry    宏觀因子模型          Risk Parity           多幣別回測           券商對接
多幣別 Portfolio        跨資產信號           Black-Litterman        期貨展期            Paper/Live
擴展 DataFeed          市場狀態識別          幣別對沖               跨資產風控           多資產前端
FRED 數據源            戰術配置引擎          再平衡邏輯             績效歸因            合規
```

### 1.3 現有基礎

| 能力 | 狀態 | 位置 |
|------|------|------|
| 股票回測引擎 | ✅ | `src/backtest/` |
| 橫截面因子研究 | ✅ | `src/alpha/` (11 模組) |
| 因子庫 (10+ 技術/基本面因子) | ✅ | `src/strategy/factors.py` |
| 風控引擎 | ✅ | `src/risk/` |
| API + WebSocket + 前端 | ✅ | `src/api/`, `apps/` |
| Alpha Research 前端 | ✅ | `apps/web/src/features/alpha/` |

---

## 2. Phase A：多資產基礎設施

**目標**: 讓系統能理解和處理股票以外的資產類型。

### Task A1: Instrument Registry

**新增**: `src/instrument/`

**目的**: 統一的金融工具模型，取代現有的 `symbol: str`。沒有這個，系統無法區分「2330.TW 是台股」和「ES=F 是 S&P 期貨」，也無法處理合約規格差異。

```python
@dataclass(frozen=True)
class Instrument:
    symbol: str                     # "2330.TW", "ES=F", "TLT", "GC=F"
    name: str
    asset_class: AssetClass         # EQUITY, FIXED_INCOME, COMMODITY, FX
    sub_class: str                  # "stock", "etf", "future", "bond", "spot"
    market: Market                  # TW, US, GLOBAL
    currency: Currency              # TWD, USD, EUR, JPY
    contract_size: Decimal          # 期貨合約乘數
    tick_size: Decimal              # 最小跳動
    margin_rate: Decimal | None     # 保證金比率
    expiry: date | None             # 到期日
    coupon_rate: Decimal | None     # 債券票息
    lot_size: int                   # 最小交易單位
    commission_rate: Decimal        # 手續費率
    tax_rate: Decimal               # 交易稅率

class InstrumentRegistry:
    def get(symbol) -> Instrument
    def search(query, asset_class?) -> list[Instrument]
    def by_market(market) -> list[Instrument]
    def by_asset_class(cls) -> list[Instrument]
    def load_from_yaml(path) -> None  # 從配置檔載入
```

**遷移策略**: 先讓 `Instrument` 和 `symbol: str` 共存，不破壞現有功能。

### Task A2: 多幣別 Portfolio

**修改**: `src/domain/models.py`

**目的**: 現有 `Portfolio.cash` 是單一 `Decimal`。持有美股 + 台股 + 黃金期貨時，需要分幣別追蹤現金和計算 NAV。

```python
@dataclass
class Portfolio:
    positions: dict[str, Position]
    cash: dict[Currency, Decimal]       # TWD: 5M, USD: 100K
    base_currency: Currency = Currency.TWD

    def nav(self, fx_rates) -> Decimal:
        """以 base_currency 計價的 NAV。"""

    def currency_exposure(self) -> dict[Currency, Decimal]:
        """各幣別暴露金額。"""

    def asset_class_weights(self, fx_rates) -> dict[AssetClass, float]:
        """各資產類別的權重。"""
```

**向後相容**: 提供 `total_cash(fx_rates)` 回傳單一值，現有代碼可漸進遷移。

### Task A3: 擴展 DataFeed

**修改**: `src/data/feed.py`, `src/data/sources/`

```python
class DataFeed(ABC):
    def get_ohlcv(symbol, start, end) -> DataFrame       # 所有資產共用
    def get_fx_rate(base, quote, date) -> Decimal          # 匯率
    def get_futures_chain(root, date) -> list[Contract]    # 期貨合約鏈
    def get_yield_curve(date) -> DataFrame                 # 殖利率曲線
```

Yahoo Finance 已支援期貨 (`ES=F`, `GC=F`)、ETF、外匯 (`USDTWD=X`)。

### Task A4: FRED 宏觀數據源

**新增**: `src/data/sources/fred.py`

| 數據 | FRED ID | 用途 |
|------|---------|------|
| 聯邦基金利率 | FEDFUNDS | 利率因子 |
| 10Y 公債殖利率 | DGS10 | 殖利率曲線 |
| 2-10Y 利差 | T10Y2Y | 衰退信號 |
| CPI 年增率 | CPIAUCSL | 通膨因子 |
| 失業率 | UNRATE | 成長因子 |
| VIX | VIXCLS | 波動率狀態 |
| 信用利差 | BAAFFM | 信用因子 |

### Phase A 完成標誌

能建立一個包含台股 + 美股 + ETF + 黃金期貨的 Portfolio，以 TWD 計算 NAV，Instrument 物件含各自的合約規格和交易成本。

---

## 3. Phase B：跨資產 Alpha

**目標**: 回答「現在應該把多少比例放在股票、債券、商品？」

### Task B1: 宏觀因子模型

**新增**: `src/allocation/macro_factors.py`

| 因子 | 指標 | 信號 |
|------|------|------|
| 成長 | GDP, PMI, 就業 | 加速 → 股票+、債券− |
| 通膨 | CPI, PPI, 油價 | 上升 → 商品+、長債− |
| 利率 | 央行利率, 殖利率斜率 | 下降 → 長債+、成長股+ |
| 信用 | 信用利差, 違約率 | 收窄 → 高收益債+、股票+ |

### Task B2: 跨資產信號

**新增**: `src/allocation/cross_asset.py`

| 因子 | 定義 | 適用 |
|------|------|------|
| 時間序列動量 | 12M 報酬 (12-1) | 所有資產 |
| Carry | 股息率 / 殖利率 / 展期收益 | 股/債/期貨 |
| Value | 長期均值回歸 (CAPE, 殖利率偏離) | 股/債 |
| Volatility | 已實現 vs 隱含波動率 | 所有 |

### Task B3: 戰術配置引擎

**新增**: `src/allocation/tactical.py`

結合戰略配置 + 宏觀觀點 + 跨資產信號 → 戰術權重。

### Phase B 完成標誌

能自動產出「股票 55% / 債券 30% / 商品 10% / 現金 5%」的戰術配置建議，回測驗證超額報酬。

---

## 4. Phase C：多資產組合最佳化

**目標**: 將戰術配置 + 資產內選擇合併為最終持倉。

### Task C1: 多資產最佳化器

**新增**: `src/portfolio/optimizer.py`

方法：Mean-Variance, Risk Parity, Black-Litterman, HRP

### Task C2: 幣別對沖

**新增**: `src/portfolio/currency.py`

根據幣別暴露和對沖成本，自動決定對沖比例。

### Task C3: 兩層配置整合

```
戰略配置 → 戰術偏離 → 資產內選擇 → 組合最佳化 → 最終持倉
```

### Phase C 完成標誌

輸入「戰略配置 + 宏觀觀點 + 因子信號」，自動產出跨市場最終持倉權重（含幣別對沖建議）。

---

## 5. Phase D：回測與風控升級

### Task D1: 多幣別回測

NAV 以 base_currency 計價，分離資產報酬與匯率報酬。

### Task D2: 期貨展期模擬

自動偵測近月到期，模擬 roll 到下期合約，展期成本納入績效。

### Task D3: 跨資產風控規則

```
max_asset_class_weight()   — 資產類別上限
max_currency_exposure()    — 單一幣別上限
max_leverage()             — 總槓桿上限
max_duration()             — 組合久期上限
stress_test_limit()        — 壓力測試情境虧損上限
```

### Task D4: 績效歸因

三層：資產配置歸因 + 選股歸因 + 匯率歸因。

### Phase D 完成標誌

能回測多資產策略，報表分離配置/選股/匯率貢獻，風控涵蓋槓桿/幣別/久期。

---

## 6. Phase E：實盤與商業化

| 任務 | 說明 |
|------|------|
| 券商對接 | 台股 (永豐 Shioaji) + 美股 (Interactive Brokers) |
| 即時行情 | 填補 WebSocket market 頻道 |
| Paper Trading | 完整紙上交易循環 |
| 多資產前端 | 配置儀表板、跨市場持倉、幣別暴露圖 |
| 合規與部署 | HTTPS、備份、免責聲明 |

---

## 7. 已完成的里程碑

### 股票交易系統 (2026-03-22 ~ 2026-03-23)

回測引擎、7 策略、風控、SimBroker、REST API + WebSocket、Web + Mobile 前端、通知、排程。

### Alpha 研究層 (2026-03-24)

11 模組：universe, neutralize, cross_section, turnover, orthogonalize, construction, pipeline, strategy, regime, attribution + API 端點 + 前端頁面。

### 前端擴展 (2026-03-24)

股票池選取器 230 支標的 (美股 101 + 台股 84 + ETF 45)，市場分頁、預設組合、行業分組。

---

> **文件維護說明**: 每完成一個 Task 標注日期。每完成一個 Phase 更新 `SYSTEM_STATUS_REPORT.md`。
