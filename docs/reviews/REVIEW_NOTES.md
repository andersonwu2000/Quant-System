# Autoresearch 架構審查筆記

**日期**：2026-03-28
**審查對象**：
- `docs/reviews/AUTORESEARCH_OPERATIONS_REVIEW_2026Q1.md`（運營檢討）
- `docs/plans/phase-y-containerized-autoresearch.md`（容器化計畫）
- `docs/reviews/autoresearch-alpha/evaluate.py`（評估引擎 v2）
- `docs/reviews/autoresearch-alpha/program.md`（研究協議 v2）

---

## 發現的問題

### P-01: OOS 間接過擬合無具體對策

Operations Review §8.1 識別了「L5 的 pass/fail 反饋會逐漸侵蝕 OOS 獨立性」這個風險，但只列了籠統的緩解方向，沒有落地到 evaluate.py 或 program.md 的任何具體實作。Phase Y 的安全對照表也標註「不解決（需在 evaluate.py 層處理）」。

這意味著目前 evaluate.py 的 L5 輸出包含 OOS ICIR 的具體數值，agent 看得到，可以反向學習 OOS 期間的特徵。

### P-02: results.tsv 仍會被 git reset 清空

Phase Y 用 named volume 保護 results.tsv，但 `entrypoint.sh` 裡 `git add factor.py results.tsv` 把 results.tsv 加入 git 追蹤。Agent 的 `git reset --hard HEAD~1` 會回滾 results.tsv 到上一個 commit 的狀態。

Operations Review §1.6 已記錄此問題，Phase Y 聲稱用 named volume 解決，但實際上 git 追蹤層的問題沒有被處理。

### P-03: Watchdog 不監控連續 crash

Watchdog（Phase Y §3.5）監控 results.tsv 是否停滯、evaluate.py checksum、異常檔案、磁碟用量。但不監控 run.log 的 crash 狀態。如果 factor.py 有系統性 bug（比如 import error），每次 evaluate 都 crash，watchdog 只會報「停滯」，不會報「連續 crash」。Agent 可能在 crash → reset → 改一行 → crash 的循環裡空轉。

### P-04: 成功因子沒有畢業流程

Agent 發現通過 L4 + Stage 2 的好因子後，唯一的保留機制是 `git tag`。沒有定義：
- 好因子如何進入 StrategyValidator 15 項驗證
- 好因子如何進入 Paper Trading
- 多個好因子如何比較和篩選
- 何時由人類介入審查

Phase Y §6 日常操作只有 `cp factor.py factor_winner.py`，是臨時方案。

### P-05: loop-docker.ps1 的 prompt 與 program.md 重複

loop-docker.ps1 的 `$prompt` 重新描述了實驗循環的步驟（哪個目錄、怎麼 commit、怎麼 run），這些已在 program.md 裡定義。兩處維護同一件事，遲早不同步。

### P-06: Docker image 的 Python 依賴無版本鎖定

Dockerfile 用 `pip install --no-cache-dir numpy pandas scipy pyarrow`，無版本 pin。重建 image 可能拿到不同版本，導致 evaluate.py 行為微妙變化（如 NaN handling、ddof 預設值、浮點精度差異）。同一個 factor.py 在不同時間建構的 image 上可能得到不同 composite_score。

### P-07: 沒有定義退出條件

兩份文件都假設系統持續運行，但沒回答「什麼時候算完成？」。缺少：
- 短期目標（找到幾個好因子算成功？）
- 飽和偵測（連續 N 個實驗無 keep = 因子空間已耗盡？）
- 成本上限（每天/每週最多消耗多少 API 額度？）
