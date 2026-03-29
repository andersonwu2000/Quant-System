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

## Phase 0：開盤前（放假期間）— ✅ 全部完成

| # | 項目 | 來源 | 狀態 |
|---|------|------|:----:|
| 0.1 | Validator 2× 成本 check | QUANT_FUND_COMPARISON §7.1 | ✅ 2026-03-29 |
| 0.2 | FULL_SYSTEM H-1~H-6 + M-09 修復 | code-quality/FULL_SYSTEM | ✅ 2026-03-29 |
| 0.3 | evaluate.py docstring（Bailey 引用） | AB §V-2/V-3 | ✅ 2026-03-29（已正確） |
| 0.4 | AE-H1 strategies/ mount | code-quality/FULL_SYSTEM | ✅ 2026-03-29（已有） |
| 0.5 | Lot size 感知 | AA §4.7 + DEFERRED A-1 | ✅ 2026-03-29（fractional_shares=true, max_holdings=10） |
| 0.6 | 滑價追蹤 | AA §441 + DEFERRED A-2 | ✅ 2026-03-29（trade log 記錄 signal/fill/shortfall） |
| 0.7 | LT-1 PaperBroker crash + PT-1 precision + PT-6 avg_cost | LIVE+PAPER REVIEW | ✅ 2026-03-29 |
| 0.8 | LT-2 CA 缺失 connect 回 True | LIVE_TRADING_INFRA | ✅ 2026-03-29 |
| 0.9 | LT-5 config.py live mode 驗證 | LIVE_TRADING_INFRA | ✅ 2026-03-29 |
| 0.10 | LT-3,4,6,7,8,9,10,14 實盤 CRITICAL | LIVE_TRADING_INFRA | ✅ 2026-03-29（9/9 CRITICAL 已修） |
| 0.11 | PT-1,3,5,6,8,10,11,12 paper trading | PAPER_TRADING_INFRA | ✅ 2026-03-29 |
| 0.12 | P-1 hedged bear_scale=0.0→0.30 | PAPER_BEHAVIOR_AUDIT | ✅ 2026-03-29 |
| 0.13 | P-2 月度 idempotency 擋整月 | PAPER_BEHAVIOR_AUDIT | ✅ 2026-03-29 |
| 0.14 | AD1 增量價格更新 | DEFERRED A-7 | ✅ 2026-03-29（pipeline 內建 _async_price_update） |
| 0.15 | Pipeline 持久化 portfolio + nav_sod | 發現的新問題 | ✅ 2026-03-29 |
| 0.16 | 初始資金從 config 讀取 | 發現的新問題 | ✅ 2026-03-29（was 硬編碼 10M） |
| 0.17 | PaperBroker 零股最低手續費 1 元 | 發現的新問題 | ✅ 2026-03-29（was 20 元） |
| 0.18 | Auto-deploy 用實際 NAV + 併發 lock | 管線管理 | ✅ 2026-03-29 |
| 0.19 | 主 kill switch 連動停止 auto 策略 | 管線管理 | ✅ 2026-03-29 |
| 0.20 | .env 清理 + .env.example 同步 | 維護 | ✅ 2026-03-29 |
| 0.21 | Discord 通知設定 | PRODUCTION_READINESS §5 | ✅ 2026-03-29 |
| 0.22 | Paper trading dry run 通過 | 驗證 | ✅ 2026-03-29（7 筆零股，NAV=9992，持久化 OK） |

## Phase 1：開盤第一天（3/30）

| # | 項目 | 做法 | 狀態 |
|---|------|------|:----:|
| 1.1 | 啟動 API server | `make dev` | 3/30 |
| 1.2 | 確認 scheduler 啟動 | log 出現 `Scheduler started` | 3/30 |
| 1.3 | 手動觸發首次建倉 | `curl -X POST http://localhost:8000/api/v1/scheduler/trigger/pipeline -H "X-API-Key: dev-key"` | 3/30 |
| 1.4 | 確認 7 筆零股訂單 | 查 `data/paper_trading/trades/` | 3/30 |
| 1.5 | 確認 portfolio_state.json | cash 從 10000 減少，7 positions | 3/30 |
| 1.6 | 確認 Discord 通知 | pipeline 完成後收到通知 | 3/30 |

**預期結果**（dry run 驗證）：

| 指標 | 值 |
|------|------|
| 策略選股 | 10 支 |
| 可執行 | 7 支（3 支高價股跳過） |
| 總投入 | ~5,660 TWD（57%） |
| 手續費 | ~8 TWD（0.15%） |
| 現金餘額 | ~4,330 TWD |

## Phase 2：開盤第一週

| # | 項目 | 來源 | 狀態 |
|---|------|------|:----:|
| 2.1 | ~~AD1 增量數據更新~~ | ~~phase-ad §AD1~~ | ✅ 0.14 已做 |
| 2.2 | 用 2× 成本重跑 Validator（全策略） | QUANT_FUND_COMPARISON §7.1 | ⏳ |
| 2.3 | AG 手動端到端第 3 次 | phase-ag §10 BLOCKING | ⏳ |
| 2.4 | **確認 paper trading 正常後準備微額實盤** | 見 §微額實盤設計 | CA 憑證取得後 |

Phase 2.4 前置條件：
- Phase 1 paper trading 已跑 1 週無異常
- CA 憑證已取得
- Discord 通知已確認能收到
- SinopacBroker simulation=False 手動測過 1 次

## Phase 3：前 30 天（雙軌觀察）

**不寫新代碼。只觀察。**

每日：確認 paper trading NAV 有記錄、Discord 通知正常
每週：計算 paper vs 回測的偏差

30 天後評估：

| 條件 | 動作 |
|------|------|
| 累計虧損 > 10% 或 MDD > 15% | 停止，回到研究 |
| 沒崩潰 | 繼續到 90 天 |

## Phase 4：30-90 天（繼續觀察 + 研究新因子）

並行：
- **4A** 繼續觀察（不動代碼）
- **4B** autoresearch 研究新因子（目標 5+ 獨立方向 L5 因子）
- **4C** 根據實際數據校準成本模型
- **4D** L5 因子部署時的管線管理
- **4E-4F** evaluate.py 診斷改進

### 數據擴充（FinLab 借鑒，2026-03-30 研究）

| # | 數據 | 來源 | 因子用途 | 優先級 |
|---|------|------|---------|:------:|
| D1 | **集保戶股權分散表** | FinMind `TaiwanStockShareholding` / TDCC API | 大戶增持+散戶減少（台股最強籌碼信號） | **高** |
| D2 | **處置股/注意股/全額交割** | 公開資訊觀測站 | 風控過濾（必須排除不可交易股） | **高** |
| D3 | **市值** | close × shares_outstanding（自算） | size neutralization、factor analysis 基礎 | **高** |
| D4 | 內部人持股變化+質押 | 公開資訊觀測站 | 董監減持=負面信號、高質押=風險 | 中 |
| D5 | 借券餘額 | FinMind `TaiwanStockSecuritiesLending` | 做空壓力指標 | 中 |
| D6 | 景氣指標+PMI | FinMind `tw_business_indicators` / `tw_total_pmi` | 總經擇時 | 低 |

### 因子維度擴充

Agent 目前只在 revenue ratio 空間。以下是 FinLab 驗證過的台股因子方向（需要對應數據先到位）：

| 方向 | 因子範例 | 需要數據 | 預期 |
|------|---------|---------|------|
| **籌碼-大戶** | 大戶持股連 3 週增加 + 散戶減少 | D1 集保 | 台股經典信號，和 revenue 不相關 |
| **籌碼-法人** | 三大法人同買、外資買超率 | 已有 institutional | 可立即嘗試（但之前 L1） |
| **營收進階** | 營收創 N 月新高、YoY 連續 > 20% | 已有 revenue | 比純 ratio 更穩健 |
| **估值動量** | PE 動量（PE 在改善中）、PEG | 已有 per_history | 可立即嘗試 |
| **融資融券** | 券資比變化、融券增加 | 已有 margin | 可立即嘗試 |
| **內部人** | 董監增持、低質押率 | D4 | 需要新數據 |

### 評估改進

| # | 項目 | 說明 | 優先級 |
|---|------|------|:------:|
| 4E | **行業中性化 IC 診斷** | demean factor values by industry，IC 下降 → 因子只是在挑產業 | 高 |
| 4F | **IC 趨勢回歸** | `linregress(ic_series)` slope < 0 → 因子衰退。記錄到 output | 高 |
| 4G | **Rebalance 對齊營收公告日** | 月 10 日前公告 → 公告後才 rebalance | 中 |
| 4H | **Size neutralization** | 用 market_value 做 neutralize，確保非 small-cap bias | 中 |

## Phase 5：90 天後（決策點）

| 條件 | 動作 |
|------|------|
| 超額報酬 > 0 且 t-stat > 1.0 | 逐步加碼 |
| 超額 ≤ 0 但一致 | 測試 alpha combining 或換因子 |
| 超額 ≤ 0 且不一致 | 校準成本模型 |
| 超額 ≤ 0 且無新因子 | 接受目前沒有 alpha |

---

## 微額實盤設計

**資金**：1 萬元零股
**策略**：revenue_momentum_hedged（max_holdings=10）
**成本**：零股手續費最低 1 元，每筆 ~1-1.5 TWD

**已驗證的執行路徑**（dry run 2026-03-29）：
```
Config → Strategy(hedged, max_holdings=10) → on_bar(10 targets)
→ weights_to_orders(7/10, lot=1) → risk_check(7/7 pass)
→ PaperBroker.submit(7 filled) → apply_trades → save_portfolio
→ NAV=9992, cash=4329, 7 positions
```

**管線管理**：Auto-deployed 因子和主策略完全隔離。已有：
- PaperDeployer singleton + 併發 lock
- 主 kill switch 連動停止所有 auto 策略
- Auto-deploy 用實際 portfolio NAV（非硬編碼）
- 最多 3 個 auto 策略，各 5% NAV，30 天自動停

---

## 不做的事

| 提議 | 為什麼不做 |
|------|-----------|
| 新的 Phase | 功能已足夠。問題是 alpha 不是功能 |
| 多市場擴展 | 先證明台股有 alpha |
| 更複雜的組合優化 | DeMiguel：equal-weight 就好 |
| 更多 Validator checks | 16 項已夠多 |

---

## 追蹤

本文件是唯一的「接下來做什麼」參考。每週覆核一次。
