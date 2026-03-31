# Phase AI：生產運營架構 — 控制平面設計

> 狀態：✅ Phase 1-4 實作完成，Phase 5（UI）可選
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

## 6. 元件評估：保留 vs 重寫

> 原則：如果重寫能達到更好的最終效果，就重寫。不為了保留舊代碼而妥協設計。

| 元件 | 現狀 | 能達到目標？ | 決定 |
|------|------|:----------:|------|
| **SchedulerService** | 3 個獨立 cron，互不協調 | ❌ | **重寫**為 daily_ops 統一流程 |
| **execute_pipeline** | 300 行，refresh→gate→strategy 已串通 | ✅ | **保留**，被 daily_ops 調用 |
| **通知系統** | 單一級別，全送 Discord | ❌ | **改寫**，加 P0-P3 分級 |
| **數據刷新** | 只在 pipeline 內跑 price+revenue | ❌ | **擴展**，TWSE 快照+全數據集 |
| **Heartbeat** | 不存在 | ❌ | **新建** |
| **日報** | 不存在 | ❌ | **新建** |
| **Ops API** | 不存在（看狀態要讀 JSON） | ❌ | **新建** |
| **交易日曆** | 有，但 scheduler 不用 | ⚠️ | 簡單整合 |
| **Portfolio state** | JSON，paper mode 夠用 | ✅ | 不改（live 前再加 ledger）|
| **策略生命週期** | Phase AG 已完成 | ✅ | 不改 |
| **DataCatalog** | Phase AD 剛建完 | ✅ | 不改 |

### SchedulerService 重寫設計

現在：3 個獨立 cron job，加到 7-8 個會變成維護噩夢。

```python
# 現在（散落的 cron jobs）
scheduler.add_job(run_pipeline, cron="3 9 11 * *")
scheduler.add_job(run_reconcile, cron="30 14 * * 1-5")
scheduler.add_job(run_deployed, cron="0 10 12 * *")
```

```python
# 重寫後（統一 daily_ops 流程）
scheduler.add_job(daily_ops, cron="50 7 * * 1-5")  # 每交易日 07:50

async def daily_ops(config):
    """每日運營統一入口。非交易日自動跳過。"""

    if not is_trading_day():
        await notify(P2, "今日休市")
        return

    # ── 開盤前 ──────────────────────────────
    await heartbeat("系統啟動，準備交易日")

    reports = await data_refresh()       # TWSE快照 + Yahoo增量 + FinMind(conditional)
    if not all_ok(reports):
        await notify(P1, "數據刷新失敗", reports)
        # 不停止 — 用現有數據繼續（Quality Gate 會把關）

    gate = await quality_gate(universe)
    if not gate.passed:
        await notify(P0, "品質閘門攔截", gate)
        return  # 停止交易

    # ── 交易 ──────────────────────────────
    if is_rebalance_day(config):         # 月度/週度/日度可配
        result = await execute_pipeline(config)  # 已有，不改
        await heartbeat(f"交易完成：{result.n_trades} 筆")

    if is_deployed_execution_day():      # 每月 12 日
        await run_deployed_strategies()  # Phase AG，不改

    # ── 收盤後（排程在 13:30）──────────────
    await schedule_at("13:30", eod_ops, config)

async def eod_ops(config):
    """收盤後流程。"""
    await execute_daily_reconcile(config)   # 券商對帳，已有
    await execute_backtest_reconcile()      # 回測比對，已有
    summary = await generate_daily_summary()  # 新建
    await notify(P2, summary)
    await heartbeat("EOD 完成")
```

**不動的函式**：execute_pipeline、execute_daily_reconcile、execute_backtest_reconcile、run_deployed_strategies — 這些是「做事的」，邏輯正確，不需要重寫。

**重寫的是「編排」**：誰先跑、誰後跑、失敗怎麼處理、通知什麼級別。

---

## 7. 執行計畫

> 參考：NautilusTrader crash-only design — startup 和 recovery 共用同一個 code path。
> Paper mode 用 SimBroker（同步撮合），intent log + ledger 留到 live 前。

### Phase 1：重寫 SchedulerService + daily_ops（P0）

核心改動。把散落的 cron 整合為統一的每日運營流程。

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 1a | 重寫 SchedulerService — daily_ops 統一入口 | `src/scheduler/__init__.py` |
| 1b | daily_ops 流程（交易日檢查→數據刷新→QG→pipeline→EOD） | `src/scheduler/ops.py`（新建）|
| 1c | 每日數據刷新步驟（TWSE 快照 + Yahoo 增量） | `src/scheduler/ops.py` |
| 1d | is_rebalance_day（月度/週度/日度可配） | `src/core/config.py` |
| 1e | SIGTERM handler（關機前存 portfolio） | 修改 `src/api/app.py` |
| 1f | Docker API healthcheck | 修改 `docker-compose.yml` |

### Phase 2：Heartbeat + 通知分級 + 日報（P1）

讓系統會說話 — 正常時報平安，異常時告急。

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 2a | HeartbeatMonitor（開盤前/交易後/收盤後 Discord ping） | `src/scheduler/heartbeat.py` |
| 2b | 通知分級（P0 緊急 → P3 調試） | 修改 `src/notifications/` |
| 2c | 每日摘要報告（Discord：NAV、trades、drift、數據狀態） | `src/scheduler/ops.py` |
| 2d | Ops API endpoints（`/ops/daily-summary`、`/ops/positions`） | `src/api/routes/ops.py` |

### Phase 3：Live Trading 準備（live 啟動前，P1）

Paper mode 不需要，但 live 前必須有。

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 3a | Intent log（下單前寫入意圖） | `src/execution/intent_log.py` |
| 3b | Trade ledger（逐筆 append-only） | `src/execution/trade_ledger.py` |
| 3c | 重啟時 ledger 重播恢復 | 修改 `src/api/state.py` |
| 3d | 掛單持久化（pending orders → SQLite） | `src/execution/order_book.py` |

### Phase 4：Autoresearch 同步（P2）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 4a | Docker volume mount 對齊新目錄結構 | `docker/autoresearch/docker-compose.yml` |
| 4b | 容器內數據驗證 | 驗證腳本 |

### ~~策略生命週期管理~~ → Phase AG 已完成

PaperDeployer + DeployedExecutor + 多 portfolio 隔離 + 安全限制均在 Phase AG，不重複。

### Phase 5：使用者介面（P2，可選）

| 步驟 | 內容 | 備註 |
|------|------|------|
| 5a | Discord Bot（/status, /rebalance） | 日常操作最方便的方式 |
| 5b | Web Dashboard Ops 頁面 | 系統狀態一覽 |
| 5c | Mobile Push 通知 | P0 告警推播 |

---

## 8. 不做的事

| 項目 | 原因 |
|------|------|
| Prefect / Dagster / Airflow | 單人系統，daily_ops 函式就是編排器 |
| Paper mode 的 intent log | SimBroker 同步撮合，重跑 pipeline 即可恢復 |
| Kubernetes | 單機部署 |
| 分散式 portfolio lock | 單進程，asyncio.Lock 足夠 |
| 完整 GUI 交易台 | Web Dashboard 有基本頁面，不做 Bloomberg 級別 |
| HFT 級 tick engine | 台股日頻策略不需要 |

---

## 8. 設計原則

1. **無人值守** — 正常情況下不需要人工操作，系統自己跑
2. **異常通知** — 只在出問題時打擾你，不發廢通知
3. **Crash-only design** — startup 和 recovery 共用同一個 code path（參考 NautilusTrader）。Paper mode 重跑 pipeline 即恢復；live mode 靠 trade ledger 重播
4. **一鍵查看** — 一個指令/一次點擊看到系統全貌
5. **漸進上線** — paper 30 天 → 人工審核 → live，不自動用真錢
6. **結果導向** — 如果重寫能達到更好的最終效果，就重寫。不為了保留舊代碼而妥協設計

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

---

## 11. 覆核（2026-03-31，對修改版的二次審批）

### 判定：✅ 修改版解決了 4 個問題中的 3 個。daily_ops 重寫方案合理，同意執行。

---

### 問題 1 回覆（Phase AG 重複）：✅ 已解決

§7 新增「~~策略生命週期管理~~ → Phase AG 已完成」。§6 元件評估明確標記「策略生命週期 — 不改」。不再重複。

### 問題 2 回覆（Crash Recovery）：✅ 已解決

Intent log + ledger 降為 Phase 3（live 前才做）。§8 新增「Paper mode 的 intent log — 不做」。正確。

### 問題 3 回覆（DAG 設計）：⚠️ 部分接受，有條件同意

修改版把「自寫 DAG engine」改為「重寫 SchedulerService，用 daily_ops 函式統一編排」。這比原始的 DAG 提案務實很多。

**同意的理由**：
1. 現有 SchedulerService 確實有問題 — 3 個獨立 cron 無法表達「先 refresh → 再 QG → 再 pipeline」的依賴關係。如果 refresh 卡住，pipeline 仍會在 09:03 啟動
2. `daily_ops()` 不是 DAG engine — 就是一個 async 函式，按順序呼叫已有函式。複雜度可控
3. `execute_pipeline` 內部已有 refresh → QG → strategy 流程，但它混合了「編排」和「執行」。拆出 daily_ops 做編排層是合理的分層

**條件**：
1. `daily_ops` 不超過 100 行 — 如果超過，說明它承擔了太多邏輯
2. `execute_pipeline` 內部的 refresh + QG 邏輯要移到 daily_ops 還是保留？需要明確。目前 execute_pipeline 已在做 refresh + QG（jobs.py:415-460），如果 daily_ops 也做，就會重複
3. 建議：daily_ops 做交易日檢查 + heartbeat + EOD 排程，`execute_pipeline` 保留 refresh + QG + strategy（不拆開）

### 問題 4 回覆（工作量預估）：✅ 已解決

修改版不再給小時數。

---

### 新增觀察

**§8 編號重複**：有兩個 `## 8.`（不做的事 + 設計原則）。應改為 `## 8.` 和 `## 9.`（原來的 §9 成功標準變 §10）。

**§6 元件評估的「數據刷新 — 擴展」和 Phase AD 重疊**：Phase AD 的 refresh engine 已支援全數據集（12 種），不只是 price+revenue。§6 的「擴展 TWSE 快照+全數據集」大部分已在 Phase AD 完成。應標注現狀。

**daily_ops 和 execute_pipeline 的分界需要更精確**：
- 如果 daily_ops 呼叫 `execute_pipeline(config)`，而 execute_pipeline 內部已經做 refresh + QG，那 daily_ops 的 `data_refresh()` 和 `quality_gate()` 步驟就是重複的
- 建議二選一：(a) daily_ops 只做交易日 + heartbeat + EOD，pipeline 保持現狀；(b) 從 pipeline 拆出 refresh + QG 到 daily_ops，pipeline 只做 strategy → broker
- 修改版的 §6.2 pseudocode 暗示 (b)，但沒有明確說要從 execute_pipeline 拆出 refresh + QG

**結論**：Phase 1 可以開始，但實作前先決定 daily_ops vs execute_pipeline 的分界。
