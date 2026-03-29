# Next Actions — 具體待辦事項（取代新開發計畫）

> 不再開新 Phase。現有 AE-AG 已覆蓋所有需要的功能。
> 本文件只列「接下來該做什麼」，按時間排序。
> 每完成一項打 ✅ + 日期。

---

## 為什麼不寫新開發計畫

LESSONS #21：先研究再建基礎設施。
LESSONS #27：定期停下來驗證，不要被進展感掩蓋底層問題。

目前的底層問題是：**不知道策略有沒有 alpha。** 在這個問題回答之前，任何新功能都是浪費。

---

## Phase 0：開盤前（放假期間）

全部是已識別的問題修復，不是新功能。

| # | 項目 | 來源 | 工作量 | 狀態 |
|---|------|------|:------:|:----:|
| 0.1 | Validator 回測加 2× 成本 check | QUANT_FUND_COMPARISON §7.1 | ~10 行 | ⏳ |
| 0.2 | FULL_SYSTEM H-1~H-6 修復 | code-quality/FULL_SYSTEM | ~30 行 | ✅ 2026-03-29（H-1/H-2/H-3/H-4/H-5/H-6/M-09 已修，CR-2 已有 double-check locking 保護） |
| 0.3 | evaluate.py docstring 修正（Bailey 引用） | AB §11 V-2/V-3 | ~5 行 | ✅ 2026-03-29（已修：L1082 "Only L3+", L1086 Bailey 引用） |
| 0.4 | AE-H1 evaluator 加 strategies/ mount | code-quality/FULL_SYSTEM AE issues | 1 行 | ✅ 2026-03-29（docker-compose.yml 已有） |

## Phase 1：開盤第一天

| # | 項目 | 來源 | 做法 | 狀態 |
|---|------|------|------|:----:|
| 1.1 | **啟動 Paper Trading** | PRODUCTION_READINESS §2 | revenue_momentum_hedged（零股，1 萬元，max_holdings=10）。L5 因子 0 個，先跑主策略 | 3/30 手動觸發 |
| 1.2 | 市場數據確認 | AD 未做的 workaround | 數據最新到 3/27（上個交易日），✅ 已是最新 | ✅ |
| 1.3 | 設定通知告警 | PRODUCTION_READINESS §5 | .env 加 Telegram/LINE token | ⏳ |
| 1.4 | **手動觸發首次建倉** | cron=每月 11 日，3/30 不會自動跑 | `make dev` → `curl -X POST http://localhost:8000/api/v1/scheduler/trigger/pipeline -H "X-API-Key: dev-key"` | 3/30 做 |

### 1.2 微額實盤設計

**目的**：Paper trading 無法驗證真實滑價、零股成交率、券商 API 行為、T+2 交割。微額實盤平行跑，兩條 NAV 曲線的差距 = 執行成本的真實度量。

```
Paper Trading (SimBroker)          微額實盤 (SinopacBroker)
  虛擬 1000 萬                       真實 10-30 萬
  15 檔持倉                          3-5 檔（top 信號，資金不夠 15 檔整張）
  同一策略                           同一策略
  月度再平衡                         月度再平衡
       ↓                                ↓
  NAV 曲線 A                        NAV 曲線 B
       ↓                                ↓
       └──────── 每日比對 ────────────┘
                    ↓
            差異 = 執行落差
            (滑價 + 成交率 + 延遲 + 交割)
```

**前置條件**：
- CA 憑證取得（外部依賴，永豐金）
- SinopacBroker simulation=False 測試通過
- 通知告警已設定

**風控**：
- 最大虧損 = 30 萬 × 15% MDD = 4.5 萬（可接受的學費）
- Kill switch 5% 日回撤照用
- **Paper vs 實盤 NAV 偏差 > 3% → 暫停實盤排查原因**
- 第一個月只買整張（不買零股），觀察整張的成交行為

**資金規模**：1 萬起步，全部用零股交易。

**為什麼零股更好**：
- 個人投資者的真實場景就是零股（1 張台積電 ~60 萬，散戶買不起）
- 零股的成交行為和整張不同（盤中零股撮合、流動性差、可能不成交）
- 1 萬元 ÷ 10 檔 ≈ 每檔 ~950 元（max_holdings 從 15 降為 10，提高資金利用率 40%→57%）
- 最大虧損 = 1 萬 × 15% MDD = 1,500 元 — 極低風險

**零股交易的特殊考量**：
- 台股盤中零股交易時間：09:10-13:30，每 1 分鐘撮合一次
- 零股手續費最低 1 元（多數券商）— 小額交易成本比例偏高
- 1 萬元 × 15 檔 × 每月再平衡 ≈ 手續費 ~15-30 元/月（成本率 ~0.3%/月 = 3.6%/年）
- **這個成本率遠高於整張交易** — 正好可以測試「零股成本是否吃掉 alpha」

**系統需要確認的**：
- `_shares_to_lots()` 對零股（< 1000 股）回傳 `(qty, True)` ✅ 已驗證
- SimBroker 的零股手續費最低 1 元 ✅ `min_commission_odd_lot=1.0`（已正確）
- Shioaji 零股委託用 `StockOrderLot.IntradayOdd` ✅ 已實作

**微額實盤驗證的指標**（paper trading 無法測量的）：

| 指標 | 怎麼量 | 門檻 |
|------|--------|------|
| 零股成交率 | 成功成交筆數 / 委託筆數 | 觀察（首月無門檻，收集數據） |
| 實際滑價 | 委託價 vs 成交價的差 | 觀察（零股撮合價可能偏離） |
| 零股手續費佔比 | 手續費 / 交易金額 | 記錄（預期遠高於整張） |
| NAV 偏差 | paper NAV vs 實盤 NAV | < 5%（零股成本高，允許更大偏差） |
| 交割異常 | T+2 資金扣款是否正確 | 0 次異常 |
| API 斷線次數 | 重連次數 / 交易日 | < 1 次/週 |
| 零股未成交處理 | 策略如何處理部分成交 | 記錄（pending order 管理） |

## Phase 2：開盤第一週

| # | 項目 | 來源 | 工作量 |
|---|------|------|:------:|
| 2.1 | AD1 增量數據更新 | phase-ad-data-pipeline §AD1 | ~100 行 |
| 2.2 | 用 2× 成本重跑 Validator（全策略） | QUANT_FUND_COMPARISON §7.1 | 1 小時跑回測 |
| 2.3 | AG 手動端到端第 3 次 | phase-ag §10 BLOCKING | 1 小時 |
| 2.4 | **確認 paper trading 正常後啟動微額實盤** | 見 §1.2 設計 | CA 憑證 + 1 萬元零股 |

Phase 2 的 2.4 前置條件：
- Phase 1 的 paper trading 已跑滿一週且無異常
- CA 憑證已取得
- 通知告警已確認能收到
- SinopacBroker simulation=False 手動測過一次（用最小金額買 1 股確認流程）

## Phase 3：前 30 天（雙軌觀察）

**不寫新代碼。只觀察兩條 NAV 曲線。**

每日做：
- 確認 paper trading 有記錄 NAV
- 確認微額實盤成交正常（如果 CA 憑證已取得）
- 比對 paper vs 實盤的持倉和 NAV
- 記錄到 `docs/paper-trading/daily/`

每週做：
- 計算 paper vs 實盤的 NAV 偏差
- 記錄滑價、成交率、API 穩定度

30 天後評估：

| 條件 | 動作 |
|------|------|
| 累計虧損 > 10% 或 MDD > 15% | 停止兩者，回到研究 |
| Paper vs 實盤 NAV 偏差 > 5% | 暫停實盤，排查執行落差 |
| 沒崩潰 + 偏差 < 3% | 繼續到 90 天 |

## Phase 4：30-90 天（繼續觀察 + 研究新因子）

並行三件事：

**4A. 繼續雙軌觀察**（不動代碼）

**4B. 跑 autoresearch 研究新因子**（用修正後的 evaluate.py）
- 目標：累積 5+ 個獨立的 L5 因子
- 用於未來的 alpha combining（QUANT_FUND_COMPARISON §7.2）
- factor_returns 重新累積 → PBO 可重算 → DSR N 動態更新

**4C. 根據微額實盤數據校準成本模型**
- 用實際滑價替換回測的 5 bps 假設
- 用實際成交率估算 capacity
- 更新 Validator 的 cost_ratio check

## Phase 5：90 天後（決策點）

| 條件 | 動作 |
|------|------|
| 超額報酬 > 0 且 t-stat > 1.0 | 逐步加碼（每月 +10-20% 資金） |
| 超額 ≤ 0 但實盤和 paper 一致 | 確認「沒有 alpha」不是執行問題。測試 alpha combining 或換因子 |
| 超額 ≤ 0 且實盤比 paper 差很多 | 執行成本比預期高。校準成本模型後重新評估 |
| 超額 ≤ 0 且無新因子 | 接受「目前沒有 alpha」，系統轉為被動投資工具 |

---

## 不做的事（明確排除）

| 提議 | 為什麼不做 |
|------|-----------|
| 新的 Phase（AH, AI, AJ...） | 功能已足夠。問題是 alpha 不是功能 |
| 多市場擴展（美股/日股） | 先證明台股有 alpha 再擴展 |
| GPU 加速 | 17 實驗/hr 的瓶頸在 LLM，不在計算 |
| 更複雜的組合優化 | DeMiguel：equal-weight 就好 |
| 更多 Validator checks | 16 項已夠多，問題不在 check 數量 |
| 重寫前端 | 不影響 alpha |

---

## 追蹤

本文件是唯一的「接下來做什麼」參考。不再散落在各 Phase 計畫中。

每週覆核一次。完成的打 ✅ + 日期。
