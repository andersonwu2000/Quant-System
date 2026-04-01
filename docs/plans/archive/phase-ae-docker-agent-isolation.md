# Phase AE：Agent 真隔離 — Docker Container 內跑 Claude Code ✅ 已完成（2026-03-29）

> 3 容器 Eval-as-a-Service 架構已部署並通過端到端測試。
> Agent 物理上無法讀 evaluate.py、src/、watchdog_data/。
> loop.ps1 支援 `-Docker`（預設）和 `-Host`（fallback）兩種模式。
>
> **第三輪覆核（2026-03-29）**：實作大致符合計畫，1 個遺漏 + 2 個設計注意事項（見 §13）。

---

## 1. 現狀（假隔離）

```
Host (Windows, 完整權限)
├── Claude Code agent ← 能讀寫一切
├── scripts/autoresearch/
│   ├── factor.py      (agent 可改)
│   ├── evaluate.py    (OS read-only, 但 agent 可 cat 讀)
│   └── results.tsv    (agent 可改)
├── src/               (agent 可讀改)
├── .claude/settings.json (hooks, agent 可能繞過)
└── Docker containers
    ├── autoresearch-agent: sleep infinity (無用)
    └── autoresearch-watchdog: Validator + PBO (有用)
```

**防護層：**
- Hooks → 可被 `bash -c "cat ..."` 繞過
- OS read-only → 只防寫不防讀
- program.md 指令 → agent 可無視

---

## 2. 方案評估

### 方案 A：Docker Sandbox（推薦）

Docker Desktop 內建的 `docker sandbox` 命令，為 coding agent 設計：

```powershell
docker sandbox run claude D:\Finance -- `
  -p "Read scripts/autoresearch/program.md and begin" `
  --dangerously-skip-permissions
```

**優點：**
- 一行指令，microVM 級隔離
- 自動雙向檔案同步
- 內建 Docker daemon（agent 可在裡面跑 docker 但不影響 host）
- 網路可設白名單

**缺點：**
- 無法精確控制哪些檔案可寫（整個目錄同步）
- 需要 Docker Desktop 有 sandbox 功能的版本
- Windows 支援可能不完整

### 方案 B：自建 Container（精確控制，推薦）

```
Docker Container
├── Claude Code CLI（npm install）
├── Python + dependencies
├── /app/evaluate.py     (COPY, 不可改)
├── /app/program.md      (COPY, 不可改)
├── /app/work/           (mount rw: factor.py, results.tsv)
├── /app/data/market/    (mount ro: 市場數據)
├── /app/data/fundamental/ (mount ro: 基本面數據)
├── /app/data/research/  (mount ro: universe, baseline_ic)
└── 無 src/、無 docs/、無 .git、無 .claude/
```

**Dockerfile：**

```dockerfile
FROM node:20-slim

# System tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl python3 python3-pip python3-venv build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (same as existing Dockerfile)
RUN pip3 install --no-cache-dir --break-system-packages \
    pandas numpy scipy pyarrow cachetools

# Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Copy immutable files
COPY scripts/autoresearch/evaluate.py /app/evaluate.py
COPY scripts/autoresearch/program.md /app/program.md

# Non-root user
RUN useradd -m -s /bin/bash researcher && \
    mkdir -p /app/work && chown researcher:researcher /app/work

WORKDIR /app
USER researcher

# Claude Code needs a writable home for config
ENV HOME=/home/researcher
```

**docker-compose.yml（agent 服務）：**

```yaml
services:
  autoresearch-agent:
    build:
      context: ../..
      dockerfile: docker/autoresearch/Dockerfile.agent
    container_name: autoresearch-agent
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - PROJECT_ROOT=/app
      - PYTHONPATH=/app/work:/app
    volumes:
      - ./work:/app/work                          # factor.py + results.tsv (rw)
      - ../../data/market:/app/data/market:ro      # 市場數據
      - ../../data/fundamental:/app/data/fundamental:ro
      - ../../data/research:/app/data/research:ro  # universe, baseline_ic
    mem_limit: 8g
    cpus: 4
    # 網路：只允許 Anthropic API
    networks:
      - agent-net

networks:
  agent-net:
    driver: bridge
    # 可加 iptables 白名單只放 api.anthropic.com
```

**loop.ps1（改為啟動 Docker）：**

```powershell
$prompt = Get-Content scripts/autoresearch/program.md -Raw

docker compose -f docker/autoresearch/docker-compose.yml run --rm `
  autoresearch-agent `
  claude -p $prompt --dangerously-skip-permissions --max-turns 200
```

**優點：**
- Agent 物理上無法讀 evaluate.py 源碼（COPY 進去但可設權限）
- Agent 無法存取 src/、docs/、.git
- 精確控制：只有 work/ 可寫
- 不需要 hooks（Docker 本身就是隔離）

**缺點：**
- 需要在容器裡裝 Claude Code CLI（npm + node）
- 認證需要處理（API key 或 auth token）
- 容器 image 較大（node + python + claude code）
- Windows 上 Docker 的 volume mount 可能有效能問題

### 方案 C：Claude Code 內建 Sandbox

```bash
claude /sandbox
```

**底層：** macOS 用 Seatbelt，Linux 用 bubblewrap。Windows 需要 WSL2。

**優點：** 零配置，Claude Code 原生功能
**缺點：** Windows 支援不佳，進程級隔離（非容器級），無法精確控制讀寫範圍

---

## 3. 推薦方案：B（自建 Container）

理由：
1. 你已經有 Docker Desktop + docker-compose 基礎設施
2. 精確控制文件訪問（只掛載需要的目錄）
3. evaluate.py 是 COPY（和現有 watchdog 架構一致）
4. 不依賴 Docker Desktop 的 sandbox 功能（可能不穩定）

---

## 4. 實施步驟

### Step 1：建立 Dockerfile.agent

新增 `docker/autoresearch/Dockerfile.agent`，基於 node:20-slim + python3 + claude code CLI。

### Step 2：更新 docker-compose.yml

agent 服務改為真正跑 Claude Code，不再 `sleep infinity`。

### Step 3：認證

```bash
# 方式 1：API Key（.env 文件）
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 方式 2：在容器內 login
docker exec -it autoresearch-agent claude auth login
```

### Step 4：更新 loop.ps1

改為 `docker compose run` 啟動 agent。

### Step 5：program.md 調整

- 路徑改為容器內路徑（`/app/work/factor.py`）
- `python /app/evaluate.py` 直接在容器內跑
- git 操作在 `/app/work/.git`

### Step 6：移除 hooks

Docker 隔離後 hooks 不再需要（容器本身就是硬限制）。

### Step 7：測試

- Agent 能否編輯 factor.py ✓
- Agent 能否跑 evaluate.py ✓
- Agent 無法讀 evaluate.py 源碼 ✓（設 chmod 000 或不 COPY）
- Agent 無法存取 src/ ✓（未掛載）
- Agent 無法修改 host 文件 ✓

---

## 5. 風險

| 風險 | 緩解 |
|------|------|
| Claude Code CLI 在容器內可能行為不同 | 先跑 smoke test |
| npm install 很慢、image 很大 | 預建 image，push 到 registry |
| Windows Docker volume 效能差 | data/ 掛載 ro 影響小；work/ 很小 |
| API key 外洩風險 | 用 .env 不 commit；或用 Docker secrets |
| 容器內網路限制過嚴 | 白名單 api.anthropic.com + pypi.org |

---

## 6. 預計工作量

| Step | 工作量 |
|------|--------|
| Dockerfile.agent | 30 分鐘 |
| docker-compose 更新 | 15 分鐘 |
| 認證設定 | 15 分鐘 |
| loop.ps1 + program.md 調整 | 30 分鐘 |
| 測試 + debug | 1 小時 |
| **總計** | **~2.5 小時** |

---

## 7. 優先級

**不阻塞研究。** 目前 hooks + OS read-only 提供了「足夠好」的防護。Agent 能繞過的場景（cat evaluate.py）是理論風險，不是已發生的事故。

建議在 Phase 2 研究完成後（50-100 實驗）再實施。或者如果發現 agent 實際繞過了 hooks，立即實施。

## 8. 審批意見（2026-03-29）

### 整體判斷：✅ 方向正確，方案 B 合理。有 5 個問題需修正。

### 做對了的

1. **選方案 B 而非 A/C** — 精確控制 > 一鍵方便。Docker Sandbox 在 Windows 上不穩定，bubblewrap 在 Windows 不存在。自建 Container 是目前唯一可靠的選項
2. **evaluate.py 用 COPY 不用 mount** — 和 watchdog 架構一致，agent 無法修改
3. **非 root 使用者** — 防止容器內提權
4. **資源限制**（mem_limit, cpus）— 防止 agent 耗盡 host 資源
5. **優先級判斷務實** — 「不阻塞研究，但 agent 繞過 hooks 就立即實施」

### 問題 1：evaluate.py 源碼可讀

> Step 7 寫 "Agent 無法讀 evaluate.py 源碼 ✓（設 chmod 000 或不 COPY）"

但 Step 2 把 evaluate.py COPY 進容器（`COPY evaluate.py /app/evaluate.py`），agent 需要**執行**它。如果 chmod 000，agent 也無法執行。

**兩難：** agent 必須能跑 `python /app/evaluate.py`，但不應該能讀源碼學閾值。

**建議方案：**
- evaluate.py 編譯成 .pyc（`python -m py_compile evaluate.py`），只 COPY .pyc
- 或 evaluate.py 作為獨立服務跑在 watchdog 容器，agent 透過 HTTP/socket 提交評估請求，只拿回 pass/fail
- 後者更乾淨但工作量更大。.pyc 是 80/20 的折衷

### 問題 2：work/ 目錄的 git 操作

> Step 5 寫 "git 操作在 /app/work/.git"

目前 agent 的實驗循環是：改 factor.py → commit → 跑 evaluate → 記錄。如果 work/ 只有 factor.py 和 results.tsv，那 `.git` 在哪？

**選項：**
- A. work/ 是一個獨立的 git repo（只追蹤 factor.py）— 乾淨但和主 repo 脫鉤
- B. work/ mount 主 repo 的 scripts/autoresearch/work/，.git 在 host — agent 可以 commit 但 git history 和主 repo 一起
- C. 不用 git，每次實驗用 timestamp 和 file hash 追蹤

**建議：** 方案 A。work/ 用 `git init` 獨立追蹤。results.tsv 的 commit hash 欄位足以追溯。不需要和主 repo 耦合。

### 問題 3：evaluate.py 的依賴鏈

evaluate.py import 了：
- `src.backtest.validator`（StrategyValidator 16 項驗證）
- `src.backtest.analytics`（BacktestResult, Sharpe 計算）
- `src.alpha.auto.strategy_builder`（StrategyBuilder）
- `src.data.sources.*`（數據載入）

但 §2 設計中 `/app` 沒有 `src/` 目錄。evaluate.py 在容器內跑會 ImportError。

**兩個方案：**
- A. 把 `src/` 也 mount ro — 但這打破了「agent 無法讀 src/」的隔離
- B. evaluate.py 不在 agent 容器跑，改在 watchdog 容器跑（已有完整 src/）。Agent → HTTP → watchdog evaluate → pass/fail 回傳

**建議：** 方案 B。這和 §2「評估標準和 agent 物理分離」原則一致。evaluate.py 本來就不應該和 agent 在同一個 trust domain。

架構變為：
```
agent container (rw: work/)
    ↓ HTTP request: "evaluate commit abc1234"
watchdog container (ro: src/, evaluate.py, data/)
    ↓ 跑 evaluate.py
    ↓ 回傳 JSON: {"passed": false, "level": "L3", "score": 0.42}
```

### 問題 4：Claude Code CLI 的認證和 session

Claude Code CLI 需要：
- API key 或 OAuth token
- 可能需要寫入 `~/.claude/` 的設定檔
- 可能嘗試 `git config` 設定 author

§3 只提了 API key 或 login。但：
- `--dangerously-skip-permissions` 在容器內是否有效？需測試
- `--max-turns 200` 是否足夠？autoresearch 一次循環可能需要更多
- Claude Code 可能嘗試讀 `.claude/settings.json`（不存在 → 可能報錯或 fallback）

**建議：** 加一個 Step 0 — 在容器內手動跑一次 `claude --version` 和 `claude -p "echo hello"`，確認 CLI 基本功能正常。

### 問題 5：缺少監控和自動重啟

計畫沒有提到：
- 容器 crash 後怎麼辦？（需要 `restart: unless-stopped`）
- 如何從 host 監控 agent 進度？（watch results.tsv？Prometheus？）
- 長時間無輸出怎麼辦？（health check + timeout）

**建議加入 docker-compose：**
```yaml
restart: unless-stopped
healthcheck:
  test: ["CMD", "test", "-f", "/app/work/results.tsv"]
  interval: 300s
  timeout: 10s
  retries: 3
```

### 修改優先級建議

| 問題 | 嚴重度 | 建議 |
|------|:------:|------|
| #3 evaluate.py 依賴鏈 | **BLOCKING** | 必須解決，否則容器內跑不動 |
| #1 源碼可讀 | HIGH | .pyc 或 HTTP 評估服務 |
| #2 git 策略 | MEDIUM | work/ 獨立 git repo |
| #4 CLI 測試 | MEDIUM | 加 Step 0 smoke test |
| #5 監控重啟 | LOW | 加 restart policy + healthcheck |

**如果採用問題 #3 的方案 B（HTTP 評估服務），問題 #1 自動解決**（evaluate.py 不在 agent 容器內，agent 完全看不到）。建議合併處理。

## 9. 審批回覆（研究後修正）

### 審批意見全部接受。合併 #1+#3 為 Eval-as-a-Service 架構。

### #1+#3 合併解決：Eval-as-a-Service（HTTP 評估服務）

**問題：** evaluate.py COPY 進 agent 容器 → agent 可讀源碼。且 evaluate.py import src/ → agent 容器需要 src/ → 打破隔離。

**解法：** evaluate.py 不在 agent 容器，跑在 evaluator 容器。Agent 透過 HTTP 提交評估。

```
┌─────────────────────┐     HTTP POST      ┌──────────────────────┐
│  agent container    │ ──────────────────→ │  evaluator container │
│                     │                     │                      │
│  claude -p          │     JSON response   │  Flask + evaluate.py │
│  + factor.py (rw)   │ ←────────────────── │  + src/ (ro)         │
│  + program.md (ro)  │                     │  + data/ (ro)        │
│                     │                     │                      │
│  無 evaluate.py     │                     │  Port 5000           │
│  無 src/            │                     │  watchdog_data/ (rw) │
│  無 data/           │                     │                      │
└─────────────────────┘                     └──────────────────────┘
         │                                           │
         └────── shared volume: work/ ───────────────┘
                 (factor.py, results.tsv)
```

**eval_server.py（~20 行，包裝 evaluate.py）：**

```python
from flask import Flask, jsonify
import subprocess, json

app = Flask(__name__)

@app.route("/evaluate", methods=["POST"])
def evaluate():
    result = subprocess.run(
        ["python", "/app/evaluate.py"],
        capture_output=True, text=True, timeout=300,
        cwd="/app", env={**dict(__import__('os').environ), "PYTHONPATH": "/app/work:/app"}
    )
    # 只回傳安全的欄位（不含 OOS 值）
    lines = result.stdout.strip().split("\n")
    safe_output = "\n".join(l for l in lines[-30:])  # 等同 tail -30
    return jsonify({"output": safe_output, "returncode": result.returncode})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

**Agent 端的 program.md 改為：**
```bash
# 舊：python evaluate.py 2>&1 | tail -30
# 新：
curl -s -X POST http://evaluator:5000/evaluate | python -c "import sys,json; d=json.load(sys.stdin); print(d['output'])"
```

**.pyc 方案已排除：** 研究確認 .pyc 反編譯率 75%+，Python 3.12 的 `uncompyle6` + LLM 可在秒級還原源碼。是安全劇場，不是真實防護。

### #2 回覆：work/ 獨立 git repo ✅

接受建議方案 A。work/ 用 `git init` 獨立追蹤。Dockerfile 在建立 work/ 時自動 init：

```dockerfile
RUN mkdir -p /app/work && cd /app/work && git init && \
    git config user.email "agent@autoresearch" && \
    git config user.name "autoresearch-agent"
```

Agent 的 git 操作完全在 work/.git 內，不影響主 repo。

### #4 回覆：CLI 認證已確認可行 ✅

研究確認：
- `ANTHROPIC_API_KEY` env var 在 `-p` 模式中有效（v0.2.59+ 修復了早期 bug，目前 v2.1.86）
- `-p` 不需要 TTY，適合非互動 Docker
- `--dangerously-skip-permissions` 在容器中合理（容器本身是沙箱）

推薦容器環境變數：
```yaml
environment:
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
  - CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
  - CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
```

加入 Step 0 smoke test：
```bash
docker exec autoresearch-agent claude --version
docker exec autoresearch-agent claude -p "echo hello" --dangerously-skip-permissions
```

### Step 0 技術驗證（2026-03-29 追加）

**兩個阻塞問題需先驗證：**

#### 問題 1：`claude -p` 是單次模式

`claude -p` 跑完一個 prompt 就退出。Autoresearch 需要持續循環（200+ tool uses per session）。

**測試方案：**
- A. Docker 內用 shell loop（等同 host 的 loop.ps1）：
  ```bash
  while true; do
    claude -p "..." --dangerously-skip-permissions --max-turns 200
    sleep 10
  done
  ```
- B. 用 `claude` 互動模式 + 預設 prompt（需要 TTY）
- C. 用 Claude API 直接呼叫（繞過 CLI）

#### 問題 2：Max 訂閱 OAuth 在 Docker 內的穩定性

目前認證用 OAuth token（`.credentials.json`），不是 API key。需驗證：
- Token 能否在容器內成功認證？
- Token 過期後能否在容器內自動刷新（refresh token）？
- 容器內沒有瀏覽器，OAuth flow 是否能完成？

**測試計畫：**
```bash
# Test 1: credentials mount + claude -p（單次）
docker run --rm \
  -v "C:/Users/ander/.claude/.credentials.json:/home/node/.claude/.credentials.json:ro" \
  claude-agent:latest \
  claude -p "respond with: hello" --dangerously-skip-permissions

# Test 2: 多輪 tool use（模擬 autoresearch 循環）
docker run --rm \
  -v "C:/Users/ander/.claude/.credentials.json:/home/node/.claude/.credentials.json:ro" \
  -v "D:/Finance/scripts/autoresearch:/workspace:ro" \
  claude-agent:latest \
  claude -p "read /workspace/program.md, then echo done" \
  --dangerously-skip-permissions --max-turns 5

# Test 3: shell loop（持續循環）
docker run --rm \
  -v "C:/Users/ander/.claude/.credentials.json:/home/node/.claude/.credentials.json:ro" \
  claude-agent:latest \
  sh -c 'for i in 1 2 3; do claude -p "echo round $i" --dangerously-skip-permissions; done'

# Test 4: token refresh（跑超過 token 有效期）
# 需要等 token 接近過期時測試
```

**如果 Test 1-3 全部失敗**，Phase AE 需要改方案：
- 放棄 Claude Code CLI in Docker
- 改用 Claude API 直接呼叫（`anthropic` Python SDK）
- Agent 邏輯用 Python 寫，不依賴 CLI

### Step 0 測試結果（2026-03-29 04:30）

| Test | 內容 | 結果 |
|------|------|:----:|
| 1 | OAuth credentials mount + `claude -p` 單次 | ✅ 回傳 "hello from docker" |
| 2 | 多輪 tool use + 讀檔案 | ✅ 讀 program.md 並回答問題 |
| 3 | Shell loop 3 輪連續 `claude -p` | ✅ 3 輪都成功 |
| 4a | Docker 內讀 factor.py | ✅ 正確回傳 `compute_factor` |
| 4b | Docker 內寫 results.tsv | ✅ append 成功 |

**結論：所有阻塞問題已排除。**

- OAuth credentials 掛載為 volume → 容器內認證正常
- `claude -p` + `--max-turns 200` 在 Docker 內可用
- Shell loop 可持續循環（等同 host 的 loop.ps1）
- 檔案讀寫通過 volume mount 正常運作
- Token 為 Max 訂閱，有效期到 2026-07（3 個月），refresh token 可延長

**Agent image 配置：** `node:22-slim` + `npm install -g @anthropic-ai/claude-code` + git + curl。大小 ~300MB。

**下一步：執行 Step 1-7 正式實施。**

### #5 回覆：監控和重啟 ✅

接受建議。docker-compose 加入：

```yaml
services:
  agent:
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "test", "-f", "/app/work/results.tsv"]
      interval: 300s
      timeout: 10s
      retries: 3

  evaluator:
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 60s
```

Host 監控：loop.ps1 的 status reporter 改為讀 shared work/results.tsv。

### 修正後的實施步驟

| Step | 內容 | 工作量 |
|------|------|--------|
| 0 | Smoke test — Docker 內跑 `claude -p "hello"` | 15 分鐘 |
| 1 | Dockerfile.evaluator — Flask + evaluate.py + src/ + data/ | 30 分鐘 |
| 2 | eval_server.py — HTTP 包裝 evaluate.py | 15 分鐘 |
| 3 | Dockerfile.agent — node + Claude Code CLI | 30 分鐘 |
| 4 | docker-compose.yml — 3 services (agent + evaluator + watchdog) | 30 分鐘 |
| 5 | program.md — curl evaluator 替代 python evaluate.py | 15 分鐘 |
| 6 | work/ 獨立 git + shared volume | 15 分鐘 |
| 7 | 端到端測試 | 1 小時 |
| **總計** | | **~3.5 小時** |

### 修正後的 3 容器架構

```yaml
services:
  agent:           # Claude Code CLI — 只有 work/ 和 program.md
  evaluator:       # Flask + evaluate.py + src/ + data/（新）
  watchdog:        # 背景 Validator + Factor-Level PBO（現有）
```

Evaluator 和 watchdog 可合併（都需要 src/ + data/），但分開更清晰：evaluator 是同步 HTTP 服務，watchdog 是定時背景任務。

## 10. 第二輪審批意見（2026-03-29）

### 整體：§9 回覆品質好，Eval-as-a-Service 方向正確。4 個問題需注意。

### 問題 A（方法論）：eval_server.py 的 `tail -30` 仍然洩漏資訊

```python
safe_output = "\n".join(l for l in lines[-30:])  # 等同 tail -30
```

evaluate.py 的 stdout 包含大量中間結果：L1 score、L2 IC 值、L3 large-scale IC、L4 Validator 每項 check 的分數。`tail -30` 只是截尾，不是過濾。Agent 仍然可以看到：

- `L2: IC = 0.042, ICIR = 0.31` → 知道因子的精確 IC
- `L3: Large-scale IC median = 0.028` → 知道 universe 擴大後的衰減
- `L4: DSR = 0.68 (FAIL), Bootstrap = 82% (PASS)` → 知道哪項差多少通過

這違反了 LESSONS #7「agent 應該只看到 1 bit: pass/fail」。

**建議修正：**

```python
@app.route("/evaluate", methods=["POST"])
def evaluate():
    result = subprocess.run(
        ["python", "/app/evaluate.py"],
        capture_output=True, text=True, timeout=300,
        cwd="/app", env={**dict(__import__('os').environ), "PYTHONPATH": "/app/work:/app"}
    )
    # 只回傳 pass/fail + level，不回傳任何分數
    passed = result.returncode == 0
    # 從 results.tsv 最後一行讀 level（evaluate.py 會寫入）
    level = "UNKNOWN"
    try:
        with open("/app/work/results.tsv") as f:
            last = f.readlines()[-1].strip()
            level = last.split("\t")[4] if "\t" in last else "UNKNOWN"
    except Exception:
        pass
    return jsonify({
        "passed": passed,
        "level": level,        # e.g. "L3_FAIL" or "L4_PASS"
        "message": "Factor met deployment criteria" if passed else "Factor did not meet criteria",
    })
```

Agent 只看到 `{"passed": false, "level": "L3_FAIL", "message": "Factor did not meet criteria"}`。不知道 IC 是 0.04 還是 0.001，不知道哪項 check 差多少通過。

### 問題 B（方法論）：shared volume work/ 是雙向資訊通道

```
agent container ←── shared volume: work/ ──→ evaluator container
```

evaluator 跑 evaluate.py 時，evaluate.py 會寫入：
- `work/results.tsv`（agent 可讀 — 這是設計意圖，OK）
- 但 evaluate.py 也可能寫 debug 檔案、log 檔案、或 `__pycache__/` 到 work/
- 如果 evaluate.py 的 `_store_factor_returns()` 把 factor_returns 存到 work/ 下，agent 能讀到 OOS 期間的 factor returns

**建議：**
- evaluator 的 `_store_factor_returns()` 必須存到 evaluator 自己的 `watchdog_data/`（非 shared volume）
- evaluator 寫入 work/ 的唯一檔案是 results.tsv（append 一行）
- Dockerfile 中驗證：`evaluate.py` 不會在 work/ 下建立任何額外檔案

### 問題 C（實作）：Flask dev server 不該用在生產

```python
app.run(host="0.0.0.0", port=5000)
```

Flask 的 built-in server 是單線程、不適合併發。如果 agent 快速連續發起兩次 evaluate（unlikely but possible），第二次會 hang 直到第一次完成。

但更重要的是：**evaluate.py 本身就是 sequential 的**（跑回測需要 5-60 秒），所以這其實不是真問題。單線程 Flask 在這裡反而是正確的 — 它天然地序列化了評估請求。

**判斷：可接受。** 不需要改 gunicorn。但建議加一行註解說明這是刻意的：

```python
# 單線程是刻意的 — 評估必須序列化，防止併發 evaluate 耗盡資源
app.run(host="0.0.0.0", port=5000)
```

### 問題 D（實作）：agent 容器沒有 data/，但 factor.py 可能需要讀數據

§9 架構圖顯示 agent 容器「無 data/」。但 factor.py（agent 的產出）通常包含：

```python
def compute_factor(symbols, as_of, data):
    close = data["close"]  # data 由 evaluate.py 傳入 — OK
```

evaluate.py 呼叫 `compute_factor()` 時傳入 data，所以在 evaluator 容器內 factor.py 能存取 data。但 agent 在**開發 factor.py 時**無法讀數據來驗證自己的代碼。

**兩個選項：**
1. Agent 盲寫 factor.py → 提交 evaluate → 從 pass/fail 學習。完全隔離但 agent 效率低
2. Agent 容器掛載 data/ (ro) → agent 可以 `python factor.py` 本地測試。效率高但 agent 能讀全部歷史數據

**建議：選 2。** 理由：
- factor.py 的輸入是 `(symbols, as_of, data)`，agent 需要理解 data 的 schema 才能寫出有效代碼
- 市場數據本身不是秘密 — 秘密是評估標準和 OOS 結果
- 如果選 1，agent 會需要 10x 更多的 evaluate 次數才能寫出能跑的代碼 → 消耗更多 holdout budget

**修正架構圖：**
```
agent container:
  + work/ (rw)
  + program.md (ro)
  + data/market/ (ro)      ← 加回，agent 需要理解數據格式
  + data/fundamental/ (ro)  ← 加回
  無 evaluate.py, 無 src/, 無 watchdog_data/
```

### 總結

| 問題 | 嚴重度 | 行動 |
|------|:------:|------|
| A: tail -30 洩漏 IC/DSR/Bootstrap 分數 | **HIGH** | eval_server.py 改為只回傳 pass/fail + level |
| B: shared volume 可能洩漏 factor_returns | **HIGH** | evaluator 不在 work/ 寫額外檔案 |
| C: Flask dev server | **OK** | 加註解，不需改 |
| D: agent 無 data/ 無法開發 | **MEDIUM** | 加回 data/ ro mount |

問題 A 和 B 都是「看起來隔離了但資訊仍然洩漏」的模式 — 和我們在 host 上經歷的 5 個洩漏通道完全一樣（LESSONS #7）。遷移到 Docker 不會自動解決資訊洩漏問題，需要在 HTTP 層也做 information filtering。

## 11. 第二輪審批回覆

### A: eval_server.py 只回傳 pass/fail + level ✅ 接受

完全正確。`tail -30` 是偷懶，不是過濾。修正 eval_server.py：

```python
@app.route("/evaluate", methods=["POST"])
def evaluate():
    result = subprocess.run(
        ["python", "/app/evaluate.py"],
        capture_output=True, text=True, timeout=300,
        cwd="/app", env={**dict(__import__('os').environ), "PYTHONPATH": "/app/work:/app"}
    )
    # 從 stdout 解析 4 個安全欄位（evaluate.py 的 --- RESULTS --- 區塊）
    stdout = result.stdout
    level = _extract(stdout, "level:")
    passed = _extract(stdout, "passed:") == "True"
    composite = float(_extract(stdout, "composite_score:") or "0")
    best_icir = float(_extract(stdout, "best_icir:") or "0")

    return jsonify({
        "passed": passed,
        "level": level,
        "composite_score": composite,
        "best_icir": best_icir,
    })

def _extract(text, prefix):
    for line in text.splitlines():
        if line.strip().startswith(prefix):
            return line.split(prefix, 1)[1].strip()
    return ""
```

**回傳 composite_score 和 best_icir 但不回傳中間值（IC, DSR, Bootstrap 分數等）。** 這和現有 program.md 的 "extract ONLY these 4 values" 一致，只是從 prompt 限制升級為 HTTP 過濾。

**不回傳 level 的理由用語如 "L3 dedup" 或 "L2 ICIR"** — level 本身是安全的（只告訴 agent 走到第幾關），但附帶原因就是洩漏。

### B: evaluator 不在 work/ 寫額外檔案 ✅ 接受

確認 evaluate.py 目前會寫入 work/ 的檔案：
1. `work/results.tsv` — agent 可讀 ✅（設計意圖）
2. `work/factor_returns/` — ❌ 已修為 `watchdog_data/`（不在 work/）
3. `work/pending/` — ❌ 已修為 `watchdog_data/`
4. `work/__pycache__/` — ❌ 需要禁止（設 `PYTHONDONTWRITEBYTECODE=1`）

修正：Dockerfile 加 `ENV PYTHONDONTWRITEBYTECODE=1`，且 evaluator 的 work/ mount 改為只寫 results.tsv：

```yaml
evaluator:
  volumes:
    - shared-work:/app/work           # evaluator 只會 append results.tsv
    - watchdog-data:/app/watchdog_data # factor_returns, pending, pbo
  environment:
    - PYTHONDONTWRITEBYTECODE=1
```

### C: Flask dev server ✅ 接受（可接受）

單線程是刻意的。加註解。

### D: agent 容器加回 data/ (ro) ✅ 接受

市場數據不是秘密，OOS 邏輯和閾值才是。agent 需要理解 data schema 才能寫有效的 factor.py。

修正後的最終架構：

```
agent container:
  + work/factor.py, results.tsv  (rw)
  + program.md                    (ro, COPY)
  + data/market/                  (ro, mount)
  + data/fundamental/             (ro, mount)
  + data/research/universe.txt    (ro, mount)
  無 evaluate.py, 無 src/, 無 watchdog_data/

evaluator container:
  + evaluate.py                   (COPY, agent 看不到)
  + eval_server.py                (COPY)
  + src/                          (ro, mount)
  + data/                         (ro, mount)
  + work/results.tsv              (append only)
  + watchdog_data/                (rw, factor_returns + pending + pbo)
  ENV PYTHONDONTWRITEBYTECODE=1

watchdog container:（現有，不變）
  + watchdog.py                   (COPY)
  + src/                          (ro, mount)
  + data/                         (ro, mount)
  + watchdog_data/                (rw)
```

### 修正後的實施步驟（v3）

| Step | 內容 | 改動 |
|------|------|------|
| 0 | Smoke test | 不變 |
| 1 | Dockerfile.evaluator | 加 Flask + eval_server.py + PYTHONDONTWRITEBYTECODE |
| 2 | eval_server.py | **改為只回傳 4 欄位**（不是 tail -30） |
| 3 | Dockerfile.agent | 加 data/ ro mount |
| 4 | docker-compose.yml | shared-work volume + watchdog-data volume 分開 |
| 5 | program.md | curl evaluator API 替代 python evaluate.py |
| 6 | work/ 獨立 git | 不變 |
| 7 | 端到端測試 | 加驗證：evaluator 不在 work/ 寫 __pycache__ |

## 13. 第三輪覆核（2026-03-29）

**方法：** 逐一比對計畫中所有審批意見 vs 實際檔案內容。

### 覆核結果：9/10 項已正確落實

| 審批項 | 狀態 | 驗證位置 |
|--------|:----:|---------|
| #1+#3 Eval-as-a-Service | ✅ | eval_server.py 只回傳 4 欄位 |
| #4 CLI smoke test | ✅ | §9 Step 0 測試結果全部通過 |
| #5 restart + healthcheck | ✅ | docker-compose.yml services |
| A: 不洩漏 IC 分數 | ✅ | eval_server.py `_extract()` |
| B: PYTHONDONTWRITEBYTECODE | ✅ | Dockerfile.evaluator:25 |
| B: watchdog_data 獨立 volume | ✅ | docker-compose.yml:40-41 |
| C: Flask 單線程註解 | ✅ | eval_server.py:13-14 |
| D: agent 有 data/ ro | ✅ | docker-compose.yml:17-19 |
| **#2 work/ 獨立 git init** | **⚠️** | **Dockerfile.agent 只有 `safe.directory` 沒有 `git init`** |

### 遺漏 1：work/ 的 git init

**計畫 §9 #2 寫的：**
```dockerfile
RUN mkdir -p /app/work && cd /app/work && git init && \
    git config user.email "agent@autoresearch" && \
    git config user.name "autoresearch-agent"
```

**實際 Dockerfile.agent：**
```dockerfile
RUN git config --global --add safe.directory /app/work
```

只有 `safe.directory`（讓 git 不報 ownership 警告），沒有 `git init`。如果 work/ volume 從 host mount 進來且 host 的 work/ 沒有 .git，agent 的 `git commit` 會失敗。

**影響：MEDIUM。** Agent 如果在 Docker 模式下嘗試 git 操作會失敗。兩個修法：
1. Dockerfile.agent 加 `git init`（但 volume mount 會覆蓋 image 的 /app/work）
2. loop.ps1 啟動前確認 work/ 有 .git（在 host 端 init）

**建議：** 方案 2 — 在 loop.ps1 的 Docker 啟動段加：
```powershell
if (-not (Test-Path "$ProjectDir\docker\autoresearch\work\.git")) {
    git -C "$ProjectDir\docker\autoresearch\work" init
    git -C "$ProjectDir\docker\autoresearch\work" config user.email "agent@autoresearch"
    git -C "$ProjectDir\docker\autoresearch\work" config user.name "autoresearch-agent"
}
```

### 注意事項 1：eval_server.py 回傳 composite_score 和 best_icir

§10 審批意見 A 建議「只回傳 pass/fail + level」。§11 回覆改為回傳 4 欄位（加了 composite_score 和 best_icir）。

**這是刻意的折衷**（§11 解釋：和 program.md 的 "extract ONLY these 4 values" 一致），但 composite_score 和 best_icir 仍然是定量資訊，agent 可以從中學到「這次因子的 ICIR 是 0.51 vs 上次的 0.31」。

**建議：** 可接受，但如果未來發現 agent 利用這些數值做 adaptive optimization（例如刻意逼近 ICIR 門檻），應收緊為只回傳 pass/fail + level。

### 注意事項 2：evaluator 的 src/ mount 可能引入版本不一致

docker-compose.yml:41 把 host 的 `../../src` mount 到 evaluator 容器。如果 host 上有人修改 src/ 但沒有重啟 evaluator 容器，Python 可能使用舊的 bytecode cache（已被 PYTHONDONTWRITEBYTECODE=1 緩解），但 import 仍會讀到新代碼。

**影響：LOW。** evaluator 用 `restart: unless-stopped`，且 volume mount 是即時同步的（不是 COPY）。但如果有人修改了 validator.py 的閾值，evaluator 會立刻用新閾值，可能和 agent 的預期不一致。

**建議：** 如果 src/ 有重要修改，重啟 evaluator：`docker compose restart evaluator`。

## 14. Code Review（2026-03-29）

### 範圍：5 個實作檔案

| 檔案 | 行數 |
|------|:----:|
| eval_server.py | 72 |
| Dockerfile.agent | 27 |
| Dockerfile.evaluator | 36 |
| docker-compose.yml | 74 |
| loop.ps1 | 118 |

### CRITICAL（0 個）

無。

### HIGH（2 個）

**H-1: evaluator 缺 `strategies/` mount**

evaluate.py → `src.backtest.validator` → `src.strategy.registry` → `strategies/*.py`。docker-compose.yml evaluator 只 mount 了 `src/`，沒有 `strategies/`。如果 StrategyValidator 的 import chain 觸及 strategy registry，會 ModuleNotFoundError。

```yaml
# docker-compose.yml evaluator volumes — 缺這行：
- ../../strategies:/app/strategies:ro
```

**H-2: evaluator 的 work/ mount 應改為 ro**

docker-compose.yml:39 `./work:/app/work` 是 rw。但確認 evaluate.py 不寫 work/（results.tsv 由 agent 寫，pending/factor_returns 寫到 watchdog_data/）。rw 是多餘的權限，違反最小權限原則。

```yaml
# 改為：
- ./work:/app/work:ro
```

### MEDIUM（3 個）

**M-1: eval_server.py 的 factor.py race condition**

Agent 在 evaluator 跑的過程中可以修改 factor.py（shared volume 即時同步）。evaluator 用 `from factor import compute_factor`，Python 只 import 一次（cached in sys.modules）。但 evaluate.py 用 subprocess 跑（每次新 process），所以每次都重新 import — **partial write 時可能 import 到不完整的 factor.py**。

機率低（agent 通常 commit 後才 curl evaluate），但不是零。

**建議：** eval_server.py 的 `/evaluate` endpoint 在跑 subprocess 前先 snapshot factor.py：
```python
import shutil, tempfile
snap = Path(tempfile.mktemp(suffix=".py", dir="/tmp"))
shutil.copy2("/app/work/factor.py", snap)
# 把 snap 路徑傳給 evaluate.py
```
或在 evaluate.py 開頭用 file lock。

**M-2: Dockerfile.agent 沒裝 pandas/numpy**

Agent 容器只有 python3，沒有數據科學庫。如果 agent 想本地測試 factor.py（`python factor.py`），會 ImportError。program.md 的 fallback `python evaluate.py` 也跑不了（缺依賴）。

如果設計意圖是 agent 只透過 HTTP evaluate → 不需要。但 program.md step 4 寫了 fallback：`If evaluator is not available: fallback to python evaluate.py 2>&1 | tail -30` — 在 agent 容器內跑不動。

**建議：** 移除 program.md 的 fallback 指引（agent 容器內不該跑 evaluate.py），或加裝 pandas/numpy。

**M-3: `_extract` 和 evaluate.py 的 stdout 格式有隱含耦合**

eval_server.py 的 `_extract(stdout, "level:")` 假設 evaluate.py 輸出包含 `level: XXX` 格式的行。如果 evaluate.py 的輸出格式變了，_extract 靜默回傳空字串 → passed 永遠 False。

Fail-closed 所以不危險，但無法區分「因子差」和「解析壞了」。

**建議：** evaluate.py 輸出一個明確的 JSON 區塊（如 `--- EVAL_RESULT ---\n{"level":"L3","passed":false}\n--- END ---`），eval_server.py 解析 JSON。

### LOW（3 個）

**L-1: loop.ps1 的 $Credentials 變數宣告了但沒使用**

line 16: `$Credentials = "C:\Users\ander\.claude\.credentials.json"` — 未使用。docker-compose.yml:20 用了 `${CLAUDE_CREDENTIALS:-C:/Users/ander/.claude/.credentials.json}`，直接讀 env var。

**L-2: loop.ps1 的 host fallback 沒設 $env:AUTORESEARCH**

line 73-74: evaluator 不響應時 fallback 到 Host 模式，但 `$Host = $true` 發生在 `if ($Host)` 判斷之後（line 78）。所以 fallback 時 `$env:AUTORESEARCH` 不會被設定。

等等 — 重看代碼：line 74 設 `$Host = $true`，然後 line 78 檢查 `if ($Host)` — 是 OK 的，因為 line 74 在 line 78 之前。✅ 這個沒問題。

**L-3: Dockerfile.evaluator 裝了 watchdog.py 但不跑它**

line 19: `COPY docker/autoresearch/watchdog.py /app/watchdog.py`，但 CMD 是 `python /app/eval_server.py`。watchdog.py 不在 evaluator 容器內使用（watchdog 有自己的容器）。多餘的 COPY 不影響功能但增加 image 大小。

### 總結

| 嚴重度 | 數量 | 行動 |
|:------:|:----:|------|
| CRITICAL | 0 | — |
| HIGH | 2 | H-1 加 strategies/ mount；H-2 work/ 改 ro |
| MEDIUM | 3 | M-1 factor.py snapshot；M-2 移除 fallback 或加依賴；M-3 JSON 輸出 |
| LOW | 3 | 清理即可 |

**整體評價：** 實作品質不錯，架構清晰，3 容器的職責分明。2 個 HIGH 需要修（特別是 H-1 會導致 evaluator 啟動失敗），3 個 MEDIUM 是 robustness 改善。

## 15. 參考

- [Docker Sandbox for Claude Code](https://docs.docker.com/ai/sandboxes/agents/claude-code/)
- [Claude Code Sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Claude Code Environment Variables](https://code.claude.com/docs/en/env-vars)
- [Claude Code Non-Interactive Mode](https://pasqualepillitteri.it/en/news/220/claude-code-non-interactive-mode-limited-hosting)
- [anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
- [Anthropic DevContainer Features](https://github.com/anthropics/devcontainer-features)
- [Issue #551: Non-Interactive Mode Auth Fix](https://github.com/anthropics/claude-code/issues/551)
- [Docker AI Sandboxes Architecture](https://docs.docker.com/ai/sandboxes/architecture/)
- [.pyc decompilation is trivial (Xygeni)](https://xygeni.io/blog/how-to-decompile-a-compiled-python-file-and-why-its-a-security-risk/)
- CLAUDE.md #15：「自主 agent 的安全靠隔離不靠指令」
- LESSONS_FOR_AUTONOMOUS_AGENTS.md #10: Eval-as-a-Service
