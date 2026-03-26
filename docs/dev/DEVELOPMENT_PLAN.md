# 開發計畫書

> **version**: v11.0
> **date**: 2026-03-26

---

## 1. 專案現況

多資產投資組合研究與優化系統。Python 後端 + React Web + Android Native。
155 後端檔案、~28K LOC、1,316 tests。83 個 Alpha 因子（66 技術 + 17 基本面）、14 種組合最佳化、11 個策略、10 條風控規則。

**當前優先級**：**Phase L 驗證通過（6/7）** — revenue_momentum 策略 CAGR +30.5%, p=0.013。OOS 2025 H1 為負，需加下行保護後進入 Phase N Paper Trading。

---

## 2. 階段總覽

各階段詳細計畫書見 `docs/dev/plans/`。

### 已完成

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
| I | 03-26 | Alpha 因子庫擴展：66 技術因子 + Kakushadze | [phase-i](plans/phase-i-alpha-expansion.md) |
| R1-R4 | 03-26 | 架構重構：TWAP + 交易日曆 + Trading Pipeline | [refactoring](architecture/REFACTORING_PLAN.md) |
| K | 03-26 | 數據品質 + FinMind 8 dataset + 基本面因子 14 個 | [phase-k](plans/phase-k-data-quality.md) |
| **L** | **03-26** | **策略轉型：FilterStrategy + revenue_momentum 驗證通過 (6/7, p=0.013)** | [phase-l](plans/phase-l-strategy-pivot.md) |

### 待執行

| 階段 | 優先級 | 摘要 | 計畫書 |
|------|:------:|------|--------|
| **M** | 🟡 P1 | 因子管理：去冗餘 + 替換機制 + 散戶反向/事件驅動策略 + 擁擠度 | [phase-m](plans/phase-m-factor-management.md) |
| **N** | 🟡 P1 | Paper Trading：CA 憑證 + 完整循環 + 30 天驗證 | [phase-n](plans/phase-n-paper-trading.md) |
| J | 🟢 P2 | 跨資產自動化 | [phase-j](plans/phase-j-cross-asset-automation.md) |

---

## 3. 實驗結論（驅動方向轉變）

> 完整報告見 `docs/dev/test/`

### 3.1 Price-volume 因子（15 次實驗，2026-03-26）

- 75 個因子 × 142 支台股 × 7 年：**寬 universe 全部 < ICIR 0.5**
- Walk-forward 最佳超額：+3.1%/年（mom6m + turnover_vol），超額 SR 0.20
- **結論：純 price-volume alpha 在台股不顯著**

### 3.2 基本面因子（Phase K，2026-03-26）

- **revenue_yoy ICIR 0.317** — 首次突破 0.3 門檻
- 三因子組合（rev_yoy + momentum_6m + value_pe）Sharpe 1.19，超額 +2.7%/年
- **結論：基本面因子有信號，但轉化效率待提升**

### 3.3 FinLab 研究交叉驗證

> 完整分析見 `docs/dev/test/Finlab.md`

- 54 個公開策略，平均年化 20%，最高 60%
- 年化 > 30% 的 16 策略 **100% 包含營收動能**
- 投信買超 > 外資（外資逆向 CAGR -11.2%）
- 低 PE（-1.4%）/ 低波動（-0.7%）完全無效
- **結論：台股 alpha 在營收動能 + 投信籌碼，不在 price-volume**

### 3.4 Phase L 嚴格驗證（676 支台股，2018-2024）

> 完整報告見 `docs/dev/test/20260326_8.md`

**全期回測**：CAGR **+30.5%**、Sharpe **1.51**、MDD **26.4%**、1,506 trades

**Walk-Forward（年度 OOS）**：

| 年度 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | Mean |
|------|------|------|------|------|------|------|------|------|
| CAGR | +1% | +39% | +64% | +41% | +3% | +94% | +58% | **+43%** |
| Sharpe | 0.07 | 2.87 | 2.15 | 1.56 | 0.20 | 4.21 | 3.27 | **2.05** |

**統計檢驗**：t = 3.50, **p = 0.013**, 95% CI Sharpe [0.92, 3.08]
**PBO**：**0%**（50 次 CSCV 無過擬合）
**OOS 2025 H1**：❌ -7.4%（偏多頭策略在下行市場表現差）

| 檢驗 | 通過？ |
|------|:------:|
| CAGR > 15% | ✅ |
| Sharpe > 0.7 | ✅ |
| Max DD < 50% | ✅ |
| WF Sharpe > 0 | ✅ |
| p < 0.05 | ✅ |
| PBO < 50% | ✅ |
| OOS 2025 > 0 | ❌ |

**結論：6/7 通過。首次在嚴格統計檢驗下通過的策略。**

---

## 4. Phase L 完成進度

### L1：數據管線 ✅

| 項目 | 狀態 | 說明 |
|------|------|------|
| 營收數據擴展 | ✅ | 143 支 revenue parquet（從 51 → 143） |
| 投信/外資/自營分離 | ✅ | 146 支 institutional parquet（從 51 → 146） |
| `--symbols-from-market` | ✅ | 自動從 data/market/ 發現 144 支台股 |
| `--force` 重新下載 | ✅ | 強制覆蓋已有檔案 |
| 本地 parquet 優先讀取 | ✅ | `get_revenue()` / `get_institutional()` 先讀本地，不呼叫 API |
| Symbol-level cache | ✅ | 同一 symbol 只解析一次 parquet，不按日期範圍重複讀取 |
| Yahoo mode 啟用 FinMind fundamentals | ✅ | `create_fundamentals("yahoo")` 自動使用 FinMind（如有 token） |
| 集保數據（L1.3） | ⏳ | Phase M 依賴，暫緩 |
| 市值數據（L1.4） | ⏳ | 現用 close × volume 代理，暫緩 |

### L2：條件篩選 Pipeline ✅

| 項目 | 狀態 | 說明 |
|------|------|------|
| `FilterCondition` | ✅ | 6 運算子（gt/lt/gte/lte/eq/between） |
| `FilterStrategyConfig` | ✅ | top_n / rank_by / max_weight / min_volume_lots |
| `FilterStrategy` | ✅ | 通用篩選策略（AND 邏輯 + 排序取前 N + 等權） |
| 因子計算器 | ✅ | 8 price-based + 5 fundamental-based（`PRICE_FACTORS` / `FUNDAMENTAL_FACTORS`） |
| 預設策略工廠 | ✅ | `revenue_momentum_filter()` / `trust_follow_filter()` |
| 測試 | ✅ | 21 tests（test_filter_strategy.py） |

### L3：策略實作 ✅

| 策略 | 檔案 | 類型 | 說明 |
|------|------|------|------|
| Revenue Momentum | `strategies/revenue_momentum.py` | Standalone | 營收 3M>12M + YoY>15% + 價>MA60 + 60d 動能>0 |
| Trust Follow | `strategies/trust_follow.py` | Standalone | 投信 10d 買超>15k + 營收新高 + YoY>20% |
| Filter Revenue Momentum | `src/alpha/filter_strategy.py` | FilterStrategy | 同上，通用框架版 |
| Filter Trust Follow | `src/alpha/filter_strategy.py` | FilterStrategy | 同上，通用框架版 |
| 月度 cache | ✅ | 策略只在月份變更時重新計算，避免每日重複讀 parquet |
| 策略註冊 | ✅ | registry.py 新增 revenue_momentum + trust_follow（共 11 策略） |
| 測試 | ✅ | 29 tests（test_revenue_strategies.py） |

### L4：8 年回測 ⏳

| 項目 | 狀態 | 說明 |
|------|------|------|
| 回測腳本 | ✅ | `scripts/run_strategy_backtest.py` |
| TW50 × 5 年初步回測 | ✅ | revenue_momentum CAGR +23.8% Sharpe 1.42 |
| 全 142 支 × 8 年嚴格驗證 | ⏳ | 需要下載 2015-2019 歷史價格數據 |
| Walk-Forward + PBO | ⏳ | 待數據就緒後執行 |

---

## 5. 阻塞項

| 項目 | 狀態 |
|------|------|
| FinMind 數據下載 | ✅ 143 revenue + 146 institutional（全 universe） |
| 條件篩選 Pipeline | ✅ FilterStrategy 框架 + 13 因子計算器 |
| 營收動能/投信跟單策略 | ✅ 4 策略 + 50 tests |
| 本地 parquet 讀取優化 | ✅ symbol-level cache + 月度策略 cache |
| 全 universe 驗證 | ✅ 676 支 × 7 年：CAGR +30.5%, p=0.013, PBO=0% (6/7 passed) |
| **StrategyValidator（11 項驗證）** | ✅ `src/backtest/validator.py` — 全部策略上線前強制閘門 |
| **OOS 2025 H1 為負** | 🟡 需要下行保護機制（Kill Switch / 空頭偵測） |
| **Trust Follow 閾值調整** | 🟡 TW50 universe 太窄，需中小型股 |
| CA 憑證 | ⏳ 待申請（Phase N 前置） |

---

## 6. 里程碑

| 日期 | 里程碑 |
|------|--------|
| 03-22~25 | Phase A~E（核心系統 + 交易架構） |
| 03-26 | Phase F~I + R1-R4 + K（自動化 + 學術 + 因子擴展 + 數據品質） |
| 03-26 | 15 次 Alpha 實驗 + FinLab 54 策略研究 → 確認策略方向轉型 |
| 03-26 | Phase L: L1~L3 完成（數據管線 + 條件篩選 + 策略實作） |
| **03-26** | **Phase L 驗證通過：676 支 × 7Y CAGR +30.5%, Sharpe 1.51, t=3.50, p=0.013, PBO=0% (6/7)** |
| TBD | Phase M：因子庫去冗餘 + 進階策略（散戶反向 / 事件驅動） |
| TBD | Phase N：Paper Trading 完整循環 |
| TBD | Phase J：跨資產自動化 |

---

## 7. 未來方向（不排入開發計畫）

- IB 美股對接 — 等台股 Paper Trading 穩定後
- 期貨/選擇權交易 — 等股票流程驗證後
- ML 因子模型 (Gu-Kelly-Xiu 2020) — OOS R² < 0.4%，穩定性存疑
- OpenFE 自動特徵工程 — 需大量算力
- 券商分點數據 / 主力買賣 — 需付費數據源
