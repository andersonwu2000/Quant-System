# Phase T：Paper Trading 完善

> 狀態：✅ 完成
> 前置：Paper Trading 審查修復完成（10/15 已修）
> 目標：補齊 Paper Trading 的三個功能缺口

---

## 現狀

Paper Trading 管線代碼已就緒，10 個 bug 已修。剩餘 3 個功能缺口：

| # | 問題 | 影響 |
|---|------|------|
| T1 | Paper mode 任意時間下單，用過時收盤價 | 週六觸發用週五收盤，和週一開盤有落差 |
| T2 | 無回測 vs Paper Trading R² 比較 | 無法驗證回測引擎可信度（Phase N4 核心需求） |
| T3 | 無自動對帳 | 策略目標 vs 實際持倉偏差不會被偵測 |

---

## T1：市場時段感知

**問題**：cron 在任何時間觸發都會下單。`feed.get_latest_price()` 取的是最後交易日收盤價。

**方案**：Pipeline 啟動時檢查是否為交易日 + 交易時段。非交易時段 → 跳過並 log。

```python
# 在 _execute_pipeline_inner 開頭加入
from src.core.calendar import get_tw_calendar
cal = get_tw_calendar()
now = datetime.now()
if not cal.is_trading_day(now.date()):
    return PipelineResult(status="skipped", error="Non-trading day")
# 台股 09:00-13:30，允許 08:00-14:00 的寬鬆時段
if not (8 <= now.hour <= 14):
    return PipelineResult(status="skipped", error=f"Outside trading hours ({now.hour}:00)")
```

**難度**：低（10 分鐘）

---

## T2：回測 vs Paper Trading R² 比較

**問題**：Phase N4 要求「同期回測 NAV vs Paper Trading NAV 的 R²」但沒有實作。

**方案**：

1. 每次 pipeline 完成後，用相同策略 + 相同日期跑一次回測，存結果
2. 累積足夠數據後（≥ 5 個月），計算 R²
3. 存到 `data/paper_trading/backtest_comparison/`

```python
async def _record_backtest_comparison(config, strategy, target_weights, trades):
    """跑同期回測，記錄 NAV 用於未來 R² 比較。"""
    from src.backtest.engine import BacktestEngine, BacktestConfig

    today = datetime.now().strftime("%Y-%m-%d")
    bt_config = BacktestConfig(
        universe=list(target_weights.keys()),
        start=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        end=today,
        initial_cash=float(state.portfolio.initial_cash),
    )
    engine = BacktestEngine()
    result = engine.run(strategy, bt_config)

    comparison = {
        "date": today,
        "paper_nav": float(state.portfolio.nav),
        "backtest_nav": result.nav_series.iloc[-1] if not result.nav_series.empty else 0,
        "paper_trades": len(trades),
        "backtest_trades": result.total_trades,
    }
    # 存檔
    path = Path("data/paper_trading/backtest_comparison") / f"{today}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(comparison, indent=2))
```

**難度**：中（30 分鐘）

---

## T3：自動對帳

**問題**：Pipeline 完成後沒有比對策略目標 vs 實際持倉。

**方案**：Pipeline 結束前加入對帳步驟。

```python
def _reconcile(target_weights, portfolio, trades):
    """比對策略目標 vs 實際持倉，回傳偏差。"""
    deviations = []
    for sym, target_w in target_weights.items():
        actual_w = float(portfolio.get_position_weight(sym))
        diff = abs(target_w - actual_w)
        if diff > 0.02:  # 偏差 > 2%
            deviations.append({
                "symbol": sym,
                "target": round(target_w, 4),
                "actual": round(actual_w, 4),
                "deviation": round(diff, 4),
            })
    return deviations
```

偏差 > 5% 時發通知告警。

**難度**：低（15 分鐘）

---

## 執行順序

```
T1（市場時段，10 分鐘）→ T3（對帳，15 分鐘）→ T2（R² 比較，30 分鐘）
```

預估總工時：~1 小時
