# 開發計畫書

> **version**: v13.0
> **date**: 2026-03-27

---

## 1. 專案現況

多資產投資組合研究與優化系統。Python 後端 + React Web + Android Native。
156 後端檔案、~28K LOC、1,329 tests。83 個 Alpha 因子（66 技術 + 17 基本面）、14 種組合最佳化、11 個策略、10 條風控規則。

**當前優先級**：Phase N — Paper Trading 準備。真實性修正後策略績效：revenue_momentum CAGR +13.8% Sharpe 0.79（含 40 天營收延遲 + 漲跌停 + 成交量限制）。

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
| K | 03-26 | 數據品質 + FinMind 8 dataset + 基本面因子 | [phase-k](plans/phase-k-data-quality.md) |
| L | 03-26 | 策略轉型：FilterStrategy + revenue_momentum 驗證 | [phase-l](plans/phase-l-strategy-pivot.md) |
| M | 03-27 | 下行保護 + 引擎優化 + 因子全流程驗證（13 次實驗） | [phase-m](plans/phase-m-downside-protection.md) |

### 待執行

| 階段 | 優先級 | 摘要 | 計畫書 |
|------|:------:|------|--------|
| **N** | 🔴 P0 | **Paper Trading 準備 + 30 天驗證** | [phase-n](plans/phase-n-paper-trading.md) |
| O | 🟡 P1 | 事件時機層 + 多策略組合（FinLab 差距 P1 項） | TBD |
| J | 🟢 P2 | 跨資產自動化 | [phase-j](plans/phase-j-cross-asset-automation.md) |

---

## 3. 實驗總結

> 完整報告見 `docs/dev/test/`

### 因子研究結論

| 結論 | 證據 |
|------|------|
| **rev_yoy（營收年增率）是台股最強公開因子** | ICIR 0.674, t=16.1, p<0.000001 |
| 10 年每年正 IC（100% 穩定） | 2016~2025 無一年失效 |
| 多因子組合幾乎無加成 | 最佳組合 ICIR 0.692 vs 單因子 0.674（+2.7%） |
| 價格因子有害 | 加入 momentum/volatility 後 ICIR 崩跌 |
| 籌碼面適合篩選、不適合加權 | trust_10d 加入後 ICIR -0.164 |
| 中型股 rev_yoy+rev_accel 最強 | ICIR 0.628 |
| 小型股 rev_yoy+trust_10d 最強 | ICIR 0.648 |

### 策略驗證結論

| 指標 | baseline | composite_b0% |
|------|----------|---------------|
| CAGR | +29.5% | +26.5% |
| Sharpe | 1.63 | 1.48 |
| MDD | 22.0% | 21.4% |
| OOS 2025 H1 | -16.1% | **-5.4%** |
| 2022 MDD | 11.2% | **8.5%** |
| StrategyValidator | — | **10/13** |

### 因子來源歸因

營收因子方向來自 FinLab 社群研究（54 篇部落格 + 15 篇 FB）。我們的貢獻是嚴格統計驗證（WF/PBO/t-test）、下行保護機制、引擎優化。

---

## 4. Phase N：Paper Trading 準備（🔴 P0）

### N1：策略整合到主系統

| 項目 | 說明 |
|------|------|
| composite_b0% 正式化 | 從實驗腳本移到 `strategies/revenue_momentum_hedged.py`，註冊到 registry |
| 即時模式適配 | 確認 ExecutionService paper mode 能驅動月度再平衡的 on_bar() |
| Context 即時數據 | 確認 LiveContext 提供最新價格 + FinMind 營收（本地 parquet） |
| 整股下單邏輯 | 台股 1 張 = 1,000 股，確認 `weights_to_orders()` 正確轉換 |

### N2：月營收自動更新

| 項目 | 說明 |
|------|------|
| 排程下載 | APScheduler 每月 11 日自動跑 `download_finmind_data.py --dataset revenue` |
| 增量更新 | 只下載上個月的新數據，不重新下載全部 |
| 數據驗證 | 下載後自動檢查 parquet 完整性 |

### N3：通知 + 監控

| 項目 | 說明 |
|------|------|
| 交易通知 | 下單/成交時發送 Discord/LINE/Telegram 通知 |
| 每日 NAV 快照 | 每日收盤後記錄 NAV、持倉、偏差 |
| 異常告警 | 連線斷線、下單失敗、MDD 超限自動告警 |

### N4：對帳 + 績效追蹤

| 項目 | 說明 |
|------|------|
| 每日對帳 | 比對策略目標持倉 vs Shioaji 實際持倉 |
| 回測 vs 實盤比對 | 同期回測結果 vs Paper Trading，量化 R² |
| 30 天驗證日誌 | 每日記錄，月底產出完整報告 |

### N5：CA 憑證整合

| 項目 | 說明 |
|------|------|
| .pfx 設定 | `QUANT_SINOPAC_CA_PATH` + `QUANT_SINOPAC_CA_PASSWORD` |
| Deal callback | 成交回報接入 OMS + WebSocket 通知 |
| 完整循環測試 | 登入 → 選股 → 下單 → 回報 → 對帳 |

---

## 5. 阻塞項

| 項目 | 狀態 |
|------|------|
| 策略研究 | ✅ rev_yoy ICIR 0.674, t=16.1, 13 次實驗完成 |
| 下行保護 | ✅ composite_b0% OOS -16%→-5.4% |
| StrategyValidator | ✅ 10/13 通過 |
| 引擎效能 | ✅ 676 支 × 7Y 344s→55s |
| 數據 | ✅ 900 價格 + 312 營收 + 223 法人 |
| **composite_b0% 正式整合** | 🔴 N1（從實驗腳本移到主系統） |
| **月營收自動更新** | 🔴 N2（Paper Trading 核心依賴） |
| **通知 + 監控** | 🟡 N3 |
| **CA 憑證** | ⏳ 用戶申請中 |

---

## 6. 里程碑

| 日期 | 里程碑 |
|------|--------|
| 03-22~25 | Phase A~E（核心系統 + 交易架構） |
| 03-26 | Phase F~I + R1-R4 + K（自動化 + 學術 + 因子 + 數據品質） |
| 03-26 | Phase L：策略轉型 + 驗證 6/7（p=0.013） |
| 03-27 | Phase M + 實驗 #9~#13（修正前數字，已歸檔） |
| 03-27 | **真實性修正**：+40d 營收延遲 / 漲跌停 / ADV 限制 / 引擎驗證 15/17 |
| 03-27 | **#14-#15**：修正後 CAGR +13.8% Sharpe 0.79，rev_accel ICIR 0.476，4/7 門檻 |
| **TBD** | **Phase N：Paper Trading（策略邊緣可行，需實盤驗證）** |
| TBD | Phase O：事件時機層（營收公布日觸發 → 縮短延遲）|
| TBD | Phase J：跨資產自動化 |

---

## 7. 未來方向（不排入開發計畫）

- IB 美股對接 — 等台股 Paper Trading 穩定後
- 期貨/選擇權交易 — 等股票流程驗證後
- ML 因子模型 (Gu-Kelly-Xiu 2020) — OOS R² < 0.4%
- OpenFE 自動特徵工程 — 需大量算力
- 券商分點數據 / 主力買賣 — 需付費數據源
- FinMind 價格源（去倖存者偏差）— Paper Trading 穩定後再處理
