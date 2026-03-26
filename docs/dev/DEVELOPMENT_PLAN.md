# 開發計畫書

> **version**: v12.0
> **date**: 2026-03-26

---

## 1. 專案現況

多資產投資組合研究與優化系統。Python 後端 + React Web + Android Native。
156 後端檔案、~28K LOC、1,329 tests。83 個 Alpha 因子（66 技術 + 17 基本面）、14 種組合最佳化、11 個策略、10 條風控規則。

**當前優先級**：解決 FinLab 差距分析中的 P0 缺口 — **下行保護** + **倖存者偏差修復**，然後進入 Paper Trading。

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
| L | 03-26 | 策略轉型：FilterStrategy + revenue_momentum 驗證 6/7 | [phase-l](plans/phase-l-strategy-pivot.md) |

### 待執行

| 階段 | 優先級 | 摘要 | 計畫書 |
|------|:------:|------|--------|
| **L+** | 🔴 P0 | **下行保護 + 數據修復**：空頭偵測、FinMind 價格源、事件時機層 | [phase-l+](plans/phase-l-plus-gap-fix.md) |
| **M** | 🟡 P1 | 因子管理：去冗餘 + 多策略組合 + AI 自動搜索 | [phase-m](plans/phase-m-factor-management.md) |
| **N** | 🟡 P1 | Paper Trading：CA 憑證 + 完整循環 + 30 天驗證 | [phase-n](plans/phase-n-paper-trading.md) |
| J | 🟢 P2 | 跨資產自動化 | [phase-j](plans/phase-j-cross-asset-automation.md) |

---

## 3. FinLab 差距分析

> 完整報告見 `docs/dev/test/Finlab.md`

### 3.1 績效差距

| 指標 | 我們 (revenue_momentum) | FinLab 最佳 | 差距 | 差距來源 |
|------|------------------------|------------|------|---------|
| CAGR | +30.5% | +60% | -29.5pp | 無事件時機層、單一策略 |
| Sharpe | 1.51 | Sharpe(D) > 3 | ~2x | 日頻 vs 月頻再平衡 |
| Sortino | 2.16 | 3.02 | -0.86 | 無下行保護（Beta ≈ 1） |
| Beta | ≈ 1.0（純多頭） | **-0.43** | **根本差異** | 無做空/對沖能力 |
| OOS 2025 H1 | **-7.4%** | 負 Beta 策略應正 | **致命** | 純多頭在下行市場 |

### 3.2 架構差距

| 維度 | 我們 | FinLab | 差距等級 |
|------|------|--------|---------|
| 下行保護 | ❌ 純多頭 | ✅ Beta -0.43 策略 | 🔴 致命 |
| 數據可靠性 | Yahoo（倖存者偏差） | 全台股含下市 | 🔴 致命 |
| 事件時機 | 月度再平衡 | 事件後 T+4~T+7 | 🟡 重要 |
| AI 策略搜索 | 手動設計 | Claude Code Agent 自動 | 🟡 重要 |
| 指標數量 | 83 因子 | 900+ | 🟢 可接受（83 已夠） |
| 多策略組合 | 1 策略 | 54 策略輪動 | 🟡 重要 |

### 3.3 驗證標準（我們更嚴格）

| 檢驗 | 我們 | FinLab 公開展示 | 比較 |
|------|------|---------------|------|
| Walk-Forward | ✅ 7 年逐年 | 未公開 | **我們更嚴格** |
| PBO | ✅ 0% | 未提及 | **我們更嚴格** |
| t-test (p<0.05) | ✅ p=0.013 | 未公開 | **我們更嚴格** |
| StrategyValidator 11 項 | ✅ 強制閘門 | `verify_strategy()` | 同等 |
| OOS 獨立驗證 | ✅ 2025 H1 | 未明確 | **我們更嚴格** |

**結論**：我們的統計驗證框架比 FinLab 公開的更嚴格，但策略能力（下行保護、事件時機）落後。

---

## 4. Phase L+ ：解決 P0 差距（🔴 最高優先）

### L+.1 空頭市場偵測 + 現金避險

> 解決：OOS 2025 H1 失敗、Beta ≈ 1 無下行保護

```
邏輯：
- 大盤 MA200 斜率 < 0 且 大盤在 MA200 以下 → 空頭市場
- 空頭市場時：策略權重 × 0.3（只持 30% 倉位，70% 現金）
- 或：加入反向 ETF（0050 反1 = 00632R.TW）
```

**實作**：在 `revenue_momentum.py` 的 `on_bar()` 開頭加入市場環境判斷。

**預期效果**：2022 年 MDD 從 26% 降至 ~10%、2025 H1 從 -7.4% 改善到 ~-2%。FinLab 的 Beta -0.43 策略本質就是這種多空切換。

### L+.2 FinMind 價格數據源（修復倖存者偏差）

> 解決：Yahoo Finance 不含已下市股票 → 回測結果過度樂觀

```
方案：
- 用 FinMind TaiwanStockPrice 取代 Yahoo Finance 作為回測數據源
- FinMind 含已下市股票，消除倖存者偏差
- 下載全台股 2015-2025 價格到本地 parquet
```

**實作**：修改 `scripts/download_finmind_data.py` 加入 `price` dataset，用 FinMind 批量下載。

**預期效果**：回測 CAGR 可能下降 3-8pp（消除倖存者偏差），但結果更可靠。

### L+.3 事件時機層（Timing Layer）

> 解決：月度再平衡 vs FinLab 的事件驅動（Sharpe 差距 2x）

```
方案：
- 月營收公布後 T+1 觸發重新選股（目前是每月底固定）
- 法人異常買超（trust_10d > 3σ）觸發事件進場
- FinLab 發現：跳過事件後前 3 天，第 4-7 天進場績效最好
```

**實作**：新增 `EventDrivenRebalancer`，取代固定月度再平衡。

### L+.4 多策略組合

> 解決：單策略集中風險 vs FinLab 54 策略輪動

```
方案：
- revenue_momentum（營收動能，純多頭）
- revenue_momentum_hedged（加空頭偵測）
- trust_follow（投信跟單，中小型股）
- momentum_12_1（價格動量，基線）
- 按 inverse-volatility 加權組合
```

---

## 5. 阻塞項

| 項目 | 狀態 |
|------|------|
| Phase L 驗證 | ✅ 6/7 通過 (p=0.013, PBO=0%) |
| StrategyValidator 11 項 | ✅ `src/backtest/validator.py` |
| 數據擴充 | ✅ 900 支價格 + 312 營收 + 223 法人 |
| **空頭偵測 + 現金避險** | 🔴 Phase L+.1（解決 OOS 失敗） |
| **FinMind 價格源（去倖存者偏差）** | 🔴 Phase L+.2（回測可靠性） |
| **事件時機層** | 🟡 Phase L+.3（Sharpe 提升） |
| **多策略組合** | 🟡 Phase L+.4（降低單策略風險） |
| CA 憑證 | ⏳ Phase N 前置 |

---

## 6. 里程碑

| 日期 | 里程碑 |
|------|--------|
| 03-22~25 | Phase A~E（核心系統 + 交易架構） |
| 03-26 | Phase F~I + R1-R4 + K（自動化 + 學術 + 因子 + 數據品質） |
| 03-26 | 15 次 Alpha 實驗 + FinLab 54 策略研究 → 策略方向轉型 |
| 03-26 | Phase L 驗證：CAGR +30.5%, p=0.013, PBO=0% (6/7) |
| 03-26 | FinLab 差距分析：下行保護 + 數據修復 = P0 缺口 |
| 03-27 | 實驗 #9：空頭偵測比較 — vol_hedge OOS +8pp，MA200 無效 |
| 03-27 | 實驗 #10：複合偵測器 b0% — OOS -16%→**-5.4%**（+10.7pp），牛市反增 +3.4pp |
| 03-27 | 引擎優化：676 支 × 7Y 344s → **55s**（6.3x 提速） |
| 03-27 | composite_b0% StrategyValidator：**10/13 通過**（OOS -3.7%、PBO 0.67 待調整） |
| 03-27 | 實驗 #12：因子全流程驗證 — 4 因子全 ICIR>0.3、10/10 年正、t=16.1 |
| 03-27 | 實驗 #13：多因子組合 — rev_yoy 單因子（0.674）≈ 最佳組合（0.692），所有跨類型因子無加成 |
| **TBD** | **Phase N：Paper Trading** |
| TBD | Phase N：Paper Trading 完整循環 |
| TBD | Phase J：跨資產自動化 |

---

## 7. 未來方向（不排入開發計畫）

- IB 美股對接 — 等台股 Paper Trading 穩定後
- 期貨/選擇權交易 — 等股票流程驗證後
- ML 因子模型 (Gu-Kelly-Xiu 2020) — OOS R² < 0.4%
- OpenFE 自動特徵工程 — 需大量算力
- 券商分點數據 / 主力買賣 — 需付費數據源
- 1,500 特徵模型 — FinLab 路線，需更多算力和數據
