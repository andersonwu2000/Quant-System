# 實驗報告 #18：基準因子重跑（全 bug 修正後）

> 日期：2026-03-27
> Universe：865 支台股（min 500 bars）
> 期間：2017-01 ~ 2025-12（106 個月度取樣點）
> 方法論：完全遵循 `docs/claude/EXPERIMENT_STANDARDS.md`
> 耗時：172 秒

---

## 1. 方法論聲明

本次實驗為 4 輪代碼審計（40+ bug 修正）後的基準重跑。與先前實驗 #16/#17 的差異：

| 項目 | #16（舊） | #18（本次） |
|------|----------|------------|
| Forward return | `after[h-1]/after[0] - 1`（少算第 0→1 天） | `after[h-1]/as_of - 1`（和 L1-L5 一致） |
| 月末取樣 | 直接用月末日期（可能非交易日） | 找月末最近交易日 |
| 活躍股票判定 | `len(df[df.index <= as_of]) > 120`（O(N²)） | `as_of in df.index`（O(1)） |
| 營收延遲 | 40 天（正確） | 40 天（正確） |
| IC 方法 | Spearman（正確） | Spearman（正確） |

## 2. 結果

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | N | Hit%(20d) |
|--------|:--------:|:---------:|:---------:|:-:|:---------:|
| **revenue_acceleration** | +0.292 | **+0.438** | **+0.582** | 98 | 67.3% |
| **revenue_new_high** | +0.249 | **+0.374** | **+0.435** | 98 | 67.3% |
| **revenue_momentum** | +0.135 | +0.296 | +0.441 | 95 | 55.8% |
| revenue_yoy | +0.199 | +0.132 | +0.197 | 98 | 57.1% |
| rev_seasonal_deviation | +0.128 | +0.183 | +0.117 | 92 | 53.3% |
| rev_accel_2nd_derivative | -0.042 | +0.094 | +0.123 | 102 | 52.0% |

## 3. 與 #16 的比較

| Factor | #16 ICIR(20d) | #18 ICIR(20d) | 變化 | 原因 |
|--------|:---:|:---:|:---:|------|
| revenue_acceleration | +0.240 | **+0.438** | +83% | forward return 修正 + 交易日校正 |
| revenue_new_high | +0.207 | **+0.374** | +81% | 同上 |
| revenue_yoy | +0.037 | +0.132 | +257% | 同上 |

**所有因子 ICIR 上升**，主因是 forward return 從 `after[0]→after[h-1]` 改為 `as_of→after[h-1]`，多算了第一天的報酬。排序不變。

## 4. 自動發現因子（修正 40d lag 後）

| Factor | ICIR(20d) | 評估 |
|--------|:---------:|------|
| rev_seasonal_deviation | +0.183 | 弱（< 0.20 部署門檻） |
| rev_accel_2nd_derivative | +0.094 | 無效 |

修正 look-ahead bias 後，所有自動發現因子的大規模 ICIR 都不足 0.20。

## 5. 結論

1. **revenue_acceleration 仍為最強因子**，ICIR(20d) +0.438，ICIR(60d) +0.582
2. **revenue_new_high 為第二強**，ICIR(20d) +0.374，可考慮與 acceleration 組合
3. **revenue_momentum（3M/6M）為第三**，60d ICIR +0.441 接近 new_high
4. **revenue_yoy 弱但正向**，ICIR(20d) +0.132
5. **自動因子全部不合格** — 40d lag 修正後 IC 大幅降低
6. 本次基準值已更新到 EXPERIMENT_STANDARDS.md 和 alpha_research_agent.py
