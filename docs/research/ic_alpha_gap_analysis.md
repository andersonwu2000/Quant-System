# IC-Alpha Gap 分析

**日期**：2026-03-30
**觸發**：110 個 L5 因子全部 Validator 16/17（vs_ew_universe 失敗）

---

## 問題

因子能正確排名股票（IC/ICIR 通過 L5），但 top-15 等權跑輸 200 支等權。

**根因**：Transfer Coefficient 損耗。Grinold 基本法則 `E(R) = TC × IC × √BR × σ`，top-15 等權的 TC ≈ 0.10（MSCI 2019 實測）。ICIR 0.30 × TC 0.10 = 有效 ICIR 0.03 — 不可能打敗任何 benchmark。

**等權 benchmark 的內建 premium**：size +1.5-2.5%、rebalancing +0.5-1.0%、value +0.5%，合計 +2.5-4.0%/年。Top-15 要先 cover 這個才能打平。DeMiguel (2009)：等權 1/N 在 14 種最佳化中無一被一致性超越。

## PBO 不可算

只有 1 個 independent cluster（revenue ratio 113 個 clone）。Bailey CSCV 在 N=1 時無意義。

**替代驗證堆疊**（通過 1-4 有合理信心可小規模部署）：

| Level | 方法 | 我們的狀態 |
|:-----:|------|:----------:|
| 1 | Permutation Test p < 0.10 | ✅ |
| 2 | DSR with correct K | ⚠️ K 需校準 |
| 3 | Walk-Forward Efficiency > 0.5 | ⚠️ 有 WF 沒算 WFE |
| 4 | OOS/IS Sharpe > 0.4 | ✅ |
| 5 | Cross-Market Validation | ❌ |
| 6 | Paper Trading 3+ months | ⏳ 3/30 啟動 |

## Agent 優化目標

現狀：agent 優化 IC/ICIR（L5），不知道 portfolio 不賺錢。110 個 L5 "keep" → 以為方向正確 → 繼續產 clone。

**雙重目標**（不矛盾）：

- **A. 營利**：evaluate.py 加 excess_return gate → agent 看到 fail 才知道要調整
- **B. 多樣化**：evaluate.py 加 novelty indicator → agent 看到新方向的正向回饋

**三個反饋信號（代碼層，比文字引導可靠）：**

| 信號 | 做什麼 | 引導什麼行為 |
|------|--------|------------|
| L5b excess_return | top quintile 月報酬 > universe 月報酬 | 找真正能盈利的因子 |
| L5c monotonicity | 分位報酬單調性 Spearman > 0.5 | 信號在頂端有效不只是中間 |
| novelty indicator | bucketed corr: high/moderate/low | 往新方向深入探索 |

**不在 program.md 說 revenue 飽和** — revenue 方向仍有潛力（sector-neutral revenue、revenue × momentum 交互項）。excess_return gate 會自然過濾無效變體。

## 待做

| # | 項目 | 優先級 |
|---|------|:------:|
| 1 | evaluate.py 加 L5b excess_return gate | **高** |
| 2 | evaluate.py 加 novelty indicator（bucketed corr） | **高** |
| 3 | program.md 更新（新數據 + TC 概念，不限制方向） | 高 |
| 4 | 診斷：quintile monotonicity + sector concentration | 中 |
| 5 | 測試 score-tilt（TC 0.10 → 0.45） | 中 |
| 6 | watchdog PBO fallback 到 DSR | 中 |
| 7 | Cross-Market Validation（韓/日） | 低 |

**已完成：**
- [x] 新數據（per_history 472 支, margin 220 支）✅ 2026-03-30
- [x] Returns dedup 擋 clone ✅ 2026-03-29
- [x] PBO read-only bug 修復 ✅ 2026-03-30

**不做：** 不降低 vs_ew_universe 門檻、不把多樣化量化為分數、不限制 agent 探索方向。

## 參考

- Bailey & López de Prado (2014). Deflated Sharpe Ratio / PBO. *JCAM*, *JPS*.
- Clarke, de Silva & Thorley (2002). Portfolio Constraints and the Fundamental Law. *FAJ*.
- DeMiguel, Garlappi & Uppal (2009). Optimal vs. Naive Diversification. *RFS*.
- Harvey, Liu & Zhu (2016). ...and the Cross-Section of Expected Returns. *RFS*.
- MSCI (2019). Portfolio-Weighting Schemes and Factor Exposures.
- S&P Global / Solactive (2018). Equal-Weight Indexing.
- AQR (2023). Fact, Fiction and Factor Investing. *JPM*.
- Qian, Sorensen & Hua (2007). Information Horizon. *JPM*.
