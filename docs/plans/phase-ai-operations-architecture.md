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

## 6. 執行計畫（審批修正版）

> 參考：NautilusTrader 的 crash-only 設計 — startup 和 recovery 共用同一個 code path。
> Paper mode 用 SimBroker（同步撮合），不存在「下單後、成交前崩潰」場景。
> Intent log + trade ledger 留到 live trading（SinopacBroker async callback）前做。

### Phase 1：基礎韌性 + 交易日感知（本週，P0）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 1a | SIGTERM handler（關機前存 portfolio + 取消掛單） | 修改 `src/api/app.py` |
| 1b | Docker API healthcheck（`GET /system/health`） | 修改 `docker-compose.yml` |
| 1c | `execute_pipeline` 開頭加交易日檢查 | 修改 `src/scheduler/jobs.py` |
| 1d | SchedulerService 加 TradingDayFilter | 修改 `src/scheduler/__init__.py` |
| 1e | 每日數據刷新排程（TWSE 快照 + Yahoo 增量） | 修改 `src/scheduler/__init__.py` |

### Phase 2：Heartbeat + 通知分級 + 日報（下週，P1）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 2a | HeartbeatMonitor（開盤前/交易後/收盤後 Discord ping） | `src/scheduler/heartbeat.py` |
| 2b | 通知分級（P0 緊急 → P3 調試） | 修改 `src/notifications/` |
| 2c | 每日摘要報告（Discord：NAV、trades、drift） | 修改 `src/scheduler/jobs.py` |
| 2d | Ops API endpoints（`/ops/daily-summary`、`/ops/positions`） | `src/api/routes/ops.py` |

### Phase 3：Live Trading 準備（live 啟動前，P1）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 3a | Intent log（下單前寫入意圖）— SinopacBroker async 需要 | `src/execution/intent_log.py` |
| 3b | Trade ledger（逐筆 append-only 成交記錄） | `src/execution/trade_ledger.py` |
| 3c | 重啟時 ledger 重播恢復 | 修改 `src/api/state.py` |
| 3d | 掛單持久化（G4，pending orders → SQLite） | `src/execution/order_book.py` |

### Phase 4：Autoresearch 同步（P2）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 4a | Docker volume mount 對齊新目錄結構 | `docker/autoresearch/docker-compose.yml` |
| 4b | 容器內數據驗證 | 驗證腳本 |

### ~~Phase 5：策略生命週期管理~~ → 已由 Phase AG 完成

PaperDeployer + DeployedExecutor + 多 portfolio 隔離（main + auto×3）+ 5% NAV cap + 3% DD kill switch 均在 Phase AG 實作完成，不在此重複。

### Phase 5：使用者介面強化（P2，可選）

| 步驟 | 內容 | 備註 |
|------|------|------|
| 5a | Discord Bot（/status, /rebalance） | 比 Web 更方便的日常操作 |
| 5b | Web Dashboard Ops 頁面 | 系統狀態一覽 |
| 5c | Mobile Push 通知 | P0 告警推播 |

---

## 7. 不做的事

| 項目 | 原因 |
|------|------|
| 自寫 DAG engine | `execute_pipeline` 內部已是 DAG-like 流程，不需另建 |
| Prefect / Dagster / Airflow | 單人系統，APScheduler + cron 足夠 |
| Paper mode 的 intent log | SimBroker 是同步撮合，pipeline 重跑即可恢復 |
| Kubernetes | 單機部署 |
| 分散式 portfolio lock | 單進程，asyncio.Lock 足夠 |
| 完整 GUI 交易台 | Web Dashboard 有基本頁面，不做 Bloomberg 級別 |
| HFT 級 tick engine | 台股日頻策略不需要 |
| StrategyManager 重寫 | Phase AG 已完成策略生命週期管理 |

---

## 8. 設計原則

1. **無人值守** — 正常情況下不需要人工操作，系統自己跑
2. **異常通知** — 只在出問題時打擾你，不發廢通知
3. **Crash-only design** — startup 和 recovery 共用同一個 code path（參考 NautilusTrader）。Paper mode 重跑 pipeline 即恢復；live mode 靠 trade ledger 重播
4. **一鍵查看** — 一個指令/一次點擊看到系統全貌
5. **漸進上線** — paper 30 天 → 人工審核 → live，不自動用真錢
6. **最小改動** — 不重寫已有的 SchedulerService/PaperDeployer，只在必要處加邏輯

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

---

## 10. 嚴格審批（2026-03-31）

### 判定：設計方向正確，但有 4 個結構性問題。Phase 1 可以開始，Phase 2-6 需修正。

---

### 問題 1（CRITICAL）：Phase 4 和 Phase AG 大量重複

§2 策略生命週期和 §6 Phase 4 的內容——多策略並行、StrategyManager、部署審批、策略比較——**幾乎完全是 Phase AG 已實作的東西**。

已有：
- `PaperDeployer`（deploy/stop/kill/update_nav）✅
- `DeployedStrategyExecutor`（獨立 NAV 追蹤）✅
- `SchedulerService` 已註冊 `deployed_strategies` cron job（每月 12 日）✅
- 多 portfolio 隔離（main + auto×3, 5% NAV cap, 3% DD kill switch）✅

**如果 Phase AI Phase 4 重新設計這些，會和 Phase AG 代碼衝突。**

**修正**：刪除 Phase 4（§6 Phase 4）。策略生命週期管理是 Phase AG 的範圍，不應在此重複。§2 可以保留作為架構概覽，但 §6 的實作步驟 4a-4d 應刪除。

---

### 問題 2（HIGH）：Phase 1 的 Crash Recovery 設計過度

§3.1 提出 intent log + trade ledger + 重播恢復，但：

1. **台股月頻策略每月交易 1 次**，pipeline 從 weights → SimBroker → apply_trades → save_portfolio 是**同步的**（不是 async callback）。同步流程中間崩潰 = 整個 pipeline 失敗 → 重跑即可
2. **Paper trading 用 SimBroker**（記憶體撮合），沒有「下單後、成交前崩潰」的場景
3. **真正需要 ledger 的是 live trading 用 SinopacBroker**（async callback），但 live 還沒啟動

現有的 `_save_trade_log()`（jobs.py:205）已經在成交後寫 JSON，`save_portfolio()` 在 pipeline 結束時寫 JSON。這已經涵蓋了「portfolio JSON 過時」的場景（pipeline 重跑會重新計算）。

**修正**：Phase 1 縮減為：
- 1d：SIGTERM handler（有價值，<30 分鐘）
- 1e：Docker healthcheck（有價值，<15 分鐘）
- 1a-1c：intent log + ledger → 降為 Phase 3（live trading 啟動前做）

---

### 問題 3（HIGH）：DAG Scheduler 是過度設計

§6 Phase 2 提出寫 `src/scheduler/dag.py` 取代現有 `SchedulerService`。但：

1. 現有 `SchedulerService` 用 APScheduler cron 已能完成所有排程需求（pipeline cron + reconcile cron + deployed_strategies cron）
2. `execute_pipeline` 內部已有 DAG-like 流程：refresh → quality gate → strategy → broker → reconcile → save
3. 自寫 DAG engine 等於重造 Prefect/Dagster — §7 自己說了不用這些工具，但又要自寫一個

**真正需要的只是**：
- 交易日過濾（已有 `is_trading_day`，只是沒在 scheduler 層檢查）
- heartbeat（Phase 3，值得做）
- 非交易日不觸發（SchedulerService 加一行 `if not is_trading_day: return`）

**修正**：刪除 Phase 2 的 DAG 設計。改為：
- 2a：`execute_pipeline` 開頭加交易日檢查（5 行）
- 2c：TradingDayFilter 加到 SchedulerService（10 行）
- 其他不變

---

### 問題 4（MEDIUM）：工作量預估不可信

| 步驟 | 預估 | 評估 |
|------|------|------|
| 1a Intent log | 1h | ⚠️ 需要定義 schema + 序列化 + 測試 → 3-4h |
| 1c Ledger 重播 | 2h | ⚠️ 需要處理 partial replay + idempotency → 1-2 天 |
| 2a DAG | 2h | ❌ 自寫 DAG engine → 1-2 週（如果認真做） |
| 4a StrategyManager | 3h | ❌ 多策略編排 → 1 週+（Phase AG 花了更多） |

歷史教訓（LESSONS #22）：「代碼完成 ≠ 功能正常」。計畫總共預估 ~20 小時，但實際至少 3-4 週。

**修正**：不給小時數。按 Phase 排期，每個 Phase 1-2 週。

---

### 做得好的部分

1. **§1.2 每日運營流程圖**清晰完整——這正是系統需要的全景
2. **§2.2 自動 vs 人工**的分界正確——live trading 必須人工確認
3. **§4.3 通知分級**設計合理——P0~P3 分層避免通知疲勞
4. **§5 數據自動化排程**和 Phase AD 一致
5. **§7 不做的事**全部正確——不引入 K8s、Airflow、HFT engine
6. **§8 設計原則**5 條全部合理

---

### 修正後的執行計畫

```
Phase 1（本週）：
  1d  SIGTERM handler（關機前存 portfolio）
  1e  Docker API healthcheck
  2a  execute_pipeline 加交易日檢查
  2c  SchedulerService 加 TradingDayFilter

Phase 2（下週）：
  3a  HeartbeatMonitor（15 分鐘無心跳 → Discord 告警）
  3b  通知分級（P0~P3）
  3c  每日摘要報告

Phase 3（live trading 啟動前）：
  1a-1c  Intent log + trade ledger + 重播（SinopacBroker 需要）
  G4     掛單持久化（IMPROVEMENT_PLAN 的 G4）

```

### 前置條件

| 條件 | 狀態 |
|------|:----:|
| Phase AD 數據平台 | ✅ Phase 1-3 完成 |
| Phase S 統一管線 | ✅ |
| Phase AG 策略生命週期 | ✅ Steps 1-6 完成 |
| 1810 tests passing | ✅ |
