# IC-Alpha Gap 分析

**日期**：2026-03-30

---

## 問題

110 個 L5 因子全部 Validator 16/17（vs_ew_universe 失敗）。因子能排名但 top-15 等權跑輸大盤。

根因：TC 損耗。`E(R) = TC × IC × √BR × σ`，top-15 等權 TC ≈ 0.10（MSCI 2019）。等權 benchmark 有 +2.5-4%/年內建 premium。

## 診斷（revenue ratio，22 季度 2020-2025）

- Dispersion 10.6%（充足）、Sector 13/15 非半導體（不是產業曝險）
- **Q5 excess vs EW: +1.34%/20d** — top quintile 打敗大盤，因子有效
- Monotonicity 0.50 — 頂端有效但中間噪音
- Score-tilt Sharpe +11%（3.33 vs 3.00），但 excess 差距小（+0.08%）
- **所有建構方式（含 top-15 EW）都贏大盤** — Validator 不通過原因待查

注意：以上僅針對 revenue ratio。其他因子可能有不同特性。

## PBO

N=1 cluster（113 clone），CSCV 無意義。替代：Permutation ✅、DSR ⚠️（K 需校準）、WFE ⚠️、OOS decay ✅、Paper Trading ⏳。

## Agent 反饋信號

| 信號 | 做什麼 | 引導行為 |
|------|--------|---------|
| L5b excess_return | top quintile > universe | 營利 |
| L5c monotonicity | 分位單調性 > 0.5 | 頂端有效 |
| novelty indicator | bucketed corr | 多樣化 |

不在 program.md 限制方向。代碼 gate 比文字引導可靠。

## 待做

**結構性（所有因子受益）：**

| # | 項目 | 優先級 |
|---|------|:------:|
| 1 | evaluate.py 加 L5b/L5c gate | **高** |
| 2 | evaluate.py 加 novelty indicator | **高** |
| 3 | program.md 加 TC 概念 | **高** |
| 4 | evaluate.py construction → quintile/score-tilt | 高 |
| 5 | watchdog PBO fallback → DSR | 中 |

**Factor-specific：** Validator 差異排查（中）、Cross-Market（低）

**已完成：** 新數據 ✅、returns dedup ✅、PBO 修復 ✅、診斷 ✅、score-tilt 測試 ✅

**不做：** 不降門檻、不量化多樣化為分數、不限制方向。

## 參考

Bailey (2014) PBO/DSR、Clarke (2002) TC、DeMiguel (2009) 1/N、Harvey (2016) multiple testing、MSCI (2019) TC 實測、AQR (2023) fact/fiction。
