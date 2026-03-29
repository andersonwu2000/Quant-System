# IC-Alpha Gap 分析

**日期**：2026-03-30

---

## 問題

110 個 L5 因子全部 Validator 16/17（vs_ew_universe 失敗）。

## 排查結果

**兩個因素疊加：**

1. **Net vs Gross 不公平比較（已修）**：策略 annual_return 扣成本，EW benchmark 不扣 → 已改為 gross vs gross。

2. **EW benchmark 在台股多頭中極強（真實現象）**：200 支等權 2017-2024 年化 **+26.82%**（total +3383%）。策略 gross 需 > 26.82% 才通過。Top-15 集中度在長期多頭中因波動拖累複利，不如 200 支分散。DeMiguel (2009)：等權 1/N 在 14 種最佳化中無一被一致性超越。

**簡化診斷 vs 完整回測的差異**：
- 診斷用 22 季度平均 20d excess（+1.41%）— 短期 snapshot，不受複利影響
- Validator 用 2017-2024 完整回測年化複利 — 多頭中 EW 分散的複利效應極強
- 兩者不矛盾：因子短期有 selection alpha，但長期複利跑不贏高度分散的 EW

## 診斷數據（revenue ratio，22 季度 2020-2025）

- Dispersion 10.6%（充足）、Sector 13/15 非半導體（不是產業曝險）
- Q5 excess vs EW: +1.34%/20d — 因子有短期選股能力
- Monotonicity 0.50 — 頂端有效但中間噪音
- Score-tilt Sharpe 3.33 vs top-15 EW 3.00（+11%），但 excess 差距小（+0.08%）

注意：以上僅針對 revenue ratio。

## PBO

N=1 cluster（113 clone），CSCV 無意義。替代：Permutation ✅、DSR ⚠️（K 需校準）、WFE ⚠️、OOS decay ✅、Paper Trading ⏳。

## Agent 反饋信號

| 信號 | 做什麼 | Agent 看到 | 防過擬合 |
|------|--------|-----------|---------|
| L5b excess_return | top quintile > universe | **pass/fail only** | 不洩漏量級 |
| L5c monotonicity | 分位單調性 > 0.5 | **pass/fail only** | 不洩漏值 |
| novelty indicator | max corr with existing | **bucketed: high/moderate/low** | 不洩漏精確 corr |

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

**已完成：** 新數據 ✅、returns dedup ✅、PBO 修復 ✅、診斷 ✅、score-tilt 測試 ✅、vs_ew_universe gross 修復 ✅

**不做：** 不降門檻、不量化多樣化為分數、不限制方向。

以上診斷和測試針對 revenue ratio。其他因子可能有不同特性。應優先做對所有因子有效的結構性改進。

## 參考

Bailey (2014) PBO/DSR、Clarke (2002) TC、DeMiguel (2009) 1/N、Harvey (2016) multiple testing、MSCI (2019) TC 實測、AQR (2023) fact/fiction。
