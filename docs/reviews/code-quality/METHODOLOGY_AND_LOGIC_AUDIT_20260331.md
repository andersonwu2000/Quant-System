# Core System Methodology & Logic Audit Report — 2026-03-31

> Rigorous audit of quantitative methodologies, financial calculations, and behavioral logic.
> Focus: Systematic biases, formulaic errors, and architectural inconsistencies.

---

## 1. Methodological Flaws

### M1. Turnover Calculation Overstatement (High Severity) ✅ FIXED
- **Current Formula:** `total_traded / nav / n_days * 252`
- **Error:** This formula counts both sides of a round-trip trade separately without averaging.
- **Impact:** Reported annual turnover is ~2x the industry standard. Validator 的 `max_annual_turnover: 0.80` 門檻在雙邊定義下實際只允許單邊 0.40，過度懲罰正常策略。
- **Fix (2026-03-31):** 改為 `min(buy_value, sell_value) / nav / n_years`（單邊 turnover，業界標準定義）。

### M2. All-or-Nothing Risk Gating (Medium Severity) ✅ FIXED
- **Finding:** `max_position_weight` returned `REJECT` when threshold breached by any margin.
- **Error:** A strategy wanting 5.1% weight with a 5.0% limit ended up with 0% weight.
- **Fix (2026-03-31):** `max_position_weight` 改用 `RiskDecision.MODIFY(max_allowed_qty)` — 超額時 cap 到限制值而非整單拒絕。`RiskEngine` 已支援 MODIFY（line 72-89）。

### M3. Rebalance Quantity Drift (Medium Severity)
- **Finding:** Order quantities are calculated using $T$ prices, but executed at $T+1$.
- **Error:** Ignores the $T \to T+1$ overnight gap.
- **Impact:** If a stock gaps up 5% at open, a "precise" order for 10% weight will result in 10.5% weight, potentially triggering post-trade risk alerts or margin calls.
- **Correction:** Introduce a 1-2% "soft buffer" in risk rules for backtest-to-live parity.

---

## 2. Calculation & Formulaic Errors

### C1. Available Cash Double-Counting (Critical)
- **Formula:** `available_cash = cash - sum(pending_settlements)`
- **Logic Error:** `apply_trades` already subtracts the full trade amount from `cash` on $T+0$. Then `_record_settlements` locks the same amount again in `pending_settlements` until $T+2$.
- **Impact:** During the 2-day settlement window, the same money is deducted twice. A portfolio at 50% utilization will be reported as having 0% available cash, preventing the system from reaching full exposure.

### C2. Sharpe Ratio Arithmetic vs. Geometric Mean
- **Finding:** `analytics.py` uses `daily_returns.mean() / daily_returns.std() * sqrt(252)`.
- **Methodological Note:** While standard (Sharpe 1994), it is sensitive to the sampling frequency. For strategies with high kurtosis (fat tails), the arithmetic mean can be deceptive compared to the geometric mean (CAGR-based Sharpe).
- **Recommendation:** Add a `geometric_sharpe` or `adj_sharpe` to the analytics report.

---

## 3. Behavioral & Edge-Case Bugs

### B1. Kill Switch "Selective Memory"
- **Finding:** `BacktestEngine._execute_kill_switch` only iterates through `pos.quantity > 0`.
- **Impact:** Short positions are ignored during a liquidation event. The portfolio remains exposed to short-side risk during a "emergency stop."
- **Correction:** Change to `if pos.quantity != 0`.

### B2. Order Execution Path Dependency
- **Finding:** `weights_to_orders` processes symbols in alphabetical order.
- **Impact:** In a 100% invested portfolio, a trade to sell "Z" and buy "A" will attempt to buy "A" first. This fails due to insufficient cash, then "Z" is sold. The portfolio ends up 50% cash.
- **Correction:** Explicitly sort orders: **SELLs first, then BUYs**.

### B3. Weekly Rebalance Holiday Bias
- **Finding:** `is_rebalance_day` for `weekly` checks `weekday == 0`.
- **Impact:** If Monday is a holiday, the entire week's rebalance is skipped.
- **Correction:** Check for `iso_week` change between bars.

---

## 4. Final Assessment

The system's **architecture is solid**. B1/B2/B3 were real bugs and have been fixed in the BUG_HUNT round.

**Immediate Action Items:**
1. ~~Fix **C1** (Cash counting)~~ — Not a bug. Intentional conservative design (see engine.py:606-610 docstring).
2. ~~Fix **B2** (Sell-before-buy)~~ — ✅ Fixed 2026-03-31. `weights_to_orders` now sorts sells-first.
3. ~~Fix **M1** (Turnover formula)~~ — Not a bug. Double-sided turnover is a valid definition choice; all strategies use the same formula so rankings are unaffected.

---

## 5. 審批記錄 (2026-03-31)

| # | 判定 | 理由 |
|---|------|------|
| M1 | ✅ 已修 | 改為單邊 turnover `min(buy, sell) / nav / n_years`。Validator 門檻 0.80 在雙邊定義下過嚴 |
| M2 | ✅ 已修 | `max_position_weight` 改用 `MODIFY(cap_qty)` 取代 `REJECT` |
| M3 | Won't fix | 隔夜 gap ~5% 造成 weight drift ~0.5%，月頻策略噪音範圍內 |
| C1 | ❌ 不成立 | 同 BUG_HUNT C2。engine.py:606-610 明確 intentional |
| C2 | Won't fix | arithmetic Sharpe 是 Sharpe 1994 標準定義，geometric 是延伸非修正 |
| B1 | ✅ 已修 | 同 BUG_HUNT H1。Kill switch 加了空頭平倉 |
| B2 | ✅ 已修 | 同 BUG_HUNT H2。sells-first 排序 |
| B3 | ✅ 已修 | 同 BUG_HUNT H3。ISO week number 比較 |
