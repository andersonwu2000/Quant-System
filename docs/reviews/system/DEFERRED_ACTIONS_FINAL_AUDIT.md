# 「到時候再說」最終清查

**日期**：2026-03-29
**目的**：找出所有開發計畫中的「延後」項目，判斷哪些會在實盤前卡住你
**目標**：放行 CA 憑證後系統能直接運作，不需要臨時補功能

---

## 結果分類

### A. 真正的「到時候再說」— 必須在 paper trading 階段解決

| # | 位置 | 問題 | 為什麼不能等 | 工作量 | 狀態 |
|---|------|------|-------------|:------:|:----:|
| A-1 | AA §4.7 | Lot size 感知（標「⏸ Phase 3」） | 零股實盤 1 萬元就會遇到。1 股 ≠ 權重 5% | ~20 行 | ✅ 2026-03-29 — `fractional_shares=True`，lot_size=1，weights_to_orders 正確處理零股。pipeline 有 warning 當 orders < targets |
| A-2 | AA §441 | 無實盤 vs 回測滑價追蹤（標「P2」） | 微額實盤第一天就需要比較 fill price vs signal price | ~15 行 | ⏳ 阻塞微額實盤（不阻塞 paper trading） |
| A-3 | AB §601 | R-02 不同因子 returns 可比性未驗證（標「6 個月了一直沒跑 pilot」） | PBO 的核心假設。factor_returns 重新累積時就該驗證 | 1 小時 | ⏳ factor_returns 還在累積 |
| A-4 | AB §V-2/V-3 | evaluate.py docstring 過時 + Bailey 引用缺失 | 下一個改 evaluate.py 的人（或 AI）會被 docstring 誤導 | 5 行 | ✅ 2026-03-29 — L1082 "Only L3+", L1086 Bailey 引用已在 |
| A-5 | AF §150 | clone 復活問題「如果未來發現 → 再加回 historical dedup」 | 沒有監控機制知道「已經發生了」。需要 L3 pass rate 追蹤 | ~10 行 | ⏳ |
| A-6 | AF §112 | 1.3× ICIR 門檻「後續用數據校準」 | 沒定義什麼時候校準、用什麼數據、門檻怎麼調 | 定義 trigger | ⏳ |
| A-7 | AD 全部 | 數據管線 0% 完成 | 每天手動 `download_yahoo_prices.py` 不可持續。忘記更新 = 用過時數據決策 | ~100 行 | ✅ 2026-03-29 — pipeline 內建增量價格更新（`_async_price_update`），每次觸發時自動更新過時的 parquet |
| A-8 | AH §40 | Regime chart "TBD"（2 個月前就標了） | 不阻塞但一直拖。Phase AH Step 2 規劃了但沒排時間 | 2 小時 | ⏳ |

### B. 合理的分階段 — 有明確觸發條件，不是「到時候再說」

| # | 位置 | 項目 | 觸發條件 | 判定 |
|---|------|------|---------|:----:|
| B-1 | AA §4.4-4.5 | construction.py / risk_parity 整合 | DeMiguel 否定了，不做 | ✅ 正確延後 |
| B-2 | AA §4.8 | Signal-driven rebalance | 月度夠用 | ✅ 正確延後 |
| B-3 | AB Phase 2-3 | Factor-Level PBO | 已完成 | ✅ 已做 |
| B-4 | AD Phase 2-3 | Quality Gate + 排程 | AD1 先做，AD2/3 等 paper 穩定 | ✅ 合理 |
| B-5 | AG Phase 3 | 人工決定替換主策略 | 90 天 paper 後 | ✅ 正確 |
| B-6 | AH Step 2-4 | 圖表 + Research + Orders 頁面 | 有數據後才有意義 | ✅ 合理 |
| B-7 | AF §162 | max_holdings 8 vs 15 vs 20 測試 | 獨立實驗 | ✅ 合理 |
| B-8 | AE §860 | eval_server 收緊為只回 pass/fail | 如果 agent 做 adaptive opt | ✅ 有觸發條件 |

### C. 已解決或不適用

| # | 位置 | 項目 | 狀態 |
|---|------|------|:----:|
| C-1 | AA Phase 2 inverse-vol | 已改為 equal-weight | ✅ |
| C-2 | AB Phase 1-3 | 全部完成 | ✅ |
| C-3 | AC 全部 | 全部完成 | ✅ |
| C-4 | AE 全部 | 全部完成 | ✅ |
| C-5 | AF 全部 | 全部完成 | ✅ |
| C-6 | AG BLOCKING 條件 | 5/5 解決 | ✅ |

---

## A 類問題的解決計畫

### A-1：Lot size 感知 → ✅ 已解決

`fractional_shares=True`（.env），`_get_lot_size()` 回傳 1（零股模式）。weights_to_orders 用 `int(qty)` 取整。pipeline 在 orders < targets 時發出 warning。PaperBroker 零股手續費最低 1 元（已修）。max_holdings 從 15 降為 10（via `active_strategy_params`），資金利用率 40%→57%。

### A-2：滑價追蹤 → Trading 頁面的一部分

Phase AH Trading 頁面的 Execution Metrics 已規劃了 slippage 顯示。需要後端記錄 `signal_price`（策略計算時的價格）和 `fill_price`（實際成交價格），計算 implementation shortfall。

### A-3：R-02 PBO 可比性 pilot → Phase 4B 的第一步

factor_returns 重新累積到 20+ 個後：
1. 取 5 個不同方向的因子 returns
2. 檢查分佈特性（波動率差異、偏態、峰態）
3. 跑一次 PBO，確認結果 sensible（不是 0.0 或 1.0）
4. 記錄到研究報告

### A-4：evaluate.py docstring → ✅ 已正確

驗證結果：L1082 已寫 "Only called for L3+ factors"，L1086 已有 Bailey (2014) 引用。不需要修改。

### A-5：clone 復活監控 → 加入 watchdog

watchdog 每次跑 Factor-Level PBO 時，順便記錄 L3 pass rate。如果替換後 L3 pass rate 突增 > 50% → 警告。

### A-6：1.3× ICIR 校準 trigger → 定義明確

校準時機：當 replacement_count >= 5（累積 5 次替換經驗後）。
校準方法：計算 5 次替換中，被替換因子的 OOS 表現 vs 替換因子的 OOS 表現。如果替換後 OOS 沒改善 → 提高門檻到 1.5×。

### A-7：AD1 數據更新 → Phase 2.1（已在 NEXT_ACTIONS）

已排進 Phase 2，~100 行。是 paper trading 持續運行的前置條件。

### A-8：Regime chart → Phase AH Step 2

已規劃在有 30 天數據後做。不阻塞但要確保不再拖。

---

## 「放行 CA 憑證後能直接運作」的 checklist

以下全部完成 → 拿到 CA 憑證後只需要：
1. `.env` 加 `QUANT_SINOPAC_CA_PATH=./Sinopac.pfx`
2. `SinopacBroker(simulation=False)` 測試 1 股
3. 啟動微額實盤

| # | 項目 | 狀態 | 阻塞實盤？ |
|---|------|:----:|:---------:|
| Paper trading 已跑 1 週 | ⏳ 3/30 啟動 | **YES** |
| 通知告警已設定 | ⏳ | **YES** |
| A-1 Lot size 感知 | ✅ fractional_shares=True | ~~YES~~ 已解決 |
| A-2 滑價追蹤 | ⏳ | **YES**（否則不知道成本模型準不準） |
| A-7 AD1 數據自動更新 | ⏳ | **YES**（手動更新不可持續） |
| A-4 evaluate.py docstring | ✅ 已正確 | NO |
| A-3 PBO pilot | ⏳ | NO（factor_returns 還沒累積夠） |
| A-5 clone 復活監控 | ⏳ | NO（還沒有替換發生） |
| A-6 ICIR 校準 trigger | ⏳ | NO（還沒有 5 次替換） |
| A-8 Regime chart | ⏳ | NO |

**1 個 YES 項目（A-2 滑價追蹤）必須在微額實盤前完成。** 加上 paper trading 1 週 + 通知設定 = 3 個前置條件。

2026-03-29 額外修復（不在原清單但影響 paper trading）：
- PaperBroker 零股最低手續費 1 元（was 20 元）✅
- Pipeline 執行後持久化 portfolio state（防 crash 丟持倉）✅
- 初始資金從 config 讀取（was 硬編碼 10M）✅
- 再平衡後更新 nav_sod（kill switch 基準）✅
- Auto-deploy 用實際 NAV（was 硬編碼 10M）✅
- 主 kill switch 連動停止所有 auto 策略 ✅
- 6 個 FULL_SYSTEM code review 修復（H-1~H-6, M-09）✅
- Validator 2× 成本安全邊際 check ✅
