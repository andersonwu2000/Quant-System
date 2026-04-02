# AutoResearch System Review

> Reviewer: Claude Opus 4.6 | Date: 2026-04-02
> Scope: Full system review — architecture, methodology, security, operations, code quality

---

## Executive Summary

AutoResearch is a well-architected autonomous factor mining system built on the Karpathy autoresearch pattern. The 3-container Docker isolation (Agent / Evaluator / Watchdog) is a strong design choice, and the L0-L5 gate system with progressive filtering is methodologically sound. However, there are several areas where the system could be significantly improved, ranging from statistical methodology gaps to operational blind spots and potential overfitting vectors that the current design doesn't fully address.

**Overall assessment: 7.5/10** — Production-quality infrastructure with some methodology and operational gaps that should be addressed before scaling up.

---

## 1. Statistical Methodology

### 1.1 Composite Score Formula Is Weak

**File:** `evaluate.py:1680-1683`

```python
composite = (
    fitness * 1.5
    + (positive_years / max(total_years, 1)) * 2.0
)
```

Problems:
- **fitness 本身包含 median_icir**（line 1102: `fitness = sqrt(returns_proxy / effective_turnover) * median_icir`），所以 composite 基本上就是 ICIR 的非線性變換加上 stability ratio，缺乏獨立維度
- **returns_proxy = |IC_20d| * 10000** — 這是一個任意的倍數，沒有經濟學意義。IC 0.03 變成 300 "returns"，但真實的 portfolio return 取決於 holding period、universe size、weighting scheme
- **positive_years 的權重 2.0 相對於 fitness 1.5 太弱** — 一個 fitness=10 但 stability=50% 的因子 composite=17，一個 fitness=3 但 stability=100% 的因子 composite=6.5，前者勝出但後者可能更可靠
- **建議：** 使用 rank-weighted composite 或直接用多維 Pareto front（ICIR, stability, capacity, novelty），避免用一個 scalar 壓縮多維品質

### 1.2 Normalization Selection 存在 Look-Ahead Bias

**File:** `evaluate.py:886-924`

Stage 0 在前 15 個 IS dates 上選擇最佳 normalization（raw/rank/zscore/winsorize/percentile_rank），然後用這個 normalization 跑剩餘的 IS 和 OOS 評估。

- **問題：** 即使只用 IS 數據選 normalization，這仍然是一個 model selection step，增加了 effective degrees of freedom。5 種 normalization × 4 horizons = 20 種組合，但 Deflated Sharpe Ratio (DSR) 和 Thresholdout budget 都沒有把 normalization selection 納入多重比較校正
- **OOS 污染：** normalization 在 IS 上選定後直接用於 OOS evaluation，但如果 IS 期間某個 normalization 碰巧好，OOS 的 "驗證" 其實帶著 IS 的 selection bias
- **建議：** 要嘛固定用 rank normalization（Spearman IC 本身就是 rank-based，額外 normalize 改善有限），要嘛把 normalization selection 的自由度記入 Thresholdout budget

### 1.3 Thresholdout 實作的有效性存疑

**File:** `evaluate.py:1468-1490`

Thresholdout (Dwork et al. 2015) 的設計意圖是保護 holdout set 的信息不被漸進洩漏。但：

- **noise scale 0.05 太小** — `THRESHOLDOUT_NOISE_SCALE = 0.05`。典型 IC 值在 0.02-0.10 範圍，0.05 的 Laplace noise 可能足以翻轉 marginal cases，但對 IC sign = +0.06 vs 需要是正的 check，noise 不夠大到真正保護
- **seed 包含 factor_hash** — `rng_l5 = np.random.default_rng(hash((ic_20d, best_icir, l5_query_n, _factor_hash)))` — 如果 agent 可以控制 factor code 的 hash（它可以，因為它寫 factor.py），理論上可以遍歷不同的 factor code 來找到使 noise 有利的 seed。實務上這很難利用，但在安全模型中是一個 gap
- **budget 200 可能不夠** — `L5_QUERY_BUDGET = 200`，但 budget 只是 warning，不是 hard block（line 1488-1490 只印 stderr）。Agent 理論上可以無限查詢 L5
- **建議：**
  1. 把 L5 query budget 做成 hard block（超過就不跑 L5）
  2. noise scale 應該與 IC distribution 的 std 成比例（如 `0.2 * IC_std`），而非固定值
  3. 移除 factor_hash from seed，改用只有 evaluator 知道的 secret salt

### 1.4 OOS Split 只有一半可用

**File:** `evaluate.py:47-59`

```python
# OOS split: L5 uses first half (OOS1), Validator uses second half (OOS2).
```

OOS 總共 ~549 天，分成兩半，L5 用 ~275 天，Validator 用 ~274 天。

- **275 天的 OOS 只有 ~14 個 20-day sampling points**（每 20 天取一個 IC）。14 個 data points 做 ICIR 估計的 standard error 非常大（SE ≈ ICIR / sqrt(14)），統計檢驗力極低
- **滾動 OOS 隨時間移動** — `today - 90 - 548` 到 `today - 90`，這意味著每天 OOS window 都在移動。如果 agent 長時間運行，同一個 factor 在不同日子 submit 可能得到不同的 L5 結果（因為 OOS dates 變了），引入非確定性
- **建議：**
  1. 如果 Validator 已經有獨立的 OOS2 驗證，考慮讓 L5 用完整 OOS（549 天，~27 points），分工改為 L5 做 sign+stability check、Validator 做 full backtest
  2. 或者把 OOS window 固定（在 session 開始時計算一次），而不是每次 evaluate 都重算

### 1.5 Forward Return 有 Overlap Bias

**File:** `evaluate.py:62`, `SAMPLE_FREQ_DAYS = 20`

每 20 天取一個 IC，但 forward horizons 包括 60d。60 天的 forward return 跨了 3 個 sampling points，這意味著：
- 相鄰 IC observations 之間有 ~67% 的 return overlap
- IC series 的自相關被人為拉高
- ICIR = mean(IC) / std(IC) 會被高估（因為 std 被 autocorrelation 壓低）

目前有 ESS（Effective Sample Size）校正但只在 `MAX_ICIR_L2` 檢查中用到（line 1191-1214），L2 min threshold 沒有做 ESS 校正。

**建議：** 對 60d horizon，sample freq 應至少 60 天；或用 Newey-West standard error 替代 `ddof=1 std` 來計算 ICIR

### 1.6 Industry Neutralization 是粗糙的

**File:** `evaluate.py:1130-1141`

用台股代碼前 2 碼做 industry classification（"11"=水泥, "23"=半導體 etc.），這是：
- **不準確** — 很多公司代碼前 2 碼不能反映真正的產業。例如上市 vs 上櫃公司代碼規則不同
- **粒度不一致** — "30-39" 全部歸為電子，但電子內部差異巨大（半導體 vs PCB vs 光電）
- **缺少上櫃股** — `.TWO` 股票的代碼規則和上市不同

而 `_compute_ic()` 裡用的 `_load_industry_map()` 依賴 `FinMindFundamentals.get_sector()`（line 533-550），如果 API 不可用就直接 fall back 到空 dict（不做 neutralization）。

**建議：** 使用 TWSE 正式的產業分類（已有 finmind 數據），或至少用 DataCatalog 中的靜態 mapping file，不要依賴 runtime API call

---

## 2. Architecture & Design

### 2.1 Three-Container Design 優秀但 Evaluator 是單點故障

3 容器（Agent / Evaluator / Watchdog）的分離是正確的：
- Agent 只能看到 `work/` (rw) + `data/` (ro)
- Evaluator 看到 `work/` (ro) + `src/` (ro) + `watchdog_data/` (rw)
- Watchdog 看到 `work/` (ro) + `watchdog_data/` (rw)

但 Evaluator 是 single-threaded Flask（line `eval_server.py:12` 註釋：「單線程是刻意的」），如果 evaluate 跑到 timeout 或 hang，整個 pipeline 就停了。

- **沒有 liveness probe** — `docker-compose.yml` 只有 healthcheck（hit `/health`），但 `/health` 只回 `{"status": "ok"}`，不檢查 evaluate 是否 functional（如數據是否可載入）
- **建議：** healthcheck 加上數據可用性檢查；evaluator 加上 watchdog timer（如果一個 evaluate 超過 5 分鐘就 kill 掉）

### 2.2 Agent 的 Git 隔離不夠嚴格

**File:** `Dockerfile.agent:33-35`

Git wrapper 只 block `reset --hard` 和 `clean -f`：
```shell
case "$*" in *reset*--hard*|*clean*-f*)
```

但 agent 仍然可以：
- `git checkout -- .`（恢復所有文件）
- `git stash` + `git stash drop`
- `git rebase --abort`
- `git merge --abort`
- 直接用 Python 的 `subprocess` 呼叫 `/usr/local/lib/git-safe/git`（原始 git binary）繞過 wrapper

**建議：** 用 allowlist（只允許 `add`, `commit`, `checkout HEAD~1 -- factor.py`, `tag`, `log`）而非 blocklist

### 2.3 work/ Volume Mount 的 Permission Model

Docker compose 把 `./work` 掛為 rw 給 agent 和 ro 給 evaluator/watchdog。但在 Windows（host），volume mount 的權限實際上由 host filesystem 決定，Docker Desktop 不支持真正的 POSIX permissions。

- Agent 容器裡的 `researcher` user 可能實際有權限寫 evaluate.py（因為 evaluate.py 在 image 裡，不在 volume 上，但 agent 可以嘗試 `curl` 下載替換）
- **work/ 裡的 .git 目錄** 包含完整 git history — agent 理論上可以用 `git log -p` 看到歷史上所有的 factor.py 版本

### 2.4 Ensemble Mode 的安全模型不完整

**File:** `eval_server.py:300-443`

`/evaluate-ensemble` endpoint 直接 `exec()` factor library 中的代碼：
```python
spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
```

- factor library 的代碼是之前 agent 寫的，存在 watchdog_data 裡（agent 無法直接訪問）
- 但如果 agent 能觸發多次 evaluate 讓 "near" factor 進入 library，然後組合它們，理論上可以構造任意 ensemble
- **更重要的是：** ensemble 只檢查 L2（ICIR >= 0.30），不跑 L3-L5 gates、不做 dedup、不做 OOS。這意味著 ensemble 可以繞過所有 overfitting 防護

**建議：** ensemble 至少要跑 L3 dedup + L5 OOS，否則這是一個 backdoor

---

## 3. Security & Isolation

### 3.1 evaluate.py READ ONLY 未在 Evaluator Container 中強制

`preflight.py:294-301` 檢查 evaluate.py 是否 read-only（OS permission），但：
- Evaluator Dockerfile 不設置 evaluate.py 為 read-only（`COPY` 預設是 rw）
- 只有 agent 不應該改 evaluate.py，而 evaluate.py 在 evaluator container 裡，agent 根本接觸不到
- 真正的風險是 evaluator 的 eval_server.py 被 exploit（如 request smuggling），讓 agent 間接修改 evaluate.py

**建議：** 在 Dockerfile.evaluator 中加 `RUN chmod 444 /app/evaluate.py`，defense in depth

### 3.2 Agent 可以推測 OOS Dates

OOS dates 是 `today - 90 - 548` 到 `today - 90`。Agent 知道 today（可以 `date` 命令），所以可以精確計算 OOS window。雖然 evaluate.py 不回傳 OOS 數值，但 agent 知道 OOS 的時間範圍後，可以：
- 在 factor.py 中寫條件邏輯：`if as_of > threshold: return special_values`
- 針對 OOS 期間的已知市場事件優化

**風險等級：中** — program.md 禁止讀 evaluate.py，但 dates 的計算邏輯很簡單（90 天 + 18 個月），agent 可能從 program.md 的 "L5: OOS holdout" 描述中推測出大致範圍。

**建議：**
1. 不在任何 agent 可見的文件中提到 OOS 的天數
2. evaluate.py 中對 as_of 做 sanity check：如果 factor 在 IS 和 OOS 期間回傳的值分佈有統計顯著差異（KS test），自動 reject
3. 隨機化 OOS offset（在 90 ± 30 天之間隨機，每個 session 固定一個值）

### 3.3 Credentials Mount 是攻擊面

**File:** `docker-compose.yml:22-24`

```yaml
- ${CLAUDE_HOME}/.credentials.json:/home/researcher/.claude/.credentials.json  # rw: token refresh
```

credentials.json 以 rw 掛載到 agent container。Agent 可以讀取 OAuth token，理論上可以：
- 用 token 直接呼叫 Anthropic API（繞過 `--max-turns 200` 限制）
- 用 token 在 Anthropic API 上做其他操作

**建議：** 改為 read-only mount（`credentials.json:ro`）。Token refresh 改由 host-side 的 `credJob`（already implemented in loop.ps1）處理後，agent 只需要讀取。

### 3.4 `exec()` 在 Watchdog 中的使用

**File:** `watchdog.py:446`

```python
exec(factor_code, factor_module)
```

Watchdog 直接 `exec()` factor code 來構造 Strategy 物件。雖然 factor_code 來自 watchdog_data（agent 無法直接寫入），但如果 evaluator 被 exploit 後寫入惡意 marker JSON，watchdog 會 exec 任意代碼。

**建議：** 在 exec 之前做 AST 分析，只允許 import pandas/numpy/scipy + 函數定義，block os/subprocess/socket 等

---

## 4. Operational Concerns

### 4.1 Session Recovery 有缺陷

**File:** `loop.ps1:117-158`

研究 loop 的設計是：session 結束後 reset factor.py 到 baseline，10 秒後重啟。但：

- **results.tsv 在 agent container 裡** — 如果 agent session crash 在 commit 之前，這個實驗的結果就丟失了（沒有寫入 results.tsv 也沒有寫入 learnings.jsonl）
- **context window management** 依賴 agent 自覺（program.md line 168: "After every 30 experiments, write a brief summary"）。如果 agent 忘了或 context window 被壓縮，之前的發現就可能被重複
- **`--max-turns 200`** — 如果一個 evaluate 需要 60 秒，200 turns 可能只跑 ~100 個實驗就觸發限制。Session 重啟後 agent 重新讀 results.tsv，但 learnings API 的數據才是最完整的

**建議：**
1. Evaluator 在每次 evaluate 完成後同步寫入 learnings.jsonl（已經做了），但也應該更新 results.tsv（目前依賴 agent 手動寫入，可能遺漏）
2. 加一個 session-start hook：agent 啟動時自動讀 learnings API 而不是只讀 results.tsv

### 4.2 Watchdog 的 Stale Detection 粒度太粗

**File:** `watchdog.py:65-67`

```python
STALE_THRESHOLD = 1800  # 30 min
```

30 分鐘才報 stale，但一個 evaluate cycle 只需要 30-120 秒。如果 agent 卡住（如等待 API response），30 分鐘太長了。

**建議：** 加入 evaluator 端的 request-level timeout（已有 5 分鐘 timeout），但 watchdog 應該同時監控 evaluator 的 active request count

### 4.3 沒有 Cost Tracking

整個系統沒有追蹤 API token 使用量。以 `claude-sonnet-4-6` 模型，200 turns 可能消耗大量 token。

**建議：** 在 status.ps1 中加入估算 token 消耗的邏輯（從 agent container 的 claude 日誌中提取），或設定 spending limit

### 4.4 Deploy Queue 缺乏 End-to-End Acknowledgment

**File:** `watchdog.py:327-378`

`_queue_for_deployment()` 把因子寫入 `deploy_queue/`，但 host-side 的消費者（`daily_ops` or similar）的 ACK 機制是被動的（`_check_deploy_acks()` 只檢查 24 小時後有沒有 ACK）。

- 沒有 retry 機制 — 如果 host processor crash，factor 就永遠留在 queue 裡
- deploy_queue 沒有大小上限 — 如果 host 長期不處理，queue 會無限增長

**建議：** 加入 queue size alert（> 10 items），host processor 加入 cron schedule 確保定期消化

---

## 5. Agent Effectiveness

### 5.1 Program.md 給了太多線索

program.md 明確列出：
- 所有 failure levels 和原因（line 78-88）
- ICIR thresholds 的存在（0.30 standard, 0.40 non-whitelist）
- MAX_CORRELATION = 0.50（line 152）
- 可用數據的完整 schema（line 91-124）

這讓 agent 可以精確地 reverse-engineer evaluate.py 的邏輯，而不是真正做 exploratory research。Agent 會傾向於：
- 直接瞄準 ICIR 0.30 而不是追求真正的 alpha
- 微調 factor 來繞過 correlation threshold（0.50）而不是發現真正不同的信號
- 用已知的 failure modes 來 A/B test（改一行看是 L1 fail 還是 L2 fail，推斷 threshold）

**建議：** 
1. 減少 program.md 中的具體數字，改為定性描述（"moderate ICIR" 而不是 "ICIR >= 0.30"）
2. 不告訴 agent MAX_CORRELATION 的值，只說 "must be sufficiently different from known factors"

### 5.2 Learnings API 可能導致 Hill-Climbing

`/learnings` 回傳 direction_stats（哪些方向成功、哪些失敗），但只顯示 bucketed ICIR（noise/weak/near/moderate/strong/exceptional）。

- **正面：** bucket 化防止了精確的 gradient signal
- **但是：** "near" 到 "moderate" 的跳變點是明確的（0.20 vs 0.30），agent 可以在 "near" 因子上做小修改，精確定位 threshold 附近
- **saturation detection 可能被利用** — 如果 agent 知道某個 direction 已經 saturated（10 variants），它可能只需要改一個 variable name 或微調 window 來"創造新方向"

### 5.3 80 行限制是任意的

**File:** `evaluate.py:821-826`

L0 gate 限制 factor.py 最多 80 行。這是一個好的簡單性約束，但：
- 80 行允許相當複雜的邏輯（一個 80 行的因子可以包含 5+ 個 data sources 的組合）
- 沒有 AST complexity 檢查（如 cyclomatic complexity, nesting depth）
- Agent 可以用密集寫法繞過行數限制（如 one-liner comprehensions, semicolons）

**建議：** 加入 AST-based complexity check（如：max 3 data sources, max 2 nested loops, no lambda > 1 line）

---

## 6. Data & Methodology Specifics

### 6.1 Revenue 40-Day Delay 的實現

**File:** `evaluate.py:359-409`

`_mask_data()` 使用 registry 的 `pit_delay_days` 來截斷數據。這是正確的設計（從 registry 讀而不是硬編碼），但：

- **只截斷 date column** — 如果 fundamental data 有 non-date 的 forward-looking 欄位（如 analyst estimates, guidance），不會被截斷
- **financial_statement 的 45 天延遲** — 台灣上市公司季報公告期限是 Q+45 天（一般），但部分公司可能提前公告。目前統一用 pit_delay_days 是保守做法（好），但也意味著可能浪費了某些可以更早使用的數據

### 6.2 Universe 偏差

Core universe 200 支（大中型股），Large universe 865+ 支。

- **Survivorship bias** — universe.txt 是靜態文件，不包含下市/下櫃股。這意味著 backtest 只用存活至今的股票，IC 可能被高估
- **Size bias** — 200 支大中型股的因子可能不適用於小型股（865 支包含小型股）。Stage 2 的 large-scale verification 可以捕捉到這個問題，但 L1-L4 gate 是在 200 支上跑的，可能放過只在大型股有效的因子
- **建議：** 在 data/ 中加入歷史 universe 快照（每月更新），IC 計算時用對應日期的 universe

### 6.3 Canary Metric 檢測力不足

**File:** `evaluate.py:1731-1746`

Canary test 用隨機 factor 的 IC 來檢測 pipeline bias。但：
- 只用 50 支股票的 5 個日期
- threshold 是 `|mean IC| > 0.10`，這對 50 支股票的 5 個觀測來說 standard error 約 0.06（假設 IC std = 0.13），所以 power 很低
- 每次 evaluate 都跑一次 canary（浪費計算），但結果只印到 stderr

**建議：** Canary 改為 session-level check（preflight 時跑一次，用 200 支 × 30 dates），結果寫入 watchdog_data

---

## 7. Code Quality Issues

### 7.1 eval_server.py Line 251-258 — Variable Reference Before Assignment

```python
meta[os.path.basename(lib_path)] = {
    "icir": icir_bucket,
    "source": ic_source,        # <- defined at line 263
    "trend": ic_trend,           # <- defined at line 264
    "best_horizon": best_horizon, # <- defined at line 268
    "level": level,
}
```

`ic_source`, `ic_trend`, `best_horizon` 在 line 263-268 才被定義，但在 line 251 就被引用。Python 不會報錯（因為 line 251 在 try/except 裡），但 metadata 會包含上一次 evaluate 的值，或直接 NameError 被吞掉。

**修復：** 把 line 262-268 的 extraction 移到 line 222 之前

### 7.2 watchdog.py `_process_pending()` 一次只處理一個 marker

**File:** `watchdog.py:229` — `marker_path = novel[0]`

即使 pending/ 裡有多個 marker，每個 60 秒的 watchdog cycle 只處理第一個。如果 agent 在一個 session 中連續 pass 了 5 個 L5 因子，watchdog 需要 5 分鐘才能全部處理。

**建議：** 改為 batch processing（一次處理所有 novel markers），或至少處理 top-3

### 7.3 Memory Leak in `_close_matrix` / Stage 2

**File:** `evaluate.py:416`, `1573-1596`

module-level cache 在 evaluate 開始時清除（line 829），但 Stage 2 重新清除後（line 1573），Stage 2 的數據又累積。如果 evaluator 是長期運行的 Flask server，每次 evaluate 之間 cache 不清除（`_data_cache` 也是 module-level global）。

- `_data_cache` 故意長期保持（避免重複載入），這是合理的
- 但 `_fwd_return_cache` 應該在每次 evaluate 開始時清除（line 829 已做），所以這不是真正的 leak
- **真正的問題是 `_close_matrix`** — 它在 Stage 2 增加了新 symbols 到 `_data_cache["bars"]`（line 1594），但 `_close_matrix` 沒有重建。Stage 2 的 `_compute_forward_returns` 用的 `_close_matrix` 只包含 Stage 1 的 200 支股票，不包含新增的 symbols。這意味著 Stage 2 大部分用 fallback per-symbol loop（慢），而不是 vectorized path

**修復：** Stage 2 載入新 symbols 後重建 `_close_matrix`

### 7.4 `_compute_ic()` 自己手動算 Spearman

**File:** `evaluate.py:603-618`

```python
from scipy.stats import rankdata
rx = rankdata(x)
ry = rankdata(y)
```

手動做 rank -> Pearson 來算 Spearman correlation，但 scipy 已經有 `spearmanr(x, y)` 可以直接用。手動實現的風險是 tie-handling 可能不一致（`rankdata` 預設 method='average'，和 `spearmanr` 一致，所以實際上沒問題，但增加了維護負擔）。

---

## 8. Priority Recommendations

### Critical（應立即修復）

1. **Ensemble mode 缺少 L3-L5 gates** — 這是最大的 overfitting backdoor（S2.4）
2. **eval_server.py variable reference before assignment** — 會導致 metadata 不正確（S7.1）
3. **L5 query budget 不是 hard block** — 理論上 agent 可以無限查詢 OOS（S1.3）
4. **Credentials mount 應改為 ro** — 減少攻擊面（S3.3）

### High（下一個 phase 應處理）

5. **移除 normalization selection 或計入 multiple comparison** — 降低 false discovery rate（S1.2）
6. **Forward return overlap bias 校正** — 60d horizon 的 ICIR 被系統性高估（S1.5）
7. **Git wrapper 改為 allowlist** — 目前的 blocklist 有多個繞過路徑（S2.2）
8. **Stage 2 重建 `_close_matrix`** — 影響 large-scale verification 的效率和正確性（S7.3）
9. **Survivorship bias in universe** — 使用歷史 universe 快照（S6.2）

### Medium（持續改進）

10. **Composite score 公式重構** — 改用多維 Pareto 或 rank-weighted（S1.1）
11. **OOS window 固定化** — 避免 evaluate 結果的非確定性（S1.4）
12. **AST complexity gate** — 替代或補充 80 行限制（S5.3）
13. **Program.md 去具體化** — 減少 agent reverse-engineering threshold（S5.1）
14. **Industry neutralization 改用靜態 mapping** — 避免 runtime API 依賴（S1.6）
15. **Cost tracking** — 加入 API token 消耗追蹤（S4.3）
16. **Watchdog batch processing** — 一次處理多個 pending marker（S7.2）

---

## 9. What's Done Well

值得肯定的設計決策：

1. **Karpathy pattern 的正確應用** — 3 文件 + 固定 evaluator + 自由 agent，簡潔有效
2. **Revenue delay enforcement** — 在 evaluator 端強制，agent 無法繞過，是 look-ahead bias 防護的 gold standard
3. **Multi-level gate system (L0-L5)** — progressive filtering 節省算力，每層檢查不同維度
4. **Thresholdout 的引入** — 即使實現不完美，意識到 holdout adaptivity 問題本身就是先進的
5. **Factor replacement with diversity guard** — 不只替換更強的因子，還檢查 library diversity（eigenvalue-based effective_n），避免同質化
6. **Patton & Timmermann monotonicity test** — 超越 "IC is positive" 的 sanity check，驗證 quintile returns 是否單調
7. **Docker isolation architecture** — 比 prompt-level restriction 強多個數量級（CLAUDE.md lesson 15）
8. **Canary metric** — 每次 evaluate 都用隨機因子檢測 pipeline bias，雖然 power 低但方向正確
9. **Dual dedup** — IC series correlation + portfolio returns correlation，兩個維度捕捉 clone factor
10. **Hash-based re-evaluation prevention** — 防止 agent 不修改 factor.py 就反覆 submit

---

*Review completed. 以上建議按優先級排列，建議先處理 Critical 項，再依次處理 High 和 Medium。*
