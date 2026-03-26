# Phase S：自動化管線統一

> 狀態：🔵 待執行
> 前置：Phase R10（管線缺陷修正）✅
> 目標：將三條獨立排程路徑合併為一條統一管線 + 獨立研究管線

---

## 1. 現狀問題

三條路徑（General Rebalance / Monthly Revenue / Auto-Alpha）是不同 Phase 分別開發的產物，共享同一個 `state.portfolio` 但各自獨立排程。R10 加了 `asyncio.Lock` 防併發，但根本問題是：

- **General Rebalance 和 Monthly Revenue 做的事情一樣**（取數據 → 跑策略 → 下單），只是策略不同
- 兩條路徑有大量重複代碼（`execute_rebalance` vs `monthly_revenue_rebalance` 結構幾乎相同）
- 「不可同時運行」靠 lock 強制，不如從架構上消除可能性
- Auto-Alpha 不操作 Portfolio（只做因子研究），本質上與交易管線無關，不需要共享 lock

---

## 2. 目標架構

```
┌─────────────────────────────────────────────────────────┐
│  Trading Pipeline（唯一的交易管線）                       │
│                                                          │
│  Cron 觸發（可配置）                                     │
│    │                                                     │
│    ├→ 1. 更新數據（如果 active 策略需要）                │
│    │     revenue 策略 → 下載 FinMind 營收                │
│    │     其他策略 → 下載 Yahoo 行情                      │
│    │     失敗 → 重試 1 次 → 仍失敗則通知 + 中止         │
│    │                                                     │
│    ├→ 2. 執行策略                                        │
│    │     resolve_strategy(config.active_strategy)        │
│    │     strategy.on_bar(ctx) → target_weights           │
│    │                                                     │
│    ├→ 3. 風控檢查                                        │
│    │     RiskEngine.check_order() 逐筆                   │
│    │                                                     │
│    ├→ 4. 下單                                            │
│    │     ExecutionService.submit_orders()                 │
│    │     apply_trades() → Portfolio 更新                  │
│    │                                                     │
│    ├→ 5. 持久化                                          │
│    │     selection log + trade log → JSON                 │
│    │                                                     │
│    └→ 6. 通知                                            │
│          Discord / LINE / Telegram                       │
│                                                          │
│  Config:                                                 │
│    QUANT_ACTIVE_STRATEGY=revenue_momentum_hedged         │
│    QUANT_TRADING_PIPELINE_CRON=30 8 11 * *               │
│    QUANT_PIPELINE_DATA_UPDATE=true                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│  Research Pipeline（獨立，不操作 Portfolio）              │
│                                                          │
│  觸發：POST /auto-alpha/start 或 CronCreate             │
│    → 因子假說生成 → 實作 → 驗證 → Memory 回寫           │
│    → 不下單、不修改 Portfolio                             │
│    → 可與 Trading Pipeline 並行運行                      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 實作步驟

### S1：新增 `QUANT_ACTIVE_STRATEGY` config

`src/core/config.py` 新增：

```python
active_strategy: str = "revenue_momentum_hedged"
trading_pipeline_cron: str = "30 8 11 * *"
pipeline_data_update: bool = True
```

移除 `revenue_scheduler_enabled`、`revenue_update_cron`、`revenue_rebalance_cron`、`rebalance_cron`（合併為一個 cron）。

**注意**：保留向後相容，如果舊 config 存在則自動遷移。

### S2：統一 `execute_pipeline()` 函式

`src/scheduler/jobs.py` 新增一個函式取代 `execute_rebalance` + `monthly_revenue_rebalance`：

```python
async def execute_pipeline(config: TradingConfig) -> PipelineResult:
    """統一交易管線 — 更新數據 → 執行策略 → 風控 → 下單 → 持久化 → 通知。"""

    strategy = resolve_strategy(config.active_strategy)

    # 1. 數據更新（根據策略類型決定）
    if config.pipeline_data_update:
        if needs_revenue_data(strategy):
            ok = await monthly_revenue_update()
            if not ok:
                return PipelineResult(status="data_update_failed")
        else:
            await refresh_market_data(config)

    # 2. 建立 Context
    universe = get_universe(config, state.portfolio)
    feed = create_feed(config.data_source, universe)
    ctx = build_context(feed, state.portfolio, strategy)

    # 3. 執行策略
    target_weights = strategy.on_bar(ctx)

    # 4. 風控 + 下單
    orders = weights_to_orders(target_weights, ...)
    approved = risk_check(orders, state)
    trades = execute_orders(approved, state)

    # 5. 持久化 + 通知
    save_logs(target_weights, trades, strategy.name)
    await notify(config, trades, strategy.name)

    return PipelineResult(status="ok", n_trades=len(trades))
```

### S3：簡化 `SchedulerService`

```python
class SchedulerService:
    def start(self, config):
        # 只註冊一個 job
        self._scheduler.add_job(
            self._run_pipeline,
            trigger=CronTrigger.from_crontab(config.trading_pipeline_cron),
            id="trading_pipeline",
        )

    async def _run_pipeline(self, config):
        async with _pipeline_lock:
            await execute_pipeline(config)
```

從 3 個 job 變成 1 個。Auto-Alpha 不在這裡管理。

### S4：策略感知的數據更新

不同策略需要不同的數據更新邏輯：

```python
def needs_revenue_data(strategy) -> bool:
    """判斷策略是否需要 FinMind 營收數據。"""
    return strategy.name in ("revenue_momentum", "revenue_momentum_hedged", "trust_follow")
```

Revenue 策略 → 下載 FinMind 營收。其他策略 → 只更新 Yahoo 行情（或不更新）。

### S5：移除舊代碼

- 刪除 `execute_rebalance()`（被 `execute_pipeline()` 取代）
- 刪除 `monthly_revenue_rebalance()`（同上）
- 刪除 `SchedulerService._revenue_update_then_rebalance()`
- 刪除 `SchedulerService._rebalance_job()`
- Config 移除 `revenue_scheduler_enabled`、`revenue_update_cron`、`revenue_rebalance_cron`、`rebalance_cron`

### S6：更新文件

- `CLAUDE.md` Scheduling 段落
- `SYSTEM_STATUS_REPORT.md` §12 管線圖
- `.env.example`

---

## 4. 新舊對照

| 項目 | 舊（3 路徑） | 新（統一） |
|------|-------------|-----------|
| Config 欄位 | 5 個 cron/enable | 3 個（active_strategy + cron + data_update） |
| Job 數量 | 3 個（rebalance + revenue_update + revenue_rebalance） | 1 個（trading_pipeline） |
| 函式 | `execute_rebalance` + `monthly_revenue_rebalance` + `monthly_revenue_update` | `execute_pipeline` + `monthly_revenue_update` |
| 併發控制 | asyncio.Lock（R10.3 補丁） | 架構上不可能併發（只有一個 job） |
| 策略切換 | 改代碼或改 config flag | 改一個 env var `QUANT_ACTIVE_STRATEGY` |
| 數據更新 | 硬編碼 revenue | 策略感知（根據 active 策略決定） |
| Auto-Alpha | 共享 lock | 完全獨立，可並行 |

---

## 5. 不在此 Phase 處理

| 項目 | 原因 |
|------|------|
| 多策略同時運行 | 超出當前需求，一個 active 策略就夠 |
| 策略切換 UI | Web 前端可以後加 |
| Auto-Alpha 自動部署因子 | 需要先驗證 Auto-Alpha 產出的品質 |

---

## 6. 預估工作量

| 步驟 | 估計 |
|:----:|:----:|
| S1 Config | 15 min |
| S2 execute_pipeline | 45 min |
| S3 SchedulerService | 15 min |
| S4 策略感知數據更新 | 15 min |
| S5 移除舊代碼 | 15 min |
| S6 文件更新 | 15 min |
| **合計** | **~2 hr** |

---

## 7. 驗證方式

1. `pytest tests/unit/test_scheduler.py` — 現有測試通過
2. 手動測試：`QUANT_ACTIVE_STRATEGY=momentum QUANT_MODE=backtest` 確認 pipeline 能跑非 revenue 策略
3. 手動測試：`QUANT_ACTIVE_STRATEGY=revenue_momentum_hedged` 確認 revenue 路徑正常
4. 確認 Auto-Alpha 不受影響（`POST /auto-alpha/start` 仍可正常啟動）
