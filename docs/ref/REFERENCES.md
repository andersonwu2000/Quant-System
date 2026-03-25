# Portfolio Optimization Reference Library

> 對應 `docs/dev/SYSTEM_STATUS_REPORT.md` §11 學術基準差距分析
> 按優先級排列，每項標註對應的系統缺口

---

## 教科書

| 檔案 | 書名 | 說明 |
|------|------|------|
| `portfolio-optimization-book.pdf` | Portfolio Optimization: Theory and Application (Palomar) | 608 頁，15 章，本系統差距分析的基準 |
| `投資組合最佳化.pdf` | 投資組合最佳化（中文版） | 同上書中文版 |

---

## 書作者的開源實作（已下載 vignettes）

這些 R/Python 套件是書中演算法的**官方實作**，含完整數學推導 + 程式碼範例。

| 檔案 | 套件 | 對應缺口 | 內容 |
|------|------|---------|------|
| `highOrderPortfolios_vignette.Rmd` | [highOrderPortfolios](https://github.com/dppalomar/highOrderPortfolios) | MVSK 高階矩 (§11.2 P1) | SCA-Q-MVSK 演算法，含偏態+峰態的組合最佳化 |
| `riskParityPortfolio_vignette.Rmd` | [riskParityPortfolio](https://github.com/dppalomar/riskParityPortfolio) | Risk Parity 改良 (§11.2) | Vanilla + General formulation，含 SCRIP 收斂性證明 |
| `sparseIndexTracking_vignette.Rmd` | [sparseIndexTracking](https://github.com/dppalomar/sparseIndexTracking) | Index Tracking (§11.2 P1) | 稀疏回歸追蹤指數，L1 正則化 |
| `fitHeavyTail_vignette.Rmd` | [fitHeavyTail](https://github.com/dppalomar/fitHeavyTail) | 厚尾估計 (§11.1) | Tyler's M-estimator, skewed-t, GH 分布 ML 估計 |
| `portfolioBacktest_vignette.Rmd` | [portfolioBacktest](https://github.com/dppalomar/portfolioBacktest) | Multiple Randomized Backtest (§11.3 P0) | 多次隨機回測框架，含績效分布統計 |
| `riskparity_py_README.md` | [riskparity.py](https://github.com/dppalomar/riskparity.py) | Python Risk Parity | Python 實作，可直接整合 |

---

## 關鍵論文（按優先級）

### 🔴 P0 — 必讀（對應嚴重缺口）

| # | 論文 | 缺口 | 取得方式 |
|---|------|------|---------|
| 1 | Rockafellar & Uryasev (2000). "Optimization of Conditional Value-at-Risk." *J. of Risk*, 2(3), 21–42. | CVaR 組合最佳化 | Google Scholar 搜尋標題 |
| 2 | Goldfarb & Iyengar (2003). "Robust Portfolio Selection Problems." *Math. of Operations Research*, 28(1), 1–38. | Robust 組合 | Google Scholar |
| 3 | Bailey, Borwein, López de Prado, Zhu (2017). "The Probability of Backtest Overfitting." *J. of Computational Finance*, 20(4). | 回測過擬合檢測 | SSRN: 2326253 |
| 4 | López de Prado (2016). "Building Diversified Portfolios that Outperform Out of Sample." *J. of Portfolio Management*, 42(4), 59–69. | HRP 方法論 | SSRN: 2708678 |

### 🟡 P1 — 重要

| # | 論文 | 缺口 | 取得方式 |
|---|------|------|---------|
| 5 | Ledoit & Wolf (2004). "Honey, I Shrunk the Sample Covariance Matrix." *J. of Portfolio Management*, 30(4), 110–119. | 共變異數收縮（已實作，參考改進版） | ledoit.net/honey.pdf |
| 6 | Ledoit & Wolf (2017). "Nonlinear Shrinkage of the Covariance Matrix for Portfolio Selection." *Review of Financial Studies*, 30(12), 4349–4388. | 非線性收縮（改進版） | Google Scholar |
| 7 | Wang, Zhou, Palomar (2023). "Efficient High-Order Portfolio Design via MVSK." | MVSK 演算法 | 見 highOrderPortfolios vignette |
| 8 | Jorion (1986). "Bayes-Stein Estimation for Portfolio Analysis." *JFQA*, 21(3), 279–292. | 均值收縮 | Google Scholar |
| 9 | Engle (1982). "Autoregressive Conditional Heteroscedasticity." *Econometrica*, 50(4), 987–1007. | GARCH | Google Scholar |
| 10 | Benidis, Feng, Palomar (2018). "Sparse Portfolios for High-Dimensional Financial Index Tracking." *IEEE TSP*. | Index Tracking | 見 sparseIndexTracking vignette |

### 🟢 P2 — 參考

| # | 論文 | 缺口 | 取得方式 |
|---|------|------|---------|
| 11 | Gatev, Goetzmann, Rouwenhorst (2006). "Pairs Trading: Performance of a Relative-Value Arbitrage Rule." *Review of Financial Studies*. | 協整合配對交易 | Google Scholar |
| 12 | Feng & Palomar (2015). "SCRIP: Successive Convex Optimization Methods for Risk Parity." *IEEE TSP*. | Risk Parity 理論 | 見 riskParityPortfolio vignette |
| 13 | Michaud (1998). "Efficient Asset Management: A Practical Guide to Stock Portfolio Optimization." | Portfolio Resampling | Book |
| 14 | López de Prado (2018). "Advances in Financial Machine Learning." Wiley. | ML 在金融中的應用 | Book |
| 15 | Fama & French (2015). "A Five-Factor Model." *J. of Financial Economics*. | 因子模型共變異數 | Google Scholar |

---

## 實作參考

| 資源 | 語言 | 用途 |
|------|------|------|
| [riskparity.py](https://github.com/dppalomar/riskparity.py) | Python | 可直接 pip install，替換現有 Risk Parity |
| [PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) | Python | MVO/BL/HRP/CVaR 的成熟實作 |
| [Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) | Python | CVaR/CDaR/Robust 組合最佳化 |
| [skfolio](https://github.com/skfolio/skfolio) | Python | scikit-learn 風格的組合最佳化 |
| [arch](https://github.com/bashtage/arch) | Python | GARCH/EGARCH/GJR-GARCH 波動率模型 |
