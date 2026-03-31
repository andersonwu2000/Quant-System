# Phase AI Operations Architecture — Code Review

> Scope: `src/scheduler/ops.py`, `src/scheduler/__init__.py`, `src/scheduler/heartbeat.py`, `src/notifications/__init__.py`, `src/execution/trade_ledger.py`, `src/api/routes/ops.py`
> Date: 2026-03-31

---

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| HIGH     | 2     | Fixed  |
| MEDIUM   | 3     | 1 Fixed, 2 Won't Fix |
| LOW      | 2     | Won't Fix |

整體實作品質高。daily_ops 控制在 80 行，職責分離清晰。

---

## HIGH

### O1. ops.py:122 — weekly rebalance 硬編碼 weekday==0，和 engine.py 修復不一致 ✅ FIXED

```python
elif freq == "weekly":
    return today.weekday() == 0  # Monday
```

engine.py 已修為 ISO week number 比較（BUG_HUNT H3），但 ops.py 的 `_is_rebalance_day` 用舊邏輯。週一休市時 daily_ops 不觸發交易，但 backtest engine 會在該週第一個交易日觸發 — paper vs backtest 不一致。

**Fix:** 改為 ISO week 邏輯，和 engine.py 一致。

### O2. ops.py:165 — TWSE snapshot append 異常靜默吞掉 ✅ FIXED

```python
except Exception:
    pass  # 整個 append 失敗靜默忽略
```

如果現有 parquet 損壞，整個 symbol 的 TWSE 數據被跳過。沒有 log。

**Fix:** 加 `logger.debug`。

---

## MEDIUM

### O3. trade_ledger.py:128 — 時間戳字串比較不可靠 ✅ FIXED

```python
if e["type"] == "fill" and e.get("timestamp", "") > portfolio_as_of:
```

字串比較 ISO timestamp 在大部分情況正確，但如果 `portfolio_as_of` 不是 ISO 格式或有時區，比較會靜默錯誤。

**Fix:** 用 datetime 解析比較。

### O4. heartbeat.py — 每次呼叫都重新建立 notifier — Won't Fix

```python
config = get_config()
notifier = create_notifier(config)
```

每次 heartbeat 都建一個新的 notifier 實例。

**判定：** 一天最多 5 次 heartbeat，開銷可忽略。全局 singleton 會增加耦合。

### O5. ops.py:59 — deployed strategies 用 today.day==12 硬編碼 — Won't Fix

```python
if today.day == 12:
```

和 SchedulerService 舊版的 cron `"0 10 12 * *"` 重複。但 daily_ops 已取代 SchedulerService 的 deployed_strategies job，所以這個硬編碼是唯一觸發點。

**判定：** 可以改為從 config 讀，但月頻策略改日期的需求接近零。

---

## LOW（不修）

### O6. ops.py — _fetch_twse_snapshot 未做 schema validation

寫入 data/twse/ 前沒有呼叫 `schemas.validate("price", ...)`。

**判定：** TWSE OpenAPI 格式穩定，下游 quality_gate 會攔截。加 schema 會增加延遲。

### O7. ops_status API — 查詢不需認證

`/ops/status` 回傳 portfolio NAV、positions、cash。如果 API 暴露在公網，是隱私洩漏。

**判定：** 系統設計為 localhost only（config.host="127.0.0.1"）。公網部署時需加 auth，但目前不適用。

---

## 審批記錄

| # | 判定 | 修法 |
|---|------|------|
| O1 | ✅ Fixed | _is_rebalance_day weekly 改為 ISO week |
| O2 | ✅ Fixed | TWSE append 加 logger.debug |
| O3 | ✅ Fixed | get_fills_since 改用 datetime 比較 |
| O4 | Won't Fix | 一天 5 次，開銷可忽略 |
| O5 | Won't Fix | 月頻改日期需求接近零 |
| O6 | Won't Fix | 下游 QG 攔截 |
| O7 | Won't Fix | localhost only |
