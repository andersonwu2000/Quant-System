# Paper Trading 實際行為審計

**日期**：2026-03-29
**方法**：模擬 paper trading Day 1 的完整流程，追蹤每一步的實際行為
**前提**：.env 設 `QUANT_MODE=paper`, `QUANT_ACTIVE_STRATEGY=revenue_momentum_hedged`, `QUANT_BACKTEST_INITIAL_CASH=10000`

---

## 1. 策略行為驗證

### 1.1 策略鏈

```
config.active_strategy = "revenue_momentum_hedged"
    ↓
RevenueMomentumHedgedStrategy (wrapper)
    ↓ inner = resolve_strategy("revenue_momentum", {max_holdings: 10})
RevenueMomentumStrategy (actual logic)
    ↓ on_bar() → 5 項篩選 → top-10 by acceleration
    ↓
RevenueMomentumHedgedStrategy._detect_regime()
    ↓ ctx.bars("0050.TW") → Exception → return "bull"
    ↓ regime="bull" → weights unchanged (×1.0)
```

### 1.2 已驗證的行為

| 項目 | 預期 | 實際 | 判定 |
|------|------|------|:----:|
| 策略解析 | 成功 | ✅ RevenueMomentumHedgedStrategy | ✅ |
| max_holdings 傳遞 | inner.max_holdings=10 | ✅ 10 | ✅ |
| enable_regime_hedge（inner） | False | ✅ False | ✅ |
| _detect_regime（wrapper） | "bull"（0050 不在 feed） | ✅ "bull" | ⚠️ |
| on_bar 回傳 | 8 支股票，各 10% | ✅ 正確 | ✅ |
| 每支金額 | 1000 TWD | ✅ 正確 | ✅ |

### 1.3 發現的問題

**P-1（HIGH）：revenue_momentum_hedged 的 regime hedge 也是死代碼**

和 revenue_momentum.py 的問題完全相同：0050.TW 不在 feed → `_detect_regime()` 的 `except: return "bull"` → 永遠 bull。

但 **bear_scale=0.0**（不是 0.3），意味著如果真的觸發 bear，策略會**清空所有持倉**（權重歸零）。sideways_scale=0.3。

**影響**：active_strategy 是 `revenue_momentum_hedged` 不是 `revenue_momentum`。所以我們之前修的 `enable_regime_hedge=False` 只關了 inner 的 hedge，**wrapper 的 hedge 還在**（但因為 0050 問題永遠不觸發）。

**如果有人修好 0050 進 feed，bear_scale=0.0 會讓策略在空頭市場完全不持倉 — 這可能是也可能不是想要的行為，但目前未被測試過。**

**P-2（HIGH）：pipeline 跑 0 trades 因為 idempotency**

pipeline 在同月內第二次執行時被 `_has_completed_run_this_month()` 擋掉。如果第一次執行時策略回傳空 weights（例如數據問題），pipeline 記錄 "ok" → 整個月都不會再執行。

**這代表**：如果 3/30 手動觸發時數據有問題（例如 revenue cache 沒載入），pipeline 記錄 "ok" with 0 trades → 4/11 的排程也不會執行（因為 3 月已有 "ok" 記錄）。

等等 — 3/30 和 4/11 是不同月份。月度 idempotency 是 per-month，所以 3 月的 "ok" 不影響 4 月。

但如果 4/11 執行時有問題 → 4 月整個月都不會再試。

**P-3（MEDIUM）：1 萬元零股每支 1000 TWD 的實際可買股數極少**

| 股價 | 1000 TWD 可買 | 實際權重（vs 10% 目標）|
|:----:|:----------:|:---:|
| 600 | 1 股 | 6% |
| 100 | 10 股 | 10% |
| 50 | 20 股 | 10% |
| 800 | 1 股 | 8% |

高價股（如 2330 台積電 ~600 元）只能買 1 股 = 600 元 = 6%，和目標 10% 有 40% 偏差。

**但這是 1 萬元微額實盤的已知限制，不是 bug。**

---

## 2. Pipeline 流程驗證

### 2.1 完整流程追蹤

```
execute_pipeline(config)
  ↓ idempotency check: _has_completed_run_this_month()
  ↓ 如果已跑過 → return "ok" (0 trades)  ← P-2
  ↓
  ↓ resolve_strategy("revenue_momentum_hedged", {"max_holdings": 10})
  ↓ create_feed("yahoo", universe)
  ↓
  ↓ strategy.on_bar(ctx)
  ↓   → inner.on_bar(ctx) → 8 支股票 × 10%
  ↓   → wrapper._detect_regime(ctx) → "bull" → weights unchanged
  ↓
  ↓ weights_to_orders(target_weights, portfolio, prices)
  ↓   → 生成 BUY orders for 8 stocks
  ↓   → zero-stock: qty = floor(target_value / price)
  ↓
  ↓ risk_engine.check_orders(orders, portfolio)
  ↓   → max_position_weight, max_order_notional, etc.
  ↓
  ↓ execute_from_weights(... broker=execution_service ...)
  ↓   → execution_service.execute(approved, current_bars, timestamp)
  ↓   → PaperBroker.submit_order(order) for each
  ↓   → return trades
  ↓
  ↓ apply_trades(portfolio, trades)
  ↓ save_portfolio(portfolio)
  ↓ _write_pipeline_record(status="ok", n_trades=N)
```

### 2.2 已驗證的步驟

| 步驟 | 驗證方式 | 結果 |
|------|---------|:----:|
| 策略解析 | 直接呼叫 | ✅ |
| on_bar 回傳 weights | 直接呼叫 | ✅ 8 支 |
| PaperBroker.submit_order | 單元測試 + 手動 | ✅（LT-1 已修）|
| apply_trades | 單元測試 | ✅（H-04 已修）|
| portfolio 持久化 | 已有（state.py）| ✅ |

### 2.3 未驗證的步驟

| 步驟 | 風險 | 為什麼沒驗證 |
|------|------|------------|
| weights_to_orders 零股 rounding | 高價股可能 qty=0 → 不下單 | 需要跑完整 pipeline 確認 |
| risk_engine 在 10000 元下的行為 | max_position_weight 10% = 1000 元，可能所有訂單都通過 | 需要確認 |
| execution_service.execute 的 current_bars 來源 | paper mode 可能沒有 current_bars | 需要確認 |

---

## 3. 關鍵問題清單

| # | 問題 | 嚴重度 | 阻塞 paper trading？ | 修復 |
|---|------|:------:|:-------------------:|------|
| P-1 | hedged wrapper 的 regime 也是死代碼（0050） | HIGH | 否（永遠 bull = 不影響） | ✅ bear_scale 改 0.0→0.30（防清倉）。0050 死代碼待修 feed 後重新驗證 |
| P-2 | 月度 idempotency 可能擋掉整月 | MEDIUM | 潛在 | ✅ idempotency 改為只擋 n_trades > 0 的 completed，0-trade 不擋 |
| P-3 | 1 萬元高價股只買 1 股 | LOW | 否（已知限制） | 記錄偏差即可 |
| P-4 | hedged 的 bear_scale=0.0（清倉）未被測試 | MEDIUM | 否（0050 死代碼） | ✅ 已改為 0.30（和 inner 一致） |

---

## 4. 開盤第一天的具體操作建議

```bash
# 1. 啟動 API
make dev

# 2. 確認策略和數據正常
curl http://localhost:8000/api/v1/system/health

# 3. 手動觸發 pipeline
curl -X POST http://localhost:8000/api/v1/scheduler/trigger/pipeline \
  -H "X-API-Key: dev-key"

# 4. 確認結果
curl http://localhost:8000/api/v1/portfolio \
  -H "X-API-Key: dev-key"

# 5. 檢查 paper trading 日誌
cat data/paper_trading/pipeline_runs/*.json | tail -1
```

**注意**：3/30 是 4 月前的最後一個交易日。如果 3/30 觸發一次 → idempotency 記錄在 3 月 → 4/11 的排程不受影響（4 月第一次）。
