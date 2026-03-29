# Phase S：自動化管線統一

> 狀態：✅ 完成（2026-03-29）
> 前置：Phase R（管線缺陷修正）
> 目標：三條排程路徑合併為一條統一管線 + 研究管線獨立

---

## 1. 現狀問題

三條路徑（General Rebalance / Monthly Revenue / Auto-Alpha）是不同 Phase 分別開發：

- `execute_rebalance()` — 通用排程再平衡
- `monthly_revenue_rebalance()` — 營收策略專用
- Auto-Alpha — 因子研究（不操作 Portfolio）

**問題**：
1. 前兩條做一樣的事（數據→策略→下單），大量重複代碼
2. 共享 `state.portfolio` 靠 lock 防併發，架構上不應該有併發可能
3. 切換策略需要改代碼，不是改配置
4. 數據更新（revenue_update）和再平衡之間沒有依賴檢查（Phase R 已發現）

---

## 2. 目標架構

```
Trading Pipeline（唯一交易管線）
    Cron 觸發 → 數據更新 → 執行策略 → 風控 → 下單 → 持久化 → 通知

Research Pipeline（獨立，不操作 Portfolio）
    Cron 觸發 → 因子假說 → 實作 → L1-L5 → Validator → 部署判斷
```

Config:
```
QUANT_ACTIVE_STRATEGY=revenue_momentum_hedged
QUANT_TRADING_PIPELINE_CRON=30 8 11 * *
QUANT_PIPELINE_DATA_UPDATE=true
```

---

## 3. 實作步驟

### S1：Config 新增（`src/core/config.py`）

```python
active_strategy: str = "revenue_momentum_hedged"
trading_pipeline_cron: str = "30 8 11 * *"
pipeline_data_update: bool = True
```

保留舊 config 向後相容（deprecation warning）。

### S2：統一 `execute_pipeline()`（`src/scheduler/jobs.py`）

取代 `execute_rebalance` + `monthly_revenue_rebalance`：

```python
@dataclass
class PipelineResult:
    status: str  # "ok" | "data_failed" | "no_weights" | "error"
    n_trades: int = 0
    error: str = ""

async def execute_pipeline(config: TradingConfig) -> PipelineResult:
    """統一交易管線。"""
    strategy = resolve_strategy(config.active_strategy)

    # 1. 數據更新（依賴檢查：失敗則中止）
    if config.pipeline_data_update:
        ok = await _update_data_for_strategy(strategy)
        if not ok:
            await _notify_error(config, "Data update failed")
            return PipelineResult(status="data_failed")

    # 2. Context
    state = get_app_state()
    universe = _build_universe(state.portfolio)
    feed = create_feed(config.data_source, universe)
    fundamentals = create_fundamentals(config.data_source)
    ctx = Context(feed=feed, portfolio=state.portfolio, fundamentals_provider=fundamentals)

    # 3. 執行策略
    weights = strategy.on_bar(ctx)
    if not weights:
        return PipelineResult(status="no_weights")

    _save_selection_log(weights, strategy.name())

    # 4. 風控 + 下單
    prices = {s: feed.get_latest_price(s) for s in weights}
    orders = weights_to_orders(weights, state.portfolio, prices)
    approved = [o for o in orders if state.risk_engine.check_order(o, state.portfolio).approved]
    trades = state.execution_service.submit_orders(approved, state.portfolio)
    if trades:
        apply_trades(state.portfolio, trades)

    # 5. 通知
    await _notify_success(config, strategy.name(), len(trades), state.portfolio.nav)

    return PipelineResult(status="ok", n_trades=len(trades))
```

### S3：策略感知數據更新

```python
async def _update_data_for_strategy(strategy: Strategy) -> bool:
    """根據策略類型更新所需數據。"""
    revenue_strategies = {"revenue_momentum", "revenue_momentum_hedged", "trust_follow"}
    if strategy.name() in revenue_strategies:
        return await _run_revenue_update()
    # 其他策略只需要價格（由 feed 自動處理）
    return True

async def _run_revenue_update() -> bool:
    """下載最新營收，回傳是否成功。"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "scripts.download_finmind_data",
             "--symbols-from-market", "--dataset", "revenue", "--start", "2024-01-01"],
            capture_output=True, text=True, timeout=600,
        )
        return result.returncode == 0
    except Exception:
        return False
```

### S4：簡化 SchedulerService

```python
class SchedulerService:
    def start(self, config):
        # 只有一個 trading job
        self._scheduler.add_job(
            self._run_pipeline,
            trigger=CronTrigger.from_crontab(config.trading_pipeline_cron),
            id="trading_pipeline",
            kwargs={"config": config},
        )
        # Research pipeline 獨立（可選）
        # 不在這裡管理，用 POST /auto-alpha/start 或 CronCreate

    async def _run_pipeline(self, config):
        await execute_pipeline(config)
```

### S5：移除舊代碼

- `execute_rebalance()` → 被 `execute_pipeline()` 取代
- `monthly_revenue_rebalance()` → 同上
- `monthly_revenue_update()` → 整合到 `_update_data_for_strategy()`
- Config: `revenue_scheduler_enabled` / `revenue_update_cron` / `revenue_rebalance_cron` → deprecated

### S6：測試 + 文件

- 更新 `test_scheduler.py`
- 更新 CLAUDE.md、SYSTEM_STATUS_REPORT.md
- 新增不變量測試：pipeline 必須先更新數據再跑策略

---

## 4. 關鍵設計決策

| 決策 | 選擇 | 原因 |
|------|------|------|
| 數據更新失敗時 | 中止 + 通知 | Phase R 發現的 race condition |
| 併發控制 | 架構上不可能（1 job） | 比 lock 更安全 |
| 多策略 | 不支援（1 active） | 簡單優先，足夠當前需求 |
| Research Pipeline | 完全獨立 | 不操作 Portfolio，不需要 lock |

---

## 5. 驗證

1. `pytest tests/unit/test_scheduler.py`
2. 手動：`QUANT_ACTIVE_STRATEGY=momentum` 跑非 revenue 策略
3. 手動：`QUANT_ACTIVE_STRATEGY=revenue_momentum_hedged` 跑 revenue 路徑
4. 確認 Auto-Alpha 不受影響
5. 不變量測試：data_update_failed → 不下單
