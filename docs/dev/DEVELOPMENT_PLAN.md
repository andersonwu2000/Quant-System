# 開發計畫書

> **version**: v7.1
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

## 4. 待開發階段

| 階段 | 優先級 | 摘要 | 計畫書 |
|------|--------|------|--------|
| I | 🔴 P0~P1 | Alpha 因子庫擴展：Fama-French 補齊 + Kakushadze 101 精選 + 閾值校正 + Momentum Crash 防護 | [phase-i](plans/phase-i-alpha-expansion.md) |
| J | 🟡 P1~P2 | Alpha 自動化擴展至 ETF + 跨資產兩層整合 | [phase-j](plans/phase-j-cross-asset-automation.md) |

---

## 5. 未來方向（不排入開發計畫）

- **IB 美股對接** — 等台股 Paper Trading 跑穩後
- **期貨/選擇權交易** — 等股票流程驗證後
- **ML 因子模型** (Gu-Kelly-Xiu 2020) — OOS R² < 0.4%，穩定性存疑
- **MVSK / 非高斯建模** — 學術性 > 實用性

---

## 6. 里程碑

| 日期 | 里程碑 |
|------|--------|
| 2026-03-22~25 | Phase A~E（核心系統 + 交易架構） |
| 2026-03-26 | Phase F~H（自動化 + 學術升級 + 精煉），1,006 tests |
| TBD | Shioaji API Key → 整合測試 → Paper Trading |
| TBD | Phase I：Alpha 因子庫擴展 |
| TBD | Phase J：跨資產自動化 |
