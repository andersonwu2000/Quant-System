# Checklists

> 兩類：**開發 checklist**（按變更類型）和**操作 checklist**（按場景）。
> 每一條都來自至少一個真實事故。跳過任何一步都曾造成過 bug。
> Bug ID（如 `[#53]`）對應 `BUG_HISTORY.md`，Review ID（如 `[C-01]`）對應 `CODE_REVIEW_20260329.md`。

---

# Part 1: Development Checklists（按變更類型）

> **改檔案前，先查底部的 Quick Reference 找到對應 checklist。**

## D-A. Validator / Statistical Testing

> Files: `validator.py`, `overfitting.py`, `analytics.py`
> History: PBO wrong ×3 [#53-55], DSR N=1 [#9], CVaR fail-open [#47], Bootstrap ddof=0

- [ ] **讀原論文** — 不是 blog 不是 SO 不是二手摘要 [#53-55]
  - 確認：N 代表什麼？分母是什麼？單位是什麼？
  - 至少交叉比對 2 個來源（論文 + 參考實作）
- [ ] **異常回傳最壞值**，不是 0.0 或 True
  - PBO → 1.0 | Sharpe/CVaR → -999 / -1.0 | Bootstrap → 0.0 | Permutation → 1.0
  - 通則：`except → 讓 gate 失敗的值`
- [ ] **ddof 一致**：std() 用 ddof=1（和 codebase 其餘部分一致）
- [ ] **單位一致**：年化 vs 日頻、算術 vs 幾何、百分比 vs 比率
- [ ] **除法 zero guard**：分母有 `> 0` 或 `!= 0`
- [ ] **NaN/inf 傳播路徑**：如果某個輸入是 NaN，結果會是什麼？會靜默通過 gate 嗎？
- [ ] **改完跑一次 validator** 在已知因子上，確認輸出合理

## D-B. Execution / Broker / OMS

> Files: `sinopac.py`, `oms.py`, `jobs.py (execute_*)`, `realtime.py`
> History: _trades never written [H-01], overfill [C-02], unit mismatch [C-03], sell overflow [#52]

- [ ] **_order_map 和 _trades 同時寫** — cancel/update 需要 _trades [H-01]
- [ ] **所有 sub-order 都存入 _order_map**，不是只存第一個 [C-01]
- [ ] **單位轉換**：整股=張（×1000 轉股數）、零股=股數。callback 必須轉換 [C-03]
- [ ] **模擬模式只填入實際提交量**，不是 order.quantity [C-02]
- [ ] **不 mutate Trade 物件** — 用局部變數做 cap/adjust [H-04]
- [ ] **Sell cap 在 cash 計算之前** [#52]
- [ ] **Lock 範圍**：order.filled_qty / order.status 的讀寫必須在 self._lock 內
- [ ] **三條管線同步**：改了 execute_pipeline → 檢查 execute_rebalance 和 monthly_revenue_rebalance [C-08/09]

## D-C. Strategy / Factor / Signal

> Files: `strategies/*.py`, `strategy/base.py`, `strategy_builder.py`, `evaluate.py`
> History: look-ahead [#10-12], empty vols [C-07], symbol format [#45]

- [ ] **40 天營收延遲** — `as_of - DateOffset(days=40)` 在任何營收讀取前 [#10-12]
- [ ] **Symbol 格式**：函式期望 bare（`1101`）還是 suffixed（`1101.TW`）？
  - 改一處 → `grep -rn "revenue" src/ strategies/` 檢查所有數據載入點 [#45]
- [ ] **空輸入 → 空輸出**，不是 crash 或預設值
  - `risk_parity(signals, {})` → `{}` 不是 crash [C-07]
- [ ] **函式確實被呼叫**：寫完 → grep 確認有 caller
- [ ] **參數確實傳對**：不是硬編碼的固定值替代動態值 [C-07]

## D-D. Scheduler / Pipeline

> Files: `scheduler/jobs.py`, `scheduler/__init__.py`
> History: prices missing for sells [C-08/09], no mutex [#42], race [#38]

- [ ] **Price dict 包含 target + 持倉** — 否則持倉標的無法平倉 [C-08/09]
  ```python
  all_needed = set(target_weights) | set(portfolio.positions)
  ```
- [ ] **三條路徑同步**：execute_pipeline / execute_rebalance / monthly_revenue_rebalance
- [ ] **mutation_lock** 在修改 portfolio 前取得
- [ ] **Trade log 在 apply_trades 之前存**（crash recovery）[#40]
- [ ] **月度 idempotency** — 檢查本月是否已執行 [#39]

## D-E. Risk / Kill Switch

> Files: `risk/realtime.py`, `api/app.py`, `risk/engine.py`
> History: infinite loop [#19-21], no guard [#20], UTC [#41]

- [ ] **kill_switch_fired** 在清倉前設、在 re-trigger 前檢查 [#20]
- [ ] **Lock 內 double-check** — path A 和 path B 都必須在 mutation_lock 內 re-check
- [ ] **generate_liquidation_orders** 在 lock 內讀 portfolio [H-03]
- [ ] **時區 = Asia/Taipei** — 所有日期比較不用 UTC [#41]
- [ ] **門檻從 config 讀**，不是硬編碼 [#18]

## D-F. Data / Cache

> Files: `data/sources/*.py`, `data/refresh.py`, `data/quality.py`
> History: parquet never expires, revenue cache never expires [M-07]

- [ ] **增量更新**：讀 last_bar_date → 只下載新 bar → concat + drop_duplicates
- [ ] **新數據寫入前做 quality check**
- [ ] **Cache 有過期機制** — 全域 dict 必須有日期檢查或 TTL [M-07]
- [ ] **Rate limit**：Yahoo 0.5s 間隔、FinMind 600 req/hr
- [ ] **Schema 一致**：新 bar 的 columns 和既有 parquet 一致

## D-G. Academic Method Implementation（通用）

> 最貴的重複 bug 模式。PBO 實作三次全錯 [#53-55]。

**三步驟，缺一不可：**

1. **讀原論文** — 寫下公式再寫代碼。辨識每個參數的精確定義
2. **找參考實作** — GitHub 搜尋，和你的代碼比對。沒有參考就加倍小心 step 1
3. **已知範例驗證** — 用論文的範例數據驗證輸出。沒有範例就建構極端情境：
   - 完美單調 equity curve → PBO ≈ 0.0
   - 純噪音 → Sharpe ≈ 0, PBO ≈ 1.0
   - 單一試驗 → DSR ≈ raw Sharpe

## D-H. Concurrent Development（多人/多 AI 同時開發）

> History: Validator fixes reverted by other AI, sinopac changes reverted

- [ ] **改之前 git pull** — 確認檔案沒被別人改過
- [ ] **commit 前 git diff** — 確認你的修改還是你想要的
- [ ] **不假設先前的修復還在** — 如果距離上次讀取有段時間，重新讀檔案
- [ ] **被 revert 的修復 → 重新修復 + 加 regression test**
- [ ] **Commit message 解釋 WHY** — 讓其他開發者理解意圖，不只看到 WHAT

---

### Quick Reference: File → Checklist

| File | Checklists |
|------|-----------|
| `src/backtest/validator.py` | D-A |
| `src/backtest/overfitting.py` | D-A, D-G |
| `src/backtest/analytics.py` | D-A |
| `src/execution/broker/sinopac.py` | D-B |
| `src/execution/oms.py` | D-B |
| `src/scheduler/jobs.py` | D-B, D-D |
| `strategies/*.py` | D-C |
| `src/strategy/base.py` | D-C |
| `src/alpha/auto/strategy_builder.py` | D-C |
| `scripts/autoresearch/evaluate.py` | D-A, D-C |
| `src/risk/realtime.py` | D-E |
| `src/api/app.py` | D-E |
| `src/data/sources/*.py` | D-F |
| `src/data/refresh.py` | D-F |
| Any academic algorithm | D-G |
| Any file during concurrent dev | D-H |

---

# Part 2: Operational Checklists（按場景）

## O-A. 研究啟動前（每次重啟 autoresearch 前）

```
□ Docker image 是最新的？
  docker exec autoresearch-agent bash -c "grep -c THRESHOLDOUT /app/evaluate.py"
  → 如果 0，需要 rebuild

□ evaluate.py READ ONLY？
  ls -la scripts/autoresearch/evaluate.py → 應為 -r-x

□ program.md READ ONLY？
  ls -la scripts/autoresearch/program.md → 應為 -r--

□ work/ 乾淨？
  results.tsv 只有 header（新研究）或有歷史（續跑）
  factor.py 是 baseline 或上次的 keep

□ watchdog_data/ 狀態？
  factor_returns/ — 空（新研究）或有 parquets（續跑）
  factor_pbo.json — 不存在（新研究）或有值（續跑）
  l5_query_count.json — 確認 budget 剩餘

□ 數據品質？
  close=0 stocks 被 guard 過濾（vectorized + evaluate + engine）

□ hooks 設定？
  .claude/settings.json 有 PreToolUse hooks
  loop.ps1 有 $env:AUTORESEARCH = "1"

□ 所有代碼修改已 commit + push？
  git status → working tree clean（除了 results.tsv/audit.log）

□ smoke test？
  cd scripts/autoresearch && python evaluate.py 2>&1 | tail -10
  → 應成功跑完，factor_returns 存到 watchdog_data/
```

## O-B. 代碼修改後（每次改完立即做）

```
□ 立即 git add + commit（不要累積）
  → agent 的 git reset 會摧毀未 commit 的修改

□ 如果改了 evaluate.py 或 watchdog.py：
  - chmod -w 上鎖
  - docker compose build + up -d 重建
  - docker exec 驗證容器內是最新版

□ 如果改了 validator.py 或 analytics.py：
  - 跑 pytest tests/unit/test_strategy_validator.py tests/unit/test_formula_invariants.py
  - src/ 是 volume mount，不需要 rebuild Docker

□ 如果改了數據處理邏輯：
  - 確認 inf/nan/zero guard 存在
  - 考慮是否需要清空 watchdog_data/factor_returns/

□ git push（如果 autoresearch 正在跑，它可能 push experiment commits）
  - 可能需要 git pull --rebase 再 push
```

## O-C. 事故發生後

```
□ 修改被 agent reset 覆蓋？
  → 重新修改 + 立即 commit（教訓：永遠不要留 uncommitted changes）

□ PBO 或 Validator 結果異常？
  → 先檢查 factor_returns 有沒有 inf/nan
  → 再檢查原始數據有沒有 close=0
  → 最後才懷疑方法論

□ Docker 容器內代碼過時？
  → docker compose build --no-cache + up -d
  → docker exec 驗證

□ OOS 資訊洩漏？
  → 檢查 5 個通道：pending marker、日期輸出、L5 message、Validator 值、factor_returns 位置
```
