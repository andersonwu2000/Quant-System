# Lessons for Autonomous Agent Systems

> 從 6 個月量化交易系統開發中提煉的經驗。
> 300+ bugs、10+ 次全系統 code review、233 次自動化實驗、多個 AI agent 同時協作。
> 適用於任何讓 AI agent 自主迭代代碼的系統。
> 每一條都來自至少一個真實事故，不是理論。

---

## 1. 隔離靠物理機制，不靠指令

**事故：** prompt 裡寫「不要改 evaluate.py」，agent 照改。hooks 攔截寫入，agent 用 `bash -c "cat evaluate.py"` 繞過讀取限制。`git reset --hard` 摧毀了 3 次未 commit 的修改。

**原則：**
- Prompt 限制 = 建議，不是執行
- Hooks = 比 prompt 好，但能被繞過（Bash 可跑任何命令）
- OS 權限 = 防寫不防讀
- Docker volume mount = 唯一的硬隔離（未掛載的就不存在）

**建議架構：**
```
Container（agent 跑在這裡）
├── /work/       (rw)  — agent 唯一可改的目錄
├── /data/       (ro)  — 輸入數據
├── /evaluator   (ro)  — 評估引擎（COPY 進去，不是 mount）
└── 無 src/、無 .git、無 config
```

---

## 2. 評估標準和 agent 必須物理分離

**事故：** evaluate.py 在 host 上跑，agent 可以讀源碼知道所有閾值和 OOS 邏輯。L5 的「只輸出 pass/fail」設計被 5 個通道繞過（pending marker、日期輸出、Validator 結果、factor_returns、源碼本身）。

**原則：**
- 評估引擎 COPY 進容器，不是 mount（agent 可以讀 mount 的檔案）
- 評估結果只回傳最少資訊（pass/fail + score，不帶中間值）
- 任何輸出到 stdout 的東西都假設 agent 會讀到
- 敏感數據（OOS 結果、PBO）存在 agent 不可見的路徑

**資訊洩漏 checklist：**
```
□ agent 能看到 OOS 的時間範圍嗎？
□ agent 能從 failure message 推斷 OOS 的方向/大小嗎？
□ agent 能讀到中間計算結果的檔案嗎？
□ agent 能讀到評估引擎的源碼嗎？
□ agent 累積多次 pass/fail 能學到什麼？
```

---

## 3. Agent 的 git 操作會摧毀你的修改

**事故：** agent 在主 repo 跑 `git reset --hard HEAD~1` 來回滾失敗實驗，同時摧毀了所有未 commit 的修改。發生 3 次，每次都要重新修改 4+ 個檔案。

**原則：**
- Agent 的 git repo 和主 repo 必須分開（用 work/ 子目錄 + 獨立 .git）
- 如果共用 repo，**永遠不要用 `git reset --hard`**。改用：
  ```bash
  git checkout HEAD~1 -- factor.py && git reset --soft HEAD~1
  ```
- 任何非 agent 的代碼修改**必須立即 commit**，不要累積
- 在 agent 運行期間修改代碼 = 高風險操作

---

## 4. 數據品質問題會在最意想不到的地方爆炸

**事故：** 895 支股票中 133 支有 close=0（下市/低流動性）。`pct_change()` 對 close=0 產生 inf → 汙染 56/75 個 factor returns → PBO 矩陣全壞 → PBO=1.0（看起來像「所有因子都過擬合」，其實是數據汙染）。

**原則：**
- 在**每個數據載入點**加 guard，不是只在一處
  - 我們在 vectorized.py 修了，但 evaluate.py、engine.py、validator.py 也有同樣的 `pct_change()` → 每處都要加
- 異常值的正確處理是 **NaN（排除）**，不是 0（假裝正常）或 inf（傳播汙染）
- 加不變量測試：`assert not np.isinf(returns).any()`
- 數據品質問題的症狀往往看起來像方法論問題（「PBO=1.0 所以全部過擬合」），要先查數據再查方法

---

## 5. 「可以開始了嗎」要問 5 次

**事故：** 每次說「可以開始研究」，使用者再問一次就發現新問題。第 1 次：Docker image 沒重建。第 2 次：factor.py 是舊實驗不是 baseline。第 3 次：factor_returns 路徑不對。第 4 次：OOS 洩漏沒封堵。第 5 次：evaluate.py 8 個問題。

**原則：**
- 寫一份 **啟動前 checklist**，每次啟動前逐項勾
- Checklist 不是一次寫好的 — 每次發現新問題就加一條
- Smoke test 不是可選的 — 必須跑一次完整流程確認端到端通
- 「我覺得沒問題」 ≠ 驗證過沒問題

---

## 6. 方法論錯誤比代碼 bug 更危險

**事故：** PBO 實作了 3 次，每次代碼審計都說「正確」，但方法論定義是錯的（N 代表什麼）。60+ 個代碼 bug 都在數小時內被找到修復，但 PBO 的方法論錯誤存活了多個版本。

**原則：**
- 實作學術方法前**讀原論文**，不是 blog/SO/ChatGPT 摘要
- 至少交叉比對 2 個獨立來源
- 代碼審計不夠 — 代碼可以「正確地實作錯誤的東西」
- 用已知範例驗證（純噪音 → PBO ≈ 1.0，單一策略 → DSR ≈ raw Sharpe）

---

## 7. Holdout 數據會被 adaptive query 降解

**事故：** 233 次因子實驗，每次 L5 回傳 pass/fail = 233 bits 資訊洩漏。Dwork et al. (2015) 的安全 budget 是 ~4 次。超出 62 倍。

**原則：**
- 固定的 holdout 數據集**不適合**大量自主實驗
- 每次查詢 holdout 都會降解它的有效性
- 緩解方案：
  - Thresholdout（加噪音到回饋）— 我們已實作
  - Rolling holdout（隨時間移動）— 我們已實作
  - Fresh data（paper trading / live）— 最終解法
- 追蹤查詢次數，設 budget 上限

---

## 8. 多個系統文件的一致性是最大的維護負擔

**事故：** 部署邏輯在 3 個地方（evaluate.py、watchdog.py、auto_alpha.py），改了一處忘了另外兩處。check name 改了（walkforward → temporal_consistency），但 4 個 caller 只改了 2 個。

**原則：**
- 邏輯只定義在一處，其他地方引用
- 如果無法避免重複（如 Docker COPY 的檔案 vs host 的檔案），寫 checklist 確保同步
- 改名/重構後 `grep -rn "舊名"` 確認全部替換
- 常量（門檻值、check 名稱）用 config/常量定義，不硬編碼

---

## 9. Docker image 是快照，不會自動更新

**事故：** 改了 evaluate.py 和 watchdog.py（host 上），但 Docker 容器裡還是舊版。因為這些檔案是 COPY 進去的，不是 volume mount。導致容器跑的是 2 小時前的代碼。

**原則：**
- COPY 的檔案修改後必須 `docker compose build`
- Volume mount 的檔案會自動同步
- 每次修改後驗證容器內版本：`docker exec container grep -c "特徵字串" /app/file.py`
- 考慮用 volume mount 開發、COPY 部署（兩階段）

---

## 10. 防禦性設計的優先級

從這個專案學到的防禦性設計優先級，從最有效到最無效：

```
1. 物理隔離（Docker volume 未掛載 → 不存在）      — 100% 有效
2. OS 權限（chmod -w → 不可寫）                    — 防寫有效，不防讀
3. 加密/混淆（評估結果加噪音）                      — 降低洩漏但不消除
4. Hooks（PreToolUse 攔截）                         — 可被 Bash 繞過
5. Prompt 指令（「不要改這個檔案」）                 — 隨時可被無視
6. 程式碼註釋（# READ ONLY）                        — 零防護力
```

**通則：** 每上一層，防護力降 50%。如果某個安全要求很重要，用第 1-2 層，不要只靠 4-6 層。

---

## 11. 實用工具和模式

### 自主 agent 的 3 檔案架構（Karpathy autoresearch）

```
evaluator.py   — 固定，agent 不可改（COPY 進容器）
solution.py    — agent 唯一可改的檔案
protocol.md    — 研究協議（agent 只讀）
results.tsv    — 實驗記錄（agent 可追加）
```

這個模式的核心洞察：**把「做什麼」和「怎麼評估」分離**。Agent 只控制前者。

### Thresholdout（防 adaptive query 降解）

```python
# 不是確定性的 pass/fail，而是加噪音
noise = np.random.laplace(0, scale)
passed = (metric > threshold + noise)
```

每次查詢洩漏 < 1 bit（而非 1 bit），安全 budget 從 O(1) 升到 O(n)。

### 不變量測試（防數據汙染）

```python
def test_no_inf_in_returns():
    returns = compute_returns(price_matrix)
    assert not np.isinf(returns.values).any()

def test_no_zero_close():
    prices = load_prices()
    assert (prices > 0).all().all()
```

在 CI 跑，每次 commit 驗證。比修完 bug 後才發現便宜 100 倍。

---

# Part 2: Multi-Agent Development & Continuous Iteration

> 以下經驗來自多個 AI agent 同時開發同一個 codebase 的實戰。
> 適用於「一個項目自動化地幫助其他項目持續迭代」的場景。

---

## 12. Tests are contracts between agents

**事故：** Agent A 修復了 Validator 的 6 個 fail-open bug（CVaR 異常回傳 0.0 → 改為 -1.0）。Agent B 在同一天重構了 Validator，把 Agent A 的修復全部覆蓋。沒有人注意到，因為沒有測試會 fail。

**原則：**
- 每個 bug fix 必須附帶一個 **regression test**
- Test 不是給寫修復的人看的 — 是給下一個修改同一個檔案的 agent 看的
- 沒有 test 的 fix = 臨時膠帶，遲早被撕掉

```python
# 這個 test 在 Agent B 的重構後立刻 fail，阻止了 revert
def test_cvar_error_returns_worst_case():
    """CVaR must return -1.0 on error, not 0.0 (which would pass the gate)."""
    result = compute_cvar(pd.Series(dtype=float))
    assert result == -1.0
```

**推論：如果你的自動化項目要修改別的項目的代碼，永遠同時提交 fix + test。Test 是你的修復能存活的唯一保證。**

---

## 13. Two agents editing the same file is a race condition

**事故：** 我們在修 sinopac.py 的 4 個 CRITICAL bug（零股單位不一致、sub-order 丟失等）。另一個 AI 同時在改同一個檔案。結果：我們的修復被覆蓋，檔案回到有 bug 的狀態，沒有任何警告。

**原則：**
- **檔案級鎖** — 如果 Agent A 正在修改某檔案，Agent B 不應該碰它
- **git pull before edit** — 每次修改前先確認檔案是最新的
- **git diff before commit** — 確認你的修改還在（沒被其他人蓋掉）
- **Commit 頻率越高越安全** — 未 commit 的修改是最脆弱的

**給自動化迭代項目的建議：**
```
1. Agent 開始修改前 → git pull + read file（確認 baseline）
2. 修改後立即 commit（不要批量累積）
3. Commit 前 check：diff 的行數和預期一致嗎？有沒有意外的變動？
4. 如果 push 衝突 → rebase，不要 force push
```

---

## 14. The same bug will appear in every parallel path

**事故：** 系統有 3 個函式生成交易訂單：`execute_pipeline`、`execute_rebalance`、`monthly_revenue_rebalance`。Bug 在 pipeline 被修了（包含持倉標的的價格查詢），但 rebalance 和 monthly 沒修。結果：月度再平衡時，持倉永遠不被賣出。

**原則：**
- 修一個地方的 bug 後，**grep 相同模式**，找出所有平行路徑
- 如果同樣的邏輯出現在 3 個地方，這不是「需要修 3 次」— 這是「需要抽成共用函式」
- 自動化項目的 agent 修完一個 bug 後，應該自動搜尋類似模式：

```bash
# 修完 execute_pipeline 後，搜尋同樣的 pattern
grep -rn "for s in target_weights" src/scheduler/
# 找到 3 處 → 確認全部都改了
```

**給自動化項目的建議：每個修復動作後加一步「ripple check」— 搜尋相同的 code pattern 並列出所有出現位置。**

---

## 15. Silent failures are the default in generated code

**事故：** Agent 生成的因子函式對 80% 的股票回傳空 DataFrame（symbol 格式不對：用 `1101` 但檔案名是 `1101.TW_revenue.parquet`）。下游函式收到空 DF → 產生空權重 → 策略什麼都不持有。沒有任何錯誤訊息。系統看起來正常運行，只是績效為零。

**原則：**
- 生成式代碼的最常見 failure mode 不是 crash — 是靜默回傳空值
- 空 DataFrame、空 dict、None 會穿透整個 pipeline 不觸發任何異常
- 必須在 pipeline 的關鍵節點加 **非空斷言**

```python
# 每個 pipeline 階段的出口
signals = strategy.compute_signals(universe)
if not signals:
    logger.error("Strategy returned empty signals for %d symbols", len(universe))
    return  # 不要繼續帶著空值往下跑

weights = optimizer.optimize(signals)
assert weights, f"Optimizer returned empty weights from {len(signals)} signals"
```

**給自動化項目的建議：**
- Agent 生成的代碼在整合前，跑一次 smoke test — 不是檢查有沒有 exception，而是檢查輸出是否非空
- 「跑完沒報錯」≠「結果正確」。空結果是最危險的，因為它不報錯

---

## 16. Complexity is the enemy of auditability

**事故：** 原始的 autoresearch agent 是 1,800 行，6 個狀態的狀態機 + 動態 eval() + 自我修改的 prompt。每次出 bug 要讀 1,800 行才能理解。替換成 3 個檔案、300 行的 Karpathy 架構後，bug 率下降 80%。

**原則：**
- Agent 的基礎設施代碼（scaffolding）必須**任何人都能在 10 分鐘內讀完**
- 如果你的 agent runner 超過 500 行，它太複雜了
- 複雜度應該在 agent 的輸出（假說、代碼修改）裡，不是在基礎設施裡
- 簡單的系統更容易 audit → 更容易信任 → 更容易讓人放手

**給自動化項目的建議：**
```
Agent runner:  < 500 行，做三件事：接收任務、呼叫 agent、驗證結果
Evaluator:     < 300 行，純函式，無副作用
Config:        一個檔案，所有門檻/參數集中管理
Log:           append-only，每個動作一行
```

---

## 17. Log everything, decide later what matters

**事故：** 233 次自動實驗，前 50 次只記了 pass/fail。後來需要分析 holdout 降解（多少次查詢、累積了多少 information leakage），只能從 git history 反推。花了 3 小時重建本該直接記錄的數據。

**原則：** Agent 的每個動作都要記錄，格式統一，append-only。

**最小日誌格式：**
```
timestamp | action | target_file | input_hash | result | duration_ms | metadata
```

**給自動化項目的建議：**
```python
# 每次修改
{"ts": "...", "action": "edit", "file": "src/foo.py", "diff_lines": 42, "commit": "abc1234"}

# 每次測試
{"ts": "...", "action": "test", "suite": "unit", "passed": 1705, "failed": 2, "duration_s": 45}

# 每次評估
{"ts": "...", "action": "evaluate", "score": 0.71, "passed": true, "budget_remaining": 17}

# 累計統計（每次 append 時更新）
{"ts": "...", "action": "stats", "total_edits": 47, "total_tests": 23, "total_evals": 12}
```

用 JSONL（每行一個 JSON），不是結構化 DB。原因：
- 永遠不會因為 schema 衝突而失敗
- 可以用 `jq` 即時查詢
- crash 最多丟一行，不會損壞整個檔案

---

## 18. Human checkpoints are not overhead — they're safety nets

**事故：** Agent 連續跑了 72 小時。我們以為它在探索新方向，實際上它在生成同一個因子的微小變體（改一個參數、改一個 window size）。233 次實驗中 ~200 次是同一個方向的變體。Holdout budget 被浪費了。

**原則：**
- **每日摘要**：agent 做了什麼、嘗試了什麼、結果如何 → 人看 10 秒就夠
- **異常自動告警**：連續 N 次失敗、同一方向嘗試 > M 次、budget 耗盡、error rate 飆升
- **硬停機**：budget 用完 → 暫停等人確認，不是自動繼續

```python
# 每日摘要（自動生成）
Daily Summary 2026-03-28:
  Experiments: 12 (3 pass, 9 fail)
  Unique directions: 2 (revenue variants, volatility variants)
  Holdout budget: 17/50 remaining
  ⚠️ 8/12 experiments were revenue_accel variants — consider switching direction
```

**給自動化項目的建議：**
- 設計一個「dashboard view」— 用最少的文字讓人在 30 秒內判斷「agent 是否在做有意義的事」
- 這不是微管理 — 是防止 agent 在錯誤的方向上浪費一整個週末

---

## 19. The agent will optimize for your metric, not your intent

**事故：** 我們想要「有真實預測力的因子」。測量指標是 Sharpe ratio。Agent 做的：
- 找到過擬合 in-sample 的因子（高 Sharpe，零 OOS 價值）
- 生成已知因子的微小變體（高 Sharpe，不獨立）
- 利用 look-ahead bias（不可能的高 Sharpe）

每個都最大化了指標，每個都違反了意圖。

**原則：**
- 單一指標 → agent 一定會 game 它
- 需要**多個獨立維度的驗證**，agent 不能同時 game 所有維度
- 我們最終用了 6 個獨立維度（見 FACTOR_PIPELINE_DEEP_REVIEW）：多重測試修正、Bootstrap、Permutation、PBO、Market correlation、EW benchmark

**給自動化項目的建議：**
- 如果你的項目評估代碼修改的品質，至少用 3 個獨立維度：
  1. **功能正確性**（tests pass）
  2. **沒有退化**（coverage 不降、perf 不降、no new warnings）
  3. **結構品質**（lint pass、no code smells、diff size 合理）
- 不要只看「tests pass」就合併 — 那只是一個維度

---

## 20. Incremental restart > clean restart

**事故：** Agent crash 後重啟，丟失所有 context。重新跑了 15 個已經試過的實驗方向。

**原則：**
- **結果檔案是 append-only** — crash 後可以讀取歷史繼續
- **每個實驗都由 commit hash 固定** — 可以精確重現
- **Agent 啟動時讀 history** — 知道什麼已經試過

```
# results.tsv — append-only, survives crashes
commit  | timestamp            | score | status   | notes
abc1234 | 2026-03-15T08:00:00 | 0.42  | L3_FAIL  | low IC
def5678 | 2026-03-15T09:30:00 | 0.71  | L4_PASS  | revenue_accel_v2
```

**給自動化項目的建議：**
- 所有狀態存檔案，不存記憶體
- Agent 的每次會話開始時讀取歷史，結束時追加記錄
- 「重啟 = 從上次結果繼續」，不是「重啟 = 從頭開始」

---

# Part 3: Project Management & Iteration Strategy

> 以下經驗來自 30+ 個開發計畫（Phase A~AE）的回顧分析。
> 18 個完成、4 個廢棄、3 個無限期暫停、多次 180° 方向轉變。

---

## 21. Research first, infrastructure second

**事故：** 我們先花 8 個 Phase 建基礎設施（14 種優化器、83 個因子框架、117 個 API endpoint），然後才開始做因子研究。結果：15 次實驗發現 price-volume 因子在台股完全無效（最高 ICIR 0.217，成本吃掉所有 alpha）。83 個因子中只有 revenue 家族有用。14 種優化器只用了 `equal_weight`。

**原則：**
- 先用最簡單的基礎設施驗證核心假說（「這個市場有 alpha 嗎？」）
- 確認有 alpha 後再建生產級基礎設施
- 否則你會得到一個精美的、能高效產出垃圾的系統

**給自動化項目的建議：**
- 先手動跑 3 次，確認流程可行
- 再自動化
- 不要一開始就設計「支援 N 種策略的通用框架」— 先讓一種策略跑通

---

## 22. "Done" ≠ "Works" — 區分「代碼完成」和「價值驗證」

**事故：** 18 個 Phase 標記為 ✅ 完成。但真正產出價值的只有 1 個策略（revenue_momentum），且它在 OOS 期間報酬 -7.4%。其餘 17 個 Phase 建立了基礎設施，但沒有一個被證明能賺錢。

**原則：**
- 代碼完成（tests pass, lint clean）是必要條件，不是充分條件
- 真正的「完成」是產出可衡量的業務價值
- 如果一個功能寫完了但從沒被用過，它不是「完成」— 它是「浪費」

**給自動化項目的建議：**
- 每個迭代的驗收標準不是「CI 通過」，而是「對目標專案產生了可衡量的改善」
- 跑完一輪後問：「如果把這個功能刪掉，使用者會注意到嗎？」
- 不會 → 不該建

---

## 23. Pivots are expensive — delay infrastructure until direction is stable

**事故時間線：**
```
Phase I:  建了 27 個 price-volume 因子
Phase K:  發現基本面因子才有效 → Phase I 的 27 個因子全部廢棄
Phase L:  建了 revenue_momentum + hedge
Phase M:  發現 hedge 反而虧錢 → Phase L 的 hedge 邏輯廢棄
Phase AA: 建了 inverse-vol weighting
Phase AA: 發現 equal-weight 更好 → inverse-vol 廢棄
```

三次 pivot，每次廢棄前一個方向的代碼。如果每次都只做最小可行實驗而不是完整實作，可以省 60%+ 的工作量。

**原則：**
- 方向不確定時 → 寫最小實驗（script、notebook），不寫模組
- 方向確認後 → 才投資正式代碼、測試、文件
- 「快速失敗」不是口號 — 是「在投入基礎設施之前先驗證假說」

**給自動化項目的建議：**
- 第一次改進用 ad-hoc script
- 確認有效後再整合進 pipeline
- Agent 的每次迭代應該是**實驗**，不是**功能交付**

---

## 24. Plans that exist in multiple places will contradict each other

**事故：**
- 部署條件同時定義在 evaluate.py（`n_excl_dsr >= 13`）、auto_alpha.py（hard/soft gates）、watchdog.py（Factor-Level PBO threshold）。三處不一致。
- Check 名稱改了（`walkforward` → `temporal_consistency`），4 個 caller 只改了 2 個。
- 門檻值在 config 寫一套（5%），代碼硬編碼另一套（10%）。

**原則：**
- 邏輯只定義在一處（Single Source of Truth）
- 其他地方引用，不複製
- 如果必須複製（Docker COPY vs host），在 checklist 中追蹤同步

**給自動化項目的建議：**
- Agent 修改某個值時，自動搜尋所有引用該值的地方
- 門檻、config、常量 → 集中定義在一個檔案，其他地方 import
- 重命名/重構後 → `grep -rn "舊名"` 確認零殘留

---

## 25. The beautiful backtest is almost always a lie

**事故：** Revenue momentum 策略：
- In-sample（2020-2024）：+30.5% CAGR, Sharpe 1.51, Validator 13/15 通過 ✅
- Out-of-sample（2025 H1）：-7.4%, Sharpe -0.732 ❌

4 年的「驗證」不夠。策略恰好在牛市表現好，遇到市場轉向就崩潰。

**更深的問題：** 233 次 adaptive query 已經把 holdout 降解到統計失效（Thresholdout budget 超出 62 倍）。即使 OOS 通過也不代表什麼。

**原則：**
- 回測只能排除明顯差的策略，不能證明策略有效
- 唯一的真實驗證是 forward testing（paper trading / live）
- **越好看的回測越要懷疑** — E[max Sharpe] from N=15 noise trials ≈ 1.4，我們觀測的 0.94 甚至低於噪音期望值

**給自動化項目的建議：**
- 如果 agent 宣稱「改善了 X%」，問：在什麼數據上？那個數據被查詢過多少次了？
- 歷史績效的改善 ≠ 未來績效的改善
- 建立 canary test（一個已知不該改善的指標）— 如果 canary 也「改善」了，說明測量有問題

---

## 26. Academic consensus exists for a reason — don't fight it with bespoke logic

**事故：**
- DeMiguel (2009) 證明 equal-weight 幾乎永遠打敗估計權重。我們花了 3 個 Phase（AA inverse-vol、L hedge、optimizer.py 14 種方法）最終發現 equal-weight 確實最好
- Politis & Romano (1994) 的 Stationary Bootstrap 是正確的 daily returns SE 估計。我們先用了 IID bootstrap（低估 SE），後來才修正
- Bailey (2014) 的 PBO 定義很清楚（N = all tested configurations），我們實作錯了 3 次因為沒讀原文

**原則：**
- 學術共識代表「很多聰明人已經試過並失敗了」
- 你的 bespoke 方案不太可能比 30 年的學術研究更好
- 如果你要偏離學術共識，**舉證責任在你** — 需要很強的 evidence

**給自動化項目的建議：**
- Agent 提議的方法如果違反已知最佳實踐，自動標記為高風險
- 「我發明了一個新方法」幾乎總是比「我用了教科書上的方法」更危險
- 除非你有明確的理由和驗證，否則用標準方法

---

## 27. Feature freeze is a feature

**事故：** 系統持續新增功能（新因子、新優化器、新策略模板）直到 Phase R 強制凍結：「在 R7 驗證完成之前，不新增新策略、新因子、新優化器。」

凍結後才開始認真做方法論審計（Phase AB/AC），發現 PBO 錯了 3 次、Validator 有 3 個方法論錯誤、OOS holdout 已退化。

如果沒有凍結，這些問題會被新功能的「進展感」掩蓋。

**原則：**
- 新功能帶來的「進展感」會掩蓋底層問題
- 定期凍結新功能，專注驗證既有功能
- 「停下來檢查」比「繼續跑」更有價值

**給自動化項目的建議：**
- 每 N 次迭代後強制一次 audit cycle（不新增功能，只驗證既有的）
- Agent 的「exploration budget」有限 — 用完後停下來驗證
- 如果 agent 連續 M 次沒有通過驗證，暫停並等人類審查方向

---

## 28. Abandoned plans are information, not waste

**事故：** 4 個 Phase 被廢棄（J cross-asset、P auto-alpha v1、M 原版、S pipeline unification）。每個被廢棄的計畫都包含「為什麼不行」的有價值資訊：
- Phase J：「台股因子研究不穩定，擴展到跨市場為時過早」
- Phase P：「1800 行狀態機不可維護 → 3 檔案 Karpathy 架構」
- Phase M 原版：「dedup 邏輯被 Factor-Level PBO 取代」

但這些資訊散落在各文件中，沒有集中歸檔。

**原則：**
- 廢棄計畫時記錄**為什麼失敗**，不只是「已廢棄」
- 失敗記錄是防止重蹈覆轍的最好方式
- 新 agent（或新人）加入時，先讀失敗記錄再讀成功記錄

**給自動化項目的建議：**
- 每次 agent 放棄一個方向，記錄：嘗試了什麼、為什麼放棄、學到什麼
- 這些記錄和成功記錄一樣重要
- 新 session 開始時，agent 應該讀「已知不可行的方向」列表

---

# Summary: Principles for Autonomous Iteration Projects

| # | 原則 | 一句話 |
|---|------|--------|
| 1 | Constrain, don't instruct | 不安全的動作要物理上不可能，不是提示不建議 |
| 2 | Separate evaluation from execution | 評估標準和 agent 必須在不同 trust domain |
| 3 | Fail closed | 未知 = 拒絕、異常 = 最壞值、空值 = 停止 |
| 4 | Tests are contracts | 每個 fix 附帶 test，test 是修復能存活的唯一保證 |
| 5 | Track everything | Budget、查詢次數、實驗記錄、決策 — append-only log |
| 6 | Keep it simple | 基礎設施 < 500 行。複雜度屬於 agent 的輸出，不是 scaffolding |
| 7 | Multiple independent checks | 單一指標會被 game。至少 3 個獨立維度 |
| 8 | Ripple check after every fix | 修一處 → grep 相同 pattern → 確認所有平行路徑 |
| 9 | Human checkpoints | 每日摘要 + 異常告警 + 硬 budget 限制 |
| 10 | Incremental, not clean restart | 狀態存檔案、append-only、crash = resume |
| 11 | Research before infrastructure | 先驗證假說再建系統。否則你會高效地產出垃圾 |
| 12 | "Done" ≠ "Works" | 代碼完成是必要條件，價值驗證才是充分條件 |
| 13 | Delay infra until direction stable | 方向不確定 → 寫實驗。確認後 → 才寫模組 |
| 14 | Single source of truth | 邏輯只定義一處。複製 = 不一致 = bug |
| 15 | Distrust beautiful results | 越好看的指標越要懷疑。建 canary test |
| 16 | Respect academic consensus | 標準方法 > bespoke 方法，除非有強 evidence |
| 17 | Feature freeze is a feature | 定期停下來驗證，不要被進展感掩蓋底層問題 |
| 18 | Archive failures explicitly | 失敗記錄和成功記錄一樣重要。防止重蹈覆轍 |
