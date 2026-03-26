# 開發計畫書

> **version**: v7.2
> **date**: 2026-03-26

---

## 1. 專案現況

多資產投資組合研究與優化系統。Python 後端 + React Web + Android Native。
147 後端檔案、~25K LOC、1,138 tests。14 種組合最佳化方法、27 個 Alpha 因子、10 條風控規則、74 個 API 端點。Phase A~I + R1-R4 全部完成。

**Shioaji 整合**：API Key 已取得，模擬模式驗證通過 (2026-03-26)。Deal callback + tick streaming 需生產環境 CA 憑證。

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
| I | 03-26 | Alpha 因子庫擴展：Fama-French 補齊 + Kakushadze 101 精選 + 閾值校正 + Momentum Crash 防護 | [phase-i](plans/phase-i-alpha-expansion.md) |
| R1-R4 | 03-26 | 架構重構：TWAP Smart Order + 台股交易日曆 + Trading Pipeline + Broker 子套件 | [refactoring](architecture/REFACTORING_PLAN.md) |

---

## 3. 阻塞項

| 項目 | 阻塞 | 解除後 |
|------|------|--------|
| Shioaji 模擬整合 | ✅ 已完成 | login + 基本下單驗證通過 (2026-03-26) |
| Deal callback + tick streaming | CA 憑證 (生產環境) | 成交回報 + 即時行情 |
| Paper Trading 完整循環 | CA 憑證 | 排程→下單→回報→對帳→通知 |
| 即時行情 WS broadcast | CA 憑證 | SinopacQuoteManager → market 頻道 |

---

## 4. 待開發階段

| 階段 | 優先級 | 摘要 | 計畫書 |
|------|--------|------|--------|
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
| 2026-03-26 | Phase F~H（自動化 + 學術升級 + 精煉） |
| 2026-03-26 | Phase I（Alpha 因子庫擴展：27 因子，向量化 15x 加速） |
| 2026-03-26 | R1-R4 重構（TWAP + 交易日曆 + Trading Pipeline + Broker 子套件） |
| 2026-03-26 | Shioaji 模擬整合通過，1,138 tests |
| TBD | CA 憑證 → Deal callback → Paper Trading 完整循環 |
| TBD | Phase J：跨資產自動化 |
