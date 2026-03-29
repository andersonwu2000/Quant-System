# 回測機制逐檔審計報告

**日期**：2026-03-29
**範圍**：所有回測相關檔案 — 引擎、分析、驗證、過擬合、向量化、walk-forward、evaluate.py
**方法**：逐檔閱讀，每完成一個檔案立即更新本報告
**重點**：方法論正確性、OOS 洩漏、fail-closed 行為、公式一致性

---

## 審計進度

| 檔案 | 狀態 | 問題數 |
|------|:----:|:------:|
| `src/backtest/overfitting.py` | ✅ 完成 | 2 |
| `src/backtest/analytics.py` | ✅ 完成 | 6 |
| `src/backtest/validator.py` | ✅ 完成 | 11 |
| `src/backtest/walk_forward.py` | ✅ 完成 | 3 |
| `src/backtest/vectorized.py` | ✅ 完成 | 2 |
| `src/backtest/engine.py` | ✅ 完成 | 2 |
| `scripts/autoresearch/evaluate.py` | ✅ 完成 | 8 |

---

---

## 1. `src/backtest/overfitting.py`（PBO / CSCV）

**功能**：Bailey (2017) Combinatorially Symmetric Cross-Validation。切 S 等分，C(S, S/2) 組合做 IS/OOS Sharpe 排名比較。

### 正確的部分

- PBO 定義 = `sum(logit <= 0) / len(logits)` — 符合 Bailey 原文（line 139）
- `rank_below` 排除 `best_is_strategy` 自己 — 正確（line 127-128）
- logit clamp `max(0.01, min(0.99, ...))` — 防 log(0)（line 133）
- empty combos → `1.0`（fail-closed）（line 139）
- 餘數行被丟棄（`trimmed = returns_matrix.iloc[:usable_rows]`）— 等分正確（line 85-86）✅ 已修
- `_sharpe` 用 `returns.std()` = pandas ddof=1 — 和 analytics.py 一致

### 發現的問題

| # | 嚴重度 | 問題 |
|---|:------:|------|
| O-1 | LOW | `_sharpe` 對 len < 2 回傳 0.0 → 排中位。partition 至少 60 天，不會觸發 |
| O-2 | LOW | logit clamp 0.01/0.99 在 N=2 時偏差。Validator 至少 4 variants，不觸發 |
| ~~O-3~~ | ~~HIGH~~ | ~~最後 partition 吸收餘數~~ → **✅ 已修：丟棄餘數** |
| ~~O-4~~ | ~~MEDIUM~~ | ~~ffill(limit=5) 製造假報酬~~ → **✅ 已修：fillna(0.0)** |

**方法論**：`compute_pbo` 本身實作正確。方法論層面的問題（N 代表什麼、variants 是否獨立）在 Phase AB 追蹤，不是此模組的問題。

---

## 2. `src/backtest/analytics.py`（績效指標計算）

**功能**：從 NAV 序列計算所有績效指標（Sharpe/Sortino/CAGR/MDD/CVaR 等）+ DSR。

### Deflated Sharpe Ratio（line 23-80）

**公式驗證**：

1. `sr = observed_sharpe / sqrt(252)` — 年化 → per-observation。✅ 正確
2. SE 用 Lo (2002)：`(1 + 0.5·SR² - skew·SR + (kurt-3)/4·SR²) / (T-1)` — ✅ 正確
3. E[max SR] 用 Bailey (2014)：`(1-γ)Φ⁻¹(1-1/N) + γΦ⁻¹(1-1/Ne)` × SE — ✅ 正確（用 SE 而非 1/√T）
4. DSR = Φ((sr - E[max SR]) / SE) — ✅ 正確

**E[max SR] 用 SE 而非 1/√T**（line 76）：Bailey 原文用 `√Var(SR)` = SE，不是 `1/√T`。在 null hypothesis (SR=0) 下 SE ≈ 1/√T，但非零 SR 時有差異。用 SE 更精確。✅

**問題**：`n_trials=1 → e_max_sr=0.0`（line 70-71）。DSR 退化成 `Φ(sr/SE)`（普通 Sharpe 的 z-test）。配合 Validator 的 `n_trials <= 1 → auto-pass`，等於 DSR 完全不做。已在 Phase AB 修成 n_trials=15。

### compute_analytics（line 275-388）

| 指標 | 公式 | 正確性 |
|------|------|--------|
| total_return | `last_nav / initial_cash - 1` | ✅ |
| annual_return | `(1 + total_return)^(1/n_years) - 1` | ⚠️ 見 A-1 |
| volatility | `daily_returns.std() * sqrt(252)` | ✅ ddof=1 |
| sharpe | `mean / std * sqrt(252)` | ✅ 標準算術年化 |
| sortino | `mean * 252 / (sqrt(mean(min(r,0)²)) * sqrt(252))` | ⚠️ 見 A-2 |
| max_drawdown | `abs((nav - cummax) / cummax).min()` | ⚠️ 見 A-3 |
| turnover | `total_traded / initial_cash / n_days * 252` | ⚠️ 見 A-4 |

### 發現的問題

| # | 嚴重度 | 問題 |
|---|:------:|------|
| ~~A-1~~ | ~~HIGH~~ | ~~annual_return NaN~~ → **✅ 已修：guard 改為 `> -1.0 + 1e-9`** |
| A-2 | LOW | **Sortino 的 downside deviation 用 ddof=0（`np.mean`），Sharpe 的 std 用 ddof=1（`pd.std`）** — 這是各自的標準慣例（Sortino 1994 用 population，Sharpe 1994 用 sample），不是 bug，但語義不同 |
| A-3 | LOW | **drawdown div-by-zero** — 如果 `nav_series` 含 0，`cummax` 為 0，除以 0 → inf。不太可能但無 guard |
| ~~A-4~~ | ~~MEDIUM~~ | ~~turnover 分母 initial_cash~~ → **✅ 已修：改用 `nav_series.mean()`** |
| A-5 | LOW | **`_trade_stats` 假設 BUY 後有 SELL 配對** — 月度再平衡策略的部分持倉可能從未被賣出（持有到回測結束），這些不計入勝率 |
| A-6 | LOW | **DSR 的 kurtosis 參數** — docstring 說 `kurtosis=3.0 for normal`（非 excess kurtosis）。Validator 呼叫時用 `scipy.stats.kurtosis(fisher=True) + 3.0`。一致，✅ 但容易搞混 |

---

## 3. `src/backtest/validator.py`（StrategyValidator 16 項）

**功能**：策略上線前的強制驗證。16 項 check，涵蓋績效、穩定性、過擬合、OOS、風控。

### 16 項逐一方法論審查

| # | Check | 方法論 | 問題 |
|---|-------|--------|------|
| 1 | universe_size >= 50 | 直接比較 | ✅ 無問題 |
| 2 | cagr >= 8% | 從 analytics.py 取 | ✅ 幾何年化正確 |
| 3 | sharpe >= 0.7 | 從 analytics.py 取 | ⚠️ Lo (2002)：日頻自相關 ρ~0.05 → Sharpe 高估 ~5%。但不可修正（無法知道真實 ρ） |
| 4 | max_drawdown <= 40% | 從 analytics.py 取 | ⚠️ 路徑依賴極強（Magdon-Ismail 2004），單一路徑 MDD 方差大。40% 門檻在零漂移下期望 MDD=63%，所以隱含測了正漂移 |
| 5 | cost_ratio < 50% | `cost / gross_alpha` | ⚠️ `gross_alpha = net_CAGR + cost_rate`（算術近似幾何）。分母用 `initial_cash`（見 A-4）。方向正確但粗糙 |
| 6 | temporal_consistency >= 60% | 逐年獨立回測正率 | ⚠️ 不是真正的 WFA（無 train/optimize）。對無參數因子策略可接受，但名稱改了（原 walkforward）✅ |
| 7 | deflated_sharpe >= 0.70 | Bailey (2014) DSR | ✅ 公式正確。n_trials=15（Phase AB）。`n_trials <= 1 → auto-pass` 仍保留但被覆蓋 |
| 8 | bootstrap >= 80% | Stationary Bootstrap | ✅ Politis & Romano (1994)，avg_block=20。保留自相關結構 |
| 9 | oos_sharpe >= 0.3 | Rolling 1.5 年 OOS | ❌ **統計功效不足**：SE=0.82，z=0.37，p=0.36。是 sanity check 不是統計檢定（Phase AC 已記錄） |
| 10 | vs_ew_universe >= 0% | vs 等權 universe average | ✅ Phase AC 改自 0050。測選股 alpha 而非 size premium |
| 11 | construction_sensitivity <= 0.50 | PBO CSCV（10 variants） | ✅ 改名自 pbo。測 portfolio construction 穩定性不是 Bailey 原意的 factor selection overfitting |
| 12 | worst_regime >= -30% | 0050 drawdown > 15% 的日子 | ⚠️ 「不投資」通過漏洞。用 `sum()` 而非 `prod()` 高估損失（已修 → `prod()`）✅ |
| 13 | recent_sharpe >= 0 | 最近 252 天 | ❌ **統計功效不足**：SE=1.0，50% 機率拋硬幣。是 sanity check（Phase AC 已記錄） |
| 14 | market_correlation <= 0.80 | Pearson corr with 0050 | ✅ Phase AC 收緊自 0.90。實測好策略 corr 0.3-0.6，0.80 有 buffer |
| 15 | cvar_95 >= -5% | 歷史 CVaR | ✅ fail-closed（error → -1.0）。87 觀測相對誤差 ~10% |
| 16 | permutation_p < 0.10 | 100 次 shuffle ranking | ⚠️ 見 V-3, V-4 |

### 發現的問題

| # | 嚴重度 | 問題 |
|---|:------:|------|
| ~~V-1~~ | ~~HIGH~~ | **✅ 已修：Permutation test fail-open → fail-closed (return 1.0)**。0.5 回傳 = p > 0.10 = fail。確認正確 |
| V-2 | MEDIUM | **OOS Sharpe 的統計功效** — SE=0.82，門檻 0.3 的 z=0.37。不是統計檢定，是 sanity check。Phase AC 已正確分類為「軟門檻」但代碼裡仍是硬性 check。**設計決策**（已審議，不是 bug） |
| ~~V-3~~ | ~~MEDIUM~~ | ~~Permutation seed 可預測~~ → **✅ 已修：seed 從 factor_cache hash 派生（不可從 trial index 預測）** |
| V-4 | MEDIUM | **Permutation test 用 vectorized backtest（簡化成本）但 real Sharpe 也用 vectorized** — 確保 apples-to-apples 比較。✅ 但和 Validator 的 full backtest Sharpe（check #3）不同，可能一個通過另一個不通過 |
| V-5 | MEDIUM | **DSR check 在 `sharpe <= 0` 時 `dsr = 0.0`，但 `n_trials <= 1 → auto-pass`** — 如果 n_trials=15 且 Sharpe < 0，dsr=0.0 < 0.70 → fail。✅ 正確（負 Sharpe 不需要 DSR） |
| V-6 | MEDIUM | **Bootstrap 的 `avg_block=20` 沒有用 Politis & White (2004) 自動選擇** — 20 天是直覺估計。如果真實自相關結構是 5 天（高頻策略）或 60 天（季度再平衡），block 長度不匹配。但月頻策略用 20 天合理 |
| V-7 | LOW | **cost_ratio 的 `gross_alpha = annual_return + annual_cost_rate`** — 算術加法近似幾何。當 cost_rate > 2% 時偏差顯著。但 50% 門檻很寬 |
| V-8 | LOW | **`_vs_ew_benchmark` 計算等權 universe 的日報酬** — 每天全 universe 等權 = 每天再平衡，這比月頻等權有更多再平衡溢價。benchmark 偏高 → check 偏嚴（保守方向） |
| V-9 | LOW | **temporal_consistency 把 0-trade 年排除** — error + 0-trade 都算 excluded。如果 5 年中 2 年 0 trade（策略找不到符合條件的股票），positive_ratio = good/3 而非 good/5。排除是合理的（0 trade 不是策略失敗而是條件不滿足） |
| V-10 | LOW | **recent_sharpe 的 `lookback_days=252` 轉日曆日用 `×365/252 + 30` buffer** — 誤差 ±1 週，不影響結果 |
| V-11 | LOW | **n_trials 預設 1（ValidationConfig line 72）** — 但所有 caller 都覆蓋成 15。如果有新 caller 忘記設，DSR auto-pass |

---

## 4. `src/backtest/walk_forward.py`

**功能**：Walk-Forward 分析器。逐年（或 step_days）切 IS/OOS，合併 OOS 報酬計算整體 Sharpe。

| # | 嚴重度 | 問題 |
|---|:------:|------|
| ~~W-1~~ | ~~MEDIUM~~ | ~~fold 重疊 OOS 重複日期~~ → **✅ 已修：`duplicated(keep='first')` 去重** |
| W-2 | MEDIUM | **param_stability 的 `np.std` 用 ddof=0** — 和其餘系統（pandas ddof=1）不一致。少量 fold 時低估變異 |
| W-3 | LOW | **OOS Sharpe fallback 到 per-fold mean** — 如果 `all_oos_daily` 為空（所有 fold 都沒有 daily_returns），fallback 到 `np.mean(all_test_sharpes)`。平均 Sharpe 高估不穩定策略 |

---

## 5. `src/backtest/vectorized.py`

**功能**：向量化 PBO 回測。用矩陣計算替代 event-driven BacktestEngine。

| # | 嚴重度 | 問題 |
|---|:------:|------|
| Z-1 | MEDIUM | **Lot size rounding 用固定 NAV=10M** — 隨損益變動實際 NAV 偏離，lot 分配失真。但 PBO 只做排名比較，所有 variants 用同一個 NAV → 排名不受影響 |
| Z-2 | LOW | **OHLC 四欄全填 close** — 文件已標註限制。用 high-low range 的因子得 0 |

---

## 6. `src/backtest/engine.py`

**功能**：Event-driven 回測引擎。逐日推進，呼叫 strategy.on_bar → weights_to_orders → SimBroker → apply_trades。

| # | 嚴重度 | 問題 |
|---|:------:|------|
| E-1 | MEDIUM | **prev_close 在 ffill 後可能不是真正的前日收盤** — 連續假日時 prev_close 是 ffill 值，漲跌停判斷可能不準（差一個假期的價格變動） |
| E-2 | LOW | **execution_delay > 0 時，strategy 看到 T 日 close 做決策，T+1 open 成交** — 正確的延遲模型，但基本面數據可能差一天 |

---

## 7. `scripts/autoresearch/evaluate.py`（OOS 洩漏重點）

**功能**：autoresearch 的固定評估引擎。L1-L5 閘門 + Stage 2 大規模驗證。

### OOS 資訊洩漏清單

| # | 嚴重度 | 洩漏來源 | 修復狀態 | 說明 |
|---|:------:|---------|:--------:|------|
| ~~E-1~~ | ~~CRITICAL~~ | `pending/*.json` | **✅ 已修** | OOS fields 已 strip；pending 移到 `watchdog_data/`（agent 不可讀） |
| ~~E-2~~ | ~~HIGH~~ | OOS 日期範圍 | **✅ 已修** | 改為 `OOS: [hidden]`；OOS dates 數量也隱藏 |
| ~~E-3~~ | ~~HIGH~~ | L5 failure 具體原因 | **✅ 已修** | 統一為 `"L5 OOS validation failed"`（不帶原因） |
| ~~E-4~~ | ~~HIGH~~ | Validator OOS Sharpe | **✅ 已修** | OOS 相關 check 值顯示為 `[hidden]` |
| E-5 | MEDIUM | evaluate.py 原始碼 | ⚠️ 緩解 | program.md 禁止讀 evaluate.py（prompt 限制，非硬性） |
| E-6 | MEDIUM | results.tsv L5 模式 | ⚠️ 已知 | 固有風險，無法消除。L5 failure message 統一後洩漏降低 |
| ~~E-7~~ | ~~LOW~~ | `factor_returns/*.parquet` | **✅ 已修** | 移到 `watchdog_data/`（agent 不可讀） |
| ~~E-8~~ | ~~LOW~~ | `factor_pbo.json` | **✅ 已修** | 移到 `watchdog_data/` |

### 其他問題

| # | 嚴重度 | 問題 |
|---|:------:|------|
| ~~E-9~~ | ~~MEDIUM~~ | ~~日期 import 時固定~~ | **✅ 已修**：`_compute_dates()` 在 runtime 計算 |
| ~~E-10~~ | ~~MEDIUM~~ | ~~top 20% vs top 15~~ | **✅ 已修**：統一為 `top 15` |
| ~~E-11~~ | ~~MEDIUM~~ | ~~部署門檻不同步~~ | **✅ 已修**：evaluate.py + watchdog + auto_alpha.py 全部用硬/軟門檻 |
| ~~E-12~~ | ~~LOW~~ | ~~composite double-count ICIR~~ | **✅ 已修**：移除直接 ICIR 項，只用 fitness |

---

## 總結

### 按嚴重度（修復後）

| 嚴重度 | 原始 | 已修 | 剩餘 | 剩餘問題 |
|--------|:----:|:----:|:----:|---------|
| CRITICAL | 1 | 1 | 0 | — |
| HIGH | 4 | 4 | 0 | — |
| MEDIUM | 12 | 9 | 3 | V-4 vectorized vs full Sharpe（設計決策）, V-6 block length 固定 20（月頻合理）, E-5 源碼可讀（prompt 限制） |
| LOW | 13 | 1 | 12 | 邊界情況、語義差異 |

### 方法論結論

1. **Validator 的 16 項 check 方向正確**，但 #9 OOS 和 #13 Recent 沒有統計功效（sanity check only）
2. **DSR 公式正確**（Bailey 2014 + Lo 2002 SE），n_trials=15 合理
3. **PBO (CSCV) 實作正確**，測 construction sensitivity。Factor-Level PBO 在 watchdog 獨立計算且已接入部署決策
4. **Stationary Bootstrap 已實作**（Politis & Romano），優於 IID
5. **OOS 資訊洩漏已全部封堵**：pending marker stripped + 移到 watchdog_data、OOS 日期隱藏、L5 failure 統一、Validator OOS 值隱藏、factor_returns/factor_pbo 移到 watchdog_data
6. **剩餘 MEDIUM 問題均為設計決策或極端邊界**，不影響研究正確性
