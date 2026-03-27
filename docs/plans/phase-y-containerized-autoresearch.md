# Phase Y：容器化 Autoresearch Agent

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
| Agent 無法安裝套件或存取任意網路 | 網路白名單 |
| 自動重啟 + 健康監控 | Watchdog + restart policy |

## 2. 架構

```
Host (Windows 11)
├── D:\Finance\                          ← 主 repo（人類操作）
│   ├── data/                            ← 市場資料
│   ├── scripts/autoresearch/            ← 原始碼（evaluate.py 等）
│   └── docker/autoresearch/             ← Docker 配置（新增）
│       ├── Dockerfile
│       ├── docker-compose.yml
│       ├── entrypoint.sh
│       └── watchdog.py
│
└── Docker Container: autoresearch-agent
    ├── /app/repo/          (bind mount, READ-ONLY)  ← 整個 repo
    ├── /app/data/          (bind mount, READ-ONLY)  ← data/ 目錄
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
- 容器本身 **無網路**（`network_mode: none`）

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
RUN pip install --no-cache-dir \
    numpy==2.2.6 \
    pandas==2.3.3 \
    scipy==1.16.3 \
    pyarrow==23.0.1

# 複製 evaluate.py（不可變）
COPY scripts/autoresearch/evaluate.py /app/evaluate.py

# 工作目錄
WORKDIR /app

# 非 root 用戶
RUN useradd -m -s /bin/bash researcher
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
    network_mode: none              # 無網路存取
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

volumes:
  autoresearch-work:
```

### 3.3 entrypoint.sh（Host 端啟動腳本）

```bash
#!/bin/bash
# Host 端啟動腳本：初始化 work/ 目錄 + 啟動容器 + 啟動 Claude Code loop

WORK_DIR="D:/Finance/docker/autoresearch/work"
SCRIPT_DIR="D:/Finance/scripts/autoresearch"

# 1. 初始化 work/ 目錄（首次啟動）
mkdir -p "$WORK_DIR"
if [ ! -f "$WORK_DIR/factor.py" ]; then
    cp "$SCRIPT_DIR/factor.py" "$WORK_DIR/factor.py"
    cp "$SCRIPT_DIR/results.tsv" "$WORK_DIR/results.tsv"
fi

# 2. 初始化獨立 git repo（如果不存在）
#    P-02 fix: results.tsv 不進 git，防止 git reset 清空實驗記錄
if [ ! -d "$WORK_DIR/.git" ]; then
    cd "$WORK_DIR"
    git init
    echo "results.tsv" > .gitignore
    echo "run.log" >> .gitignore
    echo "watchdog.log" >> .gitignore
    git add factor.py .gitignore
    git commit -m "init: autoresearch workspace"
fi

# 3. 啟動容器
cd "D:/Finance/docker/autoresearch"
docker compose up -d

# 4. 驗證容器健康
docker exec autoresearch-agent python -c "import numpy, pandas, scipy; print('OK')"

echo "Container ready. Start Claude Code loop with:"
echo "  powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop-docker.ps1"
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
import os
import time
from datetime import datetime
from pathlib import Path

WORK_DIR = Path("/app/work")
REF_DIR = Path("/app/reference")      # 掛載的原始 autoresearch/
CHECK_INTERVAL = 60                    # 秒
STALE_THRESHOLD = 1800                 # 30 分鐘無更新 = 停滯
LOG_FILE = WORK_DIR / "watchdog.log"

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
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def main():
    log("Watchdog started")

    # 記錄 evaluate.py 的初始 checksum
    eval_checksum = sha256(Path("/app/evaluate.py"))
    log(f"evaluate.py checksum: {eval_checksum[:16]}...")

    last_result_lines = count_lines(WORK_DIR / "results.tsv")
    last_update_time = time.time()

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
        expected = {"factor.py", "results.tsv", "run.log", ".git", "watchdog.log"}
        actual = {p.name for p in WORK_DIR.iterdir()} if WORK_DIR.exists() else set()
        unexpected = actual - expected
        if unexpected:
            log(f"WARNING: unexpected files in work/: {unexpected}")

        # 5. P-03: 連續 crash 偵測
        run_log = WORK_DIR / "run.log"
        if run_log.exists():
            content = run_log.read_text(encoding="utf-8", errors="ignore")
            if "--- CRASH ---" in content:
                log("WARNING: Last evaluate.py run crashed! Check factor.py for bugs.")

        # 6. 磁碟用量
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
| 1.4 權限提示阻擋 | Host 端 `--dangerously-skip-permissions`，但 docker exec 限制實際能做的事 |
| 1.5 Audit 誤報 | 不需要 audit hook，Docker volumes 即保證 |
| 1.6 results.tsv 被清空 | results.tsv 在 named volume，可設定 backup |
| 8.1 OOS 間接過擬合 | 不解決（需要在 evaluate.py 層處理） |
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
├── watchdog.py
└── work/                 ← agent 工作區（git init）
    ├── factor.py
    └── results.tsv
```

### Step 2：建構並啟動（~10 分鐘）

```powershell
cd D:\Finance\docker\autoresearch
docker compose build
docker compose up -d

# 驗證
docker exec autoresearch-agent python -c "import numpy; print('OK')"
docker exec autoresearch-agent ls /app/data/market/ | head -5
docker exec autoresearch-agent touch /app/data/test  # 應該失敗（唯讀）
```

### Step 3：初始化工作區（~5 分鐘）

```powershell
cd D:\Finance\docker\autoresearch\work
cp ../../scripts/autoresearch/factor.py .
cp ../../scripts/autoresearch/results.tsv .
git init
# P-02: results.tsv 不進 git，防止 git reset 清空
echo "results.tsv" > .gitignore
echo "run.log" >> .gitignore
echo "watchdog.log" >> .gitignore
git add factor.py .gitignore
git commit -m "init: autoresearch workspace"
```

### Step 4：更新 loop-docker.ps1 並測試（~15 分鐘）

```powershell
# 單次測試
docker exec autoresearch-agent python /app/evaluate.py

# 啟動 Claude Code loop
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop-docker.ps1
```

### Step 5：驗證安全隔離（~10 分鐘）

```powershell
# 容器內嘗試寫入唯讀目錄 → 應失敗
docker exec autoresearch-agent touch /app/data/hack.txt
docker exec autoresearch-agent touch /app/repo/hack.txt

# 容器內嘗試安裝套件 → 應失敗（read_only root）
docker exec autoresearch-agent pip install requests

# 容器內嘗試存取網路 → 應失敗
docker exec autoresearch-agent python -c "import urllib.request; urllib.request.urlopen('https://google.com')"

# work/ 目錄的 git reset 不影響主 repo
cd D:\Finance
git status  # 應乾淨
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

當 agent 發現通過 L5 + Stage 2 的因子時：

```
1. 提取代碼
   cp docker/autoresearch/work/factor.py src/strategy/factors/research/<name>.py

2. 人類審查
   - 閱讀代碼，確認有經濟直覺
   - 檢查複雜度（< 50 行為佳）
   - 確認無 look-ahead bias

3. StrategyValidator 15 項驗證
   python -m src.cli.main factors --validate <name>

4. 達標（>= 13/15）→ 進入 Paper Trading
   python -m src.cli.main deploy --strategy <name> --mode paper

5. Paper Trading 3 個月後人類決定是否上線
```

evaluate.py 的 `_auto_submit` 會自動觸發步驟 3（需 API server 運行）。
步驟 2 和 5 必須由人類完成 — 自主 agent 不應自行決定部署。

## 7. 限制與取捨

| 取捨 | 說明 |
|------|------|
| Claude Code 仍在 host 無限制 | Docker 保護的是 evaluate.py 執行環境，不是 Claude Code 本身。Agent 的 Edit tool 直接寫 host 檔案。但因為只操作 work/ 目錄，影響範圍有限。 |
| 需要安裝 Docker Desktop | Windows 11 Pro 支援 Hyper-V，安裝一次即可。 |
| evaluate.py 更新需重建容器 | 不頻繁，且 `docker compose build` 很快（cache）。 |
| 首次 docker compose build 較慢 | 需下載 python:3.12-slim + pip install，約 2-5 分鐘。後續有 cache。 |
| 不解決 OOS 過擬合 | 這是方法論問題，不是隔離問題。由 evaluate.py L5 處理。 |
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

Watchdog 負責偵測飽和與 OOS 衰退，寫入 watchdog.log 並在 console 警告。
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
