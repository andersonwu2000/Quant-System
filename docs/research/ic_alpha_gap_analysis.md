# IC-Alpha Gap 分析

**日期**：2026-03-30

---

## 問題

L5 因子全部 Validator vs_ew_universe 失敗。

## 排查結果

1. **Net vs Gross 不公平比較（已修）**：策略 net vs EW gross → 改為 gross vs gross。修後仍不通過。
2. **EW benchmark 在台股多頭中極強**：200 支等權 2017-2024 年化 +26.82%。策略 gross ≈ 20-25%。
3. **Top-15 等權結構劣勢**：variance drag ≈ 2-3%/年 + TC ≈ 0.10。
4. **因子本身有效**：Q5 excess +1.34%/20d，13/15 非半導體。問題在 construction + 評估方式。
5. **vs_ew_universe 用固定全期間（regime bias）**：2017-2024 幾乎全多頭 → EW 佔優。應改為 walk-forward 評估。

**結論：不降門檻。改 construction + 改 vs_ew_universe 為 walk-forward。**

## vs_ew_universe 評估方式問題

目前：固定 IS 全期間（2017-2024）算一個 excess return → regime bias 嚴重。

應改為：**在每個 walk-forward window 分別算 excess return，通過條件 = 多數 window excess > 0。**
- Validator 已有 walk-forward 機制（temporal_consistency #6），vs_ew_universe (#7) 應共用
- 多頭 window 輸 EW → 可接受（EW 分散化在多頭本就強）
- 空頭/盤整 window 贏 EW → 策略有防禦性 alpha
- 結構性改進，對所有因子有效，消除 regime bias

## PBO

N=1 cluster（dedup 修復前累積的 clone）。**暫時狀態**，因子庫多樣化後自然恢復。

過渡期已有 3 層過擬合防護：Permutation ✅、OOS decay ✅、WF temporal_consistency ✅。Paper Trading ⏳。

## Agent 反饋信號

| 信號 | Agent 看到 | 防過擬合 |
|------|-----------|---------|
| L5b excess_return（top quintile > universe） | pass/fail only | 不洩漏量級 |
| L5c monotonicity（分位單調性 > 0.5） | pass/fail only | 不洩漏值 |
| novelty indicator（max corr with existing） | bucketed: high/moderate/low | 不洩漏精確 corr |

代碼 gate 比文字引導可靠。program.md 提供**事實**（可用數據、TC 概念），不規定方向。

## 待做

| # | 項目 | 優先級 | 理由 |
|---|------|:------:|------|
| 1 | **Construction**：top-15 EW → top-40 score-tilt | **最高** | 結構性改善 TC 0.10 → 0.45，降 variance drag |
| 2 | **vs_ew_universe 改 walk-forward** | **最高** | 消除 regime bias，和 temporal_consistency 共用 WF window |
| 3 | evaluate.py 加 L5b/L5c gate | 高 | 早期篩選，給 agent 營利反饋 |
| 4 | evaluate.py 加 novelty indicator | 高 | 引導 agent 探索多方向 |
| 5 | program.md 更新（可用數據 + TC 概念） | 高 | 事實告知 |
| ~~6~~ | ~~watchdog PBO fallback → DSR~~ | ~~中~~ | 移除 — 已有 3 層過擬合防護（permutation + OOS + WF），過渡期短，不值得為此寫代碼 |

**不做：** 不降門檻、不改為 soft fail、不量化多樣化為分數、不限制方向。

**Validator 重跑結果（gross 修復後）**：仍 16/17。策略 gross ≈ 20-25%，EW gross = 26.82%。差距 ~5% 來自 top-15 的 variance drag + TC 損耗 — 確認是 construction 問題，非 bug。

以上診斷針對 revenue ratio。應優先做對所有因子有效的結構性改進。

## 參考

Bailey (2014) PBO/DSR、Clarke (2002) TC、DeMiguel (2009) 1/N、Harvey (2016) multiple testing、MSCI (2019) TC 實測、AQR (2023) fact/fiction。
