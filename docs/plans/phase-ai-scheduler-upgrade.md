# Phase AI：排程系統升級 — 從 Cron 到交易日曆感知 DAG

> 狀態：📋 設計完成，待開發
> 前置：Phase AD（數據平台）✅、Phase S（Trading Pipeline）✅
> 日期：2026-03-31

---

## 1. 現狀問題

### 1.1 目前架構

```
APScheduler (cron trigger)
    ├── trading_pipeline      "3 9 11 * *"  (每月11日 09:03)
    ├── daily_reconcile       "30 13 * * 1-5" (週一~五 13:30)
    └── deployed_strategies   "0 10 12 * *"  (每月12日 10:00)
```

### 1.2 問題

| 問題 | 影響 | 嚴重度 |
|------|------|:------:|
| **Cron 不感知交易日曆** | 國慶日/春節/颱風假仍觸發 pipeline，浪費 API quota + 假通知 | MEDIUM |
| **無 DAG 依賴** | data refresh 失敗但 pipeline 仍嘗試執行（Quality Gate 擋住，但已浪費時間） | LOW（已有 QG） |
| **非 daemon 模式** | 依賴外部 cron/systemd 啟動，無自我恢復 | MEDIUM |
| **無 heartbeat 監控** | 程式靜默死掉不會被發現，直到下次手動檢查 | HIGH |
| **時間線無彈性** | 每月只跑一次（11 日），無法支援每週/每日再平衡 | 設計限制 |
| **Holiday 硬編碼** | 2026 假日是估計值，颱風假/補行交易日無法動態更新 | MEDIUM |

### 1.3 業界做法研究

| 方法 | 適用場景 | 工具 | 我們適用？ |
|------|---------|------|:--------:|
| **交易日曆過濾 cron** | 日頻/週頻排程 | APScheduler + 自訂 filter | ✅ 最適合 |
| **DAG 編排器** | 複雜多步管線 | Prefect / Dagster / Airflow | ❌ 過重（單人系統） |
| **Daemon + Watchdog** | 24/7 常駐服務 | systemd + sd_notify / Docker restart | ✅ 適合 |
| **Heartbeat 監控** | 靜默失敗偵測 | Discord webhook + 定時 ping | ✅ 簡單有效 |

**結論**：不引入 Prefect/Dagster（過重），而是強化現有 APScheduler + 交易日曆 + heartbeat。

---

## 2. 設計

### 2.1 交易日曆感知排程

```python
# 現在：APScheduler cron 觸發 → pipeline 自己檢查 is_trading_day → 跳過
# 改後：APScheduler cron 觸發 → TradingDayFilter 先過濾 → 只在交易日執行

class TradingDayFilter:
    """APScheduler job filter — 非交易日直接跳過，不浪費資源。"""

    def __call__(self, job) -> bool:
        from src.core.calendar import get_tw_calendar
        return get_tw_calendar().is_trading_day(date.today())
```

### 2.2 DAG 式依賴鏈

不用 Dagster/Prefect，用簡單的 Python async chain：

```python
async def daily_trading_dag(config):
    """每日交易 DAG — 每步失敗就停止 + 通知。"""

    # Step 1: Data refresh
    reports = await refresh_all_trading_data(datasets=["price"])
    if not all(r.ok for r in reports):
        await notify("Data refresh failed", ...)
        return

    # Step 2: Quality gate
    gate = pre_trade_quality_gate(universe)
    if not gate.passed:
        await notify("Quality gate blocked", ...)
        return

    # Step 3: Strategy + execution
    result = await execute_pipeline(config)

    # Step 4: EOD reconciliation (always runs, even if step 3 fails)
    await execute_daily_reconcile(config)
    await execute_backtest_reconcile()
```

### 2.3 Holiday 動態更新

```python
# 每年 12 月從 TWSE 網站抓取次年休市日
# https://www.twse.com.tw/en/trading/holiday.html
# 颱風假：監聽行政院公告或手動 API 更新

async def sync_holidays(year: int) -> int:
    """從 TWSE 同步休市日。"""
    # 1. 嘗試從 TWSE 抓取
    # 2. 失敗則用 hardcoded fallback
    # 3. 更新 TWTradingCalendar
```

### 2.4 Heartbeat + 靜默失敗偵測

```
每日時間線：
  07:50  heartbeat_start    — Discord: "系統啟動，準備交易日"
  08:00  data_refresh       — 增量更新價格
  08:20  quality_gate       — 品質閘門
  08:30  [等待開盤]
  09:03  pipeline           — 策略計算 + 下單
  09:10  heartbeat_trade    — Discord: "Pipeline 完成，N 筆交易"
  13:30  eod_reconcile      — 對帳 + reconciliation
  13:45  heartbeat_eod      — Discord: "EOD 完成，NAV=XXX"

  如果 09:10 heartbeat 未送出 → 外部監控（Uptime Kuma/cron on another machine）告警
```

### 2.5 靈活排程頻率

```python
# 支援多種再平衡頻率，不只月度
REBALANCE_FREQUENCIES = {
    "monthly": "3 9 {rebalance_day} * *",   # 每月 N 日 09:03
    "biweekly": "3 9 1,15 * *",             # 每月 1、15 日
    "weekly": "3 9 * * 1",                   # 每週一
    "daily": "3 9 * * 1-5",                 # 每個交易日
}
# config.rebalance_frequency 控制
```

---

## 3. 執行計畫

### Phase 1：交易日感知（立即，1-2 小時）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 1a | APScheduler job 加 TradingDayFilter | `src/scheduler/__init__.py` |
| 1b | 移除 `execute_pipeline` 內的 `is_trading_day` 重複檢查 | `src/scheduler/jobs.py` |
| 1c | 支援多種再平衡頻率（config 驅動） | `src/core/config.py` |

### Phase 2：DAG 依賴鏈（本週）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 2a | `daily_trading_dag()` 統一入口 | `src/scheduler/dag.py` |
| 2b | 替換 SchedulerService 的 `_run_pipeline` 為 DAG | `src/scheduler/__init__.py` |
| 2c | Backtest reconcile 加入 EOD DAG | 修改 `src/scheduler/dag.py` |

### Phase 3：Heartbeat + 監控（本週）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 3a | Heartbeat Discord 通知（開盤/收盤） | `src/scheduler/heartbeat.py` |
| 3b | 排程 heartbeat jobs | `src/scheduler/__init__.py` |
| 3c | 外部監控整合文件（Uptime Kuma / healthcheck.io） | `docs/guides/monitoring.md` |

### Phase 4：Holiday 動態更新（下週）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 4a | TWSE 休市日爬取 | `src/core/calendar.py` |
| 4b | 每年 12 月自動同步 + 手動 API | `src/scheduler/__init__.py` |
| 4c | 颱風假手動更新 CLI | `src/data/cli.py` |

---

## 4. 不做的事

| 項目 | 原因 |
|------|------|
| Prefect / Dagster / Airflow | 單人系統不需要分散式編排器，維護成本 > 收益 |
| Kubernetes CronJob | 目前單機部署，K8s 過重 |
| 毫秒級排程精度 | 台股日頻策略，秒級精度足夠 |
| 多時區支援 | 只做台股，統一 Asia/Taipei |

---

## 5. 設計原則

1. **交易日才跑** — 非交易日一個 API call 都不發
2. **失敗就停** — DAG 每步 fail-closed，不用 fallback 數據交易
3. **靜默就告警** — 預期的 heartbeat 沒到 = 系統掛了
4. **頻率可配** — 月度→週度→日度再平衡，改 config 就好
5. **不過度設計** — APScheduler 夠用就不引入重型編排器

---

## 6. 參考資料

- [Quant Trading System Architecture (mbrenndoerfer)](https://mbrenndoerfer.com/writing/quant-trading-system-architecture-infrastructure)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/en/stable/)
- [systemd Watchdog for Python Daemons](https://blog.hqcodeshop.fi/archives/569-Writing-a-secure-Systemd-daemon-with-Python.html)
- [TWSE Holiday Schedule](https://www.twse.com.tw/en/trading/holiday.html)
- [Airflow vs Dagster vs Prefect (ZenML)](https://www.zenml.io/blog/orchestration-showdown-dagster-vs-prefect-vs-airflow)
