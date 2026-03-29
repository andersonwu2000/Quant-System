# Phase AA-AG 執行差距審計 + 策略生成方法合理性檢討

**日期**：2026-03-29
**範圍**：7 個計畫的執行狀態 + revenue_momentum 策略生成流程

---

## Part 1: AA-AG 執行差距

### 快速狀態

| Phase | 標記 | 實際 | 差距 |
|-------|:----:|:----:|------|
| AA | ✅ Phase 1 | Phase 1 完成，Phase 2 未做 | **Phase 2 全部延後** |
| AB | ✅ 完成 | Phase 1-3 + AB-4 完成 | 無（但 factor_returns 歸零，需重新累積） |
| AC | ✅ 完成 | 完成 | 無 |
| AD | 📋 待開發 | **0% 完成** | **全部未做** |
| AE | ✅ 完成 | 完成 | H-1（strategies/ mount）、H-2（work/ ro）待修 |
| AF | ✅ 完成 | 完成 | AF-H1（learnings 洩漏精確 ICIR in host mode）待修 |
| AG | 🟡 代碼完成 | Steps 1-6 完成，BLOCKING 全解 | 等 L5 因子產出後啟動 |

### 應該執行但未執行的項目

**1. Phase AA Phase 2（組合最佳化接入）**

AA Phase 1 發現 inverse-vol weighting 讓 PBO 惡化（0.702→0.910），結論是「DeMiguel (2009) 正確，equal-weight 最好」。但 Phase 2 的其他項目不是 inverse-vol：

| AA Phase 2 項目 | 說明 | 該做嗎？ |
|----------------|------|:--------:|
| 4.3 Top-n 15→25 | 擴大持倉分散風險 | ⏸ 先看 FinLab「8 檔集中更好」的結論 |
| 4.4 construction.py 整合 | 把 cost-aware 建構接入 on_bar | ❌ equal-weight 就夠 |
| 4.5 risk_parity 模組 | 已修（B-4），但 AA 結論是不用 | ❌ |
| 4.7 Lot size awareness | 1000 股整數化 | ⚠️ **應做** — 現在權重 5% 但實際可能買 1 張 = 7% |
| 4.8 Signal-driven rebalance | 營收公布 T+1 再平衡 | ⏸ 月度夠用 |

**結論**：AA Phase 2 中只有 **4.7 Lot size awareness** 值得做。其餘被 DeMiguel 結論和實驗結果否定了。

**2. Phase AD（數據管線）— 完全未做**

AD 被識別為 paper trading 的前置條件，但一行代碼都沒寫。

| AD 階段 | 說明 | 阻塞什麼 |
|---------|------|---------|
| AD1 增量更新 | 每日追加新 bar | paper trading 數據新鮮度 |
| AD2 Quality Gate | 開盤前 4 層驗證 | 防止用過時數據下單 |
| AD3 排程整合 | 08:00 刷新→08:20 gate→09:00 下單 | 自動化 paper trading |

**目前的 workaround**：手動跑 `python scripts/download_yahoo_prices.py`。對放假期間不影響，但開盤後必須解決。

**建議**：AD1（增量更新）是最小可行改進。~100 行代碼。AD2/AD3 可以後做。

**3. Phase AG — 設計完成但無法啟動**

AG 的 5 個 BLOCKING 條件：

| 條件 | 狀態 | 說明 |
|------|:----:|------|
| AB-4 完成 | ✅ | PBO 修正完成 |
| PaperDeployer 驗證 | ❌ | 死代碼，需要手動跑通 |
| 手動端到端 3 次 | ❌ | 沒做過 |
| 決策標準定義 | ✅ | §11 已定義 30天→90天 |
| Validator 職責定義 | ✅ | watchdog 唯一驗證 |

**AG 目前不能啟動。** 差的是「手動跑通」— 需要在開盤後手動提交一個因子走完全流程。

---

## Part 2: revenue_acceleration → revenue_momentum_hedged 的生成方法

### 流程分析

```
因子研究                        策略生成                        交易執行
autoresearch                  revenue_momentum.py             execute_pipeline
  │                               │                               │
  │ compute_factor()              │ on_bar()                      │
  │ → revenue acceleration        │ → 5 項篩選                    │
  │   (3M/12M 比率)               │ → top-15 by acceleration      │
  │                               │ → signal_weight()             │
  │ IC/ICIR 評估                  │ → regime hedge                │
  │ L1-L5 驗證                    │                               │
  ▼                               ▼                               ▼
factor.py 的因子           strategies/ 的策略             jobs.py 的管線
（只有因子值）             （篩選+排序+權重+regime）     （下單+風控）
```

### 問題 1（HIGH）：autoresearch 的因子和實際策略用的不是同一個東西

**autoresearch 的 evaluate.py 測的是**：
- `compute_factor(symbols, as_of, data)` → 回傳 `{symbol: factor_value}`
- IC = Spearman(factor_values, forward_20d_returns)
- 等權 top-15 portfolio 的日報酬

**revenue_momentum.py 實際做的是**：
- 5 項篩選條件（流動性、MA60、60 日漲幅、營收加速、YoY）
- 按 acceleration 排序取 top-15
- signal_weight 正規化（非等權）
- regime hedge（空頭縮倉 30%）

**差異**：

| 維度 | autoresearch 評估 | 實際策略 | 一致嗎？ |
|------|-------------------|---------|:--------:|
| 選股邏輯 | 只看因子值排名 top-15 | 先篩選（5 項）再排名 | ❌ |
| 權重方式 | 等權 | signal_weight | ❌ |
| Regime hedge | 無 | bear → 30% 倉位 | ❌ |
| 流動性篩選 | 無（在 evaluate.py 的 universe 層級） | 300 張/日門檻 | ⚠️ |
| 趨勢確認 | 無 | MA60 + 60 日漲幅 | ❌ |

**這意味著**：autoresearch 驗證的因子（revenue acceleration 的 IC/ICIR），和實際交易的策略（revenue_momentum 的 5 項篩選 + signal_weight + regime hedge）**是不同的東西**。

IC 0.476 是「acceleration 排名和未來回報的相關性」。但實際策略加了 4 項額外篩選，可能改善也可能惡化這個 IC。Regime hedge 更是完全獨立的邏輯。

**Validator 驗證的也是實際策略（revenue_momentum），不是純因子。** 所以 Validator 的 Sharpe 0.94 是策略的，不是因子的。但 autoresearch 的 L1-L5 是因子的，不是策略的。**兩套評估體系測的是不同的東西。**

### 問題 2（HIGH → ✅ 已修）：strategy_builder 的 inverse-vol 權重和 AA 的結論矛盾

~~`strategy_builder.py` 用 inverse-vol weighting，和 AA 的結論及 evaluate.py 的等權不一致。~~

**已修復**：`strategy_builder.py:157-162` 改為 `raw_weights[sym] = 1.0`（equal-weight），註解引用 DeMiguel (2009)。

### 問題 3（CRITICAL — 已驗證）：regime hedge 是死代碼

**驗證結果**：用修正後的代碼重跑，no-hedge 和 with-hedge 的結果**完全相同**。

**根因**：0050.TW（市場 proxy）不在回測 universe → `ctx.bars("0050.TW")` 拋異常 → `_market_regime()` catch exception return "bull" → hedge 永遠不觸發。

**影響**：
1. Phase M 的「hedge 虧錢」結論無效 — hedge 從未觸發
2. `enable_regime_hedge=True` 是預設開啟的死代碼
3. 舊數字 +10.8%（no-hedge）vs -7.4%（hedge）的差異不是來自 hedge，是來自其他參數

**更嚴重的發現**（重跑結果）：
- CAGR 只有 **+4.37%**（舊 +10.8%，縮水 60%）
- **vs_ew_universe = -4.59%** — 跑輸等權大盤，沒有選股 alpha
- OOS Sharpe = **-1.355** — 嚴重虧損

### 問題 4（MEDIUM）：月度再平衡沒有 no-trade zone

Phase AA 曾報告 no-trade zone 改善了 +1.3% CAGR，但這個數字是用舊代碼跑的（STALE_CONCLUSIONS_AUDIT 已標記為不可信）。`revenue_momentum.py` 目前沒有 no-trade zone — 每月無條件再平衡所有持倉。效果需要用修正後的代碼重新驗證。

### 問題 5（LOW）：_revenue_cache 永不過期

`_revenue_cache` 是全域變數，程式啟動時載入一次，之後永遠不更新。長期運行時（paper trading 連續跑數月），營收數據會過時。Phase AF §2.1 已規劃但尚未修復。

---

## Part 3: 建議

### 立即修復（開盤前）

| # | 項目 | 工作量 | 理由 |
|---|------|:------:|------|
| 1 | ~~strategy_builder.py 改為 equal_weight~~ | ~~5 行~~ | ✅ **已修** — `raw_weights[sym] = 1.0` |
| 2 | ~~修復 regime hedge 或移除~~ | ~~5 行~~ | ✅ **已修** — `enable_regime_hedge=False` 預設關閉 |

**注意**：建議 #2 的理由不再是「Phase M 證明 hedge 虧錢」（該結論已被推翻 — hedge 從未觸發）。理由改為「hedge 是死代碼，開著沒意義」。如果修復 0050 進 feed 後，hedge 的效果需要重新驗證。

### 可執行的改進計畫

| # | 項目 | 改什麼 | 工作量 | 狀態 |
|---|------|--------|:------:|:----:|
| 3 | AD1 增量數據更新 | 新增 `src/data/refresh.py` | ~100 行 | ⏳ 開盤後 |
| 4 | ~~PaperDeployer 手動跑通~~ | — | — | ✅ 已完成 |
| 5 | AA 4.7 Lot size awareness | `strategy_builder.py` + `revenue_momentum.py` 加整張 rounding | ~20 行 | ⏳ |
| 6a | Validator report 標註實際 IS 期間 | `validator.py` validate() 在 report 中記錄截斷後的 start/end | ~5 行 | 🔧 現在做 |
| 6b | Validator report 標註 universe 大小 | 已有 universe_size check，確認和實際一致 | 0 行 | ✅ 已有 |

#### #6a 詳細計畫：Validator 標註實際 IS 期間

**問題**：V8 fix 靜默截斷 `end` 到 `oos_start - 1`，外部不知道 Validator 實際跑了什麼期間。導致 CAGR 12.83%（IS only）被誤以為是全期間結果。

**改法**：validate() 截斷後把實際 start/end 寫進 report：

```python
# validator.py validate() 中，V8 截斷後加：
report.actual_is_start = start
report.actual_is_end = end  # 截斷後的值
```

**檔案**：`src/backtest/validator.py`（加 2 行）+ `ValidationReport` dataclass 加 2 個欄位
