# 架構重構計畫

> **版本**: v2.0
> **日期**: 2026-03-26
> **原則**: 不計成本，但求最合理的設計 — 合理 ≠ 最複雜

---

## 1. 檢討結論

### 1.1 放棄 Event Bus

| 考量 | 結論 |
|------|------|
| 我們的交易頻率 | 日頻（每天 09:00 一次），非 tick-by-tick |
| Event Bus 的價值 | 即時事件反應、低延遲 — 我們不需要 |
| Event Bus 的代價 | 複雜度增加、debug 困難、回測變慢 ([QuantStart](https://www.quantstart.com/articles/Event-Driven-Backtesting-with-Python-Part-I/)) |
| 業界觀點 | 「大多數日頻策略不需要事件驅動」([Modular Quant Architecture](https://hiya31.medium.com/a-modular-architecture-for-systematic-quantitative-trading-systems-2a8d46463570)) |

**決定**：不引入 Event Bus。現有的直接函數呼叫對日頻策略完全合適。

### 1.2 放棄大規模目錄遷移

128 源檔 + 85 測試檔全部改 import 路徑，風險極高，收益為零（只是目錄名字好看）。

**決定**：保持現有 `src/` 結構。只在需要時新增模組。

### 1.3 保留的改動

| 改動 | 理由 | 優先級 |
|------|------|--------|
| **Smart Order (TWAP)** | 回測暴露 1,809 筆交易 / 195 萬手續費 — 拆單可直接降低 market impact | 🔴 P0 |
| **台股交易日曆** | 排程可能在假日觸發，且回測需要正確交易日計算 | 🔴 P0 |
| **Backtest-Live 路徑對齊** | 非 Event Bus 方式 — 讓 BacktestEngine 使用 ExecutionService | 🟡 P1 |
| **Position Manager** | 獨立持倉追蹤，支援多策略隔離 | 🟢 P2 |

---

## 2. Phase R1：Smart Order（TWAP 拆單）

### 2.1 問題

剛才回測：1,809 筆交易、手續費 NT$1,951,998（佔初始資金 20%）。原因：
- 每日 rebalance 產生 ~7 筆交易
- 每筆交易直接全量市價送出
- 零股模式下撮合間隔 3 分鐘，大單衝擊價格

### 2.2 設計

```python
# src/execution/smart_order.py

@dataclass
class ChildOrder:
    parent_id: str
    instrument: Instrument
    side: Side
    quantity: Decimal
    scheduled_time: datetime
    status: OrderStatus = OrderStatus.PENDING

class TWAPStrategy:
    """時間加權均價 — 將大單分拆為 N 筆，每隔 interval 分鐘送出。"""

    def __init__(self, n_slices: int = 5, interval_minutes: int = 30):
        self.n_slices = n_slices
        self.interval_minutes = interval_minutes

    def split(self, order: Order, start_time: datetime) -> list[ChildOrder]:
        """將母單拆為 n_slices 筆等量子單。"""
        slice_qty = order.quantity / self.n_slices
        children = []
        for i in range(self.n_slices):
            child = ChildOrder(
                parent_id=order.id,
                instrument=order.instrument,
                side=order.side,
                quantity=slice_qty,
                scheduled_time=start_time + timedelta(minutes=i * self.interval_minutes),
            )
            children.append(child)
        return children
```

### 2.3 整合點

- `ExecutionService.submit_orders()`: 當 `smart_order_enabled=True` 時，先拆單再逐筆送出
- `SimBroker`: 支援子單撮合（每筆獨立計算滑點）
- `BacktestEngine`: 支援盤中多時點撮合（而非只在收盤撮合）
- Config: `QUANT_SMART_ORDER_ENABLED=true`, `QUANT_SMART_ORDER_SLICES=5`

### 2.4 效果預估

| 指標 | 無 TWAP | 有 TWAP (5 slice) |
|------|---------|-------------------|
| 單筆滑點 | 5 bps | ~2 bps（量小→衝擊小）|
| 年化 cost drag | 多出 ~200 bps | 多出 ~80 bps |

---

## 3. Phase R2：台股交易日曆

### 3.1 問題

- `market_hours.py` 判斷週末但不判斷國定假日
- Auto-alpha 排程可能在春節、清明節等假日觸發
- 回測的交易日計算不準確

### 3.2 設計

```python
# src/core/tw_calendar.py

class TWTradingCalendar:
    """台灣證券交易所交易日曆。"""

    def __init__(self) -> None:
        self._holidays: set[date] = self._load_holidays()

    def is_trading_day(self, dt: date) -> bool:
        if dt.weekday() >= 5:
            return False
        return dt not in self._holidays

    def next_trading_day(self, dt: date) -> date: ...
    def prev_trading_day(self, dt: date) -> date: ...
    def trading_days_between(self, start: date, end: date) -> list[date]: ...

    def _load_holidays(self) -> set[date]:
        """載入 TWSE 休市日。"""
        # 2024-2026 硬編碼 + exchange_calendars 套件作為後備
```

### 3.3 整合點

- `market_hours.py`: `is_tradable()` 增加 `calendar.is_trading_day()` 檢查
- `AlphaScheduler`: `run_full_cycle()` 開頭檢查是否交易日
- `BacktestEngine`: 用 `trading_days_between()` 產生交易日序列

### 3.4 資料來源

TWSE 每年 12 月公告次年休市日。實作方式：
1. 硬編碼 2024~2026 年休市日（約 15~17 天/年）
2. 可選用 `exchange_calendars` PyPI 套件（支援 XTAI 交易所）
3. 提供 `update_holidays(year, dates)` 方法手動更新

---

## 4. Phase R3：Backtest-Live 路徑對齊

### 4.1 問題

`BacktestEngine.run()` (470 LOC) 和 `ExecutionService.submit_orders()` (60 LOC) 分別實作了：

| 步驟 | BacktestEngine | ExecutionService |
|------|---------------|-----------------|
| Strategy → weights | `strategy.on_bar(ctx)` | `strategy.on_bar(ctx)` (scheduler) |
| weights → orders | `weights_to_orders()` | `weights_to_orders()` (scheduler) |
| Risk check | `risk_engine.check_orders()` | `risk_engine.check_orders()` (scheduler) |
| 撮合/下單 | `sim_broker.execute()` | `broker.submit_order()` |
| Portfolio 更新 | `apply_trades()` | `apply_trades()` (scheduler) |

共用部分已有 80%，差異只在**撮合方式**和**NAV 記錄**。

### 4.2 方式：抽出共用 Pipeline

```python
# src/core/trading_pipeline.py

def execute_bar(
    strategy: Strategy,
    ctx: Context,
    portfolio: Portfolio,
    risk_engine: RiskEngine,
    broker: BrokerAdapter | SimBroker,
    instruments: dict[str, Instrument] | None = None,
) -> list[Trade]:
    """一根 bar 的完整處理流程 — 回測和實盤共用。"""
    target_weights = strategy.on_bar(ctx)
    if not target_weights:
        return []
    prices = {s: ctx.latest_price(s) for s in target_weights}
    orders = weights_to_orders(target_weights, portfolio, prices, instruments=instruments)
    approved = risk_engine.check_orders(orders, portfolio)
    if isinstance(broker, SimBroker):
        trades = broker.execute(approved, current_bars)
    else:
        trades = submit_and_collect(broker, approved)
    apply_trades(portfolio, trades)
    return trades
```

### 4.3 改動

- **BacktestEngine**: 內部迴圈改用 `execute_bar()`
- **Scheduler jobs.py**: 改用 `execute_bar()`
- **Auto-alpha executor**: 改用 `execute_bar()`
- 舊介面保留 wrapper，測試不壞

---

## 5. 不做的事（含理由）

| 項目 | 理由 |
|------|------|
| **Event Bus** | 日頻策略不需要。增加複雜度、debug 難度，回測變慢。 |
| **目錄大遷移** | 128+85 個檔案改 import，風險高，功能零改變。 |
| **Redis / TimescaleDB** | 開發階段 SQLite + JSON 足夠。 |
| **VWAP / Iceberg** | TWAP 足夠。VWAP 需要歷史分鐘成交量數據（我們沒有）。Iceberg 適用於大額機構單，個人投資者不需要。 |
| **Position Manager** | Portfolio.positions 已夠用。多策略隔離等需求出現再做。 |
| **重寫 Strategy 介面** | `on_bar → weights` 比 `on_market_data → signals` 更好。 |

---

## 6. 執行順序

| 順序 | Phase | 內容 | 改動量 | 風險 |
|------|-------|------|--------|------|
| 1 | **R2** | 台股交易日曆 | 新增 ~200 LOC | 低 |
| 2 | **R1** | TWAP Smart Order | 新增 ~300 LOC + 修改 ExecutionService | 低 |
| 3 | **R3** | Trading Pipeline 抽取 | 重構 ~200 LOC | 中 |

**總改動量**：~700 LOC 新增 + ~200 LOC 重構。遠小於原計畫的 ~2,000 LOC。

---

## 7. 成功指標

- [ ] 1,091+ tests 全部通過
- [ ] 回測結果 bit-identical（重構前後同策略同數據）
- [ ] 排程不在假日觸發
- [ ] TWAP 拆單降低滑點 50%+
- [x] BacktestEngine 使用 `execute_one_bar()` (Phase R3 完成)
