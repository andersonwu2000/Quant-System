# 開發計畫書

> **version**: v10.0
> **date**: 2026-03-26

---

## 1. 專案現況

多資產投資組合研究與優化系統。Python 後端 + React Web + Android Native。
~150 檔案、~27K LOC、1,248 tests。80 個 Alpha 因子（66 技術 + 14 基本面）、14 種組合最佳化、10 條風控規則。

**當前優先級**：**策略方向轉型** — 從純 cross-sectional ranking 轉向多因子條件篩選 + 營收動能策略。

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
| **K** | **03-26** | **數據品質 + FinMind 8 dataset + 基本面因子 14 個 + IC 分析（revenue_yoy ICIR 0.317）** | [phase-k](plans/phase-k-data-quality.md) |

### 待執行

| 階段 | 優先級 | 摘要 | 計畫書 |
|------|:------:|------|--------|
| **L** | 🔴 P0 | **策略轉型**：條件篩選 Pipeline ✅ + 營收動能/投信跟單策略 ✅ + 8 年回測 ⏳ | [phase-l](plans/phase-l-strategy-pivot.md) |
| **M** | 🟡 P1 | **因子管理**：去冗餘 + 替換機制 + Experience Memory + 散戶反向/事件驅動策略 + 擁擠度 | [phase-m](plans/phase-m-factor-management.md) |
| **N** | 🟡 P1 | **Paper Trading**：CA 憑證 + 完整循環 + 30 天驗證 + 實盤 Checklist | [phase-n](plans/phase-n-paper-trading.md) |
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

- 年化 > 30% 的策略 **100% 包含營收動能**
- 投信買超 > 外資（外資逆向 CAGR -11.2%）
- 低 PE / 低波動完全無效
- **結論：台股 alpha 在營收動能 + 投信籌碼，不在 price-volume**

### 3.4 FactorMiner 論文（2026）

- LLM 生成因子 + Experience Memory + 因子去重/替換
- 高 IC 來自高頻 + 寬截面，不適用於我們的日線 + 窄 universe
- **採用**：因子入庫門檻、替換機制、禁區記錄（Phase M）

---

## 4. 阻塞項

| 項目 | 狀態 |
|------|------|
| FinMind 數據下載 | ✅ 8 dataset × 51 支完成 |
| 基本面因子 IC 分析 | ✅ revenue_yoy ICIR 0.317 |
| 條件篩選 Pipeline | ✅ `FilterStrategy` + 8 price + 5 fundamental calculators |
| 營收動能/投信跟單策略 | ✅ 4 策略（2 standalone + 2 FilterStrategy） |
| **8 年回測驗證** | 🔴 腳本就緒，待數據擴充後執行 |
| CA 憑證 | ⏳ 待申請（Phase N 前置） |

---

## 5. 里程碑

| 日期 | 里程碑 |
|------|--------|
| 03-22~25 | Phase A~E（核心系統 + 交易架構） |
| 03-26 | Phase F~I + R1-R4 + K（自動化 + 學術 + 因子擴展 + 數據品質） |
| 03-26 | 15 次 Alpha 實驗 + FinLab 研究 → 確認策略方向轉型 |
| **TBD** | **Phase L：營收動能策略回測驗證通過** |
| TBD | Phase M：因子庫去冗餘 + 進階策略 |
| TBD | Phase N：Paper Trading 完整循環 |
| TBD | Phase J：跨資產自動化 |

---

## 6. 未來方向（不排入開發計畫）

- IB 美股對接 — 等台股 Paper Trading 穩定後
- 期貨/選擇權交易 — 等股票流程驗證後
- ML 因子模型 (Gu-Kelly-Xiu 2020) — OOS R² < 0.4%，穩定性存疑
- OpenFE 自動特徵工程 — 需大量算力
- 券商分點數據 / 主力買賣 — 需付費數據源
