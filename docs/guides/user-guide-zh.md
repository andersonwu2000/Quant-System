# 用戶指南

## 系統是什麼

台股量化交易系統。自動研究因子 → 驗證 → paper trading → 微額實盤。

目前階段：**paper trading 驗證中**。還不能放心依賴它做投資決策。

## 快速開始

```powershell
# 後端 API（port 8000）
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload

# 前端 Web dashboard（port 3000）
cd apps/web && npm run dev

# 回測
python -m src.cli.main backtest --strategy revenue_momentum -u 2330.TW -u 2317.TW --start 2023-01-01 --end 2025-12-31
```

## 日常操作

### Paper Trading

```powershell
# 1. 啟動 API server（scheduler 自動啟動 daily_ops + eod_ops）
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload

# 2. 確認系統狀態（一個 API 看全貌）
curl http://localhost:8000/api/v1/ops/status | python -m json.tool

# 3. 手動觸發再平衡（排程每交易日 07:50 自動執行 daily_ops）
curl -X POST http://localhost:8000/api/v1/scheduler/trigger/pipeline -H "X-API-KEY: dev-key"

# 4. 查看持倉
curl http://localhost:8000/api/v1/ops/positions | python -m json.tool

# 5. 查看今日摘要
curl http://localhost:8000/api/v1/ops/daily-summary | python -m json.tool

# 6. Reconciliation 報告
python -m src.reconciliation.report
```

**每日自動流程**（不需人工操作）：
```
07:50  daily_ops → 交易日檢查 → TWSE 數據刷新 → pipeline → heartbeat
13:30  eod_ops  → 券商對帳 → backtest 比對 → 日報 → heartbeat
```

### 微額實盤（CA 憑證取得後）

```powershell
# .env 設定
QUANT_MODE=live
QUANT_SINOPAC_CA_PATH=./Sinopac.pfx
QUANT_SINOPAC_CA_PASSWORD=xxx

# 測試（買 1 股最低價股票確認流程）
python -c "
from src.execution.broker.sinopac import SinopacBroker, SinopacConfig
broker = SinopacBroker(SinopacConfig(simulation=False))
broker.connect()
# 手動下一筆最小零股測試單
"
```

### Autoresearch（因子研究）

```powershell
# 啟動研究循環（Docker 模式，包含 status reporter + credentials refresher）
powershell -ExecutionPolicy Bypass -File scripts/autoresearch/loop.ps1

# 手動查看狀態
powershell -File scripts/autoresearch/status.ps1
```

詳見 [autoresearch-guide-zh.md](autoresearch-guide-zh.md)。

### 數據管理

**自動化**（daily_ops 每交易日 07:50 執行）：
- TWSE+TPEX 全市場 OHLCV 快照 → `data/twse/`
- Yahoo 增量價格更新 → `data/yahoo/`
- Pipeline 前 FinMind 營收更新 → `data/finmind/`

**手動工具**：
```powershell
# 查看數據覆蓋率
python -m src.data.cli status

# 品質閘門檢查（dry run）
python -m src.data.cli validate

# Yahoo 全量下載
python scripts/download_yahoo_price.py

# FinMind 批次下載（需 token）
python -m scripts.download_finmind_data --dataset all --symbols-from-market

# FinLab 歷史數據（含已下市股票，免費 500MB/月）
python -m scripts.download_finlab_data

# TWSE 三大法人歷史回填（不需 token）
python scripts/backfill_twse_institutional.py --start 2015-01-01
```

**數據來源**：6 個，按來源分離儲存
```
data/
├── yahoo/    # Yahoo Finance — OHLCV（1,100+ 支）
├── finmind/  # FinMind — 基本面 + 籌碼面（12 種數據集）
├── twse/     # TWSE/TPEX — 三大法人（1,450+ 支 × 11 年）
├── finlab/   # FinLab — 歷史含已下市股（2,718 支，2007-2018）
└── ...
```

## 策略

目前：**revenue_momentum_hedged**

- 營收 trough-uplift ratio 作為排序因子
- 5 項篩選：流動性、MA60、60 日漲幅、營收加速、YoY
- 等權 top-10（零股模式，1 萬元）
- 月度再平衡（每月 11 日營收公布後）

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
# .env（已設 Discord）
QUANT_NOTIFY_PROVIDER=discord
QUANT_DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

通知分級：
- **P0 緊急**：Kill Switch 觸發、倉位不一致 → Discord + LINE
- **P1 重要**：交易完成、QualityGate 失敗、drift > 50bps → Discord
- **P2 資訊**：Heartbeat、日報、數據更新完成 → Discord
- **P3 調試**：因子評估、回測細節 → 僅寫 log

## 目錄結構

```
src/                 # Python 後端（170+ 檔）
strategies/          # 策略檔案
apps/web/            # React 前端
apps/android/        # Android app
data/yahoo/          # Yahoo Finance 價格數據
data/finmind/        # FinMind 基本面 + 籌碼面
data/twse/           # TWSE/TPEX 三大法人（11 年歷史）
data/finlab/         # FinLab 歷史數據（含已下市股票，2007-2018）
data/paper_trading/  # paper trading 狀態 + 日誌 + trade ledger
docs/plans/          # 開發計畫（Phase A~AJ）
docs/reviews/        # 審計報告（INDEX.md 是索引）
docs/research/       # 研究報告
docker/autoresearch/ # 因子研究容器（3-container: agent, evaluator, watchdog）
scripts/             # 工具腳本（download, backfill, migrate, import）
```

## 關鍵文件

| 文件 | 用途 |
|------|------|
| `docs/plans/NEXT_ACTIONS.md` | 唯一的「接下來做什麼」清單 |
| `docs/research/ic_alpha_gap_analysis.md` | IC-Alpha Gap 分析 + 待做 |
| `docs/reviews/INDEX.md` | 所有審計報告索引 |
| `docs/claude/EXPERIMENT_STANDARDS.md` | 實驗方法論標準 |
| `.env` | 所有設定（mode, strategy, scheduler, notification） |

## 緊急處理

### Kill Switch 觸發

1. `python scripts/paper_monitor.py --once` 看狀態
2. 確認是真的回撤還是數據問題
3. 真回撤 → 等市場穩定後手動重置
4. 數據問題 → 修正 → 重置

### API 無回應

```powershell
curl http://localhost:8000/api/v1/system/health
# 無回應 → 重啟
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
# 檢查 portfolio
cat data/paper_trading/portfolio_state.json | python -m json.tool
```

### 持倉和預期不一致

```powershell
# 查看最近交易
ls data/paper_trading/trades/
# 查看 pipeline 記錄
ls data/paper_trading/pipeline_runs/
```
