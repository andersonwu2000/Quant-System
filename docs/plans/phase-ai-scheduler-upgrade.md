# Phase AI：生產級排程與韌性 — 交易日曆感知 DAG + Crash Recovery + 數據自動化

> 狀態：📋 設計完成，待開發
> 前置：Phase AD（數據平台）✅、Phase S（Trading Pipeline）✅
> 日期：2026-03-31（v2 擴展）

---

## 1. 現狀問題

### 1.1 四大缺口

| # | 問題 | 現狀 | 風險 |
|---|------|------|------|
| **Q1** | 電腦關機/崩潰/斷網 | Docker restart + portfolio JSON 恢復，但下單後崩潰 = 倉位不一致 | **HIGH** |
| **Q2** | 數據收集未自動化 | Pipeline 前自動 refresh price，但 TWSE 快照/FinMind 批次/FinLab 全是手動 | MEDIUM |
| **Q3** | Autoresearch 數據不同步 | 容器內用舊路徑，主系統已遷移到 source-based 目錄 | MEDIUM |
| **Q4** | 管線未完全整合 | 交易管線連通，但 TWSE 日快照/backtest reconcile/數據定期刷新沒排進 DAG | MEDIUM |

### 1.2 現有排程

```
APScheduler (AsyncIOScheduler)
├── trading_pipeline      "3 9 11 * *"     每月11日 09:03
├── daily_reconcile       "30 14 * * 1-5"  週一~五 14:30
└── deployed_strategies   "0 10 12 * *"    每月12日 10:00
```

問題：cron 不感知交易日、無 heartbeat、數據刷新未排程、crash recovery 不完整。

### 1.3 已有的防護（不需重做）

| 機制 | 位置 | 狀態 |
|------|------|------|
| Docker `restart: unless-stopped` | docker-compose.yml | ✅ |
| 券商斷線自動重連（指數退避） | sinopac.py `_reconnect_loop` | ✅ |
| Yahoo 下載 3 次 retry | yahoo.py | ✅ |
| FinMind fallback | refresh.py | ✅ |
| 崩潰偵測 + portfolio 恢復 | jobs.py `check_crashed_runs` | ✅ |
| 每日冪等性（不重複下單） | jobs.py `_has_completed_run_today` | ✅ |
| Quality Gate fail-closed | quality_gate.py | ✅ |
| Kill Switch + Discord | risk/kill_switch.py | ✅ |
| 優雅關閉（broker disconnect） | execution/service.py | ✅ |

---

## 2. 設計

### 2.1 完整每日時間線（交易日）

```
07:50  ┌─ heartbeat_start        Discord: "系統啟動，準備交易日"
       │
08:00  ├─ data_daily_refresh     TWSE+TPEX OpenAPI 全市場快照 → data/twse/
       │                         Yahoo 增量更新 → data/yahoo/
       │                         FinMind 增量更新（有 token 時）→ data/finmind/
       │
08:20  ├─ quality_gate           L1-L4 檢查，失敗 → 停止 + 通知
       │
08:30  ├─ [等待開盤]
       │
09:03  ├─ trading_pipeline       策略 → 風控 → 下單（月度/週度/日度可配）
       │
09:10  ├─ heartbeat_post_trade   Discord: "Pipeline 完成，N 筆交易，NAV=XXX"
       │
13:30  ├─ eod_reconcile          券商對帳 + backtest reconcile
       │
13:45  ├─ eod_snapshot           NAV 快照 + 日報
       │
14:00  └─ heartbeat_eod          Discord: "EOD 完成，NAV=XXX，drift=Xbps"

非交易日：07:50 heartbeat_start 檢測到非交易日 → Discord "今日休市" → 不執行任何後續步驟
```

### 2.2 DAG 依賴鏈

```python
async def daily_trading_dag(config: TradingConfig) -> DagResult:
    """每日交易 DAG — 每步失敗就停止 + 通知。"""

    # Gate 0: 交易日檢查
    if not calendar.is_trading_day(today):
        await notify("今日休市，跳過所有任務")
        return DagResult(status="holiday")

    # Step 1: 數據刷新
    reports = await data_refresh_step(config)
    if not all(r.ok for r in reports):
        await notify("Data refresh failed", details=reports)
        return DagResult(status="data_failed")

    # Step 2: 品質閘門
    gate = quality_gate_step(universe)
    if not gate.passed:
        await notify("Quality gate blocked", details=gate)
        return DagResult(status="gate_blocked")

    # Step 3: 策略 + 執行
    result = await execute_pipeline(config)
    await notify_trade_result(result)

    # Step 4: EOD（不管 Step 3 成敗都跑）
    await eod_step(config)

    return DagResult(status="completed", trades=result.n_trades)
```

### 2.3 Crash Recovery 強化

```
現在的問題：
  1. broker 成交 → 2. portfolio 更新 → 3. JSON 寫入
  如果在步驟 2~3 之間崩潰，portfolio JSON 是舊的 → 倉位不一致

修正後：
  0. 寫 pre-trade intent log（準備下什麼單）
  1. broker 成交
  2. 寫 trade ledger（逐筆 append-only）
  3. portfolio 更新 + JSON 寫入
  4. 重啟時：讀 intent log + trade ledger → 重建正確狀態
```

### 2.4 數據自動化

| 數據 | 頻率 | 時間 | 方式 |
|------|------|------|------|
| TWSE+TPEX OHLCV | 每交易日 | 08:00 | `fetch_all_daily()` → `data/twse/` |
| TWSE 三大法人 | 每交易日 | 08:00 | `fetch_twse_institutional()` → `data/twse/` |
| Yahoo price 增量 | 每交易日 | 08:05 | `refresh_dataset("price")` → `data/yahoo/` |
| FinMind fundamental | 每月 11 日 | 08:10 | `refresh_dataset("revenue")` → `data/finmind/` |
| TWSE 休市日同步 | 每年 12 月 | 手動觸發 | `sync_holidays()` |

### 2.5 Heartbeat 監控

```python
class HeartbeatMonitor:
    """每個關鍵步驟發 Discord ping。超時未到 = 系統掛了。"""

    async def send(self, event: str, details: str = ""):
        """發送 heartbeat + 關鍵指標。"""
        # Discord webhook with timestamp + NAV + position count

    # 外部監控（可選）：
    # - healthchecks.io free tier（每步 ping 一次，超時告警）
    # - 或另一台機器的 cron 檢查 Discord 最後消息時間
```

### 2.6 Autoresearch 數據同步

```
問題：Docker 容器內 evaluate.py 用 DataCatalog，但 mount 的 data/ 路徑需對齊

修正：docker-compose volume mount 改為：
  volumes:
    - ../../data/yahoo:/app/data/yahoo:ro
    - ../../data/finmind:/app/data/finmind:ro
    - ../../data/twse:/app/data/twse:ro
    - ../../data/finlab:/app/data/finlab:ro
```

---

## 3. 執行計畫

### Phase 1：Crash Recovery（P0，最高優先）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 1a | Pre-trade intent log（下單前寫入意圖） | `src/execution/intent_log.py` |
| 1b | Trade ledger（逐筆 append-only 成交記錄） | `src/execution/trade_ledger.py` |
| 1c | 重啟時從 ledger 重建 portfolio 狀態 | 修改 `src/api/state.py` |
| 1d | SIGTERM handler（關機前取消掛單 + 存 portfolio） | 修改 `src/api/app.py` |
| 1e | Docker API healthcheck | 修改 `docker-compose.yml` |

### Phase 2：DAG + 交易日感知（P0）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 2a | `daily_trading_dag()` 統一入口 | `src/scheduler/dag.py` |
| 2b | TradingDayFilter for APScheduler | `src/scheduler/__init__.py` |
| 2c | 靈活再平衡頻率（config 驅動） | `src/core/config.py` |
| 2d | 替換 SchedulerService 的 job 為 DAG | `src/scheduler/__init__.py` |

### Phase 3：數據自動化（P1）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 3a | 每日 TWSE+TPEX 快照排程 | `src/scheduler/dag.py` |
| 3b | 每日 Yahoo 增量更新排程 | `src/scheduler/dag.py` |
| 3c | 每月 FinMind 批次更新排程 | `src/scheduler/dag.py` |
| 3d | Holiday 動態更新（TWSE 爬取） | `src/core/calendar.py` |

### Phase 4：Heartbeat + 監控（P1）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 4a | HeartbeatMonitor（Discord ping） | `src/scheduler/heartbeat.py` |
| 4b | 開盤/收盤 heartbeat 排程 | `src/scheduler/dag.py` |
| 4c | 外部監控整合文件 | `docs/guides/monitoring.md` |

### Phase 5：Autoresearch 同步（P1）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 5a | Docker volume mount 對齊新目錄結構 | `docker/autoresearch/docker-compose.yml` |
| 5b | evaluate.py 驗證（容器內跑一次確認數據可讀） | 驗證腳本 |
| 5c | Watchdog deploy queue 路徑更新 | `src/alpha/auto/deployed_executor.py` |

---

## 4. 不做的事

| 項目 | 原因 |
|------|------|
| Prefect / Dagster / Airflow | 單人系統，APScheduler + 自寫 DAG 夠用 |
| 分散式 portfolio lock | 單機部署，asyncio.Lock 足夠 |
| 毫秒級排程 | 台股日頻，秒級足夠 |
| 完整 WAL 交易日誌 | append-only ledger 已夠，不需要 DB WAL |

---

## 5. 設計原則

1. **交易日才跑** — 非交易日一個 API call 都不發
2. **失敗就停** — DAG 每步 fail-closed，不用 fallback 數據交易
3. **崩潰可恢復** — intent log + trade ledger 確保任何時刻崩潰都能重建正確狀態
4. **靜默就告警** — 預期的 heartbeat 沒到 = 系統掛了
5. **數據自動化** — 人不需要手動跑任何下載腳本
6. **頻率可配** — 月度→週度→日度再平衡，改 config 就好

---

## 6. 成功標準

| 指標 | 目標 |
|------|------|
| 非交易日 API 呼叫 | 0 |
| 崩潰後 portfolio 一致性 | 100%（ledger 重建） |
| 數據刷新 | 每交易日自動完成，無人工介入 |
| Heartbeat 覆蓋 | 開盤前/交易後/收盤後 各 1 次 |
| 再平衡頻率切換 | 改 config 重啟即生效 |

---

## 7. 參考資料

- [Quant Trading System Architecture (mbrenndoerfer)](https://mbrenndoerfer.com/writing/quant-trading-system-architecture-infrastructure)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/en/stable/)
- [systemd Watchdog for Python Daemons](https://blog.hqcodeshop.fi/archives/569-Writing-a-secure-Systemd-daemon-with-Python.html)
- [TWSE Holiday Schedule](https://www.twse.com.tw/en/trading/holiday.html)
- [Airflow vs Dagster vs Prefect (ZenML)](https://www.zenml.io/blog/orchestration-showdown-dagster-vs-prefect-vs-airflow)
