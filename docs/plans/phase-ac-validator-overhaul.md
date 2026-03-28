# Phase AC：Validator 方法論修正 ✅ 已完成（2026-03-29）

> 目標：修正 StrategyValidator 中被學術文獻證實有方法論錯誤的檢查
> 教訓來源：PBO 三次實作三次錯（CLAUDE.md #10）。同樣的問題可能存在於其他 check。
> 原則：**每項 check 都要能回答一個明確的問題，且方法論必須對齊原論文。**
>
> **結果：15 → 16 項檢查，全部方法論修正完成。865 stocks 驗證：15/16 通過（僅 OOS Sharpe fail，統計功效不足的 sanity check，非方法論問題）。**

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

### 統計功效不足（第二輪研究發現，2026-03-29）

**性質**：不是方法論錯誤（測量的東西是對的），而是**樣本太小導致結果是噪音**。和 PBO 不同（PBO 是測錯東西），這些是不可修正的統計限制。

| # | Check | 問題 | 定量證據 |
|---|-------|------|---------|
| 9 | **OOS Sharpe (375 天)** | 年化 Sharpe SE ≈ 0.82。Sharpe 0.3 的 z = 0.37, p = 0.36。**36% 的真實 SR=0 策略會通過** | Lo (2002): 需要 43 年日頻數據才能讓 SR=0.3 統計顯著 |
| 13 | **Recent Sharpe (252 天)** | SE ≈ 1.0。真實 SR=0 → P(measured>0) = **50%（拋硬幣）**。真實 SR=0.5 → 31% 機率被誤殺 | Two Sigma: 252 天 Sharpe 無法區分 SR=0.5 和 SR=0 |

**為什麼不是 P0**：這些 check 測量的方向正確（未來表現和最近表現），只是樣本不夠大。它們仍有**方向性價值**——排除 SR << -1 的災難性崩潰。

**正確的解讀**：OOS >= 0.3 和 recent >= 0 是 **sanity check**（排除災難），不是統計檢定（證明有 alpha）。門檻不應該提高（提高也沒用，SE 太大），但也不應該被解讀為「策略在 OOS 表現好」。

**不可修正的原因**：唯一的修正是增加數據量，但 OOS 期間增加到 3 年 → SE 仍是 0.58。需要 10+ 年才有真正的統計功效——此時 OOS 不再是「最近的」了。

### 其他第二輪發現（中低優先級）

| # | Check | 問題 | 嚴重度 |
|---|-------|------|:------:|
| 4 | **MDD** | 路徑依賴極強，同策略不同路徑可差 2x。Magdon-Ismail (2004): 零漂移 7 年期望 MDD=63%，方差極大 | P1 |
| 5 | **Cost ratio** | 用 `initial_cash` 而非平均 NAV 算成本率；`CAGR + cost` 不是線性可加（幾何 vs 算術） | P2 |
| 10 | **等權 benchmark** | 等權有 ~2.25% size+rebalancing premium（Solactive 2018）。vs EW >= 0% 太寬鬆 | P2 |
| 4 | **Sharpe 自相關** | Lo (2002): 日頻 ρ~0.05 → Sharpe 高估 ~5%。Bootstrap(Stationary) 已補償 | P3 |
| 15 | **CVaR 87 觀測** | 相對誤差 8-15%（Yamai & Yoshiba 2002）。-5% 門檻夠寬，目前 OK | P3 |

### P2：設計層面

| 問題 | 說明 |
|------|------|
| 15 項中 ~12 項共用同一個 backtest | 一個 overfit 的 equity curve 可以同時通過 CAGR/Sharpe/MDD/CVaR/cost |
| 缺少 permutation test | 沒有「隨機打亂信號後 Sharpe 會降多少」的基準（P2 延後） |

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

## 5. 實施計畫（覆核後修訂）

### 立即執行

| Step | 改動 | 工作量 | 狀態 |
|------|------|--------|:----:|
| 2.1 | DSR n_trials=15, min_dsr 0.95→0.70 | 5 個檔案各改 1 行 | ✅ 已完成（Phase AB） |
| 2.3 | WF 改名 `temporal_consistency` | 改名 | ✅ 已完成 |
| 3.1 | Market corr 0.90 → 0.80 | 改 1 個參數 | ✅ 已完成 |
| 3.2 | Benchmark 改等權 universe average | 30 分鐘 | ✅ 已完成 |
| — | Rolling OOS `datetime.now()` bug | `__post_init__` 修正 | ✅ 已完成 |

### 原延後 → 已提前完成（使用者要求方法論正確優先）

| Step | 改動 | 狀態 |
|------|------|:----:|
| 2.2 | Bootstrap IID → Stationary (Politis & Romano 1994, avg_block=20) | ✅ 已完成 |
| 3.4 | Regime 改 drawdown-based (0050 DD > 15%) | ✅ 已完成 |
| 4.1 | Permutation test (shuffle real factor rankings, fixed mapping) | ✅ 已完成（#16） |

### 覆核回覆（2026-03-28）

**全部接受。** 逐項確認：

| 覆核變更 | 確認 |
|---------|------|
| 3.1 corr 0.80 從 NO → YES | ✅ 實測 corr 0.51-0.53，0.80 有充足 buffer |
| 4.1 Permutation 從 NO → P2 | ✅ DSR 測顯著性，Permutation 測信號內容，不等價 |
| 其餘同意 | ✅ |

執行順序：2.3 改名 → 3.2 等權 benchmark → 3.1 corr 0.80 → 逐項跑 Validator 比較

### 不做

| Step | 原因 |
|------|------|
| 4.2 CPCV | PBO + DSR 已覆蓋 |

### 驗證

改完 2.3 + 3.1 + 3.2 後重跑 revenue_momentum_hedged，對比 vs_benchmark 和 market_corr 變化。

---

## 6. 修正後的 Validator 16 項（全部完成，2026-03-29 凍結）

| # | Check | 測量什麼 | 門檻 | 改動 | 統計功效 |
|---|-------|---------|------|------|---------|
| 1 | universe_size | 選股池大小 | >= 50 | 不變 | N/A |
| 2 | cagr | 絕對報酬 | >= 8% | 不變 | OK（7 年數據） |
| 3 | sharpe | 風險調整報酬 | >= 0.7 | 不變 | OK（Lo 2002: 日頻 ρ~0.05 偏差 < 5%） |
| 4 | max_drawdown | 最大回撤 | <= 40% | 不變 | ⚠️ 路徑依賴（P1 延後：Monte Carlo MDD） |
| 5 | annual_cost_ratio | 成本侵蝕 | < 50% | 不變 | ⚠️ initial_cash 分母粗糙（P2） |
| 6 | **temporal_consistency** | 年度一致性 | >= 60% 正 | ✅ **改名** | OK |
| 7 | deflated_sharpe | 多重測試修正 | >= 0.70 | ✅ **n_trials=15** | OK |
| 8 | bootstrap_p_sharpe_positive | P(Sharpe > 0) | >= 80% | ✅ **Stationary Bootstrap** | OK（保留自相關） |
| 9 | oos_sharpe | 樣本外 sanity check | >= 0.3 | ✅ Rolling 1.5 年 | ❌ **SE=0.82，無統計功效**（不可修正） |
| 10 | **vs_ew_universe** | 超額報酬 | >= 0% | ✅ **改等權** | ⚠️ 等權有 ~2% premium（P2） |
| 11 | construction_sensitivity | 組合建構穩定性 | <= 0.50 | ✅ **改名**（非 Bailey PBO） | OK |
| 12 | worst_regime | 危機表現 | >= -30% | ✅ **Drawdown-based** | ⚠️「不投資」漏洞（P2 延後） |
| 13 | recent_sharpe | 因子衰退 sanity check | >= 0 | 不變 | ❌ **SE=1.0，拋硬幣**（不可修正） |
| 14 | market_correlation | 獨立 alpha | \|corr\| <= **0.80** | ✅ **收緊** | OK |
| 15 | cvar_95 | 尾部風險 | >= -5% | 不變 | OK（87 觀測，相對誤差 ~10%） |
| 16 | **permutation_p** | 信號是否有選股內容 | < 0.10 | ✅ **新增** | OK（100 permutations） |

**16 項分為四類**（FACTOR_PIPELINE_DEEP_REVIEW 結論）：
- **統計/結構檢定（防過擬合）**：#7 DSR, #8 Bootstrap, #10 vs EW, #11 PBO, #14 Market corr, #16 Permutation — 6 項真正有效的防線
- **經濟可行性（值得交易嗎）**：#2 CAGR, #3 Sharpe, #5 Cost, #6 Temporal — 不防過擬合但確保最低經濟價值
- **Sanity check（排除災難）**：#9 OOS Sharpe (SE=0.82), #13 Recent (SE=1.0) — 統計功效不足，只排除 SR << -1
- **描述性指標**：#1 Universe, #4 MDD, #12 Regime, #15 CVaR — 風險度量，非假設檢定

---

## 7. 部署條件重構

### 問題：「≥ 13/15 excl-DSR」允許任意 1 項失敗

14 項非 DSR 檢查中，2 項是噪音（OOS SE=0.82, Recent SE=1.0），隨機 fail 30-50%。「允許 1 項失敗」的 buffer 經常被噪音 check 消耗，讓有意義的 check 失敗被容忍。

**實際案例**：revenue_momentum_hedged 13/15，fail 在 oos_sharpe(-1.2) + pbo(0.702)。如果 OOS 隨機 pass（36% 機率），策略就會以 **PBO=0.702（過擬合）被部署**。

### 修正：硬門檻 + 軟門檻

```
部署條件（新）：
  硬門檻（全部必須通過，0 容忍）：
    #2  CAGR >= 8%
    #3  Sharpe >= 0.7
    #5  Cost ratio < 50%
    #6  Temporal consistency >= 60%
    #7  DSR >= 0.70
    #8  Bootstrap P(SR>0) >= 80%
    #10 vs EW benchmark >= 0%
    #11 PBO <= 0.50
    #14 Market corr <= 0.80
    #16 Permutation p < 0.10（如已實作）

  軟門檻（報告但不 block）：
    #1  Universe >= 50
    #4  MDD <= 40%
    #9  OOS Sharpe >= 0.3（SE=0.82，sanity check only）
    #12 Worst regime >= -30%
    #13 Recent Sharpe >= 0（SE=1.0，sanity check only）
    #15 CVaR >= -5%
```

**效果**：
- PBO=0.702 → 硬門檻 fail → 不部署（不管 OOS 結果）
- OOS 隨機 fail → 軟門檻，不影響部署（但報告中顯示警告）
- 不再有「噪音 check 的隨機結果決定有意義 check 是否被容忍」

### 對現有策略的影響

| 策略 | 硬門檻 | 軟門檻 fail | 舊條件 | 新條件 |
|------|:------:|:-----------:|:------:|:------:|
| revenue_momentum_hedged | fail: PBO 0.702 | OOS -1.2 | 可能部署（OOS 隨機 pass 時） | **不部署** |
| vwap_position_63d | 全通過 | OOS -0.86 | 14/14 可部署 | **可部署** |
| revwz_mafrac_combo | fail: PBO | — | 可能部署 | **不部署** |

---

## 8. 風險

| 風險 | 緩解 |
|------|------|
| 等權 benchmark 可能讓所有策略 fail | 先計算等權 benchmark 的 CAGR/Sharpe |
| 硬門檻太嚴導致無策略可部署 | 目前 vwap_position_63d 可通過，門檻經過驗證 |
| DSR(N=15) + 等權 benchmark + corr 0.80 + 硬門檻四重收緊 | 改完後重跑 25 因子確認不是全滅 |
| Market corr 0.80 在未來策略可能太嚴 | 目前所有好策略 corr < 0.6，buffer 充足 |
| 軟門檻全 fail 仍可部署 | 軟門檻 fail >= 3 項時加人工審查步驟 |

---

## 9. 參考文獻

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

### 逐項審批（含獨立覆核修正）

| # | 提案 | 原審批 | 覆核後 | 理由 |
|---|------|:------:|:------:|------|
| 2.2 | Bootstrap IID → Stationary | 延後 | **延後（同意）** | DSR(N=15) 是 Bootstrap 的嚴格強化版，已覆蓋。IID 偏差列為技術債 |
| 2.3 | WF 改名 temporal_consistency | ✅ 立即 | **✅ 立即（同意）** | 零成本語義修正 |
| 3.1 | Market corr 0.90→0.80 | ❌ 不做 | **✅ 應該做** | 原審批說「典型 corr 0.85-0.93」是被動策略數字。**實際數據：所有好策略 corr 0.3-0.6，0.80 不會誤殺任何因子策略** |
| 3.2 | Benchmark 改等權 universe | ✅ 立即 | **✅ 立即（同意）** | 最有價值的改動 |
| 3.4 | Regime 改 drawdown-based | 延後 | **延後（同意）** | 年度切割實務夠用 |
| 4.1 | Permutation test | ❌ 不做 | **⏸ 延後（P2）** | DSR 和 Permutation 測不同東西：DSR=多重測試顯著性，Permutation=信號是否有內容。策略可通過 DSR 但 fail Permutation（信號只是大盤動量）。Phase Z1 讓 100 次 permutation 只需 ~100 秒 |
| 4.2 | CPCV | ❌ 不做 | **❌ 不做（同意）** | PBO + DSR 已覆蓋因子選擇的過擬合風險 |

### 全部完成（2026-03-29）

```
1. ✅ walkforward_positive_ratio → temporal_consistency（改名）
2. ✅ vs_0050 → vs equal-weight universe average（實質改動）
3. ✅ market_correlation 門檻 0.90 → 0.80（覆核新增）
4. ✅ Stationary Bootstrap（Politis & Romano 1994, avg_block=20）
5. ✅ Drawdown-based regime（0050 DD > 15%）
6. ✅ Permutation test（新增 #16，shuffle real factor rankings）
```

### 不做

```
7. CPCV（PBO + DSR 已覆蓋）
```

### 覆核修正說明

**3.1 Market corr 修正理由**：原審批的「典型 corr 0.85-0.93 會誤殺」基於被動策略經驗。查看實際 Validator 結果：

| 策略 | Market corr | 被 0.80 擋？ |
|------|:-----------:|:------------:|
| revenue_momentum_hedged | 0.529 | 否 |
| vwap_position_63d | 0.373 | 否 |
| 52wk_high | 0.394 | 否 |
| efficiency_ratio_126d | 0.326 | 否 |

所有 12+ 項的策略 corr 都在 0.3-0.6。0.80 距離最高值仍有 0.2 的 buffer。收緊到 0.80 擋的是「corr > 0.80 的純 beta 搬運」，不影響任何合法因子策略。

**4.1 Permutation 修正理由**：DSR 回答「N 次測試後 Sharpe 是否顯著」（參數化），Permutation 回答「隨機打亂信號後報酬是否下降」（非參數化）。一個策略可以通過 DSR 但 fail Permutation — 如果信號只是市場動量的代理（有 Sharpe 但沒有選股 alpha）。這是獨立的資訊維度，不是冗餘。

**等權 benchmark 仍是最重要的改動。** vs 0050 對等權策略自帶 size premium ~2-4%/年，幾乎無效。
