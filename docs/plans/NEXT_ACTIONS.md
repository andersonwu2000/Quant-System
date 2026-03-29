# Next Actions — 具體待辦事項

> 本文件是唯一的「接下來做什麼」參考。每週覆核一次。

---

## Phase 0：開盤前 — ✅ 全部完成（2026-03-29）

22 項修復。詳見 git history。

## Phase 1：開盤第一天（3/30）

| # | 項目 | 狀態 |
|---|------|:----:|
| 1.1 | 啟動 API server | ✅ |
| 1.2 | 09:03 自動觸發建倉（SimBroker + Yahoo 即時價格） | ⏳ cron job set |
| 1.3 | 確認訂單和持倉 | ⏳ |
| 1.4 | 確認 Discord 通知 | ⏳ |

### 3/30 已完成的改進

| 項目 | 說明 |
|------|------|
| **Paper mode SimBroker** | 改用 SimBroker（和回測共用），含漲跌停 ±10%、partial fill、sqrt impact |
| **即時價格** | Yahoo realtime 優先，parquet fallback，prev_close for limit check |
| **IC-Alpha Gap 修復** | top-40 score-tilt construction、L5b OOS profitability、L5c MR test、novelty indicator、WF vs_ew_universe |
| **Pipeline 審計** | 10 CRITICAL + 6 HIGH + 4 MEDIUM 修復（詳見 git history） |
| **Agent 反饋** | profitability + novelty 雙目標、ic_trend、ic_source 診斷 |
| **數據擴充** | per_history 472 支、margin 220 支 |
| **Pipeline cron** | 08:30 → 09:03（開盤後） |
| **Trading hours** | paper mode 不限時段（SimBroker 模擬） |
| **Saturation** | corr > 0.20 才觸發（防誤擋新方向） |

## Phase 2：開盤第一週

| # | 項目 | 狀態 |
|---|------|:----:|
| ~~2.2~~ | ~~Paper mode SimBroker~~ | ✅ 2026-03-30 |
| 2.3 | 用 2× 成本重跑 Validator（全策略） | ⏳ |
| 2.4 | AG 手動端到端第 3 次 | ⏳ |
| 2.5 | 確認 paper trading 正常後準備微額實盤 | CA 憑證取得後 |

## Phase 3：前 30 天

不寫新代碼。每日確認 NAV + Discord 通知。每週比對 paper vs 回測。

## Phase 4：30-90 天

### 數據擴充（FinLab 借鑒）

| # | 數據 | 來源 | 優先級 |
|---|------|------|:------:|
| D1 | 集保戶股權分散表 | TDCC API（FinMind 需付費） | **高** |
| D2 | 處置股/注意股/全額交割 | 公開資訊觀測站 | **高** |
| D3 | 市值（自算） | close × shares_outstanding | **高** |
| D4 | 內部人持股+質押 | 公開資訊觀測站 | 中 |
| D5 | 借券餘額 | FinMind | 中 |

### 評估改進

| # | 項目 | 狀態 |
|---|------|:----:|
| 4E | 行業中性化 IC 診斷 | ✅ 2026-03-30 |
| 4F | IC 趨勢回歸 | ✅ 2026-03-30 |
| 4G-4K | L5b/L5c/novelty/construction/WF | ✅ 2026-03-30 |
| 4L | Rebalance 對齊營收公告日 | ⏳ |
| 4M | Size neutralization | ⏳ |

### 審計剩餘

| 項目 | 嚴重度 |
|------|:------:|
| H-003 replacement chain attack | HIGH |
| M-001 eval_server L5b/L5c parsing | MEDIUM |
| M-002 PBO silent failure validation | MEDIUM |
| L-001~004 atomicity + cleanup | LOW |

## Phase 5：90 天後

| 條件 | 動作 |
|------|------|
| 超額 > 0 且 t-stat > 1.0 | 逐步加碼 |
| 超額 ≤ 0 但一致 | alpha combining 或換因子 |
| 超額 ≤ 0 且不一致 | 校準成本模型 |
| 超額 ≤ 0 且無新因子 | 接受沒有 alpha |

---

## 不做的事

新 Phase、多市場擴展、更複雜組合優化、FinLab SDK 整合、PBO DSR fallback。
