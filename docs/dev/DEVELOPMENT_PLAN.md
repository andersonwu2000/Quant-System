# 開發計畫書

> **version**: v7.0
> **date**: 2026-03-26

---

## 1. 專案現況

多資產投資組合研究與優化系統。Python 後端 + React Web + Android Native。
128 後端檔案、22.5K LOC、1,006 tests。14 種組合最佳化方法、14 個 Alpha 因子、10 條風控規則、71 個 API 端點。Phase A~H 全部完成。

**主要阻塞**：永豐金 Shioaji API Key 審核中。券商整合程式碼已完成（含 mock 測試），但尚未對接真實 API。

---

## 2. 已完成階段

各階段詳細計畫書見 `docs/dev/plans/`。

| 階段 | 日期 | 摘要 | 計畫書 |
|------|------|------|--------|
| A | 03-24 | InstrumentRegistry + 多幣別 Portfolio + FRED | [phase-a](plans/phase-a-infrastructure.md) |
| B | 03-24 | 宏觀因子 + 跨資產信號 + 戰術配置 | [phase-b](plans/phase-b-cross-asset-alpha.md) |
| C | 03-24 | 6 種最佳化 + Ledoit-Wolf + 幣別對沖 | [phase-c](plans/phase-c-optimization.md) |
| D | 03-25 | MultiAssetStrategy + 跨資產風控 + 前端 | [phase-d](plans/phase-d-integration.md) |
| E | 03-25 | SinopacBroker + ExecutionService + Scanner | [phase-e](plans/phase-e-live-trading.md) |
| F | 03-26 | 自動化 Alpha 排程 + 動態因子池 + Dashboard | [phase-f](plans/phase-f-auto-alpha.md) |
| G | 03-26 | 學術升級：+8 最佳化、GARCH、PBO、Stress Test | [phase-g](plans/phase-g-academic-upgrade.md) |
| H | 03-26 | Deflated Sharpe、Semi-Variance、Kalman Pairs | [phase-h](plans/phase-h-refinement.md) |

---

## 3. 阻塞項

| 項目 | 阻塞 | 解除後 |
|------|------|--------|
| Shioaji 整合測試 | API Key 審核 | login/下單/行情驗證 |
| Paper Trading 完整循環 | 同上 | 排程→下單→回報→對帳→通知 |
| 即時行情 WS broadcast | 同上 | SinopacQuoteManager → market 頻道 |

---

## 4. Phase I：Alpha 因子庫擴展（論文驅動） → [詳細計畫](plans/phase-i-alpha-expansion.md)

> 論文來源：`docs/ref/papers/alpha/`（10 篇）
> 差距分析：`docs/dev/SYSTEM_STATUS_REPORT.md` §11.7

### 動機

系統現有 14 個因子（11 價格 + 3 基本面），但與學術文獻比對後發現：
- **Fama-French 5-factor 不完整**：缺 SMB (size)、CMA (investment)
- **Gross Profitability 完全缺失**：Novy-Marx (2013) 證明預測力與 HML 相當
- **101 Formulaic Alphas 只覆蓋 14/101**：Kakushadze (2016) 提供可直接轉為程式碼的公式
- **因子篩選閾值過寬**：Harvey et al. (2016) 建議 t-stat > 3.0，系統目前 ICIR > 0.3

### I1: Fama-French 因子補齊（🔴 P0）

| 因子 | 定義 | 論文 | 數據需求 |
|------|------|------|---------|
| `size` (SMB) | log(market_cap) | Fama-French (1993) | FinMind 市值數據 |
| `investment` (CMA) | YoY total asset growth | Fama-French (2015) | FinMind 財報 |
| `gross_profitability` | (Revenue - COGS) / Assets | Novy-Marx (2013) | FinMind 財報 |

**實作**：`src/strategy/factors.py` 新增 3 個基本面因子 + `FUNDAMENTAL_REGISTRY` 註冊。
**價值**：補齊學術標準因子庫，使系統可復現經典研究。

### I2: Kakushadze 101 精選（🟡 P1）

從 101 個公式中挑選 **10~15 個低相關、高 Sharpe** 的因子。論文特性：
- 平均持有期 0.6~6.4 天（適合短天期 alpha）
- 平均配對相關性僅 15.9%（分散化好）
- 全部為 price-volume 公式，不需基本面數據

**實作**：`src/strategy/factors.py` 新增選定的公式因子。
**篩選標準**：先用台股回測 IC > 0.02 + 低與現有因子的相關性。

### I3: 因子篩選閾值校正（🔴 P0）

| 現況 | 論文依據 | 修正 |
|------|---------|------|
| `min_icir = 0.3` | Harvey (2016): t > 3.0 | 提高至 `0.5` |
| 無 post-publication decay 調整 | McLean & Pontiff (2016): OOS alpha ≈ 0.42× IS | `DynamicFactorPool` 加入 IS→OOS 衰減係數 |
| 無 1/N benchmark | DeMiguel (2009): N>25 T<500 時 1/N 難以打敗 | `AlphaReport` 新增 vs-1/N Sharpe t-test |

**實作**：修改 `src/alpha/auto/config.py` 和 `decision.py`。

### I4: Momentum Crash 防護（🟡 P1）

Daniel & Moskowitz (2016) 發現 momentum crash 在恐慌狀態後發生，可預測。

**實作**：
- `SafetyChecker` 新增 momentum crash 偵測（市場跌幅 > 20% + 高波動率）
- `REGIME_FACTOR_BIAS[BEAR]["momentum"]` 從 0.5 降至 0.1
- 可選：volatility-scaling `w_mom × (σ_target / σ_realized_20d)`

**位置**：`src/alpha/auto/safety.py` + `decision.py`。

---

## 5. Phase J：Alpha 自動化擴展至跨資產 → [詳細計畫](plans/phase-j-cross-asset-automation.md)

> 目標：從「台股個股選股」擴展至「ETF 配置 + 跨市場」

### J1: ETF Alpha Pipeline（🟡 P1）

Asness et al. (2013) 證明 value + momentum 在**股票、債券、外匯、商品**中普遍有效。

**實作**：
- `AlphaConfig` 新增 `asset_type: Literal["stock", "etf", "mixed"]`
- ETF 因子：momentum + value (yield/PE) + volatility + carry
- Universe：台灣 ETF（0050/0056/00878/00713 等）+ 美國 ETF（SPY/QQQ/TLT/GLD 等）
- 整合至 `AutoAlphaScheduler`，可分別跑「股票池」和「ETF 池」

### J2: 兩層自動化整合（🟢 P2）

將 auto-alpha（個股）與 TacticalEngine（資產配置）串接：
```
每日流水線（擴展版）：
1. TacticalEngine → 資產類別權重 (股票 60% / 債券 ETF 25% / 商品 ETF 15%)
2. 股票部位 → AutoAlpha 個股選股（現有流程）
3. 債券/商品部位 → ETF Alpha Pipeline（J1）
4. 合併 → PortfolioOptimizer → 最終權重
```

---

## 6. 未來方向（不排入開發計畫）

- **IB 美股對接** — 等台股 Paper Trading 跑穩後
- **期貨/選擇權交易** — 等股票流程驗證後
- **ML 因子模型** (Gu-Kelly-Xiu 2020) — trees/NN 翻倍 Sharpe，但 OOS R² < 0.4%，穩定性存疑
- **MVSK / 非高斯建模** — 學術性 > 實用性

---

## 7. 里程碑

| 日期 | 里程碑 |
|------|--------|
| 2026-03-22~25 | Phase A~E（核心系統 + 交易架構） |
| 2026-03-26 | Phase F~H（自動化 + 學術升級 + 精煉），1,006 tests |
| TBD | Shioaji API Key → 整合測試 → Paper Trading |
| TBD | I1: Fama-French 因子補齊 (size/investment/gross_profitability) |
| TBD | I3: 因子篩選閾值校正 (Harvey t>3.0 + McLean-Pontiff OOS decay) |
| TBD | I2: Kakushadze 101 精選 (10~15 個低相關公式因子) |
| TBD | I4: Momentum Crash 防護 |
| TBD | J1: ETF Alpha Pipeline |
| TBD | J2: 兩層自動化整合（個股 + ETF + 配置） |
