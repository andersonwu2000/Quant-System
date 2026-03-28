# Phase AE：Agent 真隔離 — Docker Container 內跑 Claude Code

> 問題：Agent（Claude Code）在 host 跑，有完整文件系統權限。Hooks 可被繞過（`bash -c "cat evaluate.py"`）。Docker 容器只跑 `sleep infinity`，沒有隔離任何東西。
> 教訓：CLAUDE.md #15「自主 agent 的安全靠隔離不靠指令」。prompt 限制和 hooks 被繞過 3 次以上。

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

## 10. 參考

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
