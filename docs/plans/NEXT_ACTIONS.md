# Next Actions — 具體待辦事項

> 本文件是唯一的「接下來做什麼」參考。每週覆核一次。

---

## Phase 0：開盤前 — ✅ 全部完成（2026-03-29）

22 項修復。詳見 git history。

## Phase 1：開盤第一天（3/30）— ✅ 完成

| # | 項目 | 狀態 |
|---|------|:----:|
| 1.1 | Paper trading 建倉 09:03 | ✅ 9 筆零股，NAV=9989，SimBroker + Yahoo 即時價格 |
| 1.2 | 定時監控 | ✅ 每小時自動檢查 |

### 3/30 完成的全部改進

**Paper Trading:**
- SimBroker 統一（漲跌停 ±10%、partial fill、sqrt impact、prev_close）
- Yahoo realtime 價格（fallback parquet）
- Instrument market="tw" + lot_size=1000（修正 odd lot detection）
- daily reconcile 更新 market_price（修 kill switch 失效）
- Portfolio as_of 用 UTC+8

**IC-Alpha Gap:**
- Construction: top-40 score-tilt（TC 0.10 → 0.45）
- vs_ew_universe: walk-forward per-window（消除 regime bias）
- L5b: IS + OOS profitability gate
- L5c: Patton & Timmermann MR test（bootstrap 1000 次）
- Novelty: returns correlation based（非 IC series）

**Agent 反饋:**
- profitability + novelty 雙目標
- ic_trend（stable/improving/declining）
- ic_source（stock_alpha/mixed/industry_beta）
- returns_corr 顯示（非 IC series corr）

**Pipeline 安全:**
- 全系統審計：10 CRITICAL + 6 HIGH + 4 MEDIUM 修復
- L2 median ICIR 包含 0 值 horizon
- Replacement chain depth < 3
- Thresholdout RNG 加 factor code hash
- Saturation 用 returns corr（IC corr 低的 clone 不再繞過）
- Saturation 在 replacement 之後（允許 1.3× 替換）
- Returns dedup exact stem match
- Clone group promotion 1.3× 統一門檻
- Post-validation dedup 允許 1.3× 替換
- pe/pb/roe disabled（look-ahead bias）
- 行業 prefix 處理 ETF "00xx"
- L5c OOS monotonicity 強制（≥ 5 dates）

## Phase 2：開盤第一週

| # | 項目 | 狀態 |
|---|------|:----:|
| 2.3 | 用 2× 成本重跑 Validator（全策略） | ⏳ |
| 2.4 | AG 手動端到端第 3 次 | ⏳ |
| 2.5 | 確認 paper trading 正常後準備微額實盤 | CA 憑證取得後 |

## Phase 3：前 30 天

不寫新代碼。每日確認 NAV。每週比對 paper vs 回測。

## Phase 4：30-90 天

### 數據擴充

| # | 數據 | 來源 | 狀態 |
|---|------|------|:----:|
| D1 | 集保戶股權分散表 | TDCC API（FinMind 需付費） | ⏳ |
| D2 | 處置股/注意股/全額交割 | 公開資訊觀測站 | ⏳ |
| D3 | 市值 | close × shares_outstanding | ✅ 51 支 |
| D4 | 內部人持股+質押 | 公開資訊觀測站 | ⏳ |
| D5 | 借券餘額 | FinMind | ⏳ |

### 評估改進

| # | 項目 | 狀態 |
|---|------|:----:|
| 4E-4K | IC 診斷 + L5b/L5c + novelty + construction + WF | ✅ |
| 4L | Rebalance 對齊營收公告日 | ⏳ |
| 4M | Size neutralization | ⏳ |

### 剩餘

| 項目 | 嚴重度 | 狀態 |
|------|:------:|:----:|
| M-001 eval_server L5b/L5c parsing | MEDIUM | ⏳ |
| L-001~004 atomicity + cleanup | LOW | ⏳ |

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
