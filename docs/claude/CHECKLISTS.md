# Operational Checklists

> 不是規則，是每次必須實際執行的步驟。跳過任何一步都曾造成過事故。

---

## A. 研究啟動前（每次重啟 autoresearch 前）

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

## B. 代碼修改後（每次改完立即做）

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

## C. 事故發生後

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
