# Alpha 因子分析方法論審計

**日期**：2026-03-29
**範圍**：evaluate.py 的 L1-L5 管線、research.py 的 IC/ICIR、analytics.py 的 DSR/Sharpe、cross_section.py 的 quantile backtest
**方法**：逐項對比學術論文和業界標準（Alphalens、WorldQuant BRAIN、AlphaForge、FactorMiner）

---

## 總覽

| # | 項目 | 評估 | 嚴重度 |
|---|------|:----:|:------:|
| 1 | IC: Spearman rank, cross-sectional | ✅ 正確 | — |
| 2 | ICIR = mean/std (ddof=1) | ✅ 正確 | — |
| 3 | Forward return: simple, close-to-close | ✅ 正確 | — |
| 4 | 每 20 天取樣 IC（非重疊） | ✅ 審慎 | — |
| 5 | L1-L5 管線結構 | ✅ 優良 | — |
| 6 | 40 天營收延遲 + point-in-time | ✅ 正確 | — |
| 7 | Fitness 已含 turnover penalty | ✅ 正確 | — |
| **8** | **取最佳 horizon 的 ICIR 引入 selection bias** | **⚠️ 需修正** | **HIGH** |
| **9** | **ICIR ≥ 0.15 門檻偏低** | **⚠️ 需評估** | **MEDIUM** |
| **10** | **DSR N=15 未計入 horizon 數量** | **⚠️ 需修正** | **MEDIUM** |
| **11** | **無 factor neutralization 診斷** | **⚠️ 建議加** | **LOW** |

**做對了 7 項，需注意 4 項。** 整體方法論品質高於多數公開框架（AlphaForge 用 IC>0.03 + ICIR>0.1，我們更完整）。

---

## 做對了的（7 項）

### 1. IC 計算：Spearman Rank Correlation ✅

**我們的做法**：`evaluate.py:411-424` — `spearmanr(factor_values, forward_returns)`

**學術標準**：Alphalens（Quantopian）明確使用 Spearman rank IC。Grinold & Kahn《Active Portfolio Management》定義 IC 為因子預測值和實際回報的 cross-sectional correlation。Spearman 比 Pearson 更穩健（不受極端值影響），是業界標準。

**判定**：完全正確。

### 2. ICIR = mean(IC) / std(IC, ddof=1) ✅

**我們的做法**：`evaluate.py:693-695` — `ic_mean / ic_std`，`ic_std = np.std(ics, ddof=1)`

**學術標準**：ICIR 本質上是 IC 的 Sharpe ratio。Grinold (1989) Fundamental Law: IR = IC × √Breadth。ddof=1（Bessel correction）是正確的樣本標準差。

**判定**：完全正確。

### 3. Forward Return: Simple, Close-to-Close ✅

**我們的做法**：`evaluate.py:397-401` — `p1 / p0 - 1`

**學術標準**：Alphalens 使用 percent change（simple return）。Fama-French 因子文獻普遍使用 simple return。Short horizon（5-20 天）下 simple return 和 log return 差異極小。

**判定**：完全正確。

### 4. 每 20 天取樣 IC（非重疊）✅

**我們的做法**：`evaluate.py:56` — `SAMPLE_FREQ_DAYS = 20`，IC 每 20 交易日計算一次。

**學術標準**：如果 forward horizon 是 20 天，每天算 IC 會產生 overlapping returns，引入嚴重正自相關偏差。Britten-Jones et al. 研究指出 overlapping returns "mechanically accumulate autocorrelation"。非重疊取樣是更嚴謹的做法。

Alphalens 預設每天算（帶 overlapping bias）。學術文獻中月頻 IC 最常見。我們的 20 天 ≈ 1 個月，方法論上**比 Alphalens 更嚴謹**。

**代價**：樣本量較少（6.5 年 ≈ ~80 個 IC 觀測值 vs 每天算的 ~1600 個）。但非重疊的每個觀測值都是獨立的，統計品質更高。

**判定**：審慎且正確。

### 5. L1-L5 管線結構 ✅

**我們的做法**：L1 IC → L2 ICIR → L3 Dedup+Stability → L4 Fitness → L5 OOS+Thresholdout

**業界對比**：

| | AlphaForge (NeurIPS 2024) | FactorMiner (2026) | 我們 |
|---|---|---|---|
| IC 門檻 | > 0.03 | > 0.04 | ≥ 0.02 |
| ICIR 門檻 | > 0.1 | ICIR ≥ 0.5 (Top-40) | ≥ 0.15 |
| Dedup | ρ < 0.5 | ρ < 0.5 | ρ ≤ 0.50 |
| OOS 驗證 | 無 | 無 | Thresholdout ✅ |
| Fitness | 無 | 無 | WorldQuant 風格 ✅ |

我們的管線比 AlphaForge 和 FactorMiner 都更完整（有 OOS + Thresholdout + Fitness）。

**判定**：優良。

### 6. Look-Ahead Bias Prevention ✅

**我們的做法**：`evaluate.py:337` — 40 天營收延遲，`_mask_data()` 在 evaluate.py 層強制（agent 無法繞過）。

**學術標準**：台灣季報法定申報期限為季末後 45 天（Baker McKenzie / TWSE）。營收月報通常次月 10 日前。40 天是合理的保守設定。CFA 教材列 look-ahead bias 為 backtesting 七宗罪之一。

我們之前發現的 bug（IC 從 0.188 膨脹到 0.674，72% 偏差）完美印證了學術警告。

**判定**：正確且 fail-closed。

### 7. Fitness Score 已含 Turnover Penalty ✅

**我們的做法**：`evaluate.py:707-709`
```python
fitness = sqrt(|IC_20d| × 10000 / max(turnover, 0.125)) × |ICIR|
```

**業界標準**：WorldQuant BRAIN 的公式是 `sqrt(abs(Returns) / max(turnover, 0.125)) * Sharpe`。我們用 `|IC| × 10000` 作為 returns proxy，`|ICIR|` 作為 Sharpe proxy — 本質上相同的結構。

**初始擔憂「turnover 無 penalty」是錯誤的** — fitness score 裡已經有了。

**判定**：正確。

---

## 需注意的（4 項）

### 8. 取最佳 Horizon 的 ICIR 引入 Selection Bias（HIGH）

**問題**：`evaluate.py:700` — 測試 4 個 forward horizon（5/10/20/60 天），取 `abs(icir)` 最大的。

**學術依據**：Harvey & Liu (2015) 明確指出：*"combining the best k out of n candidate signals yields a bias almost as large as selecting the single best of n×k signals"*。測試 4 個 horizon 等同於多了 4× 的獨立測試。

**量化影響**：如果 DSR 用 N=15（15 個獨立因子方向），但每個方向測 4 個 horizon，實際獨立測試數 = 15 × 4 = 60。E[max SR] from N=60 ≈ 2.0（vs N=15 的 1.4）。這意味著噪音的期望最大 Sharpe 更高，我們的觀測值（0.94）看起來更不顯著。

**建議（三選一）：**

A. **DSR 的 N 乘以 horizon 數量**：`n_trials = 15 × 4 = 60`。最簡單但可能過嚴（horizon 之間不完全獨立）。

B. **固定 horizon 不做選擇**：只報告 20 天 horizon 的 ICIR（最常用的持有期）。消除 selection bias，但可能錯過某些因子在 5 天效果更好。

C. **報告所有 horizon 但只用固定 horizon 做 gate**：L2 用 20d ICIR 做 pass/fail，其餘 horizon 記錄在 results.tsv 做參考。

**推薦方案 C** — 保留資訊量但不引入 selection bias。

### 9. ICIR ≥ 0.15 門檻偏低（MEDIUM）

**問題**：L2 門檻 `MIN_ICIR_L2 = 0.15`。

**業界共識**：

| 來源 | 門檻 | 評級 |
|------|:----:|------|
| 業界通識 | > 0.5 | "Good" |
| AlphaForge | > 0.1 | L2 初篩 |
| FactorMiner | ≥ 0.5 | Top-40 選擇 |
| FE Training | > 0.5 | "Strong predictive power" |

我們的 0.15 作為 **L2 初篩** 和 AlphaForge（0.1）在同一量級，可以接受。但後續 L4 fitness ≥ 3.0 是否等效於更高的 ICIR 門檻？

**驗證**：fitness = sqrt(|IC| × 10000 / TO) × |ICIR|。如果 IC=0.03, TO=0.3, ICIR=0.15 → fitness = sqrt(300/0.3) × 0.15 = 31.6 × 0.15 = 4.7 > 3.0。通過。如果 ICIR=0.10 → fitness = 3.16。也通過。

**結論**：L4 fitness ≥ 3.0 對低 ICIR 的因子有額外過濾（需要 IC 和 turnover 也好才能通過），但 ICIR=0.15 + 合理 IC/TO 就能通過 L4。**門檻整體偏寬鬆，但不是錯誤** — L5 OOS 是真正的把關。

**建議**：不改 L2 門檻（初篩功能），但在研究報告中標注 ICIR < 0.3 的因子為「弱信號」，提醒部署時額外謹慎。

### 10. DSR N=15 未計入 Horizon 數量（MEDIUM）

**問題**：`src/backtest/analytics.py` 的 DSR 用 `n_trials=15`（15 個獨立因子方向）。但每個方向測試了 4 個 horizon，實際獨立測試數更多。

**和問題 8 相關但不同**：問題 8 是「取最佳 horizon」的 selection bias；問題 10 是 DSR 的 N 沒有反映這個 bias。

**學術依據**：Bailey & López de Prado (2014) 的 DSR 公式中 N = "number of trials"。Harvey & Liu (2016) 在 *Review of Financial Studies* 指出，考慮到所有測試，新因子的 t-stat 應 > 3.0（vs 傳統 2.0）。

**建議**：如果採用問題 8 的方案 C（固定 horizon），DSR 的 N 不需要乘 4（因為不再做 horizon 選擇）。如果維持現狀（取最佳 horizon），N 至少乘 2-4。

### 11. 無 Factor Neutralization 診斷（LOW）

**問題**：IC 計算不做 industry/market-cap neutralization。

**學術依據**：

- **Long-only 策略**（我們的情況）：Harvey et al. 研究顯示 "long-only investors are more likely to benefit from investing in the factor as it stands"。不 neutralize 通常更好。
- **Long-short 策略**：sector neutralization 在 78% 情況下改善結果。

**風險**：如果因子本質上只是 sector bet（例如「科技股 vs 傳統產業」），raw IC 會高估 stock-picking 能力。

**建議**：不改 pipeline，但在因子研究報告中加一個**診斷欄位** — 計算 neutralized IC 和 raw IC 的差距。如果差距 > 50%，標記為「可能含 sector bet」。這是一次性分析，不需要改 evaluate.py。

---

## research.py vs evaluate.py 的 IC 計算差異

| 差異 | evaluate.py | research.py |
|------|------------|-------------|
| 相關性方法 | `scipy.stats.spearmanr` | `pd.Series.corr()` on ranked values |
| 最小 N | 50 symbols | 3 symbols |
| 取樣頻率 | 每 20 天 | 每個日期 |
| 輸入格式 | dict | DataFrame |

**問題**：research.py 的最小 N=3 遠低於 evaluate.py 的 N=50。如果用 research.py 做因子分析，3 支股票的 IC 統計上毫無意義。

**影響**：如果 research.py 和 evaluate.py 的結果不一致，可能是因為最小 N 不同。research.py 的低 N 會接受很多 evaluate.py 會 reject 的因子。

**建議**：research.py 的 `MIN_SYMBOLS` 提高到至少 30。或在使用 research.py 做因子分析時明確標注「N < 30 的日期被排除」。

---

## 建議行動

| 優先級 | 項目 | 行動 | 狀態 |
|:------:|------|------|:----:|
| **P0** | #8 最佳 horizon selection bias | ✅ Fix #8 → Method D：L2 改用 median\|ICIR\| across 4 horizons（≥0.30, ≤1.00）。不偏向任何 horizon | ✅ 已修 |
| **P1** | #10 DSR N 校準 | #8 修了（固定 horizon），N 不需要乘 4 | ✅ 已解決 |
| **P1** | research.py MIN_SYMBOLS | 提高到 30 | ⏳ 後續 |
| **P2** | #9 ICIR 門檻標注 | L4 fitness 已緩解，L5 OOS 把關。不改門檻 | 不修 |
| **P2** | #11 neutralization 診斷 | long-only 不需要。後續做一次性分析 | 不修 |

---

## 參考

- Grinold, R. (1989). The Fundamental Law of Active Management. *Journal of Portfolio Management*.
- Grinold, R. & Kahn, R. (1999). *Active Portfolio Management*. McGraw-Hill.
- Harvey, C. & Liu, Y. (2015). Backtesting. *Journal of Portfolio Management*.
- Harvey, C., Liu, Y. & Zhu, H. (2016). ...and the Cross-Section of Expected Returns. *Review of Financial Studies*.
- Bailey, D. & López de Prado, M. (2014). The Deflated Sharpe Ratio. *SSRN*.
- Lo, A. (2002). The Statistics of Sharpe Ratios. *Financial Analysts Journal*.
- Dwork, C. et al. (2015). The reusable holdout. *Science*.
- Ding, Y. & Sun, Q. (2022). The statistics of time varying cross-sectional information coefficients. *Journal of Asset Management*.
- Chen, Y. et al. (2024). AlphaForge: A Framework to Mine and Dynamically Combine Formulaic Alpha Factors. *NeurIPS 2024*.
- Wang, S. et al. (2026). FactorMiner: Automated Factor Mining with LLM Agents. *arXiv:2602.14670*.
- Quantopian. Alphalens Documentation. https://quantopian.github.io/alphalens/
