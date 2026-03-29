# 因子篩選與部署機制深度檢討

**日期**：2026-03-29
**前提**：BACKTEST_MECHANISM_AUDIT_20260329.md 的代碼 bug 已大量修復（14 個 CRITICAL/HIGH 中 14 個已修）。本報告聚焦修復後仍存在的**結構性方法論問題**。

---

## 1. 核心問題：Holdout 已被 233 次 Adaptive Query 降解

### 定量分析

| 指標 | 值 | 來源 |
|------|-----|------|
| OOS 天數 (n) | 375 | rolling 1.5 年 |
| Adaptive queries (k) | 233 | autoresearch 實驗數 |
| 每次回饋 | 1 bit (L5 pass/fail) | evaluate.py 設計 |
| k/n ratio | 0.62 | 接近 1.0 危險線 |
| Information leakage (worst case) | I(T;Φ) ≤ 233 bits | Russo & Zou (2016) |
| Overfitting bias bound | ≤ 1.1 × σ(daily) ≈ 17.5% annualized | Russo & Zou 公式 |
| Thresholdout safe budget (τ=10%) | ~4 次 | Dwork et al. (2015) |
| Ladder accuracy degradation | ~31% | Blum & Hardt (2015) |
| E[max SR] from noise (233 trials) | ~2.8 annualized | Bailey & Lopez de Prado (2014) |

### 解讀

**Dwork et al. (2015)**：Thresholdout 的安全 budget 公式 `B = τ² × n`。τ=10% 容忍誤差 → B = 0.01 × 375 = **3.75 次**。我們用了 233 次，超出 62 倍。

**Russo & Zou (2016)**：overfitting bias ≤ σ × √(2I/n)。最壞情況 I = 233 bits → bias ≤ σ × √(1.24) ≈ 1.1σ。日報酬 σ ≈ 1% → bias ≈ 1.1%/天 ≈ **17.5%/年**。這意味著一個真實年化報酬 0% 的策略，在 233 次 adaptive query 後可以看起來有 17.5% 年化報酬。

**Bailey (2014)**：233 次獨立試驗下，純噪音策略的 E[max Sharpe] ≈ **2.8**。我們觀測到的最佳策略 Sharpe 0.94 遠低於此，這是好消息 — 說明因子可能有真實 alpha，不只是噪音最大值。

**但**：我們的 233 次試驗不是獨立的（大量微調變體），實際獨立試驗 ~15 個方向。E[max SR] 降到 ~1.4（N=15）。Sharpe 0.94 > 1.4？不，0.94 < 1.4 — 這意味著即使只算 15 個獨立方向，觀測到的 Sharpe 仍然**低於**純噪音的期望最大值。

**這是一個嚴肅的警訊**：我們的最佳策略 Sharpe (0.94) 不顯著高於 N=15 的噪音期望值 (1.4)。

### 緩解因素

1. **大部分 233 次是 fail** — 如果只有 ~30 次通過 L4，實際 entropy ≈ 30 × log₂(233/30) ≈ 90 bits，低於 233 bits
2. **OOS 洩漏已封堵** — pending marker stripped、OOS 日期隱藏、L5 failure 統一、factor_returns 移到 watchdog_data。Agent 現在只看到 1 bit
3. **DSR(N=15) 提供了 parametric 修正** — 即使 holdout 退化，DSR 仍然從不同角度校正 multiple testing

---

## 2. 16 項 Validator Check 的實際防護力

### 按獨立性分類

**獨立維度 A：Full backtest（同一條 equity curve 的衍生）**
- #2 CAGR、#3 Sharpe、#4 MDD、#5 Cost ratio、#15 CVaR — 全部從同一個 BacktestResult 衍生
- 一條 overfit 的 equity curve 可以同時通過這 5 項
- **防護力**：不防過擬合，只防「策略基本面太差」

**獨立維度 B：時序穩定性**
- #6 Temporal consistency（逐年正率）、#13 Recent Sharpe（最近 252 天）
- 和維度 A 部分獨立（看不同時間切片）
- #13 的 SE=1.0（拋硬幣水準），統計功效極低
- **防護力**：弱。防「策略只在某一年好」但不防過擬合

**獨立維度 C：統計修正**
- #7 DSR(N=15)、#8 Stationary Bootstrap
- 真正測 multiple testing 和統計顯著性
- **防護力**：中等。DSR 是最有力的單一 check，但 N=15 是手動估計

**獨立維度 D：OOS 驗證**
- #9 OOS Sharpe（rolling 1.5 年）
- SE=0.82，幾乎無統計功效
- 233 次 adaptive query 已嚴重降解 holdout
- **防護力**：很弱。是 sanity check 不是統計檢定

**獨立維度 E：結構性驗證**
- #10 vs EW benchmark、#11 Construction sensitivity、#14 Market correlation、#16 Permutation test
- 各自測不同面向（選股能力、組合穩定性、市場獨立性、信號真實性）
- **防護力**：Permutation test 是最有價值的新增（直接測信號是否隨機）

### 真正有效的 check

| Check | 測什麼 | 防什麼 | 有效性 |
|-------|--------|--------|:------:|
| #7 DSR(N=15) | 多重測試後 Sharpe 是否顯著 | data mining | ✅ 有效 |
| #8 Stationary Bootstrap | P(Sharpe > 0) 含自相關 | 假陽性 | ✅ 有效 |
| #11 Construction sensitivity | PBO（portfolio variants 穩定性） | portfolio 過擬合 | ✅ 有效 |
| #16 Permutation test | 信號打亂後 Sharpe 是否下降 | 偽信號 | ✅ 有效 |
| #14 Market correlation | 和大盤相關性 < 0.80 | 純 beta 搬運 | ✅ 有效 |
| #10 vs EW benchmark | 超額報酬 > 0% | size premium 而非 alpha | ✅ 有效 |
| #6 Temporal consistency | 60%+ 年份正 Sharpe | 時序不穩定 | ⚠️ 弱 |

**5 個 check 本質上是 sanity check（排除明顯差的策略，不防過擬合）**：
- #2 CAGR、#3 Sharpe、#4 MDD、#9 OOS Sharpe、#13 Recent Sharpe

**2 個是描述性指標（風險度量，非假設檢定）**：
- #1 Universe size、#15 CVaR

**1 個是成本度量**：
- #5 Cost ratio

---

## 3. 部署條件的真實含義

### 硬門檻（全部必須通過）

```
#2 CAGR >= 8%           — sanity check
#3 Sharpe >= 0.7        — sanity check
#5 Cost < 50%           — 成本度量
#6 Temporal >= 60%      — 弱穩定性
#7 DSR >= 0.70          — ✅ 真正的統計檢定
#8 Bootstrap >= 80%     — ✅ 真正的統計檢定
#10 vs EW >= 0%         — ✅ 選股能力
#11 PBO <= 0.50         — ✅ 組合穩定性
#14 Corr <= 0.80        — ✅ 市場獨立性
#16 Permutation < 0.10  — ✅ 信號真實性
```

10 個硬門檻中，6 個是真正有效的統計/結構檢定（#7 #8 #10 #11 #14 #16），4 個是 sanity check（#2 #3 #5 #6）。

**這代表**：如果一個策略通過所有硬門檻，我們可以有中等信心（非高信心）認為它不是純噪音。特別是 Permutation test + DSR + PBO 三者聯合提供了多重測試修正、信號真實性、組合穩定性三個獨立維度的驗證。

### 但仍然不夠

1. **DSR 的 N=15 可能不準** — 如果實際獨立方向只有 8 個，DSR 偏嚴（可能 kill 合法因子）。如果有 25 個，DSR 偏鬆（可能放過假陽性）
2. **Permutation test 在 100 次 shuffle 下的功效** — p < 0.10 的最小可解析度是 1/100 = 0.01。100 次可能不夠區分 p=0.08 和 p=0.12
3. **OOS holdout 已退化** — 233 次 query 後，OOS 的 information ratio I/n = 0.62，接近失效
4. **所有 check 共用同一段歷史數據** — 即使 16 項都通過，也可能是在這特定的 7 年台股行情中恰好有效

---

## 4. 和業界標準的比較

| 項目 | 我們 | 業界最佳實務 | 差距 |
|------|------|-------------|------|
| Multiple testing correction | DSR(N=15) | DSR(N=actual) + Bonferroni/BHY | N 是手動的 |
| OOS validation | Rolling 1.5 年，233 次 query | Fresh holdout（從未被 query 過） | Holdout 已退化 |
| OOS 保護機制 | Pass/fail only（洩漏已堵） | Thresholdout（加噪音的回饋） | 沒有 Thresholdout |
| 信號真實性 | Permutation test (100 shuffles) | Permutation (1000+) + cross-asset | 只有台股單一市場 |
| Paper trading | 基礎設施就緒，尚未有 3+ 月數據 | ≥ 6 月 paper + 6 月 small-size live | 還沒開始收集數據 |
| 跨市場驗證 | 無 | 至少 2-3 個市場（US/Japan/Korea） | 完全缺失 |
| 回測次數追蹤 | 手動（n_trials=15） | 自動計入所有試驗（含失敗的） | 部分自動（watchdog n_independent） |

---

## 5. 結論

### 做對了的

1. **OOS 洩漏已全部封堵** — 14 個 CRITICAL/HIGH bug 全修
2. **Stationary Bootstrap** 取代 IID — 正確保留自相關
3. **Permutation test** 是真正有價值的新增 — 直接測信號內容
4. **DSR(N=15)** 比原來的 N=1（完全不修正）好很多
5. **硬/軟門檻** 取代「允許任意 1 項 fail」
6. **等權 benchmark** 取代 0050 — 測選股 alpha 而非 size premium
7. **Factor-Level PBO** 開始追蹤因子選擇的過擬合（watchdog）

### 結構性限制（不可修正）

1. **Holdout 已被 233 次 adaptive query 降解** — I/n = 0.62，Thresholdout budget 超出 62 倍。唯一解法是 fresh data（paper trading）
2. **OOS 1.5 年的統計功效不足** — SE=0.82，任何門檻都沒有檢定力。不可修正（除非有更多年的未來數據）
3. **所有 check 共用同一段歷史** — 7 年台股行情不代表未來。跨市場驗證缺失
4. **E[max SR] from noise > observed SR** — N=15 的噪音期望 Sharpe ~1.4 > 觀測 0.94。無法排除是噪音

### 下一步

**不要再跑更多回測。** 每次實驗都在消耗 holdout。

1. **Paper Trading** — revenue_momentum_hedged 和 vwap_position_63d 上 paper，累積 3+ 月真實報酬
2. **Thresholdout** — 未來的 autoresearch 實驗改用 noisy feedback（加噪音到 L5 的 pass/fail），減緩 holdout 降解
3. **Fresh holdout** — 等 2026Q2 結束後，用 2026Q1-Q2 作為全新的、從未被 query 過的 OOS 期間
4. **接受不確定性** — 回測能排除明顯無效的策略，但不能證明策略有 alpha。只有未來的真實市場能證明

---

## 參考文獻

- Blum, A. & Hardt, M. (2015). The Ladder: A Reliable Leaderboard for Machine Learning Competitions. ICML.
- Dwork, C. et al. (2015). The reusable holdout: Preserving validity in adaptive data analysis. Science.
- Russo, D. & Zou, J. (2016). How much does your data exploration overfit? arXiv:1511.05219.
- Steinke, T. & Ullman, J. (2015). Interactive Fingerprinting Codes. arXiv:1410.1228.
- Bailey, D. & Lopez de Prado, M. (2014). The Deflated Sharpe Ratio. SSRN.
- Bailey, D. et al. (2014). Probability of Backtest Overfitting. SSRN.
- Harvey, C., Liu, Y. & Zhu, H. (2016). ...and the Cross-Section of Expected Returns. RFS.
- Lo, A. (2002). The Statistics of Sharpe Ratios. FAJ.
- Politis, D. & Romano, J. (1994). The Stationary Bootstrap. JASA.
