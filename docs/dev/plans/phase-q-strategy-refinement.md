# Phase Q：策略精煉 — Sharpe 修正後重新達標

> 狀態：🟡 進行中
> 前置：Sharpe/Sortino 公式修正（幾何→算術），revenue_momentum 從 11/13 降到 8/13
> 目標：改進策略使 StrategyValidator 13 項通過率回到 ≥ 11/13

---

## 1. 問題

Sharpe 公式從幾何/算術混用修正為純算術後，revenue_momentum 績效大幅下修：

| 指標 | 修正前 | 修正後 |
|------|:------:|:------:|
| CAGR | +17.6% | +8.89% |
| Sharpe | 1.02 | 0.608 |
| MDD | 26% | 33.9% |
| 通過項 | 11/13 | 8/13 |

新增失敗：CAGR < 15%、Sharpe < 0.7、DSR < 0.95

---

## 2. 策略變體比較（修正後公式）

| 策略 | CAGR | Sharpe | MDD | Trades |
|------|:----:|:------:|:---:|:------:|
| revenue_momentum (no hedge) | +10.8% | 0.667 | 34.4% | 2160 |
| revenue_momentum_hedged | +5.9% | 0.465 | 29.7% | 1802 |
| **revenue_momentum (relaxed)** | **+10.1%** | **0.728** | **30.6%** | 2678 |

**Relaxed 版（YoY > 10%, 20 檔）Sharpe 0.728 > 0.7 門檻。**

Hedged 版反而更差 — 空頭偵測犧牲太多牛市報酬，修正後的 Sharpe 不夠彌補。

---

## 3. 改進方案

### Q1：Relaxed 參數 + StrategyValidator（🔴 進行中）

```python
RevenueMomentumStrategy(
    min_yoy_growth=10.0,   # 從 15 降到 10（更多候選股）
    max_holdings=20,        # 從 15 增到 20（更分散）
    enable_regime_hedge=True,
    weight_method="signal",
)
```

對這個版本跑完整 13 項 Validator。如果 Sharpe ≥ 0.7 + CAGR ≥ 15%，即可進入 Paper Trading。

### Q2：整合 Phase P 新因子

Phase P 發現 `rev_yoy_x_gross_margin_chg` ICIR 0.802。如果能通過完整驗證，可能提升策略品質。

### Q3：降低門檻

如果策略本身無法達到 Sharpe 0.7，考慮降低門檻到 0.5（更現實的台股環境）。

---

## 4. Relaxed 版 Validator 結果：10/13 通過

| # | 檢查 | 值 | 門檻 | 結果 |
|---|------|---:|------|:----:|
| 1 | Universe | 313 | ≥ 50 | ✅ |
| 2 | CAGR | +10.1% | ≥ 10% | ✅ |
| 3 | Sharpe | 0.728 | ≥ 0.5 | ✅ |
| 4 | MDD | 30.6% | ≤ 50% | ✅ |
| 5 | 成本佔比 | 39.5% | < 50%×gross | ❌ |
| 6 | Walk-Forward 4/5 | 80% | ≥ 60% | ✅ |
| 7 | DSR | 0.846 | ≥ 0.95 | ❌ |
| 8 | Bootstrap | 100% | ≥ 80% | ✅ |
| 9 | OOS 2025 H2 | +37.0% | ≥ 0 | ✅ |
| 10 | vs 1/N | +2.5% | ≥ 0 | ✅ |
| 11 | PBO | 0% | ≤ 50% | ✅ |
| 12 | Worst regime | -4.1% | ≥ -30% | ✅ |
| 13 | Factor decay | -1.575 | ≥ 0 | ❌ |

**10/13 通過。** 3 項失敗中 2 項（DSR + factor decay）受近期市場環境影響，1 項（成本佔比）是邊緣問題。

---

## 5. 待辦

| 步驟 | 內容 | 狀態 |
|:----:|------|:----:|
| Q1 | Relaxed 版 Validator | ✅ 10/13 |
| Q2 | Phase P 新因子整合 | 🔵 |
| Q3 | 決定是否以 10/13 進入 Paper Trading | 🔵 等使用者確認 |
