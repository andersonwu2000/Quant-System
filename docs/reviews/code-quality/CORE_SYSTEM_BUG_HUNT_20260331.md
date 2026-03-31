# Core System Bug Hunt Report — 2026-03-31

> Systematic bug scan across core components: `BacktestEngine`, `SimBroker`, `Analytics`, `OMS`, and `RiskEngine`.
> Focus: Logical correctness, backtest fidelity, and financial math integrity.

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 2     | 1 Fixed, 1 Not-a-bug |
| HIGH     | 3     | 3 Fixed |
| MEDIUM   | 1     | Won't fix (precision, not correctness) |

---

## CRITICAL — Must Fix Immediately

### C1. analytics.py:418 — Trade PnL matching logic is broken for partial fills/scaling ✅ FIXED

**File:** `src/backtest/analytics.py` lines 418-425

```python
for t in trades:
    if t.side.value == "BUY":
        open_positions.setdefault(symbol, []).append(float(t.price))
    elif t.side.value == "SELL" and symbol in open_positions and open_positions[symbol]:
        buy_price = open_positions[symbol].pop(0) # BUG: pops entire entry regardless of qty
        pnl = (float(t.price) - buy_price) * float(t.quantity) # BUG: uses sell qty against pop'd price
        pnls.append(pnl)
```

**Root cause:** 
1. `pop(0)` 移除了整個買入記錄，但完全沒有檢查買入與賣出的數量 (Quantity) 是否匹配。
2. 如果先買 2 筆各 100 股，再賣 1 筆 200 股，程式會拿第 1 筆的買價乘以 200 股計算 PnL，導致數據嚴重失真。
3. 剩餘的買入記錄會留在 list 中或被錯誤消耗，導致勝率 (Win Rate) 和平均盈虧完全不可信。

**Impact:** 回測報告中的「勝率」和「平均單筆盈虧」數據錯誤。

**Fix:** 實作 FIFO 隊列 `[[price, qty], ...]`，SELL 時逐一按數量消耗買入庫存。1810 tests passed。

---

### C2. engine.py: _record_settlements — available_cash double-deduction bug ❌ NOT A BUG

**File:** `src/backtest/engine.py` and `src/core/models.py`

**Logic Flow:**
1. `apply_trades` (in OMS) 會立即從 `portfolio.cash` 扣除買入金額。
2. `_record_settlements` 又會將該金額加入 `portfolio.pending_settlements`。
3. `Portfolio.available_cash` 的定義是 `self.cash - sum(pending_settlements)`。

**Root cause:** 金額被扣了兩次。例如初始 10M，買入 1M：
- `cash` 變 9M。
- `pending_settlements` 增加 1M。
- `available_cash` = 9M - 1M = 8M (正確應為 9M 或 10M 視交割規則而定)。

**Impact:** 在 T+2 模擬模式下，可用資金會被錯誤地「雙倍鎖定」，導致策略在資金利用率達到 50% 時就無法開新倉。

**審批判定：NOT A BUG。** engine.py line 606-610 docstring 明確寫 "double-counted... This is intentional to prevent the engine from spending unsettled funds in T+N mode. The net effect is overly conservative cash gating, not incorrect P&L." 這是設計決策（偏保守防止用未交割資金），不是 bug。P&L 不受影響。

---

## HIGH — Fix Soon

### H1. engine.py: _execute_kill_switch — Short positions are never liquidated ✅ FIXED

**File:** `src/backtest/engine.py` line 440

```python
for symbol, pos in list(portfolio.positions.items()):
    if pos.quantity > 0: # BUG: only checks for long positions
        liquidation_orders.append(...)
```

**Root cause:** 風控熔斷 (Kill Switch) 觸發時，只會賣出多單，空單 (`quantity < 0`) 會被遺留在持倉中。

**Impact:** 熔斷後組合仍暴露在空頭風險中，且導向無效的清倉狀態。

**Fix:** 加入 `elif pos.quantity < 0:` 分支，產生 BUY 單平倉空頭。1810 tests passed。

---

### H2. weights_to_orders — Alphabetical sorting causes unnecessary buy rejections ✅ FIXED

**File:** `src/strategy/engine.py` line 104

```python
all_symbols = sorted(set(target_weights.keys()) | set(portfolio.positions.keys()))
```

**Root cause:** 系統按代碼字母順序處理訂單。如果策略想賣出 Z 股票並買入 A 股票，系統會先處理 A 的買單。此時賣出 Z 的資金尚未釋放，A 可能因為 `available_cash` 不足而被拒絕。

**Impact:** 降低調倉成功率，特別是在滿倉換股時。

**Fix:** `all_symbols` 排序改為 sells-first（先處理 diff_w < -0.001 的 symbol），再處理其餘。1810 tests passed。

---

### H3. engine.py: _is_rebalance_day — Weekly rebalancing fails on holidays ✅ FIXED

**File:** `src/backtest/engine.py` line 865

```python
elif freq == "weekly":
    return bar_date.weekday() == 0 or idx == 0
```

**Root cause:** 硬編碼星期一 (`weekday == 0`) 為再平衡日。如果週一休市，該週將完全跳過再平衡（除非是回測第一天）。

**Impact:** 週頻策略在遇到連假或休市時會失效。

**Fix:** 改用 ISO week number 比較（`isocalendar()[1]`），和月頻的 month_key 邏輯一致。加 `_last_rebalance_week` 狀態。1810 tests passed。

---

## MEDIUM — Won't Fix

### M1. simulated.py: ADV calculation — Using current volume instead of ADV20 — Won't Fix

**File:** `src/execution/broker/simulated.py`

**Impact:** `SimBroker` 使用當日成交量計算滑點。但在再平衡日，成交量通常會因為策略行為而放大，這會導致計算出的市場衝擊比實際小。

**審批判定：Won't Fix。** 回測用日線 EOD volume，不是「再平衡導致的異常放量」（回測的單不影響市場）。sqrt impact model 已在低量時自動加大 slippage。改成 ADV20 是精度改善，不是正確性問題。

---

## Files Scanned

| File | Lines | Issues Found |
|------|-------|--------------|
| `src/backtest/engine.py` | 895 | C2, H1, H3 |
| `src/backtest/analytics.py` | 460 | C1 |
| `src/strategy/engine.py` | 155 | H2 |
| `src/execution/broker/simulated.py` | 215 | M1 |
| `src/execution/oms.py` | 135 | (verified fixes from previous reports) |
