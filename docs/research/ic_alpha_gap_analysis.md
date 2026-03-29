# IC-Alpha Gap 分析：為什麼 110 個 L5 因子全部 Validator 不通過

**日期**：2026-03-30
**觸發**：autoresearch 產出 110 個 L5 因子（median ICIR ≥ 0.30），但 Validator 全部 16/17（vs_ew_universe 失敗）

---

## 現象

| 指標 | evaluate.py (L5) | Validator |
|------|:----------------:|:---------:|
| IC/ICIR | ✅ 通過 | — |
| OOS 驗證 | ✅ 通過 | — |
| vs_ew_universe | **未測** | ❌ 全部不通過 |

因子能正確**排名**股票（高 IC），但 top-15 等權組合**跑輸全 universe 等權**。

## 根因：Transfer Coefficient 損耗

Clarke, de Silva & Thorley (2002) — Grinold 基本法則完整版：

```
E(R) = TC × IC × √BR × σ
```

等權 Top-15 的 TC << 1.0：
- **Long-only**：丟掉做空端信號（IC 衡量全截面，但只做多一半）
- **等權**：不反映信號強度（IC 0.90 和 IC 0.50 的股票權重相同）
- **Top-N 截斷**：只用排名最前 15 支，丟棄其餘 185 支的信號

## 台股特殊因素

- Revenue ratio 在**小型高波動股**可能更有效 → top-15 波動高、risk-adjusted 不如大盤
- 200 支 universe 本身已篩過流動性（ADV ≥ 340M），等權這 200 支的表現可能已經很好
- 半導體佔比高 → revenue acceleration 可能只是產業周期曝險

## 管線缺口

```
現在：  L1-L4 (IC/ICIR) ──→ L5 (OOS) ──→ StrategyValidator (16+1項)
                                          ↑
                              大跨步，中間缺少 portfolio-level 診斷
```

evaluate.py 測的是「因子信號品質」，StrategyValidator 測的是「策略表現」。中間的轉換（篩選 + 建構 + 成本）可能毀掉信號。

## 建議修正：L5 加兩個輕量 gate

| 檢查 | 做什麼 | 計算量 | 門檻 |
|------|--------|:------:|------|
| excess_return | top-15 月報酬 - universe 月報酬 | +5 秒 | > 0（不輸大盤） |
| monotonicity | 5 分位報酬是否單調遞減 | +2 秒 | Spearman > 0.5 |

evaluate.py 已有 top-15 portfolio returns，只需同時算 universe returns 比較。不改架構、不加 Validator。

## 文獻支持

- Clarke, de Silva & Thorley (2002) "Portfolio Constraints and the Fundamental Law" — TC 量化
- Qian, Sorensen & Hua (2007) "Information Horizon" — IC horizon 和換倉頻率不匹配
- Zhang, Wang & Cao (2021) "Turnover-Adjusted IR" — 成本侵蝕
- Harvey, Liu & Zhu (2016) "...and the Cross-Section of Expected Returns" — 多重測試
- AQR JPM 2023 "Fact, Fiction and Factor Investing" — IC 是初篩，組合表現是最終標準

## 外部研究結果（2026-03-30）

### Transfer Coefficient 的量化

MSCI 實測數據（2019）：

| 加權方式 | TC (Value) | TC (Momentum) |
|----------|:----------:|:--------------:|
| **Score-tilt** | **0.45** | **0.51** |
| Score-weight | 0.28 | 0.18 |
| **Equal-weight top-N** | **0.10** | **0.04** |

**我們的 top-15 等權 TC 估計 0.05-0.10。** ICIR 0.30 × TC 0.10 = 有效 ICIR 0.03。不可能打敗任何 benchmark。

### 等權 universe 的內建 premium

S&P Global / Solactive 研究分解等權指數的超額報酬：
- Size premium：+1.5-2.5%/年
- Rebalancing bonus：+0.5-1.0%/年
- Value tilt：+0.5%/年
- 合計：**+2.5-4.0%/年**

我們的 top-15 必須產生 ≥ 3% 年化 selection alpha 才能打平等權 benchmark。在 TC 0.10 下，需要 IC ≈ 0.15（極高，幾乎不可能）。

### DeMiguel (2009) 的啟示

等權 1/N 在 14 種最佳化中無一被一致性超越。要用 mean-variance 打敗 1/N，需要 ~3000 個月的估計窗口。**等權 benchmark 不是「弱 benchmark」— 它是學術上已知極難打敗的強 benchmark。**

---

## 改進建議（按優先級）

### 1. 最快的修復：evaluate.py 加 excess_return + monotonicity gate

```
L5 通過後，增加：
  L5b: excess_return = top_Q1_monthly - universe_monthly > 0
  L5c: monotonicity = spearman(quintile_ranks, quintile_returns) > 0.5
```

evaluate.py 已有 top-15 portfolio returns。改為 top-40（Q1 = 前 20%）並同時算 universe returns。

**預期效果**：過濾掉「IC 高但組合不賺錢」的因子。110 個 L5 因子可能只剩 10-30 個通過。

**工作量**：~20 行。

### 2. 最有效的改進：portfolio construction 從 top-15 等權 → top-40 score-tilt

**問題**：top-15 等權的 TC ≈ 0.10（幾乎不傳遞信號）。

**解法**：全 universe score-tilt — 按因子 z-score 加權，正值才持有。

```python
z_scores = (factor_values - factor_values.mean()) / factor_values.std()
weights = z_scores.clip(lower=0)  # long-only
weights = weights / weights.sum()  # normalize
```

**預期效果**：TC 從 ~0.10 提升到 ~0.45-0.51（MSCI 數據）。有效 ICIR 從 0.03 提升到 0.15 — 有機會 cover 成本。

**但需要修改 3 個地方**：
- evaluate.py 的 portfolio construction
- strategy_builder.py 的權重邏輯
- revenue_momentum.py 的權重邏輯

**工作量**：~30 行 per file，但需要重跑所有驗證。

### 3. 診斷性分析（不改代碼，先做）

在改代碼前，先確認問題在哪：

**3a. Cross-sectional return dispersion**
```python
# 如果月度 cross-section std < 5%，因子沒空間
dispersion = monthly_returns.std(axis=1).mean()
```

**3b. Quintile analysis**
```python
# Q1-Q5 報酬是否 monotonic？如果不是，因子無效
for q in [1,2,3,4,5]:
    stocks = universe[factor_rank_quintile == q]
    print(f"Q{q}: {stocks.monthly_return.mean():.2%}")
```

**3c. Sector concentration**
```python
# top-15 有多少半導體？
semiconductor = ['2330.TW', '2454.TW', '2303.TW', '3711.TW', ...]
n_semi = len(set(top_15) & set(semiconductor))
# 如果 > 8/15 = 53%，因子只是在選產業
```

### 4. Benchmark 調整（爭議性最大）

等權 200 支有 +3% 年化的 size + rebalance premium。`vs_ew_universe` 的門檻 0% 對 top-15 等權來說太嚴格。

**選項 A**：門檻從 0% 降到 -2%（承認 benchmark premium）
**選項 B**：benchmark 改為 sector-neutral 等權（消除 size premium）
**選項 C**：不改（堅持「不能輸大盤」這個標準）

**建議選 C** — 寧可改 portfolio construction（提高 TC）也不要降低 benchmark 標準。降低標準是自欺。

---

## PBO 不可算時的替代驗證（2026-03-30 研究）

### 為什麼 PBO 不適用

Bailey et al. (2014) CSCV 測的是「從 N 個策略中挑最好的是否 overfit」。我們只有 1 個 independent cluster（revenue ratio）→ 沒有「挑」的行為 → **PBO 在 N=1 時無意義，這是方法論限制不是實作問題。**

不應該為了讓 PBO 可算而：
- 人為拆分 revenue ratio 變體為不同 cluster
- 降低 correlation 門檻製造假獨立性
- 硬造不好的因子充數

### 替代驗證堆疊

業界共識（AQR, Harvey, Bailey）：PBO 不可算時用以下方法堆疊驗證。通過 Level 1-4 的因子有合理信心可小規模部署。

| Level | 方法 | 測什麼 | 門檻 | 我們的狀態 |
|:-----:|------|--------|------|:----------:|
| 1 | Permutation Test | 因子有預測力（vs 隨機） | p < 0.10 | ✅ Validator #16 |
| 2 | Deflated Sharpe Ratio | 考慮嘗試次數 K 後仍顯著 | DSR > 1.96 | ⚠️ 有 DSR 但 K 需校準 |
| 3 | Walk-Forward Efficiency | 跨時間穩定 | WFE > 0.5 | ⚠️ Validator 有 WF 但沒算 WFE |
| 4 | OOS 衰減率 | 不過度衰減 | OOS/IS Sharpe > 0.4 | ✅ L5 有 60% 衰減門檻 |
| 5 | Cross-Market Validation | 經濟邏輯真實 | IC 同方向 | ❌ 未做 |
| 6 | Paper Trading | 終極驗證 | 3+ 月正報酬 | ⏳ 3/30 啟動 |

### DSR 作為 PBO fallback

DSR（Bailey & López de Prado 2014）回答：「給定你做了 K 次嘗試，觀察到的 Sharpe 是否統計顯著？」

```
DSR = (SR_observed - E[max(SR) | H0]) / SE(SR)
```

- K = results.tsv 總行數（所有嘗試，含 L1/L2 失敗）
- 不需要多個獨立策略，只需要正確的 K
- **watchdog 應改為**：有 4+ cluster 時用 PBO，否則 fallback 到 DSR

### Walk-Forward Efficiency (WFE)

Validator 已有 walk-forward，但只算「OOS Sharpe > 0 的比例」（temporal_consistency）。應增加：

```
WFE = mean(OOS_Sharpe) / mean(IS_Sharpe)
```

WFE > 0.5 = 合格，> 0.7 = 優秀。IS→OOS 衰減超過 60% 是 overfit 強訊號。

### Cross-Market Validation（中期）

如果 revenue ratio 是真實定價因子，應在結構類似的市場（韓國 KOSPI、日本 TOPIX）也有效。不要求 ICIR 一樣高，但至少方向一致。

---

## 決策

**IC-Alpha Gap（portfolio construction 問題）：**

- [ ] **先做 #3 診斷**：cross-sectional dispersion + quintile monotonicity + sector concentration
- [ ] **#1 evaluate.py 加 L5b/L5c**：excess_return + monotonicity gate（~20 行）
- [ ] **#2 測試 score-tilt**：先在回測中比較 top-15 等權 vs top-40 score-tilt 的表現
- [ ] 不改 Validator 的 benchmark 標準（選項 C：不降低門檻）

**PBO 替代驗證：**

- [ ] watchdog PBO fallback 到 DSR（cluster < 4 時）
- [ ] DSR 的 K 從 results.tsv 讀取（含所有失敗嘗試）
- [ ] Validator 加 Walk-Forward Efficiency (WFE) 計算
- [ ] 中期：Cross-Market Validation（韓國/日本）

**因子探索：**

- [x] 提供 agent 新數據（per_history 472 支, margin 220 支）✅ 2026-03-30
- [ ] 觀察 agent 能否用新數據找到非 revenue 的 L3+ 因子
- [ ] 自然累積 4+ cluster 後 PBO 即可計算

**Agent 優化目標調整：**

- [ ] evaluate.py 加 excess_return gate（代碼層面的強制信號）
- [ ] program.md 引導 agent 往「營利 + 多樣化」方向探索

---

## Agent 優化目標檢討（2026-03-30）

### 現狀問題

Agent 目前的優化目標是 **maximize composite_score（通過 L5）**，定義為：
```
fitness = sqrt(returns_proxy / effective_turnover) × median_icir
```

這只衡量因子信號品質（IC/ICIR），不衡量策略營利能力（portfolio alpha）。結果：
- 110 個 L5 因子全部 Validator 16/17（vs_ew_universe 不通過）
- Agent 看到 L5 "keep" → 以為方向正確 → 繼續產 revenue clone
- 因子庫 113 個 factor_returns 全部 corr ≈ 1.0 → PBO 無法計算

### 新的雙重目標

**目標 A：找到真正能營利的因子**

問題：agent 改的是 factor.py（信號），不是 portfolio construction。告訴它「要營利」但不給營利的反饋 = 空話。

解法：**evaluate.py 加 L5b excess_return gate** → top quintile 月報酬必須 > universe 月報酬。Agent 看到 L5b fail → 知道「IC 高但選股不賺錢」→ 自然調整方向。**不是文字引導，是反饋信號。**

**目標 B：找多樣化的因子**

多樣化和營利不矛盾 — 即使 revenue 是最強方向，仍應尋找其他方向的營利可能。Agent 本來就應該在各領域深入探索。

解法：
1. **代碼層（強制）**：returns dedup（已做）擋住 clone。excess_return gate 讓 revenue clone 看到 fail → 自然嘗試新方向。
2. **反饋信號**：evaluate.py 輸出加入 **novelty indicator**（bucketed correlation with existing factors）→ agent 看到哪些方向是真正新的。

### Novelty indicator 設計

Agent 目前只在 L3 **失敗時**看到相關性。通過時不知道自己有多新穎。加 bucketed novelty：

| 標籤 | max corr with existing | Agent 學到什麼 |
|------|:----------------------:|---------------|
| `novelty: high` | < 0.20 | 全新方向，值得深挖 |
| `novelty: moderate` | 0.20 - 0.40 | 部分新穎 |
| `novelty: low` | 0.40 - 0.50 | 接近 clone 邊界 |
| _(L3 fail)_ | > 0.50 | 已有類似因子 |

好處：
- Agent 看到 `novelty: high` → 自然往新方向深入（正向回饋）
- 不洩漏精確 correlation 或因子庫組成
- 和現有 bucketed ICIR（none/weak/moderate/strong）一致
- 不限制任何方向 — revenue 變體如果通過 returns dedup 且 novelty: high 仍能探索

風險：
- Agent 為了 novelty: high 產隨機噪音？→ L1/L2 擋（需要 IC 信號）
- Agent game novelty metric？→ IC series corr < 0.20 但 returns corr > 0.85 仍被 returns dedup 擋

### 關於 program.md 的原則

**不在 program.md 說 revenue 飽和。** 理由：
1. Revenue 方向仍有潛力 — revenue × momentum 交互項、sector-neutral revenue 等可能產出真正不同的選股
2. 如果有 excess_return gate，agent 自然會看到「純 revenue ratio 都 fail L5b」→ 不需要文字限制
3. Returns dedup 只擋「選股相同的 clone」，不擋「同樣用 revenue 但選出不同股票的新做法」
4. 文字限制可能阻止 agent 發現 revenue 類中 TC 更高的信號結構

**program.md 只做兩件事：**
1. 告訴 agent 新數據可用（per_history, margin）
2. 提供 Transfer Coefficient 的概念（「concentrated signal > diffuse signal」）— 不限制方向，只引導信號結構

### 潛在風險

| 風險 | 後果 | 防護 |
|------|------|------|
| Agent 為了多樣化產低品質因子 | L1/L2 擋掉，不進 factor_returns | ✅ 已有 |
| 低品質因子僥倖到 L3 | 貢獻 PBO 新 cluster — **這是好事** | ✅ L3 門檻已合理 |
| Agent game novelty（造假低相關） | IC series corr < 0.20 但 returns corr > 0.85 | ✅ returns dedup 擋 |
| Goodhart 定律（優化 excess_return gate） | 可能，但比優化 IC 更接近真目標 | ⚠️ 可接受 |
| excess_return gate 太嚴 | 合理因子被擋 | ⚠️ 門檻設 > 0 即可 |

### 實作順序

1. **evaluate.py 加 L5b excess_return gate**（營利的反饋信號）
2. **evaluate.py 輸出加 novelty indicator**（多樣化的反饋信號）
3. **program.md 更新**（新數據 + TC 概念，不限制方向）
4. **觀察 1-2 個 research cycle**

### 不做的事

- **不在 program.md 說 revenue 飽和**（阻止 agent 繼續尋找 revenue 類更高盈利可能）
- 不把「多樣化」直接量化為分數加入 fitness（會被 game）
- 不強制「每 N 個實驗必須換方向」（限制創造力）
- 不降低 L2 ICIR 門檻來讓弱因子通過（降低品質不是多樣化）

**原則：**

- 多樣化和營利不矛盾 — 即使 revenue 是最強方向，仍應探索其他方向
- 代碼層面的反饋信號（excess_return gate + novelty indicator）比文字引導更可靠
- 不限制任何方向 — 讓 gate 和反饋信號自然引導 agent 行為
- 不為了 PBO 而造假因子 — 多樣化是自然探索的結果
- Paper trading 是終極驗證

## 參考

- Bailey, Borwein, López de Prado & Zhu (2014). The Probability of Backtest Overfitting. *JCAM*.
- Bailey & López de Prado (2014). The Deflated Sharpe Ratio. *JPS*.
- Clarke, de Silva & Thorley (2002). Portfolio Constraints and the Fundamental Law. *FAJ*.
- DeMiguel, Garlappi & Uppal (2009). Optimal vs. Naive Diversification. *RFS*.
- Harvey, Liu & Zhu (2016). ...and the Cross-Section of Expected Returns. *RFS*.
- Patton & Timmermann (2010). Monotonicity in asset returns. *JFE*.
- MSCI (2019). How Portfolio-Weighting Schemes Affected Factor Exposures.
- S&P Global / Solactive (2018). Equal-Weight Indexing.
- Morgan Stanley. Dispersion and Alpha Conversion.
- Qian, Sorensen & Hua (2007). Information Horizon. *JPM*.
- AQR (2023). Fact, Fiction and Factor Investing. *JPM*.
- Šustr et al. (2021). A Bayesian Approach to Measurement of Backtest Overfitting. *Risks*.
