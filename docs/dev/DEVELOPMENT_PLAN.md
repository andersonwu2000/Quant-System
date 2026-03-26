# 開發計畫書

> **version**: v8.0
> **date**: 2026-03-26

---

## 1. 專案現況

多資產投資組合研究與優化系統。Python 後端 + React Web + Android Native。
147 後端檔案、~25K LOC、1,138 tests。14 種組合最佳化方法、27 個 Alpha 因子、10 條風控規則、74 個 API 端點。Phase A~I + R1-R4 全部完成。

**Shioaji 整合**：API Key 已取得，模擬模式驗證通過 (2026-03-26)。模擬下單/帳務/Scanner 全部正常。

**當前優先級**：**驗證 Alpha 策略盈利能力**優先於生產環境整合。
> 原因：如果策略本身 Sharpe < 0，連上生產環境只會更快虧錢。CA 憑證是執行品質的改善，不是盈利能力的保證。

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
| R1-R4 | 03-26 | 架構重構：TWAP + 交易日曆 + Trading Pipeline + Broker 子套件 | [refactoring](architecture/REFACTORING_PLAN.md) |

---

## 3. 當前階段：Alpha 策略驗證

> **目標**：在投入真實交易前，確認自動化 Alpha 策略在模擬環境中具有正期望值。
> **不需要 CA 憑證**。全部在現有環境即可完成。

### 3.1 驗證步驟

```
Step 1: 擴大 Universe（150+ 支台股）
  → 用 Shioaji Scanner 取得活躍標的（已有 API Key）
  → 取代目前硬編碼的 20 支大型股
  → 目的：讓 cross-sectional IC 統計量可靠

Step 2: 全因子 IC 分析
  → 跑 Auto-Alpha 立即執行（150 支 × 27 因子）
  → 篩選 ICIR ≥ 0.5 的因子
  → 預期：10 支大型股時只有 momentum 通過；150 支應有更多

Step 3: Walk-forward 回測驗證
  → 用通過篩選的因子跑 1 年 walk-forward
  → 關鍵指標：
     - Sharpe > 0（最低門檻）
     - 勝過 1/N 等權基準（DeMiguel 2009）
     - 扣除交易成本後仍正（台股來回 ~50 bps）
     - Max Drawdown < 15%

Step 4: 過擬合檢測
  → Multiple Randomized Backtest（50 次）
  → CSCV/PBO（Bailey 2015）
  → P(Sharpe > 0) > 60% 才算通過

Step 5: 結論
  → 通過 → 申請 CA 憑證，開始 Paper Trading
  → 未通過 → 調整因子組合/權重方法，回到 Step 2
```

### 3.2 首次實測結果（2026-03-26）

| 指標 | 結果 | 評估 |
|------|------|------|
| Universe | 10 支大型股 | ❌ 太小，需 150+ |
| Regime | BULL | ✅ 偵測正常 |
| 因子通過篩選 | 0/21（ICIR 門檻 0.5） | ❌ Universe 太小導致 |
| momentum IC | +0.157, ICIR 0.63 | ✅ 有信號但需更大 universe 驗證 |
| 結論 | **需擴大 universe 後重新驗證** | — |

### 3.3 完成標準

| 條件 | 門檻 | 來源 |
|------|------|------|
| 至少 3 個因子通過 ICIR ≥ 0.5 | Harvey et al. (2016) | t-stat > 3.0 |
| Walk-forward Sharpe > 0（扣成本後） | DeMiguel et al. (2009) | 1/N benchmark |
| PBO < 50% | Bailey et al. (2015) | CSCV |
| Max Drawdown < 15% | 風控安全邊際 | — |
| Randomized Backtest P(Sharpe>0) > 60% | 統計顯著性 | — |

---

## 4. 阻塞項

| 項目 | 狀態 | 解除條件 |
|------|------|---------|
| Shioaji 模擬連線 | ✅ 已完成 | — |
| Alpha 策略盈利驗證 | 🔴 進行中 | 通過 §3.3 完成標準 |
| CA 憑證 | ⏳ 等待策略驗證通過 | 盈利驗證通過後申請 |
| Paper Trading 完整循環 | ⏳ 等待 CA 憑證 | CA + 交易日盤中 |

---

## 5. 待開發（策略驗證通過後）

| 階段 | 優先級 | 前置條件 | 摘要 |
|------|--------|---------|------|
| Stage 3.5 Validation Backtest | 🔴 P0 | — | Decision → Execution 之間加入回測閘門（見 architecture/AUTOMATED_ALPHA_ARCHITECTURE.md §Stage 3.5） |
| cost_drag 嚴格過濾 | 🔴 P0 | — | cost_drag > 預期 alpha 的因子直接排除 |
| Kill Switch 冷靜期恢復 | 🟡 P1 | — | 5 天冷靜後半倉恢復，非永久停止 |
| CA 憑證整合 | 🟡 P1 | 策略驗證通過 | Deal callback + tick streaming |
| Paper Trading 完整循環 | 🟡 P1 | CA 憑證 | 排程→下單→回報→對帳→通知 |
| J: 跨資產自動化 | 🟢 P2 | Paper Trading 穩定 | [phase-j](plans/phase-j-cross-asset-automation.md) |

---

## 6. 未來方向（不排入開發計畫）

- **IB 美股對接** — 等台股 Paper Trading 跑穩後
- **期貨/選擇權交易** — 等股票流程驗證後
- **ML 因子模型** (Gu-Kelly-Xiu 2020) — OOS R² < 0.4%，穩定性存疑
- **MVSK / 非高斯建模** — 學術性 > 實用性

---

## 7. 里程碑

| 日期 | 里程碑 |
|------|--------|
| 2026-03-22~25 | Phase A~E（核心系統 + 交易架構） |
| 2026-03-26 | Phase F~I + R1-R4（自動化 + 學術升級 + 因子擴展 + 重構） |
| 2026-03-26 | Shioaji 模擬整合通過，模擬下單成功 |
| 2026-03-26 | 首次台股因子 IC 分析：momentum IC=+0.157 |
| **TBD** | **Alpha 策略盈利驗證通過（§3.3 完成標準）** |
| TBD | CA 憑證 → Paper Trading 完整循環 |
| TBD | Phase J：跨資產自動化 |
