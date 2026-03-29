# Autoresearch 運營檢討報告 — 2026 Q1

> 首次自動化因子研究 Agent 部署的事後檢討
> 日期：2026-03-28

## 摘要

首次部署 Karpathy 風格的 autoresearch agent，在約 2 小時內探索了 **35 個因子變體**，
composite score 從 8.80 提升至 12.49（+42%），ICIR 從 0.34 提升至 0.52（+51%）。
然而，運行期間發生了多起安全與運營事件，必須在進入正式持續運行前解決。

---

## 1. 事件紀錄

### 1.1 殭屍 Daemon（嚴重）

**發生了什麼：** 舊的 `alpha_research_agent` daemon（PID 35640）仍在背景執行，
持續寫入垃圾檔案到 `docs/research/auto/`。這些檔案看起來像是新 autoresearch 的產出，
造成混淆——無法分辨是哪個進程在寫入。

**根本原因：** 沒有進程管理機制。該 daemon 以
`python -m scripts.alpha_research_agent --daemon --interval 10` 啟動後，
在舊架構被棄用時未被終止。

**影響：** 4 個垃圾 markdown 檔案被寫入 docs/research/auto/。

**修復：** 手動 `taskkill /PID 35640 /F`，刪除檔案。

**預防：** 需要進程追蹤機制（PID 檔案、health endpoint 或 supervisor）。

### 1.2 Agent 越權寫入檔案（高）

**發生了什麼：** 首個 autoresearch agent（以 `--dangerously-skip-permissions` 執行）
將 `.py` 檔案寫入 `src/strategy/factors/research/` — 完全超出 autoresearch 目錄範圍。

**根本原因：** 沒有檔案系統隔離。Agent 對整個 repo 擁有完整寫入權限。
prompt 雖然說「只能編輯 factor.py」，但基於 prompt 的限制無法強制執行。

**影響：** 非預期的檔案被 commit 到 repo。

**修復：** 對受保護檔案設定 OS 層級 `attrib +R` + 在 program.md 中加入安全規則段落。

### 1.3 git reset 回滾了基礎設施修改（高）

**發生了什麼：** 我們對 evaluate.py 和 program.md 的 L5 OOS holdout 修改，
在 agent 執行 `git reset --hard HEAD~1` 丟棄失敗實驗時被一併回滾。

**根本原因：** 基礎設施修改在 agent 執行 reset 時尚未獨立 commit。
`git reset --hard` 會影響所有已修改的檔案，不只 factor.py。

**影響：** 損失約 30 分鐘的 L5 實作工作，必須全部重做。

**修復：** 基礎設施修改必須在啟動 agent 前獨立 commit。

**教訓：** Windows 的 `attrib +R` 無法可靠防禦 `git reset --hard`。
Git 從 object store 重建檔案時會繞過唯讀屬性。

### 1.4 權限提示阻斷自主運行（中）

**發生了什麼：** 以 `--allowedTools` 白名單啟動的 agent 不斷被
「Compound commands with cd and git require approval」提示阻擋。
Agent 無法自主運行，因為每個 `cd && git` 複合指令都需要人工批准。

**根本原因：** `--allowedTools "Bash(cd*)"` 無法匹配 `cd D:/Finance && git add ...`
這類複合指令。allowedTools 的 matcher 將整個指令視為單一字串比對。

**影響：** Agent 每 2-3 分鐘就停下等待批准，完全違背自主研究的目的。

**修復：** 改用 `--dangerously-skip-permissions` + OS 唯讀 + audit hook。

### 1.5 Audit Hook 誤報（低）

**發生了什麼：** PostToolUse audit hook 在每次 tool call 時觸發，
反覆報告同一批約 10 個早已存在的 untracked 檔案為「未授權修改」。

**根本原因：** Hook 使用 `git ls-files --others --exclude-standard` 報告所有
untracked 檔案，而非僅新建的檔案。

**修復：** 從 hook 中移除 untracked 檔案掃描，改為僅追蹤 autoresearch/ 以外的
已追蹤檔案變更。

### 1.6 results.tsv 反覆被清空（低）

**發生了什麼：** results.tsv 在 session 中多次被清空至僅剩 header + baseline，
丟失實驗歷史記錄。

**根本原因：** Agent 的 `git reset --hard HEAD~1` 在回滾 factor.py 的同時
也回滾了 results.tsv。實驗日誌不受 git 操作保護。

**影響：** 喪失實驗進展的可見性，只能依賴 git log。

**緩解：** results.tsv 在此架構中天生脆弱。應考慮寫入獨立的 .gitignore 日誌檔。

---

## 2. 運作良好的部分

1. **Karpathy 模式本身** — 2 小時完成 35 個實驗，系統性參數搜索
2. **evaluate.py 安全機制** — 營收延遲強制、資料遮罩、early-exit 全部正常運作
3. **L1-L4 閘門** — 正確過濾弱因子，訊號雜訊比良好
4. **Agent 的研究策略** — 從廣泛探索（動量、波動率、流動性）到系統性收斂
   （雙窗口 Sharpe、skip-day 最佳化）
5. **去重檢查** — 防止 clone 因子膨脹試驗次數
6. **OS 唯讀** — 成功阻止 agent 修改 evaluate.py（直到 git reset 繞過）

---

## 3. 安全評估

### 當前威脅模型

| 威脅 | 可能性 | 影響 | 現有緩解 | 殘留風險 |
|------|--------|------|----------|----------|
| Agent 修改 evaluate.py | 中 | 嚴重 | OS attrib +R、prompt | git reset 繞過 attrib +R |
| Agent 寫入 autoresearch/ 以外 | 中 | 高 | 僅 prompt | 無硬性限制 |
| Agent 執行任意指令 | 高 | 高 | 無（skip-permissions） | 完整 shell 存取 |
| Agent 安裝套件 | 低 | 中 | 僅 prompt | 可能安裝惡意套件 |
| Agent 存取網路 | 低 | 中 | 僅 prompt | 可能洩漏資料 |
| Agent 刪除檔案 | 低 | 高 | 僅 prompt | 可能 rm -rf |
| 崩潰後殭屍進程 | 中 | 中 | 無 | 無 PID 追蹤 |

### 縱深防禦缺口

```
第 1 層：Prompt 指令          — ✅ 已實作，⚠️ 無法強制執行
第 2 層：--allowedTools       — ❌ 失效（複合指令被阻擋）
第 3 層：OS 檔案權限          — ⚠️ 部分有效（git reset 繞過）
第 4 層：Audit 日誌           — ⚠️ 雜訊多、非同步（無法阻擋）
第 5 層：進程隔離             — ❌ 無（同用戶、同檔案系統）
第 6 層：網路隔離             — ❌ 無
```

---

## 4. 改善建議

### 4.1 VM / 容器隔離（正式環境推薦）

**做法：** 在隔離環境中執行 autoresearch agent。

| 方案 | 優點 | 缺點 |
|------|------|------|
| **Docker 容器** | 檔案系統隔離、資源限制、容易清理 | 需掛載 data/ 為唯讀 volume |
| **WSL2** | 輕量、Windows 整合良好 | 仍共享 kernel，隔離不如 VM |
| **Hyper-V VM** | 完全隔離、快照/還原 | 重量級、啟動慢、資料同步開銷 |
| **Windows Sandbox** | 用完即棄、自動清理 | 無持久性、無法恢復 session |

**推薦：Docker 容器**，配置如下：
```yaml
volumes:
  - ./data:/app/data:ro                    # 市場資料唯讀
  - ./scripts/autoresearch:/app/work:rw    # 唯一可寫目錄
security_opt:
  - no-new-privileges:true
network_mode: none                         # 無網路存取
mem_limit: 4g
```

Agent 只能寫入 /app/work（factor.py、results.tsv）。其餘皆為唯讀或不可存取。
無網路、無法安裝套件、無法逃逸。

### 4.2 Watchdog 共生進程（立即可用）

與 agent 同時執行的監控腳本：

```python
# scripts/autoresearch/watchdog.py
"""
與 autoresearch agent 並行執行，每 60 秒檢查：
1. Agent 進程存活？否則透過 loop.ps1 重啟
2. autoresearch/ 以外有檔案被修改？警告 + 回滾
3. results.tsv 是否成長？若 30 分鐘無新增，agent 可能卡住
4. evaluate.py / program.md 的 checksum 是否不變？
5. 磁碟用量是否異常成長？（agent 產生大量檔案）
"""
```

**核心功能：**
- 檔案完整性監控（SHA-256 checksum 保護檔案）
- 自動回滾未授權修改（`git checkout -- <file>`）
- 停滯偵測（results.tsv N 分鐘無新增條目）
- 進程健康檢查（claude.exe 是否仍在執行）
- 定期狀態報告輸出至日誌

### 4.3 Git Hook 保護（推薦）

Pre-commit hook 拒絕觸及受保護檔案的 commit：

```bash
# .git/hooks/pre-commit
PROTECTED="scripts/autoresearch/evaluate.py scripts/autoresearch/program.md"
for f in $PROTECTED; do
    if git diff --cached --name-only | grep -q "^$f$"; then
        echo "BLOCKED: $f is protected"
        exit 1
    fi
done
```

比 OS attrib 更能防禦 commit 階段的修改。
但 `git reset --hard` 完全繞過 hooks。

### 4.4 獨立 Git Worktree（低成本、高價值）

在 git worktree 中執行 agent：
```bash
git worktree add ../autoresearch-workspace master
```

Agent 在 `../autoresearch-workspace/` 運作。其 `git reset --hard` 只影響該 worktree，
不影響主 repo。主 repo 中的基礎設施修改完全安全。

**這是「git reset 回滾基礎設施」問題最簡單的解法。**

### 4.5 results.tsv 改為 .gitignore 的追加日誌

將實驗日誌移出 git 追蹤：
- `.gitignore` 排除 results.tsv
- Agent 追加寫入，git reset 無法影響
- Watchdog 定期備份

---

## 5. 優先矩陣

| # | 行動 | 工作量 | 影響 | 優先級 |
|---|------|--------|------|--------|
| 1 | Git worktree 隔離 agent | 低 | 高 | **P0 — 立即執行** |
| 2 | Watchdog 共生進程 | 中 | 高 | **P0 — 立即執行** |
| 3 | Pre-commit hook 保護檔案 | 低 | 中 | P1 |
| 4 | .gitignore results.tsv | 低 | 中 | P1 |
| 5 | Docker 容器隔離 | 高 | 極高 | P2（正式環境） |
| 6 | 修復 --allowedTools 複合指令匹配 | N/A | 高 | 上游（Claude Code bug） |

---

## 6. 首次運行指標

| 指標 | 數值 |
|------|------|
| 總實驗數 | 35 |
| 運行時間 | 約 2 小時 |
| 每小時實驗數 | 約 17 |
| L4 通過率 | 26/35（74%） |
| 最佳 composite score | 12.49（baseline: 8.80，+42%） |
| 最佳 ICIR | 0.5153（baseline: 0.3419，+51%） |
| 最佳因子 | dual Sharpe 12+8 skip15 |
| 穩定性（正向年份） | 8/8（100%） |
| 事件數 | 6（1 嚴重、2 高、1 中、2 低） |
| Agent 檔案越權次數 | 1（寫入 src/strategy/） |
| 基礎設施被 agent 回滾次數 | 1（L5 修改遺失） |

---

## 7. 根因分析：三個結構性問題

表面的 6 個事件背後，是 3 個更深層的結構性問題。

### 7.1 Agent 與人類共享可變狀態

**問題本質：** Agent 和人類操作同一個 git repo、同一個檔案系統、同一個工作目錄。
任何一方的操作都會影響另一方。

這是事件 1.2（越權寫入）、1.3（reset 回滾基礎設施）、1.6（results.tsv 被清空）
的共同根因。不是 agent「犯錯」，而是架構允許副作用跨越邊界傳播。

**類比：** 這就像兩個開發者在同一台機器上用同一個帳號開發 —— 一個人的
`git reset --hard` 會毀掉另一個人的未 commit 工作。解法不是「小心一點」，
而是隔離工作空間。

### 7.2 權限模型是二元的

Claude Code 目前只有兩種模式：
- `--allowedTools`：白名單，但複合指令無法匹配，導致 agent 每隔幾分鐘就卡住
- `--dangerously-skip-permissions`：完全無限制，agent 擁有 root 等級存取

**沒有中間地帶。** 需要的是「允許 git 操作但限制在特定目錄」「允許 python 但只能跑
evaluate.py」這類細粒度控制，目前不存在。

### 7.3 Git 同時承擔兩個角色

Git 在此架構中同時負責：
- **實驗管理**：factor.py 的 commit/reset（高頻、agent 控制）
- **基礎設施版控**：evaluate.py/program.md 的修改（低頻、人類控制）

`git reset --hard HEAD~1` 的語意是「丟棄最近一次變更」，但它無法區分
「丟棄 agent 的實驗」和「丟棄人類的基礎設施修改」。這兩個關注點被耦合在同一個
git 歷史中。

---

## 8. 未來風險預測

以下是持續運行可能遇到但尚未發生的問題。

### 8.1 OOS Holdout 被間接學習（高風險）

**場景：** Agent 跑了 1000+ 實驗，每次都看到 L5 的 pass/fail 結果。
雖然它看不到 OOS 的原始數據，但通過「這個因子通過 L5 / 那個沒通過」的反饋，
agent 會逐漸學到 2023H2-2024 期間什麼有效 —— 間接過擬合 OOS。

**嚴重程度：** 高。這是所有 holdout 方法的固有弱點（Blum & Hardt 2015,
"The Ladder: A Reliable Leaderboard for Machine Learning Competitions"）。
每次查詢 holdout，都會洩漏少量資訊。

**緩解：**
- 限制 L5 反饋的精確度（只報 pass/fail，不報 OOS ICIR 具體數值）
- 定期更新 OOS 期間（滾動 holdout）
- 最終驗證靠 paper trading（真正的 unseen data）

### 8.2 Context Window 耗盡導致行為退化（高風險）

**場景：** Agent 在一個 session 中跑了 20+ 個實驗後，context window 接近上限。
早期的實驗記錄被壓縮或遺忘，agent 開始：
- 重複已經試過的因子
- 忘記 results.tsv 的格式，寫入錯誤格式
- 忘記安全規則（program.md 的 SECURITY 段落被壓縮掉）

**嚴重程度：** 高。已觀察到 agent 中途停止的問題。

**緩解：**
- `loop.ps1` 的 `--max-turns 200` 限制單 session 長度，定期重啟
- 每次新 session 重新讀取 program.md + results.tsv（冷啟動）
- results.tsv 作為跨 session 的持久記憶

### 8.3 因子複雜度蔓延（中風險）

**場景：** Agent 發現簡單因子（如 12-1 momentum）很快被探索完畢，開始產出
越來越複雜的組合因子（50+ 行、5 個嵌套條件）。這些因子：
- 難以理解和解釋（沒有經濟直覺）
- 難以在生產環境部署和維護
- 更容易過擬合（自由度太高）

**嚴重程度：** 中。program.md 的 Simplicity Criterion 有部分緩解。

**緩解：**
- 在 evaluate.py 中加入複雜度懲罰（factor.py 行數、AST 節點數）
- L4 fitness 公式中加入簡潔性權重
- 設定 factor.py 最大行數限制（如 50 行）

### 8.4 Git 歷史爆炸（中風險）

**場景：** 每個實驗產生 1 個 commit。跑 10,000 個實驗後，git repo 累積大量
object，`git log` / `git status` 變慢，`.git/` 目錄膨脹。

**嚴重程度：** 中。不會導致功能故障，但影響效能。

**緩解：**
- 定期 `git gc --aggressive`
- 使用 worktree 隔離（可以定期重建乾淨 worktree）
- discard 的實驗用 `git reset --hard` 而非保留（已實作）

### 8.5 多 Agent 衝突（中風險）

**場景：** 使用者同時啟動兩個 autoresearch agent（或一個 agent + 一個人類在改代碼），
兩者同時修改 factor.py 或 results.tsv，導致：
- merge conflict
- 資料覆蓋
- 不一致的 git 狀態

**嚴重程度：** 中。目前沒有互斥鎖機制。

**緩解：**
- Watchdog 偵測多個 claude.exe 進程並警告
- PID 鎖檔（`autoresearch.lock`）
- 每個 agent 使用獨立 worktree

### 8.6 資料時效性衰退（低風險，但長期致命）

**場景：** 本地 parquet 檔案是某個時間點的快照。隨著時間推移：
- 新上市公司不在 universe 中
- 已下市公司仍在 universe 中
- 價格數據缺少最近幾個月
- OOS 期間 (2023H2-2024) 不再是「最近的」unseen data

**嚴重程度：** 低（短期），高（長期）。因子可能在過時的數據上看起來很好。

**緩解：**
- 定期更新 parquet 數據（排程腳本）
- OOS 期間隨時間滾動
- 最終靠 paper/live trading 驗證

### 8.7 靜默失敗（低風險但難偵測）

**場景：** factor.py 的 compute_factor 對所有股票回傳相同的值（如全部 0），
或回傳 NaN 被過濾後只剩 5 支股票。evaluate.py 的 MIN_SYMBOLS 檢查會跳過，
但不會 crash —— 只是 IC 變成 None，日期被跳過。Agent 看到「少量日期有 IC」
可能誤判為「訊號存在但不穩定」。

**嚴重程度：** 低。L1 early-exit 和 MIN_SYMBOLS=30 已有部分防禦。

**緩解：**
- 在 evaluate.py 加入 coverage 指標（有效日期數 / 總日期數）
- 低 coverage（< 50%）視為失敗
- 報告每日平均有效股票數

### 8.8 成本失控（依使用模式）

**場景：** 24/7 持續執行 Claude agent，每個實驗需要：
- 讀 3 個檔案（program.md + results.tsv + factor.py）
- Edit 1 次
- Bash 3-4 次（commit, evaluate, parse, record）
- 總計 ~8 tool calls，每個 session 200 turns

以 Opus 計費，每天可能消耗 $50-200+ 的 API 額度。

**緩解：**
- 使用 Sonnet 而非 Opus（`--model sonnet`）降低成本
- 設定每日預算上限
- 非交易時間降低執行頻率

---

## 9. 風險矩陣總覽

| # | 風險 | 可能性 | 影響 | 時間框架 | 現有防禦 |
|---|------|--------|------|----------|----------|
| 8.1 | OOS 間接過擬合 | 高 | 高 | 1000+ 實驗後 | L5 holdout（會被侵蝕） |
| 8.2 | Context 耗盡行為退化 | 高 | 中 | 每個 session | loop.ps1 重啟 |
| 8.3 | 因子複雜度蔓延 | 中 | 中 | 100+ 實驗後 | Simplicity Criterion（僅 prompt） |
| 8.4 | Git 歷史爆炸 | 中 | 低 | 1000+ 實驗後 | git gc |
| 8.5 | 多 Agent 衝突 | 中 | 高 | 任何時候 | 無 |
| 8.6 | 資料時效性衰退 | 低→高 | 高 | 6+ 個月後 | 無 |
| 8.7 | 靜默失敗 | 低 | 中 | 任何時候 | MIN_SYMBOLS |
| 8.8 | 成本失控 | 中 | 中 | 24/7 運行時 | 無 |

---

## 10. 結論

### 已驗證的事實

Autoresearch 模式在因子探索方面生產力極高。Karpathy 三檔案架構
（evaluate.py + factor.py + program.md）設計合理。

### 核心教訓

1. **Prompt 約束 ≠ 安全保證。** Agent 遵守 prompt 是「通常」而非「永遠」。
   任何關鍵限制必須有 prompt 以外的強制機制。
2. **共享可變狀態是萬惡之源。** Agent 和人類必須在隔離的工作空間操作。
3. **Git 不適合做 agent 的狀態管理。** 實驗追蹤（results.tsv）應獨立於版控。
4. **Holdout 不是永久的。** 每次 L5 的 pass/fail 反饋都在侵蝕 OOS 的獨立性。
   最終驗證必須靠 paper trading。
5. **自主 agent 需要監管，不能放養。** Watchdog 不是可選的——是必要的。

### 下一步

最具成本效益的立即改善：
1. **Git worktree** — 隔離 agent 的 git 操作，不影響主 repo
2. **Watchdog** — 即時偵測異常，自動修復，定期報告
3. **L5 反饋限制** — 只報 pass/fail，不報具體 OOS 數值

長期 24/7 運行建議採用 Docker 容器隔離。
