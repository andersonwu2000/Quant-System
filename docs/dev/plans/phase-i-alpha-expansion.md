# Phase I：Alpha 因子庫擴展

> 狀態：待開發
> 論文來源：`docs/ref/papers/alpha/`（10 篇）
> 差距分析：`docs/dev/SYSTEM_STATUS_REPORT.md` §11.7

## 目標
基於學術論文擴展因子庫，校正篩選閾值，增加 momentum crash 防護。

---

## I1: Fama-French 因子補齊（🔴 P0）

### 新增因子

| 因子 | Registry Key | 定義 | 論文 | 數據 |
|------|-------------|------|------|------|
| `size` | `FUNDAMENTAL_REGISTRY["size"]` | -log(market_cap)（小市值溢酬，負號使「小」得到高分） | Fama-French (1993) SMB | FinMind `TaiwanStockMarketValue` |
| `investment` | `FUNDAMENTAL_REGISTRY["investment"]` | -YoY total asset growth（低投資溢酬，負號使「保守」得到高分） | Fama-French (2015) CMA | FinMind `TaiwanStockBalanceSheet` |
| `gross_profitability` | `FUNDAMENTAL_REGISTRY["gross_profit"]` | (Revenue - COGS) / Total Assets | Novy-Marx (2013) | FinMind `TaiwanStockFinancialStatements` |

### 實作位置
- `src/strategy/factors.py`：新增 3 個函數
- `src/strategy/research.py`：`FUNDAMENTAL_REGISTRY` 註冊
- `src/data/fundamentals.py`：確認 FinMind provider 能取得所需欄位
- `tests/unit/test_factors.py`：新增測試

### 注意
- Novy-Marx (2013): gross profitability 與 value (HML) 負相關 (-0.18 Spearman)，組合效果顯著
- Fama-French (2015): 加入 RMW + CMA 後 HML 變得冗餘

---

## I2: Kakushadze 101 精選（🟡 P1）

### 篩選標準
從 101 個公式（Appendix A）中挑選符合以下條件的因子：
1. 只使用 price-volume 數據（open/high/low/close/volume）— 排除需要 VWAP/industry/cap 的公式
2. 不需要 adv（average daily volume）超過 20 天 — 排除 adv60/adv81/adv120/adv180
3. 公式可在 pandas 中高效向量化
4. 台股回測 IC > 0.02

### 候選因子（初步篩選 15 個）

| Alpha# | 公式（簡化） | 類型 | 持有期 |
|--------|-------------|------|--------|
| 2 | -corr(rank(Δlog(vol), 2), rank((close-open)/open), 6) | volume-price | 短 |
| 3 | -corr(rank(open), rank(volume), 10) | volume-price | 短 |
| 6 | -corr(open, volume, 10) | volume-price | 短 |
| 12 | sign(Δvolume) × (-Δclose) | mean-reversion | 0-1天 |
| 20 | -rank(open-delay(high,1)) × rank(open-delay(close,1)) × rank(open-delay(low,1)) | gap | 0-1天 |
| 33 | rank(-(1-(open/close))) | intraday | 0-1天 |
| 34 | rank((1-rank(σ(ret,2)/σ(ret,5))) + (1-rank(Δclose))) | vol-regime | 2-5天 |
| 38 | -rank(Ts_Rank(close,10)) × rank(close/open) | mean-reversion | 短 |
| 41 | √(high×low) - vwap | intraday | 0天 |
| 42 | rank(vwap-close) / rank(vwap+close) | intraday | 0天 |
| 44 | -corr(high, rank(volume), 5) | volume-price | 短 |
| 53 | -Δ(((close-low)-(high-close))/(close-low), 9) | Williams %R 變體 | 9天 |
| 54 | -(low-close)×open^5 / ((low-high)×close^5) | price-structure | 短 |
| 84 | sign_power(Ts_Rank(vwap-max(vwap,15), 20), Δclose(5)) | momentum | 5天 |
| 101 | (close-open) / ((high-low)+0.001) | intraday momentum | 0天 |

### 實作
- `src/strategy/factors.py`：每個 alpha 一個函數，命名 `kakushadze_alpha_N()`
- 共用 helper：`rank()`, `ts_rank()`, `decay_linear()`, `correlation()`
- 先實作 15 個，用台股 IC 篩選保留 10 個

---

## I3: 因子篩選閾值校正（🔴 P0）

### 修改項目

| 檔案 | 欄位 | 現值 | 新值 | 依據 |
|------|------|------|------|------|
| `src/alpha/auto/config.py` | `DecisionConfig.min_icir` | 0.3 | 0.5 | Harvey (2016): t > 3.0 ≈ ICIR > 0.5 |
| `src/alpha/auto/dynamic_pool.py` | exclusion threshold | 無 | ICIR < 0.2 持續 30 天 | McLean-Pontiff: OOS alpha ≈ 0.42× IS |
| `src/alpha/auto/researcher.py` | FactorScore.eligible | 無 OOS 調整 | IS ICIR × 0.42 作為 OOS 估計 | McLean-Pontiff (2016) |
| `src/alpha/pipeline.py` | AlphaReport | 無 1/N benchmark | 新增 `vs_equal_weight_sharpe_ttest` | DeMiguel (2009) |

---

## I4: Momentum Crash 防護（🟡 P1）

### 實作（基於 Daniel & Moskowitz 2016）

#### 偵測條件
- 過去 12 個月市場報酬 < -20% **且** 近 1 個月波動率 > 歷史 2 倍
- 論文發現：crash 後 loser 組合有 option-like 凸性報酬

#### 修改
| 檔案 | 修改 |
|------|------|
| `src/alpha/auto/safety.py` | 新增 `check_momentum_crash(market_returns, volatility)` |
| `src/alpha/auto/decision.py` | `REGIME_FACTOR_BIAS[BEAR]["momentum"]` 從 0.5 → 0.1 |
| `src/alpha/auto/decision.py` | 新增 volatility-scaling: `w × (σ_target / σ_realized_20d)` 可選 |
| `src/alpha/auto/config.py` | 新增 `momentum_crash_market_threshold: float = -0.20` |
| `src/alpha/auto/config.py` | 新增 `momentum_crash_vol_multiplier: float = 2.0` |
| `src/alpha/auto/config.py` | 新增 `volatility_scaling_enabled: bool = False` |
| `src/alpha/auto/config.py` | 新增 `volatility_scaling_target: float = 0.15` |
