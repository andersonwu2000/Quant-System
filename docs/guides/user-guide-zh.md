# 用戶指南

## 系統是什麼

台股量化交易系統。自動研究因子 → 驗證 → paper trading → 微額實盤。

目前階段：**paper trading 驗證中**。還不能放心依賴它做投資決策。

---

## PowerShell 注意事項

PowerShell 的 `curl` 是 `Invoke-WebRequest` 的 alias，語法和 Linux curl 不同。以下三種方式任選：

```powershell
# 方式 1：curl.exe（推薦，最簡潔）
curl.exe http://localhost:8000/api/v1/ops/status

# 方式 2：Invoke-RestMethod（PowerShell 原生）
Invoke-RestMethod -Uri http://localhost:8000/api/v1/ops/status

# 方式 3：帶 Header 的 POST（注意語法差異）
curl.exe -X POST http://localhost:8000/api/v1/auto-alpha/start -H "X-API-KEY: dev-key"
# 或
Invoke-RestMethod -Method POST -Uri http://localhost:8000/api/v1/auto-alpha/start -Headers @{"X-API-KEY"="dev-key"}
```

**本文件統一用 `curl.exe` 語法。**

---

## 每日開盤前啟動流程

### 正常流程（07:50 前啟動）

```powershell
# 1. 啟動 API server（scheduler 自動註冊 daily_ops 07:50 + eod_ops 13:30）
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload

# 2. 確認系統狀態
curl.exe http://localhost:8000/api/v1/ops/status
```

系統會自動在 07:50 執行：TWSE 數據快照 → heartbeat → 再平衡日才跑 pipeline。

### 遲到流程（07:50 後才啟動）

```powershell
# 1. 啟動 server
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload

# 2. 手動補跑 TWSE 數據快照（daily_ops 已錯過）
python -c "import asyncio; from src.scheduler.ops import _fetch_twse_snapshot; print(asyncio.run(_fetch_twse_snapshot()))"

# 3. 如果是再平衡日（每月 11 日），手動觸發 pipeline
curl.exe -X POST http://localhost:8000/api/v1/scheduler/trigger/pipeline -H "X-API-KEY: dev-key"
```

> **注意**：`trigger/pipeline` 只跑 execute_pipeline（Yahoo refresh + QG + 策略），不含 TWSE 快照。TWSE 快照要另外手動跑。

### 確認 server 正常

```powershell
# 一個 API 看全貌
curl.exe http://localhost:8000/api/v1/ops/status

# 檢查重點：
# - portfolio.nav > 0（不是負數）
# - portfolio.positions 都是台股 symbol（2xxx.TW, 3xxx.TW）
# - 如果看到 AAPL/MSFT/TEST → 測試污染，需重啟（見「故障排除」）
```

---

## 每日自動流程

```
07:50  daily_ops
       ├─ 交易日檢查（假日 → Discord "休市" → 停止）
       ├─ Heartbeat: "系統啟動"
       ├─ TWSE+TPEX 全市場 OHLCV 快照 → data/twse/
       ├─ 再平衡日？→ execute_pipeline（refresh+QG+策略+下單）
       │              → Heartbeat: "交易完成，N 筆"
       └─ 非再平衡日 → Heartbeat: "非再平衡日"

13:30  eod_ops
       ├─ 券商對帳
       ├─ Backtest reconcile（預期 vs 實際）
       ├─ 日報生成
       └─ Heartbeat: "EOD 完成"
```

**再平衡日**：每月 11 日（config 可改為 weekly/daily）。
**正常日不需要任何操作**，系統自己跑。

---

## Autoresearch（因子研究）

### 啟動（需要 Docker Desktop 在跑）

```powershell
# 0. 確認 Docker 在跑
docker info 2>&1 | Select-String "Server Version"

# 1. 首次或代碼更新後：rebuild（evaluate.py 改動必須 rebuild）
cd docker/autoresearch
docker compose build
cd ../..

# 2. 透過 API 啟動容器
curl.exe -X POST http://localhost:8000/api/v1/auto-alpha/start -H "X-API-KEY: dev-key"

# 3. 另開一個終端，啟動研究循環
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1
```

### 重要：loop.ps1 的終端不要碰

啟動後會看到：
```
Autoresearch session starting...
Mode: DOCKER
Status report: D:\Finance\docs\research\status.md
█  ← 游標在這裡閃爍
```

**不要在這個終端輸入任何東西**。游標是 Claude Code agent 的 stdin，按鍵會干擾研究。如果不小心按到了：`Ctrl+C` 停掉，重新跑 `loop.ps1`。

### 監控

```powershell
# 查看狀態
curl.exe http://localhost:8000/api/v1/auto-alpha/status -H "X-API-KEY: dev-key"

# 或直接看文件
cat docs/research/status.md

# 最近實驗結果
Get-Content docker/autoresearch/work/results.tsv | Select-Object -Last 5
```

### 停止

```powershell
# 1. Ctrl+C 停 loop.ps1
# 2. 停容器
curl.exe -X POST http://localhost:8000/api/v1/auto-alpha/stop -H "X-API-KEY: dev-key"
```

詳見 [autoresearch-guide-zh.md](autoresearch-guide-zh.md)。

---

## 數據管理

### 自動（daily_ops 每交易日 07:50）

| 數據 | 來源 | 目的地 |
|------|------|--------|
| 全市場 OHLCV | TWSE+TPEX OpenAPI | `data/twse/` |
| 價格增量 | Yahoo Finance | `data/yahoo/`（pipeline 內） |
| 營收（再平衡日） | FinMind | `data/finmind/`（pipeline 內） |

### 手動工具

```powershell
# 查看數據覆蓋率（一覽表）
python -m src.data.cli status

# 品質閘門 dry run
python -m src.data.cli validate

# Yahoo 全量下載（不需 token）
python scripts/download_yahoo_price.py

# FinMind 批次下載（需 token，600 req/hr）
python -m scripts.download_finmind_data --dataset all --symbols-from-market

# FinLab 歷史數據（含已下市股票，免費 500MB/月）
python -m scripts.download_finlab_data

# TWSE 三大法人歷史回填（不需 token，~120 分鐘）
python scripts/backfill_twse_institutional.py --start 2015-01-01

# 手動觸發 TWSE 今日快照（daily_ops 錯過時）
python -c "import asyncio; from src.scheduler.ops import _fetch_twse_snapshot; print(asyncio.run(_fetch_twse_snapshot()))"
```

### 數據來源

```
data/
├── yahoo/    # Yahoo Finance — OHLCV（1,100+ 支，2015-2026）
├── finmind/  # FinMind — 基本面 + 籌碼面（12 種數據集）
├── twse/     # TWSE/TPEX — OHLCV 快照 + 三大法人（1,450+ 支 × 11 年）
├── finlab/   # FinLab — 歷史含已下市股（2,718 支，2007-2018）
└── paper_trading/  # portfolio state + trades + ledger + reconciliation
```

---

## 查看系統狀態

```powershell
# 一鍵全貌
curl.exe http://localhost:8000/api/v1/ops/status

# 持倉（含 P&L）
curl.exe http://localhost:8000/api/v1/ops/positions

# 今日摘要
curl.exe http://localhost:8000/api/v1/ops/daily-summary

# Reconciliation（回測 vs 實盤比對）
python -m src.reconciliation.report

# 數據覆蓋
python -m src.data.cli status
```

---

## 策略

目前：**revenue_momentum_hedged**

- 營收 trough-uplift ratio 作為排序因子
- 5 項篩選：流動性、MA60、60 日漲幅、營收加速、YoY
- 等權 top-10（零股模式，1 萬元）
- 月度再平衡（每月 11 日營收公布後）
- `QUANT_REBALANCE_FREQUENCY`：可設 `daily` / `weekly` / `biweekly` / `monthly`

## 風控

| 機制 | 門檻 | 動作 |
|------|------|------|
| 日回撤 | 5% | Kill switch → 清倉 |
| 單股權重 | 10%（config） | 訂單被擋 |
| 零股最低手續費 | 1 元 | PaperBroker 已設 |
| 月度 idempotency | 有交易的月不重複 | 防重複下單 |
| 主 kill switch 連動 | 觸發時停止所有 auto 策略 | 防 auto 策略繼續虛擬交易 |

## 通知

```
# .env
QUANT_NOTIFY_PROVIDER=discord
QUANT_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

| 級別 | 條件 | 管道 |
|------|------|------|
| **P0 緊急** | Kill Switch、倉位不一致 | Discord + LINE |
| **P1 重要** | 交易完成、QG 失敗、drift > 50bps | Discord |
| **P2 資訊** | Heartbeat、日報、數據更新完成 | Discord |
| **P3 調試** | 因子評估、回測細節 | 僅 log |

---

## 故障排除

### Portfolio 被測試污染（NAV 為負、出現 AAPL/MSFT/TEST）

**原因**：pytest 測試寫了假 trade 到 `data/paper_trading/ledger/`，啟動時被 replay 到 portfolio。

```powershell
# 1. 停 server (Ctrl+C)
# 2. 刪除污染的 ledger
Remove-Item data/paper_trading/ledger/*.jsonl
# 3. 確認 portfolio JSON 正確
Get-Content data/paper_trading/portfolio_state.json | python -m json.tool | Select-Object -First 5
# 4. 重啟 server
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

### Kill Switch 觸發

```powershell
# 1. 確認狀態
curl.exe http://localhost:8000/api/v1/ops/status
# 2. 確認是真的回撤還是數據問題
# 3. 真回撤 → 等市場穩定後重置
# 4. 數據問題 → 修正後重置
```

### API Server 無回應

```powershell
# 健康檢查
curl.exe http://localhost:8000/api/v1/system/health
# 無回應 → 重啟
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

### Scheduler 沒啟動（ops/status 顯示 running: false）

`--reload` 模式下偶爾 lifespan 不會正確觸發。重啟 server 即可。或手動補跑：

```powershell
# 手動 TWSE 快照
python -c "import asyncio; from src.scheduler.ops import _fetch_twse_snapshot; print(asyncio.run(_fetch_twse_snapshot()))"
# 手動 pipeline
curl.exe -X POST http://localhost:8000/api/v1/scheduler/trigger/pipeline -H "X-API-KEY: dev-key"
```

### Autoresearch 容器不健康

```powershell
# 檢查容器狀態
docker ps --filter "name=autoresearch"
# evaluator 不 healthy → rebuild
cd docker/autoresearch && docker compose build && docker compose up -d
```

### 不小心在 loop.ps1 終端打字

`Ctrl+C` 停掉，重新跑：
```powershell
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1
```

---

## 目錄結構

```
src/                 # Python 後端（170+ 檔）
src/scheduler/       # daily_ops + eod_ops + heartbeat
src/data/            # DataCatalog + Registry + SecuritiesMaster + QualityGate
src/execution/       # SimBroker + Sinopac + Trade Ledger + Order Book
src/reconciliation/  # 回測 vs 實盤比對
strategies/          # 策略檔案
apps/web/            # React 前端
apps/android/        # Android app
data/                # 按來源分離（yahoo/finmind/twse/finlab/paper_trading）
docs/plans/          # 開發計畫（Phase A~AJ）
docs/reviews/        # 審計報告
docs/research/       # 研究報告 + autoresearch status
docker/autoresearch/ # 因子研究容器（3-container）
scripts/             # 工具腳本
```

## 關鍵文件

| 文件 | 用途 |
|------|------|
| `.env` | 所有設定（mode, strategy, scheduler, notification） |
| `data/paper_trading/portfolio_state.json` | 當前持倉狀態 |
| `docs/research/status.md` | autoresearch 即時狀態 |
| `docs/plans/phase-ai-operations-architecture.md` | 運營架構設計 |
| `docs/claude/SYSTEM_STATUS_REPORT.md` | 系統全貌 |
| `docs/reviews/INDEX.md` | 所有審計報告索引 |
