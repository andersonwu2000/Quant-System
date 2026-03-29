# IC-Alpha Gap 分析

**日期**：2026-03-30

---

## 問題

110 個 L5 因子全部 Validator 16/17（vs_ew_universe 失敗）。

## 排查結果

1. **Net vs Gross 不公平比較（已修）**：策略 net vs EW gross → 改為 gross vs gross。
2. **EW benchmark 在台股多頭中極強（真實現象）**：200 支等權 2017-2024 年化 +26.82%。策略 gross ≈ 20-25%，即使修了 #1 仍不通過。
3. **Top-15 等權的結構性劣勢**：
   - Variance drag：15 支波動 >> 200 支 → 複利損失 ≈ σ²/2 ≈ 2-3%/年
   - TC ≈ 0.10：因子信號幾乎沒有傳遞到 portfolio
4. **因子本身有效**：Q5 excess vs EW +1.34%/20d，sector 分散（13/15 非半導體）。問題在 construction 不在因子。

**結論：不降門檻。跑不贏「買全部等權」就不該部署。改 construction。**

## 診斷數據（revenue ratio，22 季度 2020-2025）

- Dispersion 10.6%（充足）、Monotonicity 0.50（頂端有效）
- Score-tilt Sharpe 3.33 vs top-15 EW 3.00（+11%），excess 差距小（+0.08%）
- DeMiguel (2009)：等權 1/N 極難被打敗，需改 construction 而非降標準

## PBO

N=1 cluster（113 clone），CSCV 無意義。替代驗證：Permutation ✅、DSR ⚠️、WFE ⚠️、OOS decay ✅、Paper Trading ⏳。

## Agent 反饋信號

| 信號 | Agent 看到 | 防過擬合 |
|------|-----------|---------|
| L5b excess_return（top quintile > universe） | pass/fail only | 不洩漏量級 |
| L5c monotonicity（分位單調性 > 0.5） | pass/fail only | 不洩漏值 |
| novelty indicator（max corr with existing） | bucketed: high/moderate/low | 不洩漏精確 corr |

不在 program.md 限制方向。代碼 gate 比文字引導可靠。

## 待做

| # | 項目 | 優先級 | 理由 |
|---|------|:------:|------|
| 1 | **Construction 改進**：top-15 EW → top-40 score-tilt | **最高** | 直接解決 vs_ew_universe（降 variance drag + 提高 TC） |
| 2 | evaluate.py 加 L5b/L5c gate | 高 | 早期篩選，減少 Validator 浪費時間 |
| 3 | evaluate.py 加 novelty indicator | 高 | 引導 agent 探索新方向 |
| 4 | program.md 加 TC 概念 | 高 | 文字引導 |
| 5 | watchdog PBO fallback → DSR | 中 | |

**已完成：**
- [x] 新數據（per_history 472, margin 220）
- [x] Returns dedup 擋 clone
- [x] PBO read-only 修復
- [x] 診斷分析（dispersion + quintile + sector）
- [x] Score-tilt 測試（獨立腳本，未整合到 evaluate.py）
- [x] vs_ew_universe gross 修復（代碼已部署）
- [ ] **重跑 Validator 確認 gross 修復後的結果** ← 下一步

**不做：** 不降 vs_ew_universe 門檻、不改為 soft fail、不量化多樣化為分數、不限制方向。

以上診斷針對 revenue ratio。應優先做對所有因子有效的結構性改進。

## 參考

Bailey (2014) PBO/DSR、Clarke (2002) TC、DeMiguel (2009) 1/N、Harvey (2016) multiple testing、MSCI (2019) TC 實測、AQR (2023) fact/fiction。
