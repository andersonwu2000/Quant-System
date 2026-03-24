# 開發計畫書

> **版本**: v2.3
> **日期**: 2026-03-24
> **目標**: 建立涵蓋多個可自動交易市場的投資組合研究與優化系統
> **可交易市場**: 台股、美股、ETF（含債券/商品 ETF 代理）、台灣期貨、美國期貨
> **不納入**: 直接債券交易（OTC）、實體商品、零售外匯（台灣法規限制）
> **架構設計**: `docs/dev/MULTI_ASSET_ARCHITECTURE.md`
> **已完成**: 股票交易系統 + Alpha 研究層 + Phase A + Phase B（跨資產 Alpha）

---

## 目錄

1. [開發策略](#1-開發策略)
2. [Phase A：多資產基礎設施 + 管線整合](#2-phase-a多資產基礎設施--管線整合)
3. [Phase B：跨資產 Alpha](#3-phase-b跨資產-alpha)
4. [Phase C：多資產組合最佳化](#4-phase-c多資產組合最佳化)
5. [Phase D：回測與風控升級](#5-phase-d回測與風控升級)
6. [Phase E：實盤](#6-phase-e實盤)
7. [已完成的里程碑](#7-已完成的里程碑)
8. [設計缺陷追蹤](#8-設計缺陷追蹤)

---

## 1. 開發策略

### 1.1 核心原則

**基礎設施 → 管線整合 → Alpha → 最佳化 → 回測 → 實盤**

Phase A 的教訓：建立新模組（Instrument、多幣別欄位）不等於完成。必須將新模組**整合進現有的執行管線**（回測引擎、SimBroker、weights_to_orders），否則新舊系統斷裂。

### 1.2 階段概覽

```
Phase A ✅                  Phase B ✅           Phase C (當前)        Phase D            Phase E
基礎設施 + 管線整合           跨資產 Alpha          組合最佳化            回測+風控           實盤
───────────────────         ────────────         ─────────            ──────────         ──────
✅ A1 Instrument Registry   ✅ B1 宏觀因子模型     Risk Parity          多幣別回測          券商對接
✅ A2 多幣別 Portfolio       ✅ B2 跨資產信號       Black-Litterman      期貨展期           Paper/Live
✅ A3 擴展 DataFeed         ✅ B3 戰術配置引擎      幣別對沖              跨資產風控          多資產前端
✅ A4 FRED 數據源           ✅ API + 前端型別       兩層配置整合          績效歸因
✅ A5 管線整合 (D-01~D-06)
✅ A6 YahooFeed 韌性強化
✅ 模型統一 + 死碼清理
✅ Code Review + mypy 修復
```

### 1.3 現有基礎

| 能力 | 狀態 | 位置 |
|------|------|------|
| 股票回測引擎 | ✅ | `src/backtest/` |
| Alpha 研究層 (11 模組) | ✅ | `src/alpha/` |
| Instrument Registry | ✅ 已整合 | `src/instrument/` |
| 多幣別 Portfolio | ✅ 已整合 | `src/domain/models.py` |
| FRED 數據源 | ✅ | `src/data/sources/fred.py` |
| DataFeed 擴展 (FX/期貨) | ✅ | `src/data/feed.py` |
| mypy strict 通過 | ✅ 83 files, 0 errors | CI `backend-lint` |
| 測試套件 | ✅ 475 passed, 2 skipped | CI `backend-test` |

---

## 2. Phase A：多資產基礎設施 + 管線整合

### ✅ 全部完成

- ✅ **A1**: Instrument Registry (`src/instrument/`)
- ✅ **A2**: 多幣別 Portfolio (`cash_by_currency`, `total_cash()`, `currency_exposure()`, `nav_in_base()`)
- ✅ **A3**: DataFeed 擴展 (`get_fx_rate()`, `get_futures_chain()`)
- ✅ **A4**: FRED 宏觀數據源 (`src/data/sources/fred.py`)
- ✅ **A5a**: `weights_to_orders()` 支援合約乘數 (`qty = target_value / (price × multiplier)`)
- ✅ **A5b**: SimBroker per-instrument 費率（commission_rate / tax_rate 覆蓋 SimConfig）
- ✅ **A5c**: `Portfolio.nav_in_base(fx_rates)` 多幣別 NAV
- ✅ **A5d**: BacktestEngine `_snap_nav()` 改用 `nav_in_base()` 計算 NAV
- ✅ **A5e**: InstrumentRegistry 接入 BacktestEngine（`get_or_create()` 建構 instruments dict）
- ✅ **A6**: YahooFeed 指數退避重試 + 速率限制
- ✅ **模型統一**: 雙重 Instrument 定義合併至 `src/domain/models.py`，`src/instrument/model.py` 改為 re-export
- ✅ **死碼清理**: `combine_factors()`, `revenue_momentum()`, `TestCombineFactors` 移除（-199 LOC）
- ✅ **mypy 修復**: 14 個 strict 錯誤全部修復（orthogonalize, cross_section, construction, research, fred, yahoo, alpha routes）
- ✅ **Code Review 修復**: `registry.py` 移除錯誤的 `expiry=None` kwarg；`_snap_nav` 正確呼叫 `nav_in_base()`

### Phase A 完成標誌（已達成）

能正確回測一個混合 universe（如 `["2330.TW", "AAPL", "TLT", "GC=F"]`），其中：
- 期貨數量正確反映合約乘數
- NAV 以 base_currency (TWD) 計價，含匯率轉換
- 各標的使用各自的手續費/稅率
- InstrumentRegistry 自動推斷標的屬性

---

## 3. Phase B：跨資產 Alpha ✅

**目標**: 回答「現在應該把多少比例放在股票、債券ETF、商品、現金？」

**輸入/輸出契約**：
```
macro_signals: dict[str, float]          ← 宏觀指標（前向填補至每日）
cross_asset_signals: dict[str, float]    ← 跨資產動量/carry/value
strategic_weights: dict[AssetClass, float]  ← 靜態目標（YAML 設定）
         ↓
tactical_weights: dict[AssetClass, float]   ← 戰術偏離後的資產類別比例
```

### ✅ Task B1: 宏觀因子模型

`src/allocation/macro_factors.py` — MacroFactorModel + MacroSignals

| 因子 | 指標 | 信號 |
|------|------|------|
| 成長 | GDP, PMI, 就業 | 加速 → 股票+、債券ETF− |
| 通膨 | CPI, PPI, 油價 | 上升 → 商品ETF+、長債ETF− |
| 利率 | 央行利率, 殖利率斜率 | 下降 → 長債ETF+、成長股+ |
| 信用 | 信用利差, 違約率 | 收窄 → HYG+、股票+ |

> **頻率問題**：CPI/GDP/PMI 為月度/季度，統一以最新發布值**前向填補**（上限 66 個交易日）。宏觀信號再計算頻率建議設為月度（`rebalance_freq="monthly"`）。

### ✅ Task B2: 跨資產信號

`src/allocation/cross_asset.py` — CrossAssetSignals

| 因子 | 定義 | 適用 |
|------|------|------|
| 時間序列動量 | 12M 報酬 (12-1) | 所有資產 |
| Carry | 股息率 / 期貨展期收益 | 股票 / 期貨 |
| Value | 長期均值回歸 (CAPE) | 股票 / 債券ETF |
| Volatility | 已實現 vs 隱含波動率 | 所有 |

> **市場狀態識別 (regime)**：直接使用現有 `src/alpha/regime.py`，不在 `allocation/` 另建重複模組。

### ✅ Task B3: 戰術配置引擎

`src/allocation/tactical.py` — TacticalEngine + StrategicAllocation + TacticalConfig

結合戰略配置 + 宏觀信號 + 跨資產信號 + regime → 輸出 `dict[AssetClass, float]`（資產類別戰術權重）。

### ✅ Task B4: API + 前端型別

- `src/api/routes/allocation.py` — `POST /api/v1/allocation` 端點
- `apps/shared/src/types/` — TacticalRequest, TacticalResponse 型別
- `apps/shared/src/api/endpoints.ts` — allocation.compute() 端點

### Phase B 完成標誌（已達成）

能產出資產類別的戰術配置權重，宏觀因子、跨資產信號、市場狀態三類信號均有效影響配置。23 個單元測試全部通過。

---

## 4. Phase C：多資產組合最佳化

**輸入/輸出契約**：
```
tactical_weights: dict[AssetClass, float]   ← Phase B 輸出
symbol_weights_per_class: dict[str, float]  ← Alpha Pipeline 輸出（資產內選擇）
covariance_matrix, fx_rates, constraints    ← 市場數據 + 約束
         ↓
final_weights: dict[str, float]             ← 送進 weights_to_orders()
```

### Task C1: 多資產最佳化器 (`src/portfolio/optimizer.py`)

方法：Mean-Variance (MVO)、Risk Parity、Black-Litterman（含 views 生成）、HRP

> Black-Litterman 的 views 生成邏輯內嵌於 optimizer.py，不另建 `views.py`。

### Task C2: 幣別對沖 (`src/portfolio/currency.py`)

根據 TWD/USD 暴露和對沖成本，自動決定對沖比例。

### Task C3: 跨資產風險模型 (`src/portfolio/risk_model.py`)

相關矩陣估計（歷史法 / DCC-GARCH）+ 因子風險分解。

### Task C4: 兩層配置整合

```
戰略配置（YAML）→ 戰術偏離（B3）→ 資產內選擇（Alpha）→ 組合最佳化（C1）→ 最終持倉
```

> **約束管理**：執行期「拒絕/批准」型約束（槓桿上限、保證金不足）擴展到 `src/risk/rules.py`；最佳化器軟約束（目標函數懲罰項）內嵌於 `optimizer.py`。不另建 `constraints.py`。

### Phase C 完成標誌

輸入「戰略配置 + 宏觀觀點 + Alpha 信號」，產出跨市場最終持倉（含幣別對沖建議）。

---

## 5. Phase D：回測與風控升級

### Task D1: 期貨展期模擬

自動偵測近月到期，模擬 roll 到下期，展期成本納入績效。

### Task D2: 跨資產風控規則

擴展 `src/risk/rules.py`：

```
max_asset_class_weight()   — 資產類別上限
max_currency_exposure()    — 單一幣別暴露上限
max_leverage()             — 總槓桿上限（期貨保證金）
stress_test_limit()        — 壓力測試情境最大虧損
```

### Task D3: 三層績效歸因

資產配置歸因 + 選股歸因 + 匯率歸因。

---

## 6. Phase E：實盤

| 任務 | 說明 |
|------|------|
| 券商對接 | 台股 (永豐 Shioaji) + 美股 (Interactive Brokers) |
| 即時行情 | 填補 WebSocket `market` 頻道（目前 TODO） |
| Paper Trading | 完整紙上交易循環 |
| 多資產前端 | 配置儀表板、跨市場持倉、幣別暴露圖 |

> 券商評估細節見 `docs/dev/BROKER_API_EVALUATION.md`。

---

## 7. 已完成的里程碑

### 股票交易系統 (2026-03-22 ~ 2026-03-23)

回測引擎、7 策略、風控、SimBroker、REST API + WebSocket、Web + Mobile 前端。

### Alpha 研究層 (2026-03-24)

11 模組 + API 端點 + 前端頁面。效能優化：`compute_factor_values()` 向量化（~7 min → ~30s）。

### Phase A 完整完成 (2026-03-24)

- Instrument Registry + 多幣別 Portfolio + DataFeed 擴展 + FRED 數據源
- A5 管線整合（D-01~D-07 全修復）+ A6 YahooFeed 韌性
- 模型統一（雙重 Instrument 合併）+ 死碼清理（-199 LOC）

### 程式碼品質提升 (2026-03-24)

- **mypy strict 0 errors**：修復 14 個型別錯誤，涵蓋 7 個檔案
- **Code Review 修復**：
  - `registry.py` 移除錯誤的 `expiry=None`（YAML 載入 TypeError）
  - `_snap_nav()` 改用 `portfolio.nav_in_base(fx_rates)`（多幣別 NAV 正確）
- **測試**：475 passed, 2 skipped（全套 pytest）

### Phase B 跨資產 Alpha (2026-03-24)

- `src/allocation/macro_factors.py`：宏觀四因子模型（成長/通膨/利率/信用），FRED 數據 z-score
- `src/allocation/cross_asset.py`：跨資產信號（動量/波動率/均值回歸），per AssetClass
- `src/allocation/tactical.py`：戰術配置引擎，合成三類信號 → 資產類別權重
- `src/api/routes/allocation.py`：`POST /api/v1/allocation` API 端點
- 前端型別 + 端點定義（TacticalRequest/Response）
- 23 個單元測試，mypy strict + ruff 0 errors

---

## 8. 設計缺陷追蹤

| 編號 | 嚴重度 | 狀態 | 問題 |
|------|--------|------|------|
| ~~D-01~~ | ~~致命~~ | ✅ A5a | weights_to_orders 支援合約乘數 |
| ~~D-02~~ | ~~致命~~ | ✅ A5c | Portfolio.nav_in_base() 多幣別 |
| ~~D-03~~ | ~~致命~~ | ✅ A5d | BacktestEngine 多幣別 + Registry |
| ~~D-04~~ | ~~高~~ | ✅ A5b | SimBroker per-instrument 費率 |
| ~~D-05~~ | ~~高~~ | ✅ Phase B | 戰術配置層已實作 (`src/allocation/`) |
| ~~D-06~~ | ~~高~~ | ✅ A5e | Registry 整合 BacktestEngine |
| ~~D-07~~ | ~~中~~ | ✅ A6 | YahooFeed 重試/限流 |
| D-08 | 中 | 延後 | Alpha Pipeline GIL 限制（多執行緒瓶頸） |
| ~~D-09~~ | ~~低~~ | ✅ | 前端標的列表已擴展至 230 支（US/TW/ETF） |
| ~~D-10~~ | ~~高~~ | ✅ | 雙重 Instrument 模型已統一 |
| ~~D-11~~ | ~~致命~~ | ✅ | registry.py `expiry=None` 非法 kwarg |
| ~~D-12~~ | ~~高~~ | ✅ | `_snap_nav` 未使用 `nav_in_base()`，多幣別 NAV 算錯 |
| ~~D-13~~ | ~~中~~ | ✅ | mypy strict 14 個型別錯誤 |

---

> **文件維護說明**: 每完成一個 Task 標注日期。每完成一個 Phase 更新 `SYSTEM_STATUS_REPORT.md`。
