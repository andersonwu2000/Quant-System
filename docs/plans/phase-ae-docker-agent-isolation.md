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

## 8. 參考

- [Docker Sandbox for Claude Code](https://docs.docker.com/ai/sandboxes/agents/claude-code/)
- [Claude Code Sandboxing](https://code.claude.com/docs/en/sandboxing)
- [anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
- [Anthropic DevContainer Features](https://github.com/anthropics/devcontainer-features)
- CLAUDE.md #15：「自主 agent 的安全靠隔離不靠指令」
