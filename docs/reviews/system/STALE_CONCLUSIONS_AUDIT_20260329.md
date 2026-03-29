# 過時結論審計 — Phase M 和 AA 的數字是否可信

**日期**：2026-03-29
**問題**：Phase M 和 AA 的關鍵結論基於舊版代碼，之後有 20+ 個公式修復。這些結論還能信嗎？

---

## 1. 時間線

```
d43ec8a  Phase M/-7.4% 數字產生
    ↓
ac94f0e  fix: Sharpe/Sortino formula corrections（BUG #1-2）
81725ad  fix: CAGR off-by-one, DSR kurtosis, cost ratio（BUG #8）
f2b23e3  fix: 3 engine bugs + inf protection
a8635d6  fix: DSR E[max SR] formula
    ↓
Phase AA 4.1 inverse-vol 實驗（-7.4% 可能已用修正後的代碼）
    ↓
3df0a71  Phase AB: DSR n_trials 1→15
278dc81  Phase AC: temporal_consistency + EW benchmark + corr 0.80
05ec583  Phase AC: Stationary Bootstrap + Permutation test
d76121a  Phase 1 freeze: 20+ fixes, Thresholdout, OOS leak sealing
76bb4e2  fix: zero-price data guard
```

## 2. 哪些結論可能受影響

### Phase M 的結論

| 結論 | 數字 | 受影響的修復 | 影響方向 |
|------|------|------------|---------|
| hedge 版 OOS -7.4% | -7.4% | Sharpe/CAGR 公式修正 | **不確定** — CAGR off-by-one 修正可能改變數字 |
| no-hedge 版 +10.8% | +10.8% | 同上 | **不確定** |
| hedge 版 MDD 改善 | 數字不明 | MDD 計算未改 | ✅ 應不受影響 |

**Phase M 的核心結論是「hedge 比 no-hedge 差」。** 這個結論的方向可能對，但精確數字（-7.4% vs +10.8%）不可信。如果 CAGR 修正後 hedge 變成 -5%、no-hedge 變成 +8%，結論仍然成立。如果修正後兩者都變成 -3%，結論就不成立了。

**已重跑驗證（2026-03-29）：**

### 驗證結果

| 版本 | CAGR | Sharpe | MDD | Validator |
|------|:----:|:------:|:---:|:---------:|
| NO HEDGE | +4.37% | 0.803 | 8.41% | 12/15 |
| WITH HEDGE | +4.37% | 0.803 | 8.41% | 12/15 |

**兩者完全相同。** Regime hedge 從未觸發。

**根因**：0050.TW（市場 proxy）不在回測 universe 中 → `ctx.bars("0050.TW")` 拋異常 → `_market_regime()` 的 `except: return "bull"` → 永遠 bull → hedge 永遠不縮倉。

**這意味著**：
1. Phase M 的「hedge 版 -7.4%」和「no-hedge 版 +10.8%」**可能是相同的東西**，數字差異來自其他參數變化，不是 hedge/no-hedge
2. Regime hedge 功能**從未被真正測試過** — 代碼存在但因為 0050 不在 universe 而靜默失效
3. `enable_regime_hedge=True` 預設開啟了一個**從不生效的功能**

### 和舊數字的對比

| 指標 | Phase M 舊數字 | 重跑新數字 | 差異來源 |
|------|:------------:|:--------:|---------|
| CAGR | +10.8%（no hedge）/ -7.4%（hedge） | **+4.37%**（兩者相同） | Sharpe/CAGR 公式修正 + universe 不同 |
| Sharpe | ~0.667 | **0.803** | 公式修正 |
| OOS Sharpe | -0.744 | **-1.355** | 更嚴格的 OOS 期間 |
| Validator | 14/15 | **12/15** | AC 新增 checks + 修正方法論 |

**CAGR 從 +10.8% 降到 +4.37%** — 因為公式修正（BUG #1-2）和更完整的 universe（200 支 vs 之前可能更少）。

### Validator 失敗項（新）

| Check | 結果 | 說明 |
|-------|------|------|
| temporal_consistency | 50%（需 60%） | 只有一半的年份正 Sharpe |
| oos_sharpe | -1.355 | OOS 期間嚴重虧損 |
| vs_ew_universe | -4.59% | **跑輸等權 universe 4.59%** — 沒有選股 alpha |

**vs_ew_universe -4.59% 是最重要的發現**：策略不僅沒有超額報酬，反而**跑輸隨便買所有股票**。

### 修正後的結論

Phase M 的原始結論（hedge 虧錢）是**無效的** — hedge 從未觸發。真正的問題更嚴重：

1. **策略本身跑輸等權大盤**（-4.59%）— 沒有 alpha
2. **OOS Sharpe -1.355** — 嚴重虧損
3. **CAGR 只有 +4.37%** — 遠低於之前報告的 +10.8%
4. **Regime hedge 是死代碼** — 需要修復（0050 加入 feed）或移除

### Phase AA 的結論

| 結論 | 數字 | 受影響的修復 | 影響方向 |
|------|------|------------|---------|
| inverse-vol CAGR 9.09% | 9.09% | Sharpe/CAGR 修正 | **不確定** |
| inverse-vol PBO 0.910 | 0.910 | AB: PBO N=1→15, PBO 方法論修正 | **很可能變化** |
| baseline PBO 0.702 | 0.702 | 同上 | **很可能變化** |
| no-trade zone +1.3% CAGR | +1.3% | CAGR 修正 | **不確定** |

**Phase AA 的核心結論是「inverse-vol 不如 equal-weight」。** PBO 0.702 vs 0.910 的比較是在 N=1（DSR 自動通過）的舊代碼下跑的。AB 修正 N=15 後，兩者的 PBO 都會改變。**0.702 和 0.910 這兩個數字都不可信。**

但 DeMiguel (2009) 的學術結論（equal-weight 幾乎永遠打敗估計權重）不依賴我們的實驗數字。**理論依據仍然成立，但實驗數據需要重跑。**

## 3. 哪些結論不受影響

| 結論 | 為什麼不受影響 |
|------|--------------|
| DeMiguel: equal-weight > inverse-vol | 學術結論，不依賴我們的代碼 |
| FinLab: 投信買超是落後指標 | FinLab 的獨立實驗 |
| FinLab: 營收因子最強 | 兩個獨立系統交叉驗證 |
| 動量確認（60 日漲幅 > 0）有效 | FinLab 和我們都確認 |
| Look-ahead bias 造成 IC 膨脹 72% | 修復前後的 IC 對比是可靠的 |

## 4. 需要重跑的實驗

| # | 實驗 | 用修正後的代碼重跑 | 目的 |
|---|------|-------------------|------|
| 1 | revenue_momentum（無 hedge）的 Validator 16 checks | 確認 CAGR、Sharpe、PBO 的新數字 |
| 2 | revenue_momentum_hedged 的 Validator 16 checks | 確認 hedge 是否仍然更差 |
| 3 | inverse-vol 的 Validator 16 checks | 確認 inverse-vol 是否仍然更差 |
| 4 | no-trade zone 的 Validator 16 checks | 確認 +1.3% CAGR 是否成立 |

**每個實驗只需要 `python -m src.cli.main backtest --strategy revenue_momentum ...` 一次。** 用現在（修正後）的代碼跑，更新文件中的數字。

## 5. 可以信賴的決策方式

**不要基於舊數字做決策。** 但也不需要推翻所有結論：

1. **策略方向**（revenue acceleration + 動量確認）— 有兩個獨立系統交叉驗證，可信
2. **權重方式**（equal-weight > inverse-vol）— 有學術共識（DeMiguel），可信
3. **精確數字**（-7.4%、+10.8%、PBO 0.702、0.910）— 不可信，需重跑
4. **hedge 結論**— 方向可能對（純多頭在牛市更好），但數字需要重跑確認

## 6. 建議

**開盤後第一件事**：用現在的代碼重跑 4 個 Validator 驗證（上面的表格）。只需要 4 次回測，每次 ~30 秒。用新數字替換所有文件中的舊數字。

**在重跑之前**：
- 不修改 `enable_regime_hedge` 預設值（等重跑結果確認）
- 不修改 `strategy_builder.py` 的權重方式（等重跑結果確認）
- 但 strategy_builder 用 inverse-vol 而 evaluate.py 用 equal-weight 的**不一致性**不需要重跑就能修 — 兩者應該用同一種權重方式

**結論**：Phase M 和 AA 的方向性結論（hedge 差、equal-weight 好）可能對，但精確數字不可信。決策應基於重跑後的新數字，不是舊數字。
