# IC-Alpha Gap 分析

**日期**：2026-03-30

---

## 問題

L5 因子全部 Validator vs_ew_universe 失敗。因子有選股能力（Q5 excess +1.34%/20d），但 top-15 等權跑不贏 200 支等權（+26.82%/年）。

**原因**：top-15 等權的 variance drag（σ²/2 ≈ 2-3%/年）+ TC ≈ 0.10。Gross 修復後仍不通過 — EW benchmark 在台股多頭中真的很強。

**結論**：不降門檻，改 construction。跑不贏「買全部等權」就不該部署。

## PBO

N=1 cluster，CSCV 無意義。替代：Permutation ✅、DSR ⚠️、WFE ⚠️、OOS ✅、Paper Trading ⏳。

## 待做

| # | 項目 | 優先級 |
|---|------|:------:|
| 1 | **Construction：top-15 EW → top-40 score-tilt** | **最高** |
| 2 | evaluate.py 加 L5b/L5c gate（pass/fail only） | 高 |
| 3 | evaluate.py 加 novelty indicator（bucketed corr） | 高 |
| 4 | program.md 加 TC 概念 | 高 |
| 5 | watchdog PBO fallback → DSR | 中 |

## 參考

Clarke (2002) TC、DeMiguel (2009) 1/N、MSCI (2019) TC 實測、Bailey (2014) PBO/DSR、AQR (2023) fact/fiction。
