# Portfolio Optimization Reference Library

> 對應 `docs/dev/SYSTEM_STATUS_REPORT.md` §11 學術基準差距分析
> 按優先級排列，每項標註對應的系統缺口

---

## 目錄結構

```
docs/ref/
├── REFERENCES.md              ← 本索引
├── books/                     ← 教科書
├── papers/
│   ├── portfolio/             ← 組合最佳化論文 (CVaR, Robust, HRP, MVSK, Index Tracking)
│   ├── data-modeling/         ← 數據建模論文 (收縮估計, GARCH, 均值收縮)
│   ├── backtesting/           ← 回測方法論論文 (PBO, CSCV)
│   └── alpha/                 ← Alpha 因子研究論文 (待下載)
└── code-references/           ← 書作者的 R/Python 套件文檔 (vignettes)
```

---

## 教科書

| 檔案 | 書名 | 說明 |
|------|------|------|
| `books/portfolio-optimization-book.pdf` | Portfolio Optimization: Theory and Application (Palomar) | 608 頁，15 章，本系統差距分析的基準 |

---

## 書作者的開源實作（已下載 vignettes）

這些 R/Python 套件是書中演算法的**官方實作**，含完整數學推導 + 程式碼範例。

| 檔案 | 套件 | 對應缺口 | 內容 |
|------|------|---------|------|
| `code-references/highOrderPortfolios_vignette.Rmd` | [highOrderPortfolios](https://github.com/dppalomar/highOrderPortfolios) | MVSK 高階矩 | SCA-Q-MVSK 演算法，含偏態+峰態的組合最佳化 |
| `code-references/riskParityPortfolio_vignette.Rmd` | [riskParityPortfolio](https://github.com/dppalomar/riskParityPortfolio) | Risk Parity 改良 | Vanilla + General formulation，含 SCRIP 收斂性證明 |
| `code-references/sparseIndexTracking_vignette.Rmd` | [sparseIndexTracking](https://github.com/dppalomar/sparseIndexTracking) | Index Tracking | 稀疏回歸追蹤指數，L1 正則化 |
| `code-references/fitHeavyTail_vignette.Rmd` | [fitHeavyTail](https://github.com/dppalomar/fitHeavyTail) | 厚尾估計 | Tyler's M-estimator, skewed-t, GH 分布 ML 估計 |
| `code-references/portfolioBacktest_vignette.Rmd` | [portfolioBacktest](https://github.com/dppalomar/portfolioBacktest) | Multiple Randomized Backtest | 多次隨機回測框架，含績效分布統計 |
| `code-references/riskparity_py_README.md` | [riskparity.py](https://github.com/dppalomar/riskparity.py) | Python Risk Parity | Python 實作，可直接整合 |

---

## 關鍵論文（按優先級）

### 🔴 P0 — 必讀（對應嚴重缺口）

| # | 論文 | 缺口 | 取得方式 |
|---|------|------|---------|
| 1 | Rockafellar & Uryasev (2000). "Optimization of Conditional Value-at-Risk." *J. of Risk*, 2(3), 21–42. | CVaR 組合最佳化 | ✅ `papers/portfolio/` |
| 2 | Goldfarb & Iyengar (2003). "Robust Portfolio Selection Problems." *Math. of Operations Research*, 28(1), 1–38. | Robust 組合 | ✅ `papers/portfolio/` |
| 3 | Bailey, Borwein, López de Prado, Zhu (2015). "The Probability of Backtest Overfitting." *J. of Computational Finance*, 20(4). | 回測過擬合檢測 | ✅ `papers/backtesting/` |
| 4 | López de Prado (2016). "Building Diversified Portfolios that Outperform Out of Sample." *J. of Portfolio Management*, 42(4), 59–69. | HRP 方法論 | ✅ `papers/portfolio/` |

### 🟡 P1 — 重要

| # | 論文 | 缺口 | 取得方式 |
|---|------|------|---------|
| 5 | Ledoit & Wolf (2004). "Honey, I Shrunk the Sample Covariance Matrix." *J. of Portfolio Management*, 30(4), 110–119. | 共變異數收縮（已實作） | ✅ `papers/data-modeling/` |
| 6 | Ledoit & Wolf (2014). "Nonlinear Shrinkage of the Covariance Matrix for Portfolio Selection." *Review of Financial Studies*, 30(12), 4349–4388. | 非線性收縮 | ✅ `papers/data-modeling/` |
| 7 | Wang, Zhou, Ying, Palomar (2024). "Efficient High-Order Portfolios Design via the Skew-t Distribution." *IEEE TSP*. | MVSK 演算法 | ✅ `papers/portfolio/` |
| 8 | Jorion (1986). "Bayes-Stein Estimation for Portfolio Analysis." *JFQA*, 21(3), 279–292. | 均值收縮 | ✅ `papers/data-modeling/` |
| 9 | Engle (1982). "Autoregressive Conditional Heteroscedasticity." *Econometrica*, 50(4), 987–1007. | GARCH | ✅ `papers/data-modeling/` |
| 10 | Benidis, Feng, Palomar (2018). "Sparse Portfolios for High-Dimensional Financial Index Tracking." *IEEE TSP*. | Index Tracking | ✅ `papers/portfolio/` |

### 🟢 P2 — 參考

| # | 論文 | 缺口 | 取得方式 |
|---|------|------|---------|
| 11 | Gatev, Goetzmann, Rouwenhorst (2006). "Pairs Trading: Performance of a Relative-Value Arbitrage Rule." *Review of Financial Studies*. | 協整合配對交易 | → `papers/alpha/` Google Scholar |
| 12 | Feng & Palomar (2015). "SCRIP: Successive Convex Optimization Methods for Risk Parity." *IEEE TSP*. | Risk Parity 理論 | 見 riskParityPortfolio vignette |
| 13 | Michaud (1998). "Efficient Asset Management: A Practical Guide to Stock Portfolio Optimization." | Portfolio Resampling | → `books/` |
| 14 | López de Prado (2018). "Advances in Financial Machine Learning." Wiley. | ML 在金融中的應用 | → `books/` |
| 15 | Fama & French (2015). "A Five-Factor Model." *J. of Financial Economics*. | 因子模型共變異數 | → `papers/alpha/` Google Scholar |

---

## Alpha 研究 — 因子投資與自動化

> 對應系統 `src/alpha/` (pipeline + auto/) 和 `src/strategy/factors.py`
> 現有系統：14 因子 + Rolling IC + Regime 偵測 + 自動因子篩選/權重 + 動態因子池

### 🔴 必讀 — 因子投資理論基礎

| # | 論文 | 與系統的關聯 | 取得方式 |
|---|------|-------------|---------|
| A1 | **Fama & French (1993). "Common Risk Factors in the Returns on Stocks and Bonds."** *J. of Financial Economics*, 33(1), 3–56. | **因子模型奠基論文**。3 因子 (market/size/value)。系統的 value_pe, value_pb 因子直接來自此框架。理解因子為何能產生 alpha 的理論基礎。 | → `papers/alpha/` Google Scholar |
| A2 | **Fama & French (2015). "A Five-Factor Asset Pricing Model."** *J. of Financial Economics*, 116(1), 1–22. | 擴展為 5 因子 (+profitability/investment)。系統的 quality_roe 因子對應 profitability。**缺少的因子**：investment (資產成長率)、profitability (營業利潤/帳面價值)。 | → `papers/alpha/` Google Scholar |
| A3 | **Harvey, Liu, Zhu (2016). "...and the Cross-Section of Expected Returns."** *Review of Financial Studies*, 29(1), 5–68. | **因子動物園問題**。論文審查 316 個因子，指出多數是 data mining 產物。提出 t-stat > 3.0 (而非 2.0) 的更嚴格標準。**直接影響系統的因子篩選閾值 (AutoAlphaConfig.min_icir)**。 | → `papers/alpha/` SSRN: 2249314 |
| A4 | **McLean & Pontiff (2016). "Does Academic Research Destroy Stock Return Predictability?"** *J. of Finance*, 71(1), 5–32. | 論文發現學術發表後因子報酬**衰減 ~58%**。直接影響系統 `factor_decay()` 的解讀 — out-of-sample IC 必然低於 in-sample。**自動化系統的因子淘汰機制 (DynamicFactorPool) 需要考慮此效應**。 | → `papers/alpha/` Google Scholar |

### 🔴 必讀 — 因子組合與權重

| # | 論文 | 與系統的關聯 | 取得方式 |
|---|------|-------------|---------|
| A5 | **DeMiguel, Garlappi, Uppal (2009). "Optimal Versus Naive Diversification: How Inefficient Is the 1/N Portfolio?"** *Review of Financial Studies*, 22(5), 1915–1953. | **1/N 基準論文**。證明在 N>25 且 T<500 時，等權組合幾乎無法被最佳化方法打敗。**系統的 Alpha Pipeline 應以 1/N 為 benchmark**，任何因子組合的 OOS 必須顯著勝過 1/N 才有意義。 | → `papers/alpha/` Google Scholar |
| A6 | **Asness, Moskowitz, Pedersen (2013). "Value and Momentum Everywhere."** *J. of Finance*, 68(3), 929–985. | **跨資產因子論文**。證明 value + momentum 在股票、債券、外匯、商品期貨中**普遍有效**。系統的跨資產 Alpha (`src/allocation/cross_asset.py`) 直接受益。**建議將 value+momentum 作為 auto-alpha 的核心因子組合**。 | → `papers/alpha/` AQR.com |
| A7 | **Novy-Marx (2013). "The Other Side of Value: The Gross Profitability Premium."** *J. of Financial Economics*, 108(1), 1–28. | 系統有 quality_roe 但缺少 **gross profitability** (毛利/資產)。論文證明此因子與 value 負相關，組合效果顯著。**建議新增 `gross_profitability` 因子**。 | → `papers/alpha/` Google Scholar |

### 🟡 重要 — IC 分析與因子衰減

| # | 論文 | 與系統的關聯 | 取得方式 |
|---|------|-------------|---------|
| A8 | **Qian, Hua, Sorensen (2007). "Quantitative Equity Portfolio Management."** Chapman & Hall/CRC. | **IC→IR 公式的來源**：IR = IC × √(breadth)。系統的 `compute_ic()` 和 `compute_rolling_ic()` 直接對應。書中有完整的因子 IC 衰減分析框架。 | → `books/` 可搜尋 PDF |
| A9 | **Grinold & Kahn (2000). "Active Portfolio Management."** McGraw-Hill. | **基本定律 (Fundamental Law of Active Management)**：IR = IC × √N。系統的 `AlphaDecisionEngine` 因子篩選邏輯 (ICIR > threshold) 直接源於此。**IC 穩定性比 IC 大小更重要** — 支持 Rolling IC 加權方法。 | → `books/` 經典教科書 |
| A10 | **Kakushadze (2016). "101 Formulaic Alphas."** *Wilmott*, 2016(84), 72–81. | **101 個可程式化的 alpha 公式**。系統目前 14 個因子，此論文可直接擴充因子庫。每個 alpha 都是一行數學表達式，可直接轉為 `factors.py` 函式。 | → `papers/alpha/` arXiv: 1601.00991 (免費) |
| A11 | **Kakushadze & Tulchinsky (2016). "Performance v. Turnover: A Story by 4,000 Alphas."** *J. of Investment Strategies*, 5(2). | 因子數量 vs 換手率 vs 績效的權衡。**直接影響系統的 `ConstructionConfig.turnover_penalty` 和 `max_turnover` 設定**。 | → `papers/alpha/` SSRN: 2657603 |

### 🟡 重要 — Regime 與動態配置

| # | 論文 | 與系統的關聯 | 取得方式 |
|---|------|-------------|---------|
| A12 | **Ang & Bekaert (2004). "How Regimes Affect Asset Allocation."** *Financial Analysts Journal*, 60(2), 86–99. | 系統有 `regime.py` (Bull/Bear/Sideways)，但分類方法簡單 (trailing return)。**論文使用 Markov Switching 模型**，可捕捉 regime 轉換概率。建議升級 `classify_regimes()` 為 Hidden Markov Model。 | → `papers/alpha/` Google Scholar |
| A13 | **Daniel & Moskowitz (2016). "Momentum Crashes."** *J. of Financial Economics*, 122(2), 221–247. | 動量因子在市場反轉時會**崩潰** (momentum crash)。系統的 `REGIME_FACTOR_BIAS` 已降低 Bear 市場 momentum 權重 (0.5)，但論文建議更激進的動態對沖。**自動化系統的安全檢查 (SafetyChecker) 應納入 momentum crash 偵測**。 | → `papers/alpha/` Google Scholar |
| A14 | **Arnott, Harvey, Kalesnik, Linnainmaa (2021). "Reports of Value's Death May Be Greatly Exaggerated."** *Financial Analysts Journal*, 77(1), 44–67. | Value 因子長期表現不佳的分析。論文認為 value 需要**重新定義** (intangible-adjusted book value)。**影響系統 `value_pe`/`value_pb` 的有效性判斷**。 | → `papers/alpha/` Google Scholar |

### 🟢 進階 — 機器學習 Alpha

| # | 論文 | 與系統的關聯 | 取得方式 |
|---|------|-------------|---------|
| A15 | **Gu, Kelly, Xiu (2020). "Empirical Asset Pricing via Machine Learning."** *Review of Financial Studies*, 33(5), 2223–2273. | **ML 因子選擇的基準論文**。比較 Lasso/Ridge/Random Forest/Neural Net 對因子預測能力。系統的 `DynamicFactorPool` ICIR 排名機制是簡單版；論文提供更 sophisticated 的非線性方法。 | → `papers/alpha/` SSRN: 3159577 |
| A16 | **López de Prado (2020). "Machine Learning for Asset Managers."** Cambridge University Press. | 專門寫給資產管理者的 ML 書。涵蓋 **denoised covariance** (與系統 Ledoit-Wolf 互補)、**feature importance** (替代 IC)、**meta-labeling** (交易信號品質)。 | → `books/` |

---

## 實作參考

| 資源 | 語言 | 用途 |
|------|------|------|
| [riskparity.py](https://github.com/dppalomar/riskparity.py) | Python | 可直接 pip install，替換現有 Risk Parity |
| [PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) | Python | MVO/BL/HRP/CVaR 的成熟實作 |
| [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | Python | CVaR/CDaR/Robust 組合最佳化 |
| [skfolio](https://github.com/skfolio/skfolio) | Python | scikit-learn 風格的組合最佳化 |
| [arch](https://github.com/bashtage/arch) | Python | GARCH/EGARCH/GJR-GARCH 波動率模型 |
| [alphalens-reloaded](https://github.com/stefan-jansen/alphalens-reloaded) | Python | 因子分析: IC/turnover/quantile return (Quantopian 維護版) |
| [hmmlearn](https://github.com/hmmlearn/hmmlearn) | Python | Hidden Markov Model — Regime 分類升級 |
| [statsmodels](https://www.statsmodels.org/) | Python | Engle-Granger 共整合、VECM、Kalman Filter |
