# IC-Alpha Gap 分析

**日期**：2026-03-30

---

## 問題

L5 因子全部 Validator vs_ew_universe 失敗。

## 排查結果

1. **Net vs Gross 不公平比較**：策略 net vs EW gross → 改為 gross vs gross。修後仍不通過。
2. **EW benchmark 在台股多頭中極強**：200 支等權 2017-2024 年化 +26.82%。策略 gross ≈ 20-25%。
3. **Top-15 等權結構劣勢**：variance drag ≈ 2-3%/年 + TC ≈ 0.10。
4. **vs_ew_universe 用固定全期間**：2017-2024 幾乎全多頭 → regime bias。
5. **因子本身有效**：Q5 excess +1.34%/20d，13/15 非半導體。問題在 construction + 評估方式。

**結論：不降門檻。改 construction + 改 vs_ew_universe 為 walk-forward。**

## PBO

N=1 cluster（暫時狀態，dedup 修復前累積的 clone）。已有 3 層過擬合防護：Permutation ✅、OOS ✅、WF ✅。Paper Trading ⏳。

## Agent 評估目標

**profitability**（選股是否跑贏大盤）+ **novelty**（和現有因子庫的差異）。ICIR 是門檻（L2 gate）不是目標。

| 信號 | Agent 看到 | 防過擬合 |
|------|-----------|---------|
| L5b profitability | pass/fail only | 不洩漏量級 |
| L5c monotonicity | pass/fail only | 不洩漏值 |
| novelty indicator | bucketed: high/moderate/low | 不洩漏精確 corr |

## 施做狀態

| # | 項目 | 狀態 |
|---|------|:----:|
| 1 | Construction: top-15 EW → top-40 score-tilt | ✅ evaluate.py + vectorized.py |
| 2 | vs_ew_universe 改 walk-forward（≥50% windows positive） | ✅ validator.py |
| 3 | L5b profitability + L5c monotonicity gate | ✅ evaluate.py |
| 4 | Novelty indicator（bucketed corr） | ✅ evaluate.py output |
| 5 | program.md 更新（評估維度 + 可用數據） | ⏳ 等確認 gate 運作後 |

**不做：** 不降門檻、不改為 soft fail、不量化多樣化為分數、不限制方向。

以上診斷針對 revenue ratio。所有修改為結構性改進，對所有因子有效。

## 參考

Bailey (2014) PBO/DSR、Clarke (2002) TC、DeMiguel (2009) 1/N、MSCI (2019) TC 實測、AQR (2023) fact/fiction。
