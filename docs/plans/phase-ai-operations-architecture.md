# Phase AI：生產運營架構 — 控制平面設計

> 狀態：📋 設計中
> 前置：Phase AD（數據平台）✅、Phase S（Trading Pipeline）✅
> 日期：2026-03-31

---

## 0. 為什麼需要這份設計

系統已有 117 個 API endpoint、14 種策略、12 種數據集、5 個數據源、3 個通知管道。
但這些能力是**散落的零件**，缺少一個統一的運營框架把它們連成可靠的自動化系統。

**核心問題**：
- 你不應該需要記住 20 個 CLI 指令和 API endpoint 來操作系統
- 系統應該自己跑，出問題時通知你，而不是你每天手動檢查
- 新因子從發現到上線不應需要人工搬檔案、改 config、重啟服務

---

## 1. 完整運營架構

### 1.1 三層架構

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3: 使用者介面（查詢 + 控制）                              │
│  Web Dashboard · Discord Bot · CLI · Mobile Push               │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: 控制平面（編排 + 監控 + 決策）                         │
│  DAG Scheduler · Strategy Lifecycle · Heartbeat · Alert Router  │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: 執行層（已有，基本完整）                               │
│  DataCatalog · BacktestEngine · RiskEngine · SimBroker · OMS    │
└─────────────────────────────────────────────────────────────────┘
```

**Layer 1 已建好**（Phase A~AD）。**Layer 2 和 3 是本計畫的重點**。

### 1.2 每日運營流程（目標狀態）

```
                    ┌──────────────────┐
                    │  Trading Calendar │
                    │  is_trading_day?  │
                    └────────┬─────────┘
                             │
              ┌──────────────▼──────────────┐
              │  非交易日 → Discord "今日休市" │
              │  交易日 → 進入 DAG            │
              └──────────────┬──────────────┘
                             │
    07:50 ┌──────────────────▼──────────────────┐
          │  Heartbeat: "系統啟動"                │
          └──────────────────┬──────────────────┘
                             │
    08:00 ┌──────────────────▼──────────────────┐
          │  Data Refresh DAG                    │
          │  ├─ TWSE+TPEX 全市場快照 → data/twse/│
          │  ├─ Yahoo 增量更新 → data/yahoo/     │
          │  ├─ FinMind 增量（有 token 時）      │
          │  └─ 失敗 → 通知 + 停止              │
          └──────────────────┬──────────────────┘
                             │
    08:20 ┌──────────────────▼──────────────────┐
          │  Quality Gate (L1-L4)                │
          │  失敗 → 通知 + 停止交易             │
          └──────────────────┬──────────────────┘
                             │
    09:03 ┌──────────────────▼──────────────────┐
          │  Strategy Execution                  │
          │  ├─ 主策略（revenue_momentum_hedged） │
          │  ├─ 自動部署策略（最多 3 個）        │
          │  ├─ Risk Engine 審核所有 orders      │
          │  └─ SimBroker/SinopacBroker 執行    │
          └──────────────────┬──────────────────┘
                             │
    09:10 ┌──────────────────▼──────────────────┐
          │  Heartbeat: "交易完成，N 筆"         │
          └──────────────────┬──────────────────┘
                             │
    13:30 ┌──────────────────▼──────────────────┐
          │  EOD DAG                             │
          │  ├─ 券商對帳（broker vs system）     │
          │  ├─ Backtest Reconcile（預期 vs 實際）│
          │  ├─ NAV 快照 + 日報生成             │
          │  └─ Portfolio 持久化                 │
          └──────────────────┬──────────────────┘
                             │
    14:00 ┌──────────────────▼──────────────────┐
          │  Heartbeat: "EOD 完成，NAV=XXX"      │
          └─────────────────────────────────────┘
```

---

## 2. 策略生命週期管理

### 2.1 從發現到退役的完整流程

```
  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐
  │ 發現    │───→│ 評估     │───→│ 部署     │───→│ 監控     │───→│ 退役    │
  │Discovery│    │Evaluation│    │Deployment│    │Monitoring│    │Retire   │
  └─────────┘    └──────────┘    └──────────┘    └──────────┘    └─────────┘
   autoresearch   L1-L5 gate     paper deploy    daily P&L       auto-stop
   974+ 實驗      backtest gate  max 3 策略      drift check     30d/3%DD
                  human review?  5% NAV cap      weekly report   archive
```

### 2.2 自動 vs 需人工確認

| 步驟 | 自動？ | 說明 |
|------|:------:|------|
| 因子發現 | ✅ | autoresearch 持續跑 |
| L1-L4 評估 | ✅ | evaluate.py 自動閘門 |
| L5 Backtest | ✅ | 自動跑 StrategyValidator |
| **部署到 paper trading** | ⚠️ **需確認** | 推薦通知 → 人工批准 → 自動部署 |
| Paper trading 監控 | ✅ | 每日自動比對 |
| **升級到 live trading** | ❌ **必須人工** | 30 天 paper + 人工審核 |
| 自動退役 | ✅ | 30 天到期 或 3% drawdown |

### 2.3 多策略並行管理

```
StrategyManager
├── main_strategy          revenue_momentum_hedged  (Portfolio A, ~90% NAV)
├── auto_deployed[0]       rev_slope_6m             (Portfolio B, ≤5% NAV)
├── auto_deployed[1]       trust_momentum           (Portfolio C, ≤5% NAV)
└── auto_deployed[2]       (空位)

每個策略獨立：
  - 獨立 portfolio state（不互相干擾）
  - 獨立 P&L 追蹤
  - 獨立 risk limits（auto 更嚴：3% DD vs main 5% DD）
  - 共用 execution service（SimBroker/Sinopac）
  - 共用 data layer（DataCatalog）
```

---

## 3. 韌性設計（Crash Recovery）

### 3.1 交易原子性

```
現在：trade → update portfolio → save JSON（步驟 2~3 間崩潰 = 狀態丟失）

改後：
  0. 寫 intent log:  "準備買 2330.TW 10 股 @ ~1820"
  1. broker 成交
  2. 寫 trade ledger: "2330.TW BUY 10 @ 1821.5 confirmed"（append-only）
  3. portfolio 更新
  4. 寫 portfolio JSON

  重啟時：
  - 讀 portfolio JSON（可能是舊的）
  - 讀 trade ledger（一定是完整的）
  - 重播 ledger 中 JSON 沒反映的交易 → 正確狀態
```

### 3.2 各種故障場景

| 場景 | 現有處理 | 改進 |
|------|---------|------|
| 電腦關機 | Docker restart + portfolio JSON | + trade ledger 重播 |
| 網路斷線 | 券商自動重連（指數退避） | + heartbeat 超時告警 |
| API rate limit | Yahoo retry×3, FinMind fallback | 足夠，不改 |
| 下單後崩潰 | ❌ 倉位不一致 | + intent log + ledger |
| 程式掛死（不退出） | ❌ 不會被發現 | + Docker healthcheck + heartbeat |
| 交易所維護 | is_trading_day 跳過 | + 動態休市日更新 |

---

## 4. 使用者介面（查詢 + 控制）

### 4.1 資訊查詢：一個問題 → 一個答案

使用者最常問的問題和系統應該如何回答：

| 問題 | 現在怎麼查 | 目標 |
|------|----------|------|
| "系統還活著嗎？" | 看 Discord 有沒有消息 | Heartbeat 主動 ping |
| "今天賺多少？" | 讀 JSON 自己算 | Discord 日報 / `GET /ops/daily-summary` |
| "持倉是什麼？" | 讀 portfolio_state.json | `GET /ops/positions` (簡化版) |
| "數據新鮮嗎？" | `python -m src.data.cli status` | DAG 自動檢查 + 異常通知 |
| "策略表現如何？" | 讀多個 JSON + 回測報告 | `GET /ops/strategy-report` |
| "自動研究找到什麼？" | 讀 results.tsv | `GET /ops/research-summary` |
| "為什麼今天沒交易？" | 讀 pipeline_runs JSON | DAG 結果自動通知（含原因） |

### 4.2 控制動作：最少的操作

| 動作 | 頻率 | 方式 |
|------|------|------|
| 日常運營 | 每天 | **全自動**，只看通知 |
| 查看狀態 | 隨時 | Discord bot `/status` 或 Web Dashboard |
| 手動觸發再平衡 | 偶爾 | `POST /ops/rebalance` 或 Discord `/rebalance` |
| 批准新策略上線 | 每月 0-3 次 | Discord 通知 → 回覆確認 |
| 緊急停損 | 極少 | Kill Switch（自動 + 手動 API） |
| 修改策略參數 | 極少 | `.env` + 重啟 或 API |

### 4.3 通知分級

| 級別 | 條件 | 管道 | 動作 |
|------|------|------|------|
| **P0 緊急** | Kill Switch 觸發、倉位不一致 | Discord + LINE | 立即查看 |
| **P1 重要** | 交易完成、QualityGate 失敗、drift > 50bps | Discord | 當天查看 |
| **P2 資訊** | 日報、heartbeat、數據更新完成 | Discord | 有空看 |
| **P3 調試** | 因子評估結果、backtest 細節 | Log 檔案 | 需要時查 |

---

## 5. 數據自動化

### 5.1 排程

| 數據 | 頻率 | 時間 | 來源 | 自動？ |
|------|------|------|------|:------:|
| 全市場 OHLCV | 每交易日 | 08:00 | TWSE+TPEX OpenAPI | ✅ |
| 三大法人 | 每交易日 | 08:00 | TWSE T86 | ✅ |
| Yahoo price 增量 | 每交易日 | 08:05 | Yahoo Finance | ✅ |
| 月營收 | 每月 11 日 | 08:10 | FinMind | ✅ |
| 季報 | 5/16, 8/16, 11/16 | 08:10 | FinMind | ✅ |
| 休市日同步 | 每年 12 月 | 手動 | TWSE 網站 | ⚠️ 半自動 |
| FinLab 歷史 | 不定期 | 手動 | FinLab API | ❌ 手動 |

### 5.2 數據品質自動檢查

```
每日 08:15（數據刷新完成後）：
  1. 覆蓋率檢查：price > 90%? revenue > 70%?
  2. 新鮮度檢查：最新 bar 距今 < 3 天?
  3. 異常值檢查：漲跌 > 11%? volume = 0?
  4. 結果 → Quality Gate（已有）
```

---

## 6. 執行計畫（按依賴排序）

### Phase 1：交易原子性 + Crash Recovery（P0）

解決「下單後崩潰 = 倉位不一致」這個最危險的問題。

| 步驟 | 內容 | 檔案 | 預估 |
|------|------|------|------|
| 1a | Intent log（下單前寫入意圖） | `src/execution/intent_log.py` | 1h |
| 1b | Trade ledger（逐筆 append-only） | `src/execution/trade_ledger.py` | 1h |
| 1c | 重啟時 ledger 重播恢復 | 修改 `src/api/state.py` | 2h |
| 1d | SIGTERM handler（關機前存狀態） | 修改 `src/api/app.py` | 30m |
| 1e | Docker API healthcheck | 修改 `docker-compose.yml` | 15m |
| 1f | 測試：模擬崩潰 + 恢復 | 新增測試 | 1h |

### Phase 2：DAG + 交易日曆 + 數據自動化（P0）

解決「每天要手動操作」和「非交易日浪費資源」的問題。

| 步驟 | 內容 | 檔案 | 預估 |
|------|------|------|------|
| 2a | `daily_trading_dag()` 統一入口 | `src/scheduler/dag.py` | 2h |
| 2b | 每日數據刷新步驟（TWSE+Yahoo） | `src/scheduler/dag.py` | 1h |
| 2c | TradingDayFilter | `src/scheduler/__init__.py` | 30m |
| 2d | 靈活再平衡頻率 config | `src/core/config.py` | 30m |
| 2e | Holiday 動態更新 | `src/core/calendar.py` | 1h |
| 2f | 替換 SchedulerService 為 DAG | `src/scheduler/__init__.py` | 1h |

### Phase 3：Heartbeat + 通知分級（P1）

解決「系統掛了不知道」和「通知太吵/太少」的問題。

| 步驟 | 內容 | 檔案 | 預估 |
|------|------|------|------|
| 3a | HeartbeatMonitor | `src/scheduler/heartbeat.py` | 1h |
| 3b | 通知分級（P0~P3） | 修改 `src/notifications/` | 1h |
| 3c | 每日摘要報告（Discord） | `src/scheduler/dag.py` | 1h |
| 3d | Ops API endpoints | `src/api/routes/ops.py` | 2h |

### Phase 4：策略生命週期管理（P1）

解決「新因子從發現到上線需要人工操作」的問題。

| 步驟 | 內容 | 檔案 | 預估 |
|------|------|------|------|
| 4a | StrategyManager（多策略編排） | `src/scheduler/strategy_manager.py` | 3h |
| 4b | 多 portfolio 隔離（main + auto×3） | 修改 `src/api/state.py` | 2h |
| 4c | 自動部署審批流程（通知 → 確認） | 修改 `src/alpha/auto/paper_deployer.py` | 2h |
| 4d | 策略比較週報 | `src/reconciliation/strategy_report.py` | 1h |

### Phase 5：Autoresearch 同步 + Docker（P2）

| 步驟 | 內容 | 檔案 | 預估 |
|------|------|------|------|
| 5a | Docker volume mount 對齊 | `docker/autoresearch/docker-compose.yml` | 30m |
| 5b | 容器內數據驗證 | 驗證腳本 | 30m |
| 5c | Deploy queue 路徑更新 | `src/alpha/auto/deployed_executor.py` | 30m |

### Phase 6：使用者介面強化（P2，可選）

| 步驟 | 內容 | 備註 |
|------|------|------|
| 6a | Discord Bot（/status, /rebalance） | 比 Web 更方便的日常操作 |
| 6b | Web Dashboard Ops 頁面 | 系統狀態一覽 |
| 6c | Mobile Push 通知 | P0 告警推播 |

---

## 7. 不做的事

| 項目 | 原因 |
|------|------|
| Prefect / Dagster / Airflow | 單人系統，自寫 DAG 夠用 |
| Kubernetes | 單機部署 |
| 分散式 portfolio lock | 單進程，asyncio.Lock 足夠 |
| 完整 GUI 交易台 | Web Dashboard 有基本頁面，不做 Bloomberg 級別 |
| HFT 級 tick engine | 台股日頻策略不需要 |

---

## 8. 設計原則

1. **無人值守** — 正常情況下不需要人工操作，系統自己跑
2. **異常通知** — 只在出問題時打擾你，不發廢通知
3. **崩潰安全** — 任何時刻斷電都能正確恢復
4. **一鍵查看** — 一個指令/一次點擊看到系統全貌
5. **漸進上線** — paper 30 天 → 人工審核 → live，不自動用真錢

---

## 9. 成功標準

| 指標 | 目標 |
|------|------|
| 每日人工操作次數 | 0（正常日） |
| 崩潰後 portfolio 一致性 | 100% |
| 非交易日 API 呼叫 | 0 |
| 因子發現→paper trading 延遲 | < 1 天（審批後） |
| 系統掛死到發現 | < 15 分鐘（heartbeat） |
| 策略上線到退役全流程 | 自動化（除 live 升級需人工） |
