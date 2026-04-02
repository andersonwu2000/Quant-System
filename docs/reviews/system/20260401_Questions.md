1. sharpe, deflated_sharpe, bootstrap_p_sharpe_positive, permutation_p 指標之間高度重疊，導致過度保守

**部分同意。** 四個 check 測的東西不完全一樣：

| Check | Null Hypothesis | 獨特價值 |
|-------|----------------|---------|
| sharpe ≥ 0.7 | 絕對門檻（經濟可行性） | 最基本的「值不值得交易」 |
| deflated_sharpe | SR 在 N 次測試後是否顯著 | 多重測試校正（唯一做這件事的） |
| bootstrap_p | P(SR > 0) via block bootstrap | 考慮自相關的穩健性（月頻策略的序列相關） |
| permutation_p | 打亂因子-股票映射後 SR 是否下降 | 唯一測「選股信號本身」的（非 portfolio 層面） |

**但實務上確實過度保守。** 如果 bootstrap_p=99%（SR 幾乎確定 > 0），sharpe ≥ 0.7 就是冗餘的 — 一個 check 已經蘊含另一個。
建議：保留 deflated_sharpe + permutation_p 作為 hard（兩者測的 null 完全不同），sharpe 和 bootstrap_p 降為 soft。或者只保留 deflated_sharpe 作為統計顯著性的唯一 hard gate。

- 回復: 問題在於拒絕域（rejection region）高度重疊，bootstrap_p 高 ⇒ DSR 幾乎一定高，endorse

- 系統回覆: 同意 endorse。反向不一定成立（DSR 高不保證 bootstrap_p 高，因為 DSR 含 N 校正而 bootstrap 不含），但實務上兩者 rejection region 重疊度 >90%。行動方案：sharpe + bootstrap_p 降為 soft，保留 deflated_sharpe + permutation_p 作為 hard。

---

2. temporal_consistency 定義有偏差，小樣本時 Sharpe 很不穩，更合理的是Sharpe > 0.3 或 t-stat > 1

**同意觀點但實作沒有此問題。** 代碼裡 WF 每個 fold 都是完整日曆年（`f"{year}-01-01"` to `f"{year}-12-31"`），不存在碎片年。temporal_consistency 計算的是「OOS Sharpe > 0 的年份比例 ≥ 60%」。

但同意 Sharpe > 0 作為「正年」的定義太寬鬆 — 年化 Sharpe 0.01 也算正。改為 Sharpe > 0.3 或 t-stat > 1 是更嚴謹的定義，但這會讓 check 更難通過，不是更容易。如果目的是避免「假陽性正年」，可以改；如果目的是降低保守度，不應改。

- 回復: 更嚴謹但不更保守的方法不是改 threshold，而是改統計量，用 Median Sharpe 或 sign test + magnitude weighting，如 score = sign(SR) * min(|SR|, cap)，避免 SR=0.01 被當成有效，但不會像 hard threshold 那麼 brutal

- 系統回覆: 好建議。sign test + magnitude weighting 比 hard threshold 更 robust — 不會被單一極端年份翻轉結果，也不會把 SR=0.01 當有效。可以實作為 `score = mean(sign(SR_i) * min(|SR_i|, 2.0))`，門檻 > 0。留作後續優化。

---

3. DSR 的 N 應當設為 15

**同意需要修正 N，但不一定是 15。** 目前 N=262（results.tsv 全部實驗），這過度懲罰了 — 262 個實驗中大量是不相關的因子（動量、波動率、法人），不是同一搜索空間。

Bailey 的 DSR 假設 N 個策略來自同一假說空間。正確的 N 應該是**獨立方向數**（聚類後），和 factor-level PBO 的 N 定義保持一致。目前 watchdog 的 `factor_pbo.json` 有 `n_independent` 欄位。

固定 N=15 也可以，但不如用動態的 n_independent — 隨實驗累積自動調整，比硬編碼更準確。

- 回復: 同意，注意　clustering 方法會直接影響 DSR，考慮 correlation threshold 固定（例如 0.7）或 clustering 方法固定（hierarchical / k-means）

- 系統回覆: 同意 clustering 方法需要固定。目前 watchdog.py 用 correlation threshold 0.50（L671），選 cluster 中位數因子。建議：統一 DSR 和 PBO 都用同一個 n_independent，correlation threshold 固定 0.50（已固定），clustering 方法固定為 greedy correlation clustering（目前的實作，非 hierarchical）。在 EXPERIMENT_STANDARDS.md 中明文記載以防未來漂移。

---

4. oos_sharpe 與 recent_period_sharpe 高度相關，recent 改成「decay test」或「performance slope」

**同意高度相關。** 代碼：
- `oos_sharpe`：滾動 OOS 窗口（today-549d ~ yesterday），約 1.5 年
- `recent_period_sharpe`：最近 252 交易日

兩者時間窗口大幅重疊（recent 完全被 OOS 包含）。兩個都是 soft check，所以不影響 pass/fail 結果，但確實冗餘。

改為 decay test（比較前半 vs 後半 Sharpe 的衰退比例）或 performance slope（IC 隨時間的線性趨勢）是更有資訊量的設計 — 能偵測「因子正在失效」而非只看「最近還好不好」。

- 回復: 同意，注意即使是 soft check，feature redundancy 會降低診斷能力，導致 fail 時你不知道是「短期問題」還是「長期退化」，可以考慮 Sharpe(first_half) - Sharpe(second_half)

- 系統回覆: 同意。`recent_period_sharpe` 改為 `sharpe_decay`：`Sharpe(後半) - Sharpe(前半)`，門檻 > -0.5（允許最多衰退 0.5）。這比兩個重疊的 Sharpe 區間更有診斷價值 — 能直接看出因子是在改善還是退化。

- 額外回復: 在實作 sharpe_decay 時，請務必考慮 T 檢定 (t-stat)。因為「後半段比前半段 Sharpe 低 0.5」在只有 2 年的數據下可能只是隨機波動，但在 10 年數據下就是顯著退化。

- 系統回覆: 同意。裸 Sharpe 差值不含樣本量資訊。實作方案：計算 `delta_SR = SR(後半) - SR(前半)`，再用 Lo (2002) 的 SE 公式估計差值的標準誤 `SE(delta) ≈ sqrt(2/T_half) * (1 + SR²/4)`，得到 `t = delta_SR / SE(delta)`。門檻改為 `t > -2.0`（即衰退不顯著於 5% 水準）。這樣 2 年數據的 -0.5 衰退（t ≈ -1.1，不顯著）不會被誤判，但 10 年數據的 -0.5 衰退（t ≈ -2.5，顯著）會被正確標記。

---

5. vs_ew_universe 可以考慮 beta neutralization 或直接 regression alpha

**同意方向，但工程成本較高。** 目前 `vs_ew_universe` 只比較策略 gross return vs EW benchmark，沒有控制任何 risk factor。

- **Beta neutralization**：策略 return - beta × market return，測 alpha 而非 total return。需要估計策略的 market beta，額外引入一個參數。
- **Regression alpha**：Fama-French 迴歸取截距項。需要建構 SMB/HML/MOM 因子（台股版），工程量大。

務實建議：先做 beta neutralization（只需 0050.TW），留 Fama-French 作為未來 Phase。beta neutralization 的實作只需 3 行：`alpha_ret = strat_ret - beta * mkt_ret`，beta 用 OLS 估計。

- 回復: 同意，注意 beta 是 time-varying 的，全期間 OLS → 會 bias，考慮 60d 或 120d rolling beta

- 系統回覆: 同意 rolling beta 更準確。120d rolling 是合理選擇（和策略月頻再平衡匹配，涵蓋約 6 個月）。實作：`beta_t = OLS(strat_ret[-120:], mkt_ret[-120:])`，每月更新一次。alpha_ret = strat_ret - beta_t × mkt_ret。工程量小（~15 行），可以和 vs_ew_universe 的月頻再平衡修正一起做。

---

6. construction_sensitivity 定義不明

**定義如下：** 用 10 個 portfolio 建構變體（top_n ∈ {8,12,15,20} × weighting ∈ {equal, signal, inverse_rank}）各自跑回測，取得日報酬序列，然後跑 Bailey (2017) CSCV PBO。

PBO 衡量的是：如果你在 IS 選了最好的建構方式，它在 OOS 表現低於中位數的機率。PBO > 0.50 表示 IS 最佳的建構方式在 OOS 更可能表現不佳 — 建構方式被過擬合了。

**注意：這不是 factor-level PBO**（跨因子選擇偏誤），而是 construction-level PBO（同一因子的不同實作方式是否穩定）。兩者容易混淆。

門檻：PBO ≤ 0.50（即 IS 最佳在 OOS 仍有 ≥ 50% 機率高於中位數）。

- 回復: 同意，注意使用者很容易誤解這個數字代表「整體 overfitting 風險」

- 系統回覆: 同意。已在 EXPERIMENT_STANDARDS.md 和 validator.py 的 detail 欄位中標註「Portfolio construction variant stability (not Bailey factor-level PBO)」。報告的 summary 輸出也已加上此說明。如果仍有混淆風險，可以考慮改名為 `portfolio_construction_pbo` 以區分。

---

7. CVaR 門檻對中小型股、動能策略偏嚴，對台股 borderline

**部分同意。** 門檻是 daily CVaR(95%) ≥ -5%，即最差 5% 交易日的平均損失 < 5%。

台股特性：漲跌停 ±10%，中小型股波動大，動能策略在反轉日損失集中。但目前兩個因子都通過了：
- revenue_acceleration：CVaR = -2.47%
- per_value：CVaR = -3.02%

所以這個門檻目前不是 blocker。如果未來有中小型股因子被擋，可以考慮放寬到 -7% 或改為 soft check。**目前不需要改。**

- 回復: 同意，補充 CVaR 在 tail clustering 時會失效（regime shift）

- 系統回覆: 正確。CVaR 假設 tail 分佈穩定，但 regime shift（如 2020 COVID、2022 升息）會讓歷史 CVaR 低估未來 tail risk。目前作為 soft check 影響有限。如果未來要強化，可以加 conditional CVaR（只看 crisis regime 的 CVaR）或 worst-case scenario analysis，但優先級低於其他修正。

---

8. annual_cost_ratio 的定義，gross alpha 怎麼估？before cost return 已經包含 noise，是否考慮 signal return（pre-trade theoretical）

**目前的做法：** `gross CAGR = net CAGR + annual commission cost`，用算術加法近似。annual_cost_ratio = annual_cost / gross CAGR。

**問題：** gross return 包含了 noise（市場波動），不純粹是 alpha 貢獻。signal return（因子預測的理論報酬）更能反映「成本吃掉了多少 alpha」，但需要額外計算因子的預期報酬率（從 IC × cross-sectional vol 估計），工程量大。

**務實看法：** 目前策略的 cost_ratio 都很低（revenue_acceleration 4%，per_value 7%），遠低於 50% 門檻。除非做高頻因子（換手率極高），否則這個 check 不太可能成為 blocker。算術近似的誤差在 cost < 2% 時可忽略（約 0.01%）。**不需要改。**

- 回復: 同意

---

9. 是否有 factor exposure control / orthogonality，檢查 beta, size, value, momentum 等等？

**目前沒有。** 只有 `market_correlation ≤ 0.80` 檢查市場 beta，沒有 size/value/momentum factor exposure 的控制。

已在本次修正中新增 `factor_attribution` 描述性欄位（soft，不擋部署），報告策略和市場的相關性。但尚未做 Fama-French 風格的因子分解。

**建議分兩步：**
1. 短期：加 beta neutralization（只需 0050.TW），作為 `vs_ew_universe` 的改良
2. 長期：建構台股版 SMB/HML/MOM 因子，做完整 factor attribution

- 回復: 這是正確 roadmap，但若沒有 factor control，你的 validation 還不算完成。你在做 value（per_value）和 revenue acceleration（可能是 growth / momentum 混合）可能導致 loading 在已知因子上

- 系統回覆: 同意 validation 不完整。per_value 幾乎確定是 pure value loading（它字面上就是 -PER）。revenue_acceleration 可能是 growth + momentum 混合（營收加速 → 股價動能）。但對本系統定位（個人投資者），loading 在已知因子不是「錯」— 問題是你要知道自己在 loading 什麼。短期行動：加 rolling beta neutralization。中期：建台股 SMB/HML/MOM 做 attribution。這兩步能回答「per_value 是否只是 value ETF 的替代品」。

---

10. PBO 的策略變體是否有被保留？ 我懷疑在前方的相關性測試就先被丟掉了

**不會。兩者在不同層級運作，不互相干擾。**

- **L3 dedup**（evaluate.py）：比較的是**不同因子之間**的 IC series 相關性。例如 quiet_momentum 和 revenue_acceleration 的 IC 是否高度相關。如果 corr > 0.50，新因子被視為 clone 而拒絕。
- **construction_sensitivity PBO**（validator.py）：比較的是**同一個因子的 10 個建構變體**。例如 revenue_acceleration 用 top-8 equal vs top-20 signal 的日報酬差異。

L3 只過濾「和已知因子太像的新因子」，不會碰到 construction variants — 因為 variants 是在 Validator 內部動態產生的（`_VariantStrategy` wrapper），不經過 evaluate.py 的管線。

**但有一個邊緣情況：** 如果 autoresearch agent 自己嘗試了 top-8 和 top-20 作為兩個獨立實驗，L3 的 IC-series dedup 可能會擋掉第二個。不過 agent 通常不會這麼做 — 它改的是因子邏輯（factor.py），不是建構參數。

- 回復: PBO 不完整，是非常局部的 search space 裡做 PBO，若 avg_pairwise_corr < 0.8 則 PBO 不可信，考慮新增 AutoResearch → correlation clustering → 代表策略 → PBO

- 系統回覆: 部分同意。10 個建構變體的 avg pairwise corr 確實可能 > 0.8（它們都是同一個因子的微調），這讓 CSCV 的 IS/OOS 排名比較缺乏區分度，PBO 值不穩定。

  但 watchdog 已有第二層 PBO（factor-level PBO，watchdog.py L609-744）：用 correlation clustering（threshold 0.50）選代表因子，再對代表因子跑 CSCV。這正是外部建議的「AutoResearch → clustering → 代表策略 → PBO」。

  **真正的 gap 是**：construction_sensitivity 的 PBO 可能不可信（10 個高相關變體），但它目前是 hard check。可以考慮：
  1. 加 avg_pairwise_corr 檢查，若 > 0.8 則 PBO 結果標為 "low confidence"
  2. 或將 construction_sensitivity 降為 soft，讓 factor-level PBO（watchdog 層）作為主要過擬合控制

-------------------------------------------------------------------

 1. 「Harvey 修正」的重複懲罰 (L2 門檻)
   * 代碼實證：factor_evaluator.py 中的 adjusted_icir_threshold 屬性。

   1     # 門檻 = base * sqrt(1 + log(max(N, 1)))
   2     # N = self.total_tested (目前為 262)
   * 衝突點：在 L2 階段，你使用了 total_tested（所有實驗）來提高 ICIR 門檻。而在最後的 Validator 階段，你又使用了 DSR（同樣是基於 N 的懲罰）。    
   * 後果：這屬於 「雙重計稅」。AI 在 L2 被提高後的門檻（約 0.35）篩選掉了一次，好不容易過關後，在 Validator 又被 DSR
     按同樣的邏輯折現一次。這會導致 L2 之後幾乎沒有因子能活下來，這解釋了為什麼你的 status.md 中 L3/L4/L5 的數量全是 0。

  2. 「L5 OOS」的時間長度陷阱
   * 邏輯設計：L5 使用的是最近 549 天（1.5 年）的滾動樣本外（OOS）數據。
   * 衝突點：台股的基本面因子（如營收加速）具有強烈的 「週期滯後性」。1.5 年的時間長度往往只能覆蓋一個特定的子週期（例如只有多頭，或只有盤整）。  
   * 風險：如果這 1.5 年剛好是「成長股狂飆期」，優秀的「價值因子」在 L5 會因為 Sharpe 低於 0.3 而被 100% 誤殺。
   * 建議：L5 的 OOS 判定應包含一個「Regime 補償」，如果 0050 在 OOS 期間 Sharpe 為負，則對策略的 Sharpe 要求應相應降低。

  3. 「L3 IC 相關性」的去重偏誤
   * 代碼邏輯：L3 階段會檢查新因子與現有因子庫的 IC 相關性，若 corr > 0.5 則丟棄。
   * 問題點：你目前的因子庫中最強的是 revenue_acceleration。AI 產出的 262 個實驗中，很多基本面變體雖然與它相關性 > 0.5，但可能在 「風控端」 或    
     「持倉分布」 上有顯著改進（例如 MDD 更小）。
   * 後果：L3 門檻過於粗魯地切斷了「進化路徑」。它只允許「完全不同」的因子進入，而不允許「更好的同類」進入。
   * 建議：將 L3 門檻改為：如果 corr > 0.5 但 Sharpe 提升超過 20%，則允許替換（Replacement）而非直接丟棄。

  ---

  我發現的「隱藏地雷」：L1 的 IC 計算方式
  我注意到 factor_evaluator.py 的 _compute_ic 是使用 Spearman Rank Correlation。這在單因子測試中沒問題，但：
   * 錯誤點：它沒有對 「行業 Beta」 進行預處理。
   * 現象：很多因子通過 L1 是因為它們無意中抓到了「半導體行業的群漲」，而不是抓到了「個股的 Alpha」。到了 L5
     回測扣除行業偏誤後，這些因子會集體崩盤。

  我的最終修正建議清單：

   1. 解耦 L2 門檻與 DSR：
       * L2 的 N 不應使用 total_tested（總實驗數），而應改用 directions_tested（獨立方向數，建議固定為 15）。這能釋放被「過度懲罰」的因子。       
   2. 實作 L3 替換機制：
       * 允許新因子透過「優幣驅逐劣幣」的方式進入 L4，而不僅僅是看 IC 相關性。
   3. L5 Sharpe 門檻動態化：
       * min_oos_sharpe 應設定為 max(0.3, benchmark_sharpe * 0.8)，確保在大盤環境極差時，防禦型因子不會被誤殺。

-------------------------------------------------------------------
系統回覆（逐項）
-------------------------------------------------------------------

### 新 Issue 1：L2 Harvey 修正與 DSR 雙重懲罰

**觀點為假（前提錯誤）。** 外部提到的 `adjusted_icir_threshold` 存在於舊的 `src/alpha/auto/factor_evaluator.py`（L94-102），但 autoresearch 管線用的是 `scripts/autoresearch/evaluate.py`，兩者完全獨立。

evaluate.py 的 L2 門檻是固定的 `MIN_ICIR_L2 = 0.30`（L62），**沒有 Harvey 校正**，不隨實驗數量變動。`factor_evaluator.py` 是舊的研究管線（Phase W 時代），autoresearch 不使用它。

**不存在雙重懲罰。** L2 = 固定 0.30，DSR = Validator 階段用 N 校正，兩者在不同階段、不同邏輯。

---

### 新 Issue 2：L5 OOS 1.5 年時間長度陷阱

**觀點部分合理，但 oos_sharpe 是 soft check，不是 hard gate。** L5 在 evaluate.py 的判定條件是：
- OOS IC 方向與 IS 一致（同號）
- OOS ICIR 衰退 ≤ 60%
- OOS 正向月 ≥ 50%

這些都不要求 Sharpe ≥ 0.3。`oos_sharpe ≥ 0.3` 只在 Validator（validator.py）中出現，且是 **soft check**（SOFT_CHECKS 集合，L142），不會阻擋部署。

Regime 補償的建議合理但複雜度高。目前 soft check 不阻擋，所以不是優先項。

---

### 新 Issue 3：L3 IC 相關性去重偏誤

**觀點為假（替換機制已存在）。** evaluate.py L1048-1060 已實作 replacement 機制：

```
can_replace = (
    correlated ICIR > 0
    AND median_icir >= 1.3 × correlated_icir
    AND median_icir >= 0.20
    AND replacement_count < 10
)
```

如果新因子和舊因子 corr > 0.5，但新因子的 ICIR 是舊因子的 1.3 倍以上，允許替換（不丟棄）。這正是外部建議的「優幣驅逐劣幣」機制。門檻比外部建議的 20% Sharpe 提升更嚴格（要求 30% ICIR 提升），但機制已存在。

---

### 隱藏地雷：L1 IC 沒有行業 Beta 預處理

**觀點合理，但需要量化影響才能判斷優先級。** Spearman IC 確實不控制行業效應 — 如果半導體 10 支同漲，因子恰好選了半導體，IC 會虛高。

但這在台股 200 支 universe 中的實際影響取決於行業集中度。台股前 200 大中半導體約佔 30-40 支，如果因子系統性偏好半導體，IC 確實會被行業 beta 污染。

**修正方案**（如果要做）：IC 計算前對因子值和 forward return 都做行業中性化（減去行業均值）。這是量化研究的標準做法，工程量約 20 行代碼。但改了之後所有歷史 IC 基準都要重算。

---

### 最終修正建議回覆

| 建議 | 判定 | 理由 |
|------|:----:|------|
| 1. 解耦 L2 與 DSR | **不需要** | L2 沒有 Harvey 校正，不存在雙重懲罰 |
| 2. L3 替換機制 | **已存在** | evaluate.py L1048-1060，ICIR 1.3x 替換 |
| 3. L5 Sharpe 動態化 | **低優先** | oos_sharpe 是 soft check，不阻擋部署 |
| 隱藏地雷：行業中性化 | **值得做** | 但需要重算基準，建議作為獨立 Phase |

-------------------------------------------------------------------
改善計畫（即將施做）
-------------------------------------------------------------------

根據所有外部意見和內部驗證，以下為統一的改善計畫。全部施做，不分短期長期。

### 1. DSR N 值統一（修 bug）
- **問題**：DSR 用 N=262（全部實驗），PBO 用 n_independent（聚類後），定義不一致
- **修正**：DSR 改用 `n_independent`（從 factor_pbo.json 讀取），和 PBO 統一
- **位置**：evaluate.py L1709-1738（回退本次的修改）
- **影響**：revenue_acceleration DSR 從 0.44 大幅提升（N 從 262 降到 ~15）

### 2. sharpe + bootstrap_p 降為 soft
- **問題**：和 deflated_sharpe 拒絕域重疊 >90%，過度保守
- **修正**：HARD_CHECKS 移除 `sharpe` 和 `bootstrap_p_sharpe_positive`，移入 SOFT_CHECKS
- **位置**：validator.py L135-144
- **影響**：hard gate 從 10 個降為 8 個，但統計控制不降（DSR + permutation_p 覆蓋）

### 3. recent_period_sharpe → sharpe_decay（含 t-stat）
- **問題**：和 oos_sharpe 時間窗口重疊，冗餘且無診斷價值
- **修正**：改為 `Sharpe(後半) - Sharpe(前半)`，用 Lo (2002) SE 算 t-stat，門檻 t > -2.0
- **位置**：validator.py _check_factor_decay 方法
- **影響**：能區分「短期波動」和「長期退化」

### 4. vs_ew_universe 加 rolling beta neutralization
- **問題**：策略 total return vs EW，沒有控制 market beta
- **修正**：策略 return 先減去 `beta_t × mkt_ret`（120d rolling OLS），再和 EW 比
- **位置**：validator.py _get_ew_annual + vs_ew_universe check
- **影響**：per_value 等 value 因子不再因為市場 beta 而被懲罰

### 5. construction_sensitivity 加可信度標記
- **問題**：10 個建構變體 avg pairwise corr 可能 > 0.8，PBO 不可信
- **修正**：計算 avg pairwise corr，若 > 0.8 在 detail 標記 "low confidence"
- **位置**：validator.py _compute_pbo 方法
- **影響**：報告透明度提升，不改 pass/fail 邏輯

### 6. 行業中性化 IC
- **問題**：Spearman IC 不控制行業效應，半導體群漲會污染 IC
- **修正**：IC 計算前，因子值和 forward return 各減去行業均值
- **位置**：evaluate.py _compute_ic，需要行業分類數據
- **影響**：所有歷史 IC 基準需要重算，L1/L2 門檻可能需要微調

### 7. 台股因子 attribution（SMB/HML/MOM）
- **問題**：不知道策略 loading 在哪些已知因子上
- **修正**：建構台股版 size/value/momentum 因子，在 Validator 報告中做迴歸分解
- **位置**：新增 src/backtest/factor_attribution.py
- **影響**：部署前能看到「per_value 有 85% 是 value loading」

### 8. temporal_consistency 改 sign test + magnitude weighting
- **問題**：SR > 0 定義太寬，SR=0.01 也算正年
- **修正**：`score = mean(sign(SR_i) × min(|SR_i|, 2.0))`，門檻 > 0
- **位置**：validator.py temporal_consistency check
- **影響**：更 robust，不被極端年份或微小正值翻轉

### 施做順序

1 → 2 → 3 → 4 → 5 → 8 → 6 → 7

前 5 項改 validator.py，第 6 項改 evaluate.py（需解鎖 read-only），第 7 項新增模組。
全部改完後重跑 Experiment #25 驗證效果。