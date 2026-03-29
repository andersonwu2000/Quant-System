# 用戶指南

## 系統是什麼

台股量化交易系統。自動研究因子 → 驗證 → paper trading → 微額實盤。

目前階段：**paper trading 驗證中**。還不能放心依賴它做投資決策（見 PRODUCTION_READINESS 報告）。

## 快速開始

```bash
# 後端
make dev                  # API（port 8000）

# 前端
make web                  # Web dashboard（port 3000）

# 回測
make backtest ARGS="--strategy revenue_momentum -u 2330.TW -u 2317.TW --start 2023-01-01 --end 2025-12-31"
```

## 日常操作

### Paper Trading（每日）

```bash
# 1. 確認 API 跑著
curl http://localhost:8000/api/v1/system/health

# 2. 監控（開另一個終端）
python scripts/paper_monitor.py --interval 30

# 3. 看日報
cat docs/paper-trading/daily/$(date +%Y-%m-%d).md

# 4. 手動觸發再平衡（如果排程沒跑）
curl -X POST http://localhost:8000/api/v1/pipeline/trigger \
  -H "X-API-Key: YOUR_KEY"
```

排程：每月 11 日 08:30 自動執行。其他時間不交易。

### 微額實盤（CA 憑證取得後）

```bash
# .env 設定
QUANT_MODE=paper                    # 先 paper，確認正常後改 live
QUANT_SINOPAC_CA_PATH=./Sinopac.pfx
QUANT_SINOPAC_CA_PASSWORD=xxx
QUANT_SINOPAC_API_KEY=xxx
QUANT_SINOPAC_SECRET_KEY=xxx

# 測試（買 1 股最低價股票確認流程）
python -c "
from src.execution.broker.sinopac import SinopacBroker, SinopacConfig
broker = SinopacBroker(SinopacConfig(simulation=False))
broker.connect()
# 手動下一筆最小零股測試單
"
```

### Autoresearch（因子研究）

見 [autoresearch-guide-zh.md](autoresearch-guide-zh.md)。

### 數據更新

```bash
# 手動（Phase AD 完成前）
python scripts/download_yahoo_prices.py

# 自動（Phase AD 完成後）
# 排程在 08:00 自動執行
```

## 策略

目前唯一的策略：**revenue_momentum_hedged**

- 營收加速度（3M/12M 比率）作為排序因子
- 5 項篩選：流動性、MA60、60 日漲幅、營收加速、YoY
- 等權 top-10（零股模式，1 萬元）
- 月度再平衡（每月 11 日營收公布後）

## 風控

| 機制 | 門檻 | 動作 |
|------|------|------|
| 日回撤 | 5% | Kill switch → 清倉 |
| 單股權重 | 15%（Validator）/ 10%（config） | 訂單被擋 |
| 零股最低手續費 | 1 元 | SimBroker 已設 |
| 月度 idempotency | 每月只跑一次 | 防重複下單 |

Kill switch 觸發後需手動重置：`POST /api/v1/risk/kill-switch` toggle。

## 通知

```bash
# .env 設定（選一個）
QUANT_NOTIFY_PROVIDER=telegram
QUANT_TELEGRAM_BOT_TOKEN=xxx
QUANT_TELEGRAM_CHAT_ID=xxx
```

通知內容：kill switch 觸發、pipeline 完成、reconciliation 偏差。

## 目錄結構

```
src/                 # Python 後端
strategies/          # 策略檔案
apps/web/            # React 前端
apps/android/        # Android app
data/market/         # 市場數據（parquet）
data/fundamental/    # 基本面數據
data/paper_trading/  # paper trading 狀態 + 日誌
docs/plans/          # 開發計畫
docs/reviews/        # 審計報告
docs/paper-trading/  # 每日報告 + 監控日誌
docker/autoresearch/ # 因子研究容器
scripts/             # 工具腳本
```

## 關鍵文件

| 文件 | 用途 |
|------|------|
| `CLAUDE.md` | AI 助手的行為規範 |
| `docs/plans/NEXT_ACTIONS.md` | 唯一的「接下來做什麼」清單 |
| `docs/reviews/INDEX.md` | 所有審計報告的索引 |
| `docs/claude/CHECKLISTS.md` | 修改代碼前的 checklist |
| `docs/claude/LESSONS_FOR_AUTONOMOUS_AGENTS.md` | 自主 agent 的 28 條教訓 |

## 緊急處理

### Kill Switch 觸發

1. 查看 `docs/paper-trading/monitor.log` 最後幾行
2. 確認是真的回撤還是數據問題
3. 如果是真回撤 → 等市場穩定後手動重置
4. 如果是數據問題 → 修正數據 → 重置 → 手動觸發 reconcile

### API 無回應

```bash
# 檢查是否在跑
curl http://localhost:8000/api/v1/system/health

# 重啟
make dev

# 檢查 portfolio 有沒有被損壞
cat data/paper_trading/portfolio_state.json | python -m json.tool
```

### 持倉和預期不一致

```bash
# 手動 reconcile
curl -X POST http://localhost:8000/api/v1/execution/reconcile \
  -H "X-API-Key: YOUR_KEY"

# 查看偏差
curl http://localhost:8000/api/v1/execution/paper-trading/status \
  -H "X-API-Key: YOUR_KEY"
```
