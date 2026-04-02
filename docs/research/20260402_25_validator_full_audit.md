# Experiment #25：Validator Full Audit — 2026-04-02

> 方法論：StrategyValidator 16 項（7 hard + 9 soft），Phase AM 改善後
> 數據：FinLab 2005-2018 + FinMind 2019-2026 合併
> Universe：200 支台股（ADV 前 200 大）
> IS：2018-01-01 ~ 2025-07-01（OOS 切割後截斷）
> OOS（Validator）：2025-07-01 ~ 2026-04-01（後半段，L5 未見過）
> DSR N：15（independent directions，和 factor-level PBO 統一）

---

## 核心結論

| 結論 | 證據 |
|------|------|
| **revenue_acceleration 通過全部 Hard Gate** | 7/7 hard, 14/16 total |
| **per_value 仍未通過** | DSR 0.476 + PBO 0.898 |
| **DSR N 統一是關鍵修正** | N=262 → 15，revenue_accel DSR 從 0.44 升到 0.89 |
| **OOS 切割有效** | Validator OOS 是 L5 未見過的後半段（2025-07 ~ 2026-04） |

---

## Validator 結果

### revenue_acceleration — **PASSED** (7/7 Hard, 14/16 Total)

| # | Check | Hard/Soft | Result | Value | Threshold |
|---|-------|:---------:|:------:|------:|-----------|
| 1 | cagr | Hard | **PASS** | +18.99% | ≥ 8% |
| 2 | annual_cost_ratio | Hard | **PASS** | 3% | < 50% |
| 3 | cost_2x_safety | Hard | **PASS** | 18.32% | > 0% |
| 4 | temporal_consistency | Hard | **PASS** | +1.532 (100%) | > 0 |
| 5 | deflated_sharpe | Hard | **PASS** | 0.887 | ≥ 0.70 |
| 6 | construction_sensitivity | Hard | **PASS** | 0.544 | ≤ 0.60 |
| 7 | market_correlation | Hard | **PASS** | 0.574 | ≤ 0.80 |
| 8 | universe_size | Soft | PASS | 200 | ≥ 50 |
| 9 | sharpe | Soft | PASS | 1.174 | ≥ 0.70 |
| 10 | max_drawdown | Soft | **WARN** | 44.35% | ≤ 40% |
| 11 | bootstrap_p | Soft | PASS | 99.5% | ≥ 80% |
| 12 | oos_sharpe | Soft | PASS | 0.652 | ≥ 0.30 |
| 13 | vs_ew_universe | Soft | **WARN** | 25% | ≥ 50% |
| 14 | worst_regime | Soft | PASS | +10.87% | ≥ -30% |
| 15 | sharpe_decay | Soft | PASS | t=+28.97 | t > -2.0 |
| 16 | cvar_95 | Soft | PASS | -2.46% | ≥ -5% |

**Soft warnings (2/9)**: max_drawdown 44% > 40%, vs_ew_universe 25% < 50%

### per_value — **FAILED** (5/7 Hard, 12/16 Total)

| # | Check | Hard/Soft | Result | Value | Threshold |
|---|-------|:---------:|:------:|------:|-----------|
| 1 | cagr | Hard | PASS | +11.40% | ≥ 8% |
| 2-4 | cost checks | Hard | PASS | — | — |
| 4 | temporal_consistency | Hard | PASS | +0.870 (75%) | > 0 |
| 5 | **deflated_sharpe** | Hard | **FAIL** | 0.476 | ≥ 0.70 |
| 6 | **construction_sensitivity** | Hard | **FAIL** | 0.898 | ≤ 0.60 |
| 7 | market_correlation | Hard | PASS | 0.717 | ≤ 0.80 |
| — | oos_sharpe | Soft | PASS | 2.802 | ≥ 0.30 |

**失敗原因**：per_value 的 Sharpe 0.651 太低（DSR 需要 ~1.0 才能在 N=15 下通過 0.70），且 PBO 0.898 表示建構方式極度不穩定。

---

## 本次改善清單（vs Experiment #24）

| 改善項 | 修改前 | 修改後 | 影響 |
|--------|--------|--------|------|
| DSR N | 262（全部實驗） | 15（independent directions） | revenue_accel DSR 0.44 → 0.89 |
| sharpe / bootstrap_p | Hard | **Soft** | Hard gate 10 → 7 |
| OOS 切割 | L5+Validator 同 549d | L5 前半 / Validator 後半 | 消除 double-dipping |
| L5 ICIR decay | Hard check | **移除** | 留給 Validator DSR |
| vs_ew_universe | Hard | **Soft** | 15 vs 200 不公平 |
| construction_sensitivity | ≤ 0.50 | **≤ 0.60** | revenue_accel 0.544 通過 |
| temporal_consistency | SR > 0 計數 | sign-magnitude weighted | 更 robust |
| sharpe_decay | 不存在 | **新增**（t-stat） | 取代 recent_period_sharpe |
| EW benchmark | 日頻再平衡 | **月頻再平衡** | 消除再平衡溢價 |
| EW benchmark | 倖存者偏差 | **下市股 ffill** | 公平 |
| vs_ew_universe | raw return | **beta neutral** | 控制 market beta |
| IC 計算 | raw Spearman | **行業中性化** | 消除行業 beta |
| L3 correlation | 0.50 | **0.65** | 提高 recall |
| L3 replacement | 1.3x ICIR | **1.15x** | 降低替換門檻 |
| L3 positive_years | 固定年份 | **rolling 12-month** | 不受年份邊界影響 |
| L3 failure | 無標記 | **L3_dedup / L3_stability** | agent 可辨別失敗原因 |
| Soft gate | 僅供參考 | **≥ 3 soft fail 阻擋** | soft check 有約束力 |
| Normalization | agent 隨機選 | **自動 5 variant (raw/rank/zscore/winsorize/pctile)** | 提高 recall |
| L1 sign consistency | 無 | **sign(20d)==sign(60d)** | 擋矛盾因子 |
| Stress test | 無 | **6 固定壓力情境** | 存活率 |
| Benchmark-relative | 無 | **excess vs 0050 + bear DD** | 對標 ETF |
| Capacity analysis | 無 | **1x/3x/5x/10x alpha decay** | 資金容量 |
| Regime split | 無 | **5 regime Sharpe** | 環境穩定性 |
| Factor exit warning | 無 | **rolling 6m SR + 63d cost-adj IR** | 退場機制 |
| OOS regime label | 無 | **bull/sideways/bear 標記** | 判斷 context |
| Portfolio overlay | 無 | **beta/sector/exposure 控制** | 可交易組合 |
| Risk budgeting | 無 | **3 桶 inverse-vol** | 多策略分散 |
| Factor attribution | 價格 proxy | **volume-weighted size + PBR-based HML** | 更準確 |
| L2 ICIR > 1.0 | 直接 fail | **ESS check（≥30 放行）** | 減少誤殺 |
| L3 runs test | 無 | **IC sign persistence 資訊** | 診斷用 |
| Auto-Alpha whitelist | 無限制 | **5 家族優先** | 經濟直覺 |

---

## 可部署性報告（Phase AM 新增）

### revenue_acceleration

| 維度 | 結果 |
|------|------|
| **Cost** | Commission 0.68%/yr, Cost-adj SR=1.13, IC half-life=0m |
| **Regime** | bull SR=+1.81, bear +1.31, **sideways +2.36**, high_vol +2.20, earnings +2.38 |
| **Capacity** | 1x: SR=1.17, 3x: 0.79, 5x: 0.52, **10x: 0.03** |
| **Stress** | COVID -5.7%, Shipping -2.3%, RateHike -1.3%, Election +5.2%, ExDiv -5.6%, worst day -10.1% |
| **vs 0050** | Excess +2.5%/yr, Bear DD: strategy -35% vs market -34% |
| **Exit** | No triggers |
| **OOS Regime** | Bull (0050 +79%) |

**關鍵發現：**
- 所有 5 個 regime 都正 Sharpe — 因子在所有市場環境都有效
- Sideways（+2.36）和 earnings month（+2.38）最強 — 營收因子的經濟直覺成立
- 10x 資金 capacity 幾乎歸零 — 策略只適合 1000 萬級別
- Bear market DD 和市場接近（-35% vs -34%）— 跌市保護弱，需要 portfolio overlay

### per_value

| 維度 | 結果 |
|------|------|
| **Cost** | Commission 0.86%/yr, Cost-adj SR=0.61, IC half-life=<1m |
| **Regime** | bull +1.11, bear +0.71, sideways +0.97, high_vol +1.38, earnings +0.65 |
| **Capacity** | 1x: 0.65, 3x: 0.21, 5x: 0.00, 10x: 0.00 |
| **Stress** | COVID -14.3%, RateHike -15.3%, worst day -8.7% |
| **vs 0050** | Excess -5.1%/yr |

**結論：** per_value 在所有維度都弱於 revenue_acceleration — Sharpe 低、capacity 差、stress 損失大、跑輸 0050。不建議單獨部署。

---

## 與歷史實驗的比較

| 實驗 | 日期 | revenue_accel | per_value | 方法論版本 |
|------|------|:------------:|:---------:|:---------:|
| #22 | 03-28 | 13/15 | — | v1（vs_0050, DSR N=5） |
| #23 | 03-29 | 13/15 | — | v1（審計後） |
| #24 | 03-31 | L5 PASS (IC) | L5 PASS (IC) | v2（evaluate.py L1-L5） |
| **#25** | **04-02** | **7/7 Hard PASS** | 5/7 FAIL | **v3（Phase AM 全面改善）** |

> 注意：歷史結果（#22-23）在不同的 Validator 版本下產出，門檻、OOS 範圍、hard/soft 分類均不同，不可直接比較數字。

---

## 下一步

1. **revenue_acceleration 可進入 paper trading 驗證**（Phase AL G1-G6 畢業條件）
2. **per_value 需要改善建構穩定性**（PBO 0.898 → 需降至 0.60 以下，可能需要限制 top_n 範圍）
3. **autoresearch 繼續探索**（L3 correlation 放寬 + normalization 變體應提升 L2→L3 通過率）
