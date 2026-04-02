1. 用於 alpha research 太保守，CAGR ≥ 8%, OOS Sharpe ≥ 0.3, temporal_consistency ≥ 60% 過高，考慮進場和因子研究使用不同標準，放鬆 L1-L5 

- 系統回覆: 需要區分兩件事。L1-L5 是 evaluate.py 的因子篩選閘門，Validator 是 validator.py 的策略部署閘門。CAGR ≥ 8% 和 OOS Sharpe ≥ 0.3 是 Validator 的門檻，不在 L1-L5 裡。L1-L5 的門檻是 IC ≥ 0.02 / ICIR ≥ 0.30 / corr < 0.50 / fitness ≥ 3.0 / OOS IC 同號。

  分開看：
  - **L1 IC ≥ 0.02**：已加 60d slow-alpha bypass（|IC_60d| ≥ 0.03），合理
  - **L2 ICIR ≥ 0.30**：這是跨 4 個 horizon 的 median，已經不算嚴格。台股最強因子（revenue_acceleration）ICIR 0.63，0.30 是一半
  - **Validator CAGR ≥ 8%**：台灣無風險利率約 1.5%，8% 要求 6.5% 風險溢酬，對月頻策略合理。兩個因子都通過了
  - **Validator OOS Sharpe ≥ 0.3**：已是 soft check，不阻擋部署

  **結論**：目前門檻對「找到可交易的因子」已足夠寬鬆（revenue_acceleration 已通過全部 hard gate）。放鬆 L1-L5 會增加 false positive，不建議。

- 外部回覆：至少有一個強因子通過 是倖存者驗證，理想 L1-L5 的 pass rate 依序可以抓 30%, 45%, 65%, 55%, 75% 左右

- 系統回覆: 目前實際 pass rate（從 results.tsv 250+ 實驗）：L1 約 55%、L2 約 15%、L3+ 約 0%。L2 pass rate 15% 遠低於建議的 45%，但這反映台股因子空間本身就窄 — 大量 price/volume 因子在台股沒有持續信號。L1 55% 接近建議的 30%（偏高但合理，因為 agent 有 learnings 引導方向）。如果未來 L2 持續低於 20%，可以考慮放寬 ICIR 門檻到 0.25。

---

2. 考慮升級 AutoResearch 全變體族群，包含相似因子、不同 normalization、ranking vs z-score、lag variations，再算 rank IC dispersion 和 Sharpe dispersion  

- 系統回覆: 好建議，但和現有架構衝突。目前 autoresearch agent 每次只改 factor.py 產生一個因子，不會同時產生「同因子的 10 個 normalization 變體」。

  要做這件事需要改架構：
  1. Agent 產生一個基礎因子
  2. 系統自動產生 N 個變體（z-score / rank / winsorize / lag 1-5 等）
  3. 批次計算 IC dispersion

  這等於是 construction_sensitivity PBO 的「因子層面版本」。目前 construction_sensitivity 已經在 Validator 測 portfolio 建構穩定性。在 L2 層加「因子 normalization 穩定性」測試是有價值的，但工程量大（需改 evaluate.py 的單因子架構）。

  **建議列為未來 Phase，不在本輪做。**

- 外部回覆：有隱性風險，每次只產一個因子導致 normalization / lag / scaling 被隨機鎖定，短期應考慮對同一 factor 自動做 2-3 個 lightweight 變體，然後取 best ICIR，不算 dispersion

- 系統回覆: 同意「隨機鎖定 normalization」是隱性風險。2-3 個 lightweight 變體可以在 evaluate.py 內部自動做，不需要改 agent 架構。具體：agent 交出 factor.py 後，evaluator 自動跑 [raw, rank, z-score] 三個版本，取 best ICIR 的版本往下走。工程量小（~30 行），且不影響 agent 端。**值得做，列入本輪。**

---

3. L1 忽略 IC structure across horizons，應看整個 decay 並要求 sign consistent，考慮 mean(|IC| over horizons) ≥ 0.015 和 AND sign consistency ≥ 60%

- 系統回覆: L1 的設計意圖是**快篩**（30 個日期 × 20d IC，約 30 秒）。如果在 L1 就跑所有 horizon（5d/10d/20d/60d），時間會 4 倍變成 ~2 分鐘，失去快篩意義。

  目前已有 60d slow-alpha bypass（L1 20d fail 時額外檢查 60d），部分解決了 horizon 問題。

  `mean(|IC| over horizons) ≥ 0.015` + `sign consistency ≥ 60%` 作為 L1 的替代方案，比現有的 `|IC_20d| ≥ 0.02 OR |IC_60d| ≥ 0.03` 更全面，但計算量也更大。

  **務實折衷**：保持現有 L1 快篩。L2 已經看 4 個 horizon 的 median ICIR，sign consistency 可以加在 L2。

- 外部回覆：同意，考慮只在兩者都存在時檢查 sign(IC_20d) == sign(IC_60d)

- 系統回覆: 同意。在 L1 slow-alpha bypass 路徑裡加一行 sign consistency check：如果 20d IC 和 60d IC 符號相反，即使 60d IC 通過門檻也 fail。這能擋住「20d 做多、60d 做空」的矛盾因子。成本幾乎為零（已經算了兩個 IC）。**列入本輪。**

---

4. L2 上限有危險，應標記為 suspicious，然後丟去更嚴格測試，如 permutation test 或更嚴格 DSR    

- 系統回覆: 同意。目前 L2 上限 `MAX_ICIR_L2 = 1.00`（ICIR > 1.0 標為 suspicious）。代碼裡遇到 ICIR > 1.0 會直接 fail 並標記 "suspiciously high"。

  但「標記後丟去更嚴格測試」比「直接 fail」更好 — ICIR > 1.0 不一定是 bug，可能是短期數據的噪音。更好的處理：
  1. ICIR > 1.0 → 不直接 fail，標記 suspicious
  2. 自動觸發 permutation test（在 L2 階段就跑，不等 Validator）
  3. Permutation pass → 繼續 L3，fail → 拒絕

  **工程量中等**（需要在 evaluate.py 加入 L2 permutation），但邏輯上比現在更合理。可以在下一輪改進中做。

- 外部回覆：同意，ICIR > 1 通常來自 sample 太短、極端 outlier 或 leakage / bug，考慮當 ICIR > 1 時要求 effective sample size ≥ threshold，避免短期 lucky spike 通過 permutation

- 系統回覆: 好的補充。effective sample size 可以用 IC 序列的自相關結構估計：`ESS = N / (1 + 2 × sum(autocorr_k for k=1..lag))`。如果月頻 IC 有強自相關（如趨勢因子），ESS 會遠低於 N。當 ICIR > 1 且 ESS < 30 時，直接 fail 比跑 permutation 更快且更保守。**列為下輪改進。**

---

5. L3 的「4/6.5 年為正」太 regime-dependent，考慮 rolling window (% of positive rolling-1y IC ≥ 60%) 或 IC sign persistence test（Markov / runs test）   

- 系統回覆: 同意「年度正 IC 數」是粗糙的指標 — 2022 年一整年市場暴跌，所有因子 IC 都可能為負，不代表因子失效。

  Rolling window 方案更穩健：把 IC 序列切成 12 個月滾動窗口，計算「窗口內 IC 平均為正的比例」。這比固定年份邊界更平滑，不會被日曆年切割影響。

  IC sign persistence（runs test）也有價值 — 如果因子的 IC 正負號是隨機的（runs test p > 0.1），表示因子沒有持續性信號。

  **但 L3 目前不是 blocker**（revenue_acceleration 的 positive_years = 10/10 = 100%）。改進合理但優先級低。

- 外部回覆：不同意為低優先級，這會在你擴展因子類型時爆炸；目前沒問題可能是因為因子偏 quality, growth 或穩定型，若引入 value, mean reversion or macro timing 會系統性刪掉這些 alpha

- 系統回覆: 接受這個觀點。per_value 已經是 value 因子，如果未來研究員開始探索 mean reversion 或 macro timing 因子，固定年份邊界的 positive_years check 確實會系統性誤殺它們。**提升優先級，列入本輪。** 改為 rolling 12-month window 的正比例 ≥ 60%。

---

6. L4 偏向低 turnover 因子，考慮拆成 中低頻+(高頻/高turnover)兩條路，如 Sharpe ≥ threshold AND cost-adjusted return ≥ 0  

- 系統回覆: L4 的 fitness 公式是 `sqrt(returns_proxy / effective_turnover) × median_icir`。turnover 高的因子分母大，fitness 被壓低，確實偏向低 turnover。

  但本系統定位是**月頻再平衡的個人投資者**，高 turnover 策略的交易成本（台股來回 0.6%）會嚴重侵蝕 alpha。偏向低 turnover 是 feature not bug。

  如果未來要做高頻/日頻策略，確實需要第二條路（cost-adjusted return 門檻）。但目前不需要。

  **結論**：現階段不改。

- 外部回覆：同意，若未來做 intraday 或 stat arb，記得整個 evaluate pipeline 要 fork

- 系統回覆: 記錄。目前不需要 fork，但如果做 intraday 會在 CLAUDE.md 的 Reference Documents 表格加一行指向獨立的 evaluate_hft.py。

---

7. L5 + Validator 為雙重 OOS 懲罰，導致 double dipping 反效果，考慮 L5 保留 sign consistency 並移除 ICIR decay (留給Validator) 

- 系統回覆: **同意這是一個設計問題。** L5（evaluate.py）和 Validator（validator.py）各自有 OOS 驗證，但用的不是同一段 OOS 數據：

  | | OOS 期間 | 測的東西 |
  |---|---|---|
  | L5 | 滾動 549 天（IC 層面） | IC 方向一致 + ICIR 衰退 + 正向月 |
  | Validator | 滾動 549 天（策略層面） | OOS Sharpe ≥ 0.3（soft） |

  兩者的 OOS 窗口相同（都是 today-549d ~ today-90d 附近），**同一段數據被用了兩次**。雖然 L5 測的是 IC、Validator 測的是 Sharpe，但底層數據重疊。

  外部建議合理：
  - **L5 只保留 sign consistency**（IC 方向和 IS 一致）— 這是最不容易過擬合的指標
  - **移除 L5 的 ICIR decay check** — 留給 Validator 的 DSR + sharpe_decay 做更嚴格的策略層面驗證

  這樣 L5 變輕（只看方向），Validator 負責所有量化嚴格性。**合理且工程量小，建議做。**

- 外部回覆：同意，不過 L5 和 Validator 還是用同一段 OOS window，考慮切 OOS (OOS1（最近 549d 前半）給 L5，OOS2（最近 549d 後半）給 Validator)，避免 double dipping 且 Validator 變成真正 unseen

- 系統回覆: 很好的建議。549 天切兩半 = 各約 275 天（~13 個月）。L5 用前半（較舊），Validator 用後半（較新且真正 unseen）。這讓 Validator 的 OOS 成為 agent 從未見過的數據 — 即使 L5 結果間接洩漏了方向資訊（通過 learnings），Validator 的後半段數據仍然是乾淨的。

  工程量：改 evaluate.py 的 OOS 日期範圍（OOS_START ~ OOS_MID）和 validator.py 的 oos_start/oos_end（OOS_MID ~ today）。**列入本輪。**

---

## 改善計畫（第二輪）

根據外部第二輪回饋，以下為即將施做的改善項目。

### R2-1. L1 sign consistency check
- **問題**：slow-alpha bypass 路徑只看 |IC_60d| 門檻，沒有檢查 20d 和 60d 的 IC 方向是否一致
- **修正**：L1 bypass 時加 `sign(IC_20d) == sign(IC_60d)`，方向矛盾則不通過
- **位置**：evaluate.py L1 bypass 邏輯
- **工程量**：極小（1 個條件）

### R2-2. 因子自動 normalization 變體
- **問題**：agent 每次只產一個因子，normalization 被隨機鎖定（如只用 raw 沒試 rank）
- **修正**：evaluate.py 在收到因子值後，自動跑 [raw, rank, z-score] 3 個版本，取 best ICIR 往下走
- **位置**：evaluate.py main evaluation 路徑，_compute_ic 之前做 normalization
- **工程量**：小（~30 行，在現有 loop 外包一層 normalization 選擇）

### R2-3. L3 positive_years → rolling window
- **問題**：固定年份邊界的「正年數」check 對 value / mean reversion 因子不公平（2022 全年暴跌 → 所有因子都算負年）
- **修正**：改為 rolling 12-month window IC 平均為正的比例 ≥ 60%
- **位置**：evaluate.py L3 positive_years check
- **工程量**：中（需重寫 IC 年度統計邏輯）

### R2-4. L5 簡化 + OOS 切割
- **問題**：L5 和 Validator 用同一段 549 天 OOS 數據，構成 double dipping
- **修正**：
  1. L5 只保留 sign consistency（IC 方向和 IS 一致），移除 ICIR decay check
  2. OOS 549 天切兩半：L5 用前半（OOS1，~275 天），Validator 用後半（OOS2，~275 天）
  3. Validator 的 OOS 窗口成為 agent 真正未見過的數據
- **位置**：evaluate.py OOS 日期計算 + L5 gate 邏輯，validator.py oos_start/oos_end
- **工程量**：中（需要在兩個文件中統一日期分割邏輯）

### 施做順序

R2-1 → R2-2 → R2-4 → R2-3

R2-1 最小改動先做。R2-2 和 R2-4 互不依賴。R2-3 最後做（需重寫統計邏輯）。
全部改完後重跑 Experiment #25 驗證效果。

---

## 第三輪回饋

### 3a. L3 positive_years 門檻不合理

外部意見：台股 regime 切換很強，IC 很容易連續 1-2 年反向或震盪 around 0。4/6.5 年為正的要求會系統性刪除 value / mean reversion 因子。

系統回覆：同意，R2-3 已列入改善計畫（改為 rolling 12-month window）。但外部的觀察更深一層 — 問題不只是年份邊界，而是「IC 為正」本身在 regime 切換時不穩定。Rolling window 改善了邊界問題，但如果整段 2022-2023 IC 都為負（value 因子在成長股行情中），rolling 也救不了。

**進一步修正**：R2-3 的門檻從 ≥ 60% 降為 ≥ 50%（允許一半時間為負），配合 R2-4 的 L5 sign consistency 作為最終方向性檢驗。

### 3b. L3 correlation 門檻 0.5 太嚴

外部意見：台股因子高度集中（liquidity, momentum proxy, turnover 等本質不同但 IC 高度相關），0.5 門檻刪掉太多。

系統回覆：同意。台股 200 支的橫截面本身就窄，不同因子容易產生高 IC 相關性。目前 0.5 門檻下，autoresearch 250+ 實驗裡幾乎所有 L2+ 因子都被 L3 dedup 擋掉（和 quiet momentum 或 revenue_acceleration 相關 > 0.5）。

**修正**：`MAX_CORRELATION` 從 0.50 放寬到 **0.65**。這仍然能擋住真正的 clone（如 120d momentum vs 130d momentum），但允許本質不同但 IC 結構相似的因子通過。

### 3c. 替換門檻 1.3x 太嚴

外部意見：ICIR 0.50 的因子要替換需要 0.65（1.3x），在台股因子空間裡幾乎不可能。

系統回覆：同意。`REPLACEMENT_ICIR_MULTIPLIER = 1.3` 意味著新因子要比舊因子好 30% 才能替換。在 ICIR 0.3-0.6 的範圍，30% 提升（0.09-0.18）需要顯著的信號改善，門檻過高。

**修正**：`REPLACEMENT_ICIR_MULTIPLIER` 從 1.3 降為 **1.15**（15% 提升即可替換）。配合 `REPLACEMENT_MIN_ICIR = 0.20` 的絕對門檻，仍能防止垃圾因子替換好因子。

### 3d. L3 failure attribution

外部意見：記錄 L3 失敗原因（是 dedup 還是 positive_years）。

系統回覆：目前 L3 失敗時 evaluate.py 已記錄 `failure=f"corr={max_corr:.3f} with {corr_with}"` 或 `failure=f"positive_years={pos}/{total}"`，agent 可以在 learnings 中看到。但 learnings API 只回傳 bucketed 指標，agent 看不到具體的 corr 值和 correlated_with 名稱。

**修正**：在 learnings 的 failure 欄位裡加入 L3 失敗類型標記（`"L3_dedup"` 或 `"L3_stability"`），讓 agent 知道該往「不同方向」走還是「更穩定的同方向」走。

### 3e. High precision / low recall 問題

外部意見：系統是 high precision / low recall classifier。先提高 recall（放鬆中間層），再靠 Validator 控 precision。

系統回覆：**完全同意。** 這是本輪所有改善的核心思路：
- R2-1（sign consistency）= 不放鬆，加精準度
- R2-2（normalization 變體）= 提高 recall（同因子多個版本都試）
- R2-3（rolling window）= 放鬆 L3，提高 recall
- R2-4（OOS 切割）= 讓 Validator 成為真正的 precision 控制層
- 3b（correlation 0.65）= 放鬆 L3，提高 recall
- 3c（replacement 1.15x）= 放鬆替換，提高 recall

L1-L4 應該是「寬進」（recall 優先），Validator 負責「嚴出」（precision 優先）。

### 3f. Soft Gate 應有門檻嗎？

使用者問題：Soft Gate 現在完全僅供參考，是否不合理？

系統回覆：**合理的疑問。** 目前 soft check fail 只顯示 ⚠ 警告，不影響部署決策。這導致 soft check 等於不存在 — 沒有人會因為看到警告就不部署。

**建議改為「累積 soft fail 門檻」**：
- 單個 soft fail：允許，顯示警告
- **3 個以上 soft fail**：阻擋部署（等同 hard fail）
- 理由：1-2 個 soft warning 是正常的邊緣情況（如 MDD 44% > 40%），但如果 sharpe / max_drawdown / oos_sharpe / vs_ew_universe 全部 fail，策略顯然有系統性問題

這讓 soft check 有實際約束力，但單一 soft fail 不會過度懲罰。

---

## 更新後的改善計畫（合併第二+三輪）

| # | 項目 | 改動 | 工程量 |
|---|------|------|:------:|
| R2-1 | L1 sign consistency | bypass 時加 sign(IC_20d)==sign(IC_60d) | 極小 |
| R2-2 | 因子 normalization 變體 | 自動跑 [raw, rank, z-score] 取 best | 小 |
| R2-3 | L3 positive_years → rolling | rolling 12-month window ≥ 50% | 中 |
| R2-4 | L5 簡化 + OOS 切割 | L5 只看 sign，OOS 前半/後半分 L5/Validator | 中 |
| R3-1 | L3 correlation 放寬 | MAX_CORRELATION 0.50 → 0.65 | 極小 |
| R3-2 | 替換門檻放寬 | MULTIPLIER 1.3 → 1.15 | 極小 |
| R3-3 | L3 failure attribution | learnings 加 L3_dedup / L3_stability 標記 | 小 |
| R3-4 | Soft gate 累積門檻 | ≥ 3 soft fail → 阻擋部署 | 小 |

### 施做順序

R3-1 + R3-2（常數修改）→ R2-1（1 行條件）→ R3-3 + R3-4（小改動）→ R2-2（normalization）→ R2-4（OOS 切割）→ R2-3（rolling window）
