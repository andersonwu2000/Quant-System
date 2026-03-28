# Phase Y：容器化 Autoresearch Agent ✅ 已完成

> 解決 Phase X 檢討報告中識別的三個結構性問題：
> 共享可變狀態、權限模型二元化、Git 角色耦合

## 1. 目標

將 autoresearch agent 從「在主 repo 裸跑」遷移到「Docker 容器內隔離運行」，
實現以下安全保證：

| 保證 | 機制 |
|------|------|
| Agent 無法修改 evaluate.py / program.md | Volume 唯讀掛載 |
| Agent 無法寫入 autoresearch/ 以外的檔案 | 只有 workdir 可寫 |
| Agent 的 git reset 不影響主 repo | 獨立 git 歷史 |
| Agent 崩潰不留殭屍進程 | 容器生命週期管理 |
| Agent 無法安裝套件 | `read_only: true` 根檔案系統 |
| Agent 無法存取外網 | `internal` network（僅允許 host API） |
| 自動重啟 + 健康監控 | Watchdog + restart policy |

> **N-01 注意：** 網路非完全隔離。容器使用 `internal` network + `host.docker.internal`
> 存取 host API server (port 8000) 供因子畢業流程使用。容器可存取 host 任意 port，
> 但無法存取外部網路。如需更嚴格隔離，可改用 iptables 規則限制僅允許 port 8000。

## 2. 架構

```
Host (Windows 11)
├── D:\Finance\                          ← 主 repo（人類操作）
│   ├── data/                            ← 市場資料
│   ├── scripts/autoresearch/            ← 原始碼（evaluate.py 等）
│   └── docker/autoresearch/             ← Docker 配置（新增）
│       ├── Dockerfile
│       ├── docker-compose.yml
│       ├── init.ps1
│       └── watchdog.py
│
└── Docker Container: autoresearch-agent
    ├── /app/data/          (bind mount, READ-ONLY)  ← data/ 目錄
    ├── /app/src/           (bind mount, READ-ONLY)  ← src/ 模組（evaluate.py 依賴）
    ├── /app/work/          (named volume, READ-WRITE) ← agent 工作區
    │   ├── factor.py       ← agent 唯一可改的代碼
    │   ├── results.tsv     ← 實驗日誌
    │   ├── run.log         ← evaluate.py 輸出
    │   └── .git/           ← 獨立 git repo（僅追蹤 factor.py）
    └── /app/evaluate.py    (COPY, immutable)  ← 容器建構時複製
```

### 關鍵設計決策

**Q: Claude Code 需要網路存取 Anthropic API，怎麼隔離？**

A: 不在容器內跑 Claude Code。改為：
- Claude Code 在 **host** 上執行（loop.ps1）
- Claude Code 的 Edit tool 寫入 host 上的 bind mount 目錄
- `python evaluate.py` 透過 `docker exec` 在容器內執行
- 容器使用 `internal` network（僅能存取 host API，無外網）

```
Host Claude Code                    Docker Container
     │                                    │
     ├─ Edit factor.py ──────────────────►│ /app/work/factor.py (bind mount)
     │                                    │
     ├─ docker exec ... python ──────────►│ evaluate.py 讀 /app/work/factor.py
     │         evaluate.py                │ 讀 /app/data/ (read-only)
     │                                    │ 輸出到 stdout
     │◄───────── stdout ─────────────────┤
     │                                    │
     ├─ git (在 host work/ 目錄)          │ （容器內無 git）
     └─ 記錄 results.tsv                  │
```

**Q: 為什麼不直接在容器內跑 Claude Code？**

A: 因為：
1. Claude Code 需要網路 → 容器需要開網路 → 失去網路隔離
2. Claude Code 需要認證（API key）→ key 暴露在容器內
3. Claude Code 的 Edit/Read 工具操作 host 檔案 → bind mount 複雜度增加
4. 在 host 跑 Claude Code + 容器跑 evaluate.py 是最小改動方案

**Q: Agent 的 git 操作怎麼處理？**

A: Git 在 host 的 `work/` 目錄操作（不在容器內）。work/ 有自己的 `.git/`
（獨立 repo），`git reset --hard` 只影響 work/ 內的檔案，不影響主 repo。

## 3. 檔案結構

### 3.1 Dockerfile

```dockerfile
FROM python:3.12-slim

# P-06: 版本鎖定，確保 evaluate.py 行為可重現
# 建構時執行 pip freeze > /app/requirements.lock 記錄實際版本
RUN pip install --no-cache-dir \
    "numpy>=2.0,<3" \
    "pandas>=2.0,<4" \
    "scipy>=1.12,<2" \
    "pyarrow>=15,<24"

# 複製 evaluate.py + watchdog.py（不可變）
COPY scripts/autoresearch/evaluate.py /app/evaluate.py
COPY docker/autoresearch/watchdog.py /app/watchdog.py

# 工作目錄
WORKDIR /app

# 非 root 用戶
RUN useradd -m -s /bin/bash researcher && \
    mkdir -p /app/work && chown researcher:researcher /app/work
USER researcher

# 入口：等待 docker exec 指令
CMD ["sleep", "infinity"]
```

### 3.2 docker-compose.yml

```yaml
services:
  autoresearch:
    build:
      context: ../..
      dockerfile: docker/autoresearch/Dockerfile
    container_name: autoresearch-agent
    restart: unless-stopped
    # 需要存取 host API server (localhost:8000) 供 _auto_submit 畢業流程
    # Windows Docker Desktop: host.docker.internal 自動指向 host
    extra_hosts:
      - "host.docker.internal:host-gateway"
    networks:
      - autoresearch-net
    environment:
      - API_URL=http://host.docker.internal:8000
    mem_limit: 4g                   # 記憶體限制
    cpus: 2                         # CPU 限制
    security_opt:
      - no-new-privileges:true      # 禁止提權
    read_only: true                 # 根檔案系統唯讀
    tmpfs:
      - /tmp:size=512m              # 暫存區（evaluate.py 可能需要）
    volumes:
      # 市場資料（唯讀）
      - ../../data:/app/data:ro
      # Agent 工作區（唯一可寫）
      - autoresearch-work:/app/work
      # evaluate.py 的依賴模組（唯讀）
      - ../../src:/app/src:ro

  watchdog:
    build:
      context: ../..
      dockerfile: docker/autoresearch/Dockerfile
    container_name: autoresearch-watchdog
    restart: unless-stopped
    network_mode: none
    mem_limit: 256m
    read_only: true
    volumes:
      - autoresearch-work:/app/work:ro
      - ../../scripts/autoresearch:/app/reference:ro
    entrypoint: ["python", "/app/watchdog.py"]

networks:
  autoresearch-net:
    internal: true    # 容器間可通訊，但無外網存取

volumes:
  autoresearch-work:
```

### 3.3 init.ps1（Host 端初始化腳本）

```powershell
# Host 端啟動腳本：初始化 work/ 目錄 + 啟動容器
# 用法：powershell -ExecutionPolicy Bypass -File docker/autoresearch/init.ps1

$WorkDir = "D:\Finance\docker\autoresearch\work"
$ScriptDir = "D:\Finance\scripts\autoresearch"

# 1. 初始化 work/ 目錄（首次啟動）
if (-not (Test-Path $WorkDir)) { New-Item -ItemType Directory -Path $WorkDir }
if (-not (Test-Path "$WorkDir\factor.py")) {
    Copy-Item "$ScriptDir\factor.py" "$WorkDir\factor.py"
    Copy-Item "$ScriptDir\results.tsv" "$WorkDir\results.tsv"
}

# 2. 初始化獨立 git repo
#    P-02: results.tsv 不進 git，防止 git reset 清空
if (-not (Test-Path "$WorkDir\.git")) {
    Push-Location $WorkDir
    git init
    "results.tsv`nrun.log" | Out-File -Encoding ascii .gitignore
    git add factor.py .gitignore
    git commit -m "init: autoresearch workspace"
    Pop-Location
}

# 3. 建構並啟動容器
Push-Location "D:\Finance\docker\autoresearch"
docker compose build
docker compose up -d
Pop-Location

# 4. 驗證容器健康
docker exec autoresearch-agent python -c "import numpy, pandas, scipy; print('OK')"

Write-Host "`nContainer ready. Start research with:" -ForegroundColor Green
Write-Host "  powershell -File scripts/autoresearch/loop-docker.ps1"
```

### 3.4 loop-docker.ps1（Host 端 Claude Code 循環）

```powershell
# Host 端 Claude Code 循環
# Claude Code 在 host 跑，evaluate.py 在 Docker 內跑

# P-05: prompt 只定義 Docker 特定差異，研究協議由 program.md 定義
$prompt = @"
Read scripts/autoresearch/program.md for the full research protocol, then begin the experiment loop.

Docker-specific overrides:
- factor.py location: docker/autoresearch/work/factor.py
- results.tsv location: docker/autoresearch/work/results.tsv
- Run evaluate: docker exec autoresearch-agent python /app/evaluate.py
- Git operations: cd docker/autoresearch/work first
- NEVER modify files outside docker/autoresearch/work/

Start now. Read program.md first.
"@

while ($true) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Autoresearch (Docker) starting...     " -ForegroundColor Cyan
    Write-Host "  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    claude -p $prompt --dangerously-skip-permissions --max-turns 200

    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Session ended. Restarting in 10s..." -ForegroundColor Yellow
    Start-Sleep -Seconds 10
}
```

### 3.5 watchdog.py

```python
"""Autoresearch Watchdog — 容器內共生監控進程

每 60 秒檢查：
1. factor.py 是否存在且可讀
2. results.tsv 是否持續成長（停滯 = agent 可能卡住）
3. evaluate.py checksum 是否與建構時一致
4. /app/work/ 以外是否有新增檔案
5. 磁碟用量是否異常
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path

WORK_DIR = Path("/app/work")
CHECK_INTERVAL = 60                    # 秒
STALE_THRESHOLD = 1800                 # 30 分鐘無更新 = 停滯
# N-03: watchdog 只寫 stdout，不寫檔案（volume 是 :ro）
# 用 docker logs autoresearch-watchdog 查看

def sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()

def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8").strip().splitlines())

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)  # N-03: stdout only, use `docker logs` to view

def main():
    log("Watchdog started")

    # 記錄 evaluate.py 的初始 checksum
    eval_checksum = sha256(Path("/app/evaluate.py"))
    log(f"evaluate.py checksum: {eval_checksum[:16]}...")

    last_result_lines = count_lines(WORK_DIR / "results.tsv")
    last_update_time = time.time()
    consecutive_crashes = 0        # P-03: track consecutive crash count

    while True:
        time.sleep(CHECK_INTERVAL)

        # 1. factor.py 存在性
        if not (WORK_DIR / "factor.py").exists():
            log("WARNING: factor.py missing!")

        # 2. results.tsv 成長檢查
        current_lines = count_lines(WORK_DIR / "results.tsv")
        if current_lines > last_result_lines:
            last_result_lines = current_lines
            last_update_time = time.time()
            log(f"Progress: results.tsv has {current_lines} entries")
        elif time.time() - last_update_time > STALE_THRESHOLD:
            stale_min = int((time.time() - last_update_time) / 60)
            log(f"STALE: No new results for {stale_min} minutes")

        # 3. evaluate.py 完整性
        current_eval = sha256(Path("/app/evaluate.py"))
        if current_eval != eval_checksum:
            log(f"ALERT: evaluate.py checksum changed! was={eval_checksum[:16]}, now={current_eval[:16]}")

        # 4. 工作區異常檔案
        expected = {"factor.py", "results.tsv", "run.log", ".git", ".gitignore"}
        actual = {p.name for p in WORK_DIR.iterdir()} if WORK_DIR.exists() else set()
        unexpected = actual - expected
        if unexpected:
            log(f"WARNING: unexpected files in work/: {unexpected}")

        # 5. P-03: 連續 crash 偵測（用 mtime 判斷是否有新的 run）
        run_log = WORK_DIR / "run.log"
        if run_log.exists():
            mtime = run_log.stat().st_mtime
            if not hasattr(main, '_last_runlog_mtime'):
                main._last_runlog_mtime = 0
            if mtime > main._last_runlog_mtime:  # run.log 被更新了
                main._last_runlog_mtime = mtime
                content = run_log.read_text(encoding="utf-8", errors="ignore")
                if "--- CRASH ---" in content:
                    consecutive_crashes += 1
                    log(f"WARNING: evaluate.py crashed ({consecutive_crashes} consecutive)")
                    if consecutive_crashes >= 5:
                        log("ALERT: 5+ consecutive crashes — agent may be stuck in crash loop!")
                else:
                    consecutive_crashes = 0  # reset on successful run

        # 6. §8 退出條件偵測（飽和 + OOS 衰退）
        if (WORK_DIR / "results.tsv").exists():
            lines = (WORK_DIR / "results.tsv").read_text(
                encoding="utf-8", errors="ignore"
            ).strip().splitlines()[1:]  # skip header
            if len(lines) >= 50:
                recent = lines[-50:]
                discard_count = sum(1 for l in recent if "\tdiscard\t" in l)
                if discard_count >= 50:
                    log("ALERT: 50 consecutive discards — factor space may be exhausted")
            # OOS 衰退：連續 L4 通過但 L5 失敗
            l4_fail_l5 = 0
            for l in reversed(lines):
                if "\tL4\t" in l and "L5 OOS fail" in l:
                    l4_fail_l5 += 1
                else:
                    break
            if l4_fail_l5 >= 10:
                log(f"ALERT: {l4_fail_l5} consecutive L4-pass-L5-fail — possible OOS overfitting")

        # 7. 磁碟用量
        total_size = sum(
            f.stat().st_size for f in WORK_DIR.rglob("*") if f.is_file()
        ) if WORK_DIR.exists() else 0
        if total_size > 100 * 1024 * 1024:  # > 100MB
            log(f"WARNING: work/ size = {total_size / 1024 / 1024:.1f}MB")

if __name__ == "__main__":
    main()
```

## 4. 安全對照表

| 風險（§8 of 檢討報告） | Docker 方案如何解決 |
|------------------------|-------------------|
| 1.1 殭屍 Daemon | `restart: unless-stopped` + 容器生命週期 |
| 1.2 越權寫入 | Volume 唯讀，只有 /app/work 可寫 |
| 1.3 git reset 回滾基礎設施 | 獨立 git repo 在 work/，主 repo 不受影響 |
| 1.4 權限提示阻擋 | Host 端 `--dangerously-skip-permissions`，但 docker exec 限制容器內能做的事 |
| 1.5 Audit 誤報 | 不需要 audit hook，Docker volumes 即保證 |
| 1.6 results.tsv 被清空 | results.tsv 不進 git（.gitignore），git reset 不影響 |
| 8.1 OOS 間接過擬合 | evaluate.py L5 只輸出 pass/fail，不洩漏 OOS 具體數值 |
| 8.2 Context 耗盡 | loop-docker.ps1 自動重啟 |
| 8.3 複雜度蔓延 | 不解決（需要 evaluate.py 加限制） |
| 8.4 Git 歷史爆炸 | 獨立 work/.git，可隨時重建 |
| 8.5 多 Agent 衝突 | Docker 單容器 = 天然互斥 |
| 8.6 資料時效性 | 更新 host data/ 後重啟容器即可 |
| 8.7 靜默失敗 | Watchdog 偵測 results.tsv 停滯 |
| 8.8 成本失控 | 不解決（Claude Code 在 host 端，與容器無關） |

## 5. 實作步驟

### 前置：安裝 Docker Desktop

```powershell
# 1. 下載 Docker Desktop for Windows
#    https://docs.docker.com/desktop/setup/install/windows-install/
# 2. 安裝，啟用 WSL2 backend
# 3. 重啟電腦
# 4. 驗證
docker --version
docker compose version
```

### Step 1：建立 Docker 配置（~30 分鐘）

```
docker/autoresearch/
├── Dockerfile
├── docker-compose.yml
├── init.ps1              ← Host 端初始化腳本
├── watchdog.py
└── work/                 ← agent 工作區（init.ps1 自動建立）
```

### Step 2：建構 image（~5 分鐘）

**建構前須修改 evaluate.py：** `_auto_submit` 的 URL 從 `127.0.0.1` 改為
讀取環境變數，容器內預設用 `host.docker.internal`：

```python
# evaluate.py L739 修改為：
api_url = os.environ.get("API_URL", "http://127.0.0.1:8000")
resp = requests.post(f"{api_url}/api/v1/auto-alpha/submit-factor", ...)
```

docker-compose.yml 加入環境變數：
```yaml
environment:
  - API_URL=http://host.docker.internal:8000
```

```powershell
cd D:\Finance\docker\autoresearch
docker compose build
```

### Step 3：初始化工作區 + 啟動容器（~10 分鐘）

init.ps1 統一處理：初始化 work/ → 建構 image → 啟動容器 → 驗證健康。

```powershell
powershell -ExecutionPolicy Bypass -File docker/autoresearch/init.ps1
```

### Step 4：驗證 + 安全測試（~10 分鐘）

```powershell
# 功能測試
docker exec autoresearch-agent python -c "import numpy; print('OK')"
docker exec autoresearch-agent python /app/evaluate.py

# 安全測試（以下應全部失敗）
docker exec autoresearch-agent touch /app/data/hack.txt     # 唯讀 volume
docker exec autoresearch-agent pip install requests          # read_only root
docker exec autoresearch-agent python -c "import urllib.request; urllib.request.urlopen('https://google.com')"  # internal network，無外網

# 隔離測試
cd D:\Finance && git status  # 主 repo 應乾淨

# 啟動 Claude Code loop
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop-docker.ps1
```

## 6. 日常操作

| 操作 | 指令 |
|------|------|
| 啟動研究 | `powershell -File scripts/autoresearch/loop-docker.ps1` |
| 查看進度 | `cat docker/autoresearch/work/results.tsv` |
| 查看 watchdog | `docker logs autoresearch-watchdog --tail 20` |
| 停止研究 | Ctrl+C（停 Claude Code loop） |
| 停止容器 | `docker compose -f docker/autoresearch/docker-compose.yml down` |
| 更新 evaluate.py | 修改 scripts/ 的原始檔 → `docker compose build` → `docker compose up -d` |
| 更新市場資料 | 更新 data/ → 自動生效（bind mount） |
| 清理重來 | `docker volume rm autoresearch_autoresearch-work` |
| 提取成功因子 | 見下方「因子畢業流程」 |

### 因子畢業流程（P-04）

流程已在 auto-alpha pipeline 中實作，全自動無需人工介入：

```
L5 通過
  → evaluate.py _auto_submit() 自動提交到 API
    → POST /api/v1/auto-alpha/submit-factor
      → StrategyValidator 15 項驗證
        → >= 13/15 → 自動部署 Paper Trading（PaperDeployer）
        → < 13/15 → 記錄但不部署
```

Docker 環境下 _auto_submit 運作方式：
- 容器使用 `internal` network + `host.docker.internal` 存取 host API
- evaluate.py 中的 URL 需改為 `http://host.docker.internal:8000/...`
- 無外網存取，僅能連到 host

人類介入點：
- Paper Trading 運行 3 個月後，審查績效決定是否上線 live
- 這是唯一需要人工的步驟

## 7. 限制與取捨

| 取捨 | 說明 |
|------|------|
| Claude Code 仍在 host 無限制 | Docker 保護的是 evaluate.py 執行環境，不是 Claude Code 本身。Agent 的 Edit tool 直接寫 host 檔案。但因為只操作 work/ 目錄，影響範圍有限。 |
| 需要安裝 Docker Desktop | Windows 11 Pro 支援 Hyper-V，安裝一次即可。 |
| evaluate.py 更新需重建容器 | 不頻繁，且 `docker compose build` 很快（cache）。 |
| 首次 docker compose build 較慢 | 需下載 python:3.12-slim + pip install，約 2-5 分鐘。後續有 cache。 |
| OOS 過擬合靠 evaluate.py 處理 | L5 只輸出 pass/fail（不洩漏數值），但長期仍有間接洩漏風險。容器隔離不解決此問題。 |
| _auto_submit 需 API 存取 | 容器用 `internal` network + `host.docker.internal` 存取 host API server。無外網。evaluate.py 的 URL 需改為 `http://host.docker.internal:8000/...`。 |
| 不解決成本問題 | Claude API 費用在 host 端產生，與容器無關。 |

## 8. 退出條件（P-07）

系統不應永遠運行。定義以下停止條件：

| 條件 | 門檻 | 動作 |
|------|------|------|
| **短期目標達成** | 找到 3 個通過 L5 + Stage 2 的獨立因子 | 停止，進入人類審查 |
| **因子空間飽和** | 連續 50 個實驗無 keep（全部 discard） | 停止，更換研究方向 |
| **每日成本上限** | API 費用 > $50/天 | 暫停至隔天 |
| **每週成本上限** | API 費用 > $200/週 | 暫停至下週 |
| **OOS 信號衰退** | 連續 10 個 L4 通過但 L5 失敗 | 警告：可能開始過擬合 OOS |
| **資料過期** | 最新市場資料 > 3 個月前 | 停止，先更新資料 |

Watchdog 負責偵測飽和與 OOS 衰退，輸出至 stdout（`docker logs autoresearch-watchdog` 查看）。
成本控制需要人類在 Anthropic dashboard 設定用量上限。

## 9. 時程估計

| 步驟 | 時間 |
|------|------|
| 安裝 Docker Desktop | 15 分鐘（下載 + 安裝 + 重啟） |
| 建立配置檔案 | 30 分鐘 |
| 建構 + 測試容器 | 15 分鐘 |
| 安全驗證 | 10 分鐘 |
| loop-docker.ps1 整合測試 | 15 分鐘 |
| **總計** | **~1.5 小時** |

---

## 10. 殘留問題追蹤（2026-03-28 審查）

| 問題 | 嚴重度 | 現狀 | 說明 |
|------|:------:|:----:|------|
| **Host 安全性** | HIGH | **仍存在** | `--dangerously-skip-permissions` 在 3 個啟動腳本中。Claude Code 在 host 有完整寫入權限。Docker 只保護 evaluate.py 執行環境，不保護 host 檔案系統。prompt 約束不等於安全保證。 |
| **監控被動** | MEDIUM | **仍存在** | watchdog 只寫 stdout（`docker logs` 查看），無主動推送通知（無 Discord/LINE/Telegram）。agent 卡住 30 分鐘 watchdog 會 log「STALE」但沒人看就不知道。 |
| 環境相容性 | MEDIUM | **已解決** | evaluate.py 用 `PROJECT_ROOT` env var，容器內 Linux 路徑、host 上 Windows 路徑各自獨立。 |
| I/O 效能 | LOW | **影響小** | Windows Docker bind mount 理論上較慢，但 evaluate.py 一次性載入 parquet 到記憶體（~2-3 秒），非瓶頸。 |

### Host 安全性緩解方案（未實作）

目前唯一防護是 program.md 的 prompt 指令（「只編輯 work/factor.py」）。可能的硬性防護：

1. **Claude Code hooks**（`settings.json` 的 `PreToolUse`）— 在 Edit/Write 前檢查路徑是否在 `docker/autoresearch/work/` 內，不是就 reject。**最實際的方案**，不需要改 Docker 配置。
2. **Windows ACL** — 對 `src/`、`scripts/` 等目錄設定只讀 ACL，但 Claude Code 可能用管理員權限繞過。
3. **Git pre-commit hook** — 拒絕修改 `work/` 以外的檔案。但 Claude Code 的 Edit tool 不走 git。

### 監控被動緩解方案（未實作）

1. **watchdog 加通知** — crash 連續 3 次或 stale 30 分鐘時呼叫 `src/notifications/` 的 Discord/LINE/Telegram。需要容器有 host API 存取（已有 internal network）。
2. **run.ps1 加 health check** — 每 10 分鐘檢查 `docker logs --since 10m autoresearch-watchdog` 是否有 ALERT/WARNING，有的話印到 console。
