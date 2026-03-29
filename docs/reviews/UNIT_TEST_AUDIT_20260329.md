# 單元測試品質審計

**日期**：2026-03-29
**範圍**：7 個最關鍵的測試檔案（154 個測試），覆蓋 Validator、analytics、OMS、sinopac、risk、research、PBO
**方法**：逐檔檢查斷言品質、邊界情況、regression test 覆蓋、mock 合理性

---

## 結論

**1766 個測試、99.3% 通過率 — 但會放過 60+ 個歷史 bug 中的 35+ 個。**

測試套件的結構好（按模組組織、使用 fixture），但斷言太弱 — 很多只檢查「不是 None」或「是正確的型別」，不檢查實際值。已知的 60+ 個 bug 中只有約 40% 有對應的 regression test。

**這比沒有測試更危險**：通過的測試套件給出「一切正常」的假信心，但實際上關鍵路徑（完整 Validator pipeline、累積風控、look-ahead bias、PBO 方法論）根本沒被測到。

---

## 按嚴重度排序的問題

### CRITICAL（5 個）— 已知 bug 會復活但測試抓不到

**C-1：Validator 完整 pipeline 從未被測試**

`test_strategy_validator.py` 有 22 個測試，但**沒有任何一個呼叫 `validator.validate(result)`**。測試只驗證 config 存在、check 名稱正確、Bootstrap 分佈合理。但整條 16 項驗證的端到端流程 — 從 BacktestResult 進去到 ValidationReport 出來 — 從未被執行。

如果有人改了 Validator 的 check 順序、門檻、或 fail-closed 邏輯，測試不會 fail。

**C-2：Look-ahead bias（40 天營收延遲）沒有 regression test**

BUG #10-12 是歷史上最嚴重的 bug 之一（IC 膨脹 72%）。但測試套件中**沒有任何測試驗證 40 天延遲存在**。如果有人刪掉 `as_of - DateOffset(days=40)`，所有測試照過。

**C-3：PBO 方法論無法區分正確和錯誤的實作**

BUG #53-55：PBO 實作錯了 3 次（noise perturbation → wrong N → vectorized wrong）。`test_pbo.py` 只檢查 PBO ∈ [0,1] 和 n_combinations 公式。**如果把 CSCV 換回 noise perturbation，測試照過。**

缺少的測試：
- 全相同策略 → PBO ≈ 1.0（構建過擬合是確定的）
- 純隨機策略 → PBO ≈ 0.5（null distribution）
- 完美單調策略 → PBO ≈ 0.0

**C-4：風控累積效應未測試**

BUG #15：「10 筆各 9% 的訂單合計 90% 但逐筆檢查都通過」。`test_risk.py` 只測試單筆訂單的 max_position_weight。**如果 check_orders 不累積計算，測試照過。** 12 個風控相關的歷史 bug 中只有 3 個基本規則被測試。

**C-5：Sinopac 零股分流完全未測試**

BUG C-01~C-03（零股 sub-order 丟失、overfill、單位不一致）是實盤交易路徑的 CRITICAL bug。`test_sinopac_broker.py` 有 31 個測試但**沒有任何一個測試 `_shares_to_lots()` 的行為**。整股張數 vs 股數的轉換、零股交易時段檢查、多 sub-order 的 _order_map 註冊 — 全部未測。

---

### HIGH（4 個）— 邊界情況會導致靜默錯誤

**H-1：OMS apply_trades 沒有驗證「不產生負持倉」**

BUG #52 的修復測試只檢查 sell qty 被 cap 到 position qty。但沒有 invariant 測試：`assert all(pos.quantity >= 0 for pos in portfolio.positions.values())`。如果 cap 邏輯被改壞，測試只抓 cap 行為，不抓後果。

**H-2：DSR 沒有驗證底層 Sharpe 計算正確**

`test_deflated_sharpe.py` 測試 DSR 的行為（N 增加 → DSR 降低），但不驗證 DSR 的輸入 Sharpe 是否正確。如果 analytics.py 的 Sharpe 公式改壞（BUG #1：幾何/算術混用），DSR 測試照過。

**H-3：Forward return off-by-one 無 regression test**

BUG #7：`after[h-1]` vs `after[h]`。`test_research.py` 測試 `compute_forward_returns` 回傳正確形狀，但不驗證具體的 horizon 是否精確對齊。

**H-4：Sinopac `_trades` dict 寫入路徑被 mock 覆蓋**

`test_sinopac_broker.py` 直接設 `broker._trades["ORD001"] = trade` 然後測試 cancel。但 `submit_order` 是否真的寫入 `_trades` 從未被測試（mock 了 `place_order` 的回傳值但沒驗證副作用）。

---

### MEDIUM（5 個）

| # | 問題 | 檔案 |
|---|------|------|
| M-1 | 多數斷言只查 `is not None` 或 `isinstance`（7 處） | 多個 |
| M-2 | NaN/inf 輸入的邊界情況幾乎全缺（24+ 處） | 多個 |
| M-3 | Bootstrap 只用 500 次（論文要求 1000+） | test_strategy_validator.py |
| M-4 | Fill callback 測試只查 status，不查 filled_avg_price | test_sinopac_broker.py |
| M-5 | IC perfect correlation 測試 FAIL（test_formula_invariants.py） | test_formula_invariants.py |

---

## 最需要補的 5 個測試（按 ROI 排序）

### 1. Validator 端到端 pipeline test

```python
def test_validate_produces_complete_report():
    """Call validate() on real BacktestResult, verify all 16 checks executed."""
    result = _make_realistic_backtest_result()  # 需要構造合理的 BacktestResult
    validator = StrategyValidator(config)
    report = validator.validate(result)
    assert len(report.checks) == 16
    for check in report.checks:
        assert check.name in EXPECTED_CHECK_NAMES
        assert isinstance(check.passed, bool)
        assert check.value is not None  # 每項都有值，不是 None
```

**防護**：抓 check 順序改變、門檻漏設、fail-closed 被破壞。

### 2. Look-ahead bias regression test

```python
def test_revenue_has_40_day_delay():
    """Revenue data must not include last 40 days — BUG #10 regression."""
    from src.strategy.base import Context
    ctx = Context(feed=mock_feed, portfolio=mock_portfolio)
    ctx._now = pd.Timestamp("2024-03-15")
    revenue = ctx.get_revenue("2330.TW")
    if not revenue.empty:
        assert revenue["date"].max() <= pd.Timestamp("2024-02-03")  # 40 天前
```

**防護**：如果 40 天延遲被刪除，這個測試立刻 fail。

### 3. PBO 方法論驗證

```python
def test_identical_strategies_pbo_near_one():
    """All-identical strategies → PBO ≈ 1.0 (overfitting is certain)."""
    returns = pd.DataFrame(np.random.randn(500, 10))
    # 所有 column 都是同一個 series（copy）
    for col in returns.columns:
        returns[col] = returns[0]
    result = compute_pbo(returns, n_partitions=8)
    assert result.pbo > 0.8  # 應接近 1.0

def test_random_strategies_pbo_near_half():
    """Independent random strategies → PBO ≈ 0.5."""
    rng = np.random.default_rng(42)
    returns = pd.DataFrame(rng.standard_normal((500, 20)))
    result = compute_pbo(returns, n_partitions=8)
    assert 0.2 < result.pbo < 0.8  # 應在 0.5 附近
```

**防護**：如果 PBO 被換成 noise perturbation 或其他錯誤方法，這兩個測試會 fail。

### 4. 風控累積效應

```python
def test_cumulative_position_weight_rejected():
    """10 orders × 9% each = 90% total should be rejected — BUG #15."""
    portfolio = make_portfolio(nav=1_000_000)
    orders = [make_buy_order(notional=90_000) for _ in range(10)]  # 每個 9%
    decisions = risk_engine.check_orders(orders, portfolio)
    total_approved_weight = sum(o.notional / 1_000_000 for o, d in zip(orders, decisions) if d.approved)
    assert total_approved_weight <= 0.30  # 不該超過 30%
```

**防護**：抓「逐筆通過但合計超標」的 bug。

### 5. Sinopac 零股分流

```python
def test_shares_to_lots_splits_correctly():
    """1500 shares → 1 lot (1000) + 500 odd shares."""
    broker = SinopacBroker(SinopacConfig(simulation=True))
    parts = broker._shares_to_lots(Decimal("1500"), "2330.TW")
    assert len(parts) == 2
    assert parts[0] == (1, False)    # 1 lot, not odd
    assert parts[1] == (500, True)   # 500 shares, odd

def test_submit_registers_all_suborders():
    """Both lot + odd sub-orders must be in _order_map — BUG C-01."""
    broker = SinopacBroker(SinopacConfig(simulation=True))
    # ... setup mock
    order = make_order(quantity=1500)
    broker.submit_order(order)
    assert len(broker._order_map) >= 2  # 兩個 sub-order 都要註冊
```

**防護**：抓零股 sub-order 丟失（C-01）和單位不一致（C-03）。

---

## 統計

| 指標 | 數值 |
|------|:----:|
| 審計的測試檔案 | 7 |
| 審計的測試數量 | 154 |
| CRITICAL 問題 | 5 |
| HIGH 問題 | 4 |
| MEDIUM 問題 | 5 |
| 歷史 bug 有 regression test | ~25/60+（~40%） |
| 歷史 bug 無 regression test | ~35/60+（~60%） |
| 建議新增的測試 | 5 個（最高 ROI） |

---

## 建議

**不需要追求 100% coverage。** 1766 個測試已經很多了。問題不在數量，在品質。

**最高優先**：補上面列的 5 個 regression test。這 5 個測試能抓住 60+ 歷史 bug 中約 50% 的復發。工作量約 2 小時。

**次優先**：把現有測試中的 `assert result is not None` 改為檢查實際值。逐檔做，每次花 30 分鐘。

**不要做**：不要追加更多 happy path 測試。系統不缺「功能能跑」的驗證，缺的是「功能壞了能抓到」的驗證。
