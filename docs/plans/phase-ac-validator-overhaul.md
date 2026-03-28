# Phase AC：Validator 方法論修正

> 目標：修正 StrategyValidator 15 項中被學術文獻證實有方法論錯誤的檢查
> 教訓來源：PBO 三次實作三次錯（CLAUDE.md #10）。同樣的問題可能存在於其他 check。
> 原則：**每項 check 都要能回答一個明確的問題，且方法論必須對齊原論文。**

---

## 1. 嚴重度分級

### P0：方法論錯誤（測量的東西和宣稱的不同）

| # | Check | 宣稱測量 | 實際測量 | 根因 |
|---|-------|---------|---------|------|
| 7 | **DSR** | 多重測試後的統計顯著性 | 無（n_trials=1 自動通過） | n_trials 沒有追蹤 |
| 8 | **Bootstrap** | P(Sharpe > 0) 的統計信心 | 被 IID 假設膨脹的假信心 | 日報酬有自相關，IID bootstrap 低估標準誤 |
| 6 | **Walk-Forward** | 參數在未來是否穩定（WFA 原意） | 每年獨立跑都能賺嗎（temporal consistency） | 無參數策略不需要 WFA，但名稱誤導 |

### P1：門檻或設計缺陷（測量方向正確但門檻無意義）

| # | Check | 問題 |
|---|-------|------|
| 14 | **Market corr** | |corr| <= 0.90 幾乎不篩掉任何東西。台股組合和 0050 通常 corr 0.85-0.95 |
| 9 | **OOS holdout** | 同一 holdout 被 autoresearch 反覆使用 → 間接學習 |
| 10 | **vs 0050** | 等權因子策略和市值加權 0050 比 → 自動帶 size premium |
| 12 | **Regime** | 用年度切割不是真的 regime analysis |

### P2：設計層面（需要加入新的驗證維度）

| 問題 | 說明 |
|------|------|
| 15 項中 ~12 項共用同一個 backtest | 一個 overfit 的 equity curve 可以同時通過 CAGR/Sharpe/MDD/CVaR/cost |
| 缺少 permutation test | 沒有「隨機打亂信號後 Sharpe 會降多少」的基準 |
| 缺少 CPCV | 2024 年比較研究顯示 CPCV 防 false discovery 顯著優於 WF + holdout |

---

## 2. P0 修正方案

### 2.1 DSR n_trials（已修）

`n_trials` 已從 1 改成 15（獨立假說方向數）。DSR(N=15) 對 Sharpe 0.879 的結果是 0.773，有意義但不致命。

**狀態：✅ 已完成（Phase AB）。**

### 2.2 Bootstrap：IID → Stationary Bootstrap

**問題**：`_bootstrap_sharpe` 用 `rng.choice(returns, replace=True)` — 逐日隨機抽取，假設日報酬 IID。但日報酬有：
- 波動率聚類（GARCH 效應）：大跌後接著大跌的機率高
- 自相關：momentum 因子的報酬序列有正自相關

Two Sigma 研究和 2025 年最新論文（Tandfonline）證實：IID bootstrap 低估 Sharpe 的標準誤，P(Sharpe>0) 被系統性高估。

**修正**：改用 Stationary Bootstrap（Politis & Romano 1994）：

```python
def _bootstrap_sharpe_stationary(self, result, n_bootstrap, avg_block=20):
    """Stationary Bootstrap: 隨機長度 block resampling。

    avg_block: 平均 block 長度（交易日）。
    台股日報酬的自相關約在 lag 15-25 天衰減，avg_block=20 合理。
    """
    returns = result.daily_returns.dropna().values
    if len(returns) < 20:
        return 0.0  # fail-closed
    n = len(returns)
    p = 1.0 / avg_block  # geometric distribution parameter
    rng = np.random.default_rng(42)
    positive_count = 0
    for _ in range(n_bootstrap):
        # Build block sample
        sample = np.empty(n)
        i = 0
        pos = rng.integers(0, n)
        while i < n:
            sample[i] = returns[pos % n]
            i += 1
            pos += 1
            # With probability p, jump to a new random position
            if rng.random() < p:
                pos = rng.integers(0, n)
        mean_r = sample.mean()
        std_r = sample.std(ddof=1)
        if std_r > 0:
            sr = mean_r / std_r * np.sqrt(252)
            if sr > 0:
                positive_count += 1
    return positive_count / n_bootstrap
```

**參數選擇**：`avg_block=20` 對應約 1 個月的 block，和月度再平衡頻率匹配。

**驗證方式**：
- 對同一策略比較 IID P(SR>0) vs Stationary P(SR>0)
- 預期 Stationary 版本的 P 值更低（更保守）
- 如果差異 < 2%，說明自相關影響小，IID 可接受

### 2.3 Walk-Forward：重命名 + 加入真正的時序穩定性檢查

**問題**：`walkforward_positive_ratio` 名稱暗示是 Walk-Forward Analysis（含 train-optimize-test），但實際只是逐年獨立回測。對於無參數的因子策略，WFA 本身就不適用。

**修正**：

1. **重命名**：`walkforward_positive_ratio` → `temporal_consistency`
2. **加入更有意義的檢查**：OOS Sharpe 的年度一致性

```python
# 不只看正率，還看年度 Sharpe 的變異係數
oos_sharpes = [r["sharpe"] for r in valid_wf]
positive_ratio = sum(1 for s in oos_sharpes if s > 0) / max(len(oos_sharpes), 1)
# 新增：年度 Sharpe 的穩定性（CV < 2.0 代表相對穩定）
if len(oos_sharpes) >= 3:
    cv = np.std(oos_sharpes) / max(abs(np.mean(oos_sharpes)), 0.01)
    stability = cv < 2.0
```

---

## 3. P1 修正方案

### 3.1 Market correlation 門檻收緊

| 現在 | 改後 | 理由 |
|------|------|------|
| \|corr\| <= 0.90 | \|corr\| <= 0.80 | 台股等權組合和 0050 通常 corr 0.85-0.95。0.90 不篩掉任何東西 |

或改為 **residual alpha test**：回歸掉 0050 報酬後，殘差的 Sharpe > 0。

### 3.2 Benchmark 選擇

| 現在 | 問題 | 改後 |
|------|------|------|
| vs 0050.TW（市值加權） | 等權策略自動帶 size premium | vs 等權 universe average |

等權 universe average = 全 universe 等權持有的報酬，和策略唯一的差別是選股。這才是 alpha。

### 3.3 OOS holdout 污染

**短期**：已改為 rolling 1.5 年（比固定 2024H2 好）。

**長期**：加入 holdout 使用次數計數。每測試一個因子，計數 +1。當計數 > 20 時，自動更新 holdout 窗口（往前滾動 6 個月）。

### 3.4 Regime 改為 drawdown-based

```python
# 從年度切割改為：識別市場大跌期間（drawdown > 10%），測策略在這些期間的表現
market_dd = compute_drawdown(market_returns)  # 0050 的 drawdown 序列
crisis_mask = market_dd < -0.10               # 市場回檔 > 10% 的日期
crisis_return = strategy_returns[crisis_mask].sum()
```

---

## 4. P2：新增驗證維度

### 4.1 Permutation Test（信號打亂）

```python
def permutation_test(strategy_sharpe, returns_matrix, n_permutations=100):
    """隨機打亂因子信號的選股，看 Sharpe 降多少。

    如果真實 Sharpe 不顯著高於隨機 Sharpe，因子沒有 alpha。
    """
    random_sharpes = []
    for _ in range(n_permutations):
        shuffled = np.random.permutation(factor_values, axis=1)  # 打亂 cross-section
        random_return = backtest(shuffled)
        random_sharpes.append(sharpe(random_return))
    p_value = sum(1 for s in random_sharpes if s >= strategy_sharpe) / n_permutations
    return p_value  # < 0.05 = 策略顯著
```

**價值**：完全獨立於 DSR/Bootstrap/PBO 的過擬合檢測。如果 permutation p-value > 0.10，因子可能只是運氣。

### 4.2 CPCV（Combinatorial Purged Cross-Validation）

2024 年比較研究（ScienceDirect）顯示 CPCV 在防 false discovery 上顯著優於 WF + holdout。

CPCV 和 PBO 的 CSCV 類似，但：
- PBO 比較 N 個策略的排名
- CPCV 對單一策略做多種 IS/OOS 分割，估算 OOS 表現分佈

**實作**：直接用現有 `compute_pbo` 的分割邏輯，但只有 1 個策略，計算每個分割的 OOS Sharpe。

---

## 5. 實施計畫

### Phase 1：P0 修正（1-2 天）

| Step | 改動 | 工作量 |
|------|------|--------|
| 2.1 | DSR n_trials | ✅ 已完成 |
| 2.2 | Bootstrap IID → Stationary | 1 小時（30 行代碼 + 驗證） |
| 2.3 | WF 重命名 temporal_consistency | 15 分鐘 |

### Phase 2：P1 修正（1-2 天）

| Step | 改動 | 工作量 |
|------|------|--------|
| 3.1 | Market corr 0.90 → 0.80 | 改 1 個參數 |
| 3.2 | Benchmark 改等權 average | 30 分鐘 |
| 3.3 | OOS 使用次數計數 | 1 小時 |
| 3.4 | Regime 改 drawdown-based | 1 小時 |

### Phase 3：P2 新增（3-5 天）

| Step | 改動 | 工作量 |
|------|------|--------|
| 4.1 | Permutation test | 2 小時 |
| 4.2 | CPCV | 3 小時 |

### 驗證

每個修正後重跑 revenue_momentum_hedged，對比前後差異。

---

## 6. 修正後的 Validator 15+2 項

| # | Check | 測量什麼 | 門檻 | 改動 |
|---|-------|---------|------|------|
| 1 | universe_size | 選股池大小 | >= 50 | 不變 |
| 2 | cagr | 絕對報酬 | >= 8% | 不變 |
| 3 | sharpe | 風險調整報酬 | >= 0.7 | 不變 |
| 4 | max_drawdown | 最大回撤 | <= 40% | 不變 |
| 5 | annual_cost_ratio | 成本侵蝕 | < 50% | 不變 |
| 6 | ~~walkforward~~ **temporal_consistency** | 年度一致性 | >= 60% 正 + CV < 2.0 | **重命名 + 加 CV** |
| 7 | deflated_sharpe | 多重測試修正 | >= 0.70 | **n_trials=15 已修** |
| 8 | bootstrap_p | P(Sharpe > 0) | >= 80% | **IID → Stationary** |
| 9 | oos_sharpe | 樣本外表現 | >= 0.3 | Rolling 1.5 年（已改） |
| 10 | vs_benchmark | 超額報酬 | >= 0% | **0050 → 等權 universe** |
| 11 | pbo | 過擬合機率 | <= 0.50 | 不變（Phase AB 後續） |
| 12 | worst_regime | 危機表現 | >= -30% | **年度 → drawdown-based** |
| 13 | recent_sharpe | 因子衰退 | >= 0 | 不變 |
| 14 | market_correlation | 獨立 alpha | \|corr\| <= **0.80** | **收緊** |
| 15 | cvar_95 | 尾部風險 | >= -5% | 不變 |
| **16** | **permutation_p** | **信號是否隨機** | **< 0.10** | **新增** |
| **17** | **cpcv_oos_sharpe** | **CPCV OOS Sharpe 分佈** | **median > 0** | **新增** |

---

## 7. 風險

| 風險 | 緩解 |
|------|------|
| Stationary Bootstrap 的 avg_block 選擇影響結果 | 用多個 block size（10/20/40）取中位數 |
| 門檻收緊後現有策略全部 fail | 逐項改、逐項跑，不一次改完 |
| Permutation test 計算量大（100 次 backtest） | 用向量化回測（Phase Z1），~10 秒/次 |
| CPCV 和 PBO 結果矛盾 | CPCV 看單一策略、PBO 看多策略選擇，兩者回答不同問題 |
| 等權 benchmark 可能讓所有策略 fail（台股等權近年很強） | 先計算等權 benchmark 的 CAGR/Sharpe，確認門檻合理 |

---

## 8. 參考文獻

- Bailey, D. & Lopez de Prado, M. (2014). The Probability of Backtest Overfitting.
- Bailey, D. & Lopez de Prado, M. (2014). The Deflated Sharpe Ratio.
- Politis, D. & Romano, J. (1994). The Stationary Bootstrap. JASA.
- Two Sigma (2018). A Short Sharpe Course: Sharpe Ratio Estimation.
- Tandfonline (2025). IID Resampled Backtests Introduce Bias.
- Joubert et al. (2024). The Three Types of Backtests.
- Arian et al. (2024). Backtest Overfitting Comparison. Knowledge-Based Systems.
- Harvey, Liu & Zhu (2016). ...and the Cross-Section of Expected Returns. RFS.
- AllianceBernstein (2024). Why Idiosyncratic Alpha is Better.
- FactSet (2024). Understanding Regime Changes in Backtesting.
- Ledoit & Wolf (2008). Robust performance hypothesis testing with the Sharpe ratio.
- Politis & White (2004). Automatic Block-Length Selection for Dependent Bootstrap.
- DeMiguel, Garlappi, Uppal (2009). Optimal Versus Naive Diversification. RFS.

---

## 9. 審批意見（2026-03-28）

**審批結果：部分通過。7 項中 2 項立即執行，2 項延後，3 項不做。**

### 逐項審批

| # | 提案 | 決定 | 理由 |
|---|------|:----:|------|
| 2.2 | Bootstrap IID → Stationary | **延後** | 偏差真實但 ~20%，已有 DSR+OOS+WF 冗餘覆蓋。非 P0，降為 P1 |
| 2.3 | WF 改名 temporal_consistency | **✅ 立即** | 語義修正，零成本 |
| 3.1 | Market corr 0.90→0.80 | **❌ 不做** | 0.80 對等權台股因子太嚴（典型 corr 0.85-0.93），會誤殺合法策略 |
| 3.2 | Benchmark 改等權 universe | **✅ 立即** | **最有價值的改動** — vs 0050 對等權策略自帶 size premium，幾乎無效 |
| 3.4 | Regime 改 drawdown-based | **延後** | 理論更好但現有年度切割實務已夠用，列 P2 |
| 4.1 | Permutation test | **❌ 不做** | 被 DSR(N=15) 覆蓋，冗餘 |
| 4.2 | CPCV | **❌ 不做** | 為 ML 策略設計（大量超參數），無參數因子策略收益為零 |

### 立即執行

```
1. walkforward_positive_ratio → temporal_consistency（改名，15 分鐘）
2. vs_0050 → vs equal-weight universe average（實質改動，30 分鐘）
```

### 延後（Phase 2）

```
3. Stationary Bootstrap（有價值但非急迫，已有冗餘保護）
4. Drawdown-based regime（理論更好但改動大）
```

### 不做

```
5. Market corr 0.80（太嚴）
6. Permutation test（被 DSR 覆蓋）
7. CPCV（無參數策略不需要）
```

### 補充說明

**等權 benchmark 是本計畫最重要的改動。** 目前 `vs_0050_excess >= 0` 幾乎是免費通過（等權天然 size premium ~2-4%/年）。改成等權 universe average 後，這個 check 才真正測選股能力。

**Validator 修改後為 15 項（不增不減）：** 不新增 permutation/CPCV，只修正現有 check 的方法論。符合「最小改動最大收益」原則。
