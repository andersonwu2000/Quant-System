# 頂級量化基金實務 vs 本系統 — 差距分析

**日期**：2026-03-29
**來源**：Two Sigma、Renaissance、AQR、WorldQuant、DE Shaw、Man AHL、Citadel 的公開論文、演講、書籍、開源專案
**目的**：識別本系統和業界最佳實務的差距，找出值得學習的具體做法

---

## 1. 統計門檻對比

| 指標 | 業界標準 | 本系統 | 差距 |
|------|---------|--------|:----:|
| 新因子 t-stat | **> 3.0**（Harvey 2016, AQR, López de Prado） | 無明確 t-stat 門檻（用 DSR + ICIR） | ⚠️ |
| 單一 alpha Sharpe | **> 1.5**（WorldQuant BRAIN） | ICIR ≥ 0.30（L2 門檻）≈ Sharpe ~0.5 | ❌ 差距大 |
| 組合 Sharpe（毛） | **> 2.0**（WorldQuant, Man AHL） | 最佳 0.94 | ❌ 差距大 |
| Paper trading | **3-12 個月**（AQR 6 個月, Man AHL 3-12 個月） | 0 天 | ❌ 未開始 |
| 最低回測長度 | **10-20 年**（AQR, Man AHL） | 7 年（2017-2024） | ⚠️ 偏短 |
| 交易成本安全邊際 | **實際的 1.5-2×**（Man AHL） | 面值（0.1425% + 0.3%） | ⚠️ 無安全邊際 |
| 多市場驗證 | **至少 1 個獨立市場**（AQR） | 僅台股 | ❌ 完全缺失 |

**總評**：本系統的統計門檻遠低於業界標準。業界要求 Sharpe > 1.5 才算「值得看」，我們最好的因子 Sharpe 0.94 在業界連初篩都過不了。

---

## 2. 研究管線對比

### 業界共同流程

```
Idea → Literature Review → Hypothesis → Economic Rationale
  → Point-in-time Backtest → Multiple Testing Correction
    → Peer Review → Committee Review
      → Paper Trade (3-12 月)
        → Small Live (1-5% 目標配置)
          → Gradual Scale-up → Full Allocation
```

### 本系統流程

```
Agent 生成 factor.py → evaluate.py L1-L5 → watchdog Validator
  → （缺）Paper Trade → （缺）Small Live → （缺）Scale-up
```

### 差距分析

| 步驟 | 業界 | 本系統 | 判定 |
|------|------|--------|:----:|
| Economic Rationale | 必須（AQR：「不接受純數據挖掘」） | program.md 要求 docstring 解釋 | ⚠️ 有但不嚴格 |
| Point-in-time Data | 核心基礎設施（Man AHL Arctic） | 40 天營收延遲 + _mask_data | ✅ |
| Multiple Testing | DSR + Bonferroni（Two Sigma, AQR） | DSR(N=15) + Thresholdout + PBO | ✅ 方法完整 |
| Peer Review | 2-3 人審查 + Committee | 無（單人 + AI） | ❌ |
| Paper Trading | 3-12 個月（硬性要求） | 0 天 | ❌ |
| 逐步放大 | 1-5% → 逐月增加 | 未設計 | ❌ |
| Alpha Combining | 數千弱 alpha 組合（WorldQuant） | 單一因子 top-15 等權 | ❌ 差距大 |

---

## 3. 過擬合防範對比

| 方法 | 業界使用 | 本系統 | 差距 |
|------|---------|--------|:----:|
| DSR | ✅ López de Prado | ✅ N=15（動態更新） | ✅ |
| PBO (CSCV) | ✅ Bailey | ✅ Factor-Level PBO | ✅ |
| Thresholdout | ✅ Dwork | ✅ Laplace noise on L5 | ✅ |
| Bootstrap | ✅ Politis & Romano | ✅ Stationary Bootstrap | ✅ |
| Permutation Test | ✅ 常見 | ✅ 100 shuffles | ✅ |
| CPCV | ✅ López de Prado | ❌ 未實作 | ⚠️ |
| 多市場 OOS | ✅ AQR（必要條件） | ❌ 僅台股 | ❌ |
| 多 Regime 測試 | ✅ Man AHL | ⚠️ regime check 是死代碼 | ❌ |
| 交易成本扣除後評估 | ✅ 所有公司 | ⚠️ fitness 有 turnover penalty 但不扣成本 | ⚠️ |
| Alpha 去重 | ✅ WorldQuant corr < 0.7 | ✅ IC-series corr < 0.50 | ✅ 更嚴格 |

**總評**：過擬合防範是本系統做得最好的部分。6 項統計檢定超過多數公開框架。但缺少多市場驗證和 regime 測試（後者已發現是死代碼）。

---

## 4. 執行 & 交易成本對比

| 項目 | 業界做法 | 本系統 | 差距 |
|------|---------|--------|:----:|
| 交易成本模型 | Almgren-Chriss market impact + spread + timing cost | 固定 bps（slippage 5bps + commission + tax） | ❌ 過度簡化 |
| 成本安全邊際 | 回測用 1.5-2× 實際成本 | 用面值 | ⚠️ |
| 容量分析 | alpha vs 資金規模的衰減曲線 | 無 | ❌ |
| 執行延遲 | 模擬真實的 fill latency | Validator 有 execution_delay=1 但策略回測沒有 | ⚠️ |
| 大盤股 vs 小盤股成本差異 | 按 ADV 分級（5-50bps） | 統一 5bps | ⚠️ |

**AQR 的研究**（2019 "Trading Costs of Asset Pricing Anomalies"）：扣除交易成本後，大多數因子回報降低 40-60%。我們的 CAGR +4.37% 扣除 40-60% 的成本影響後可能接近 0。

---

## 5. 風控對比

| 項目 | 業界做法 | 本系統 | 差距 |
|------|---------|--------|:----:|
| 獨立風控團隊 | 必須（不向交易報告） | 風控邏輯在同一 codebase | ⚠️ 個人專案可接受 |
| 即時 VaR | 每秒更新 | RealtimeRiskMonitor 每 tick | ✅ |
| Kill switch | 自動減倉 | 雙路徑 + portfolio lock | ✅ |
| Stress testing | 歷史情境 + 假設情境 | 無 | ❌ |
| 策略間相關性 | 監控並限制 | 單策略，不適用 | N/A |
| Drawdown 限制 | Pod 級別 5-7%（Citadel） | 日回撤 5% kill switch | ✅ 類似 |

---

## 6. 數據管理對比

| 項目 | 業界做法 | 本系統 | 差距 |
|------|---------|--------|:----:|
| Point-in-time DB | Man AHL Arctic（版本化數據） | 40 天延遲 + _mask_data | ⚠️ 概念有但不是真正的版本化 |
| Survivorship bias | 必須修正 | FinMind 含下市股票 | ✅ |
| 數據品質 gate | 自動化品質檢查 | quality.py 7 項檢查 | ✅ |
| 數據刷新 | 自動化管線 | 手動下載（Phase AD 未做） | ❌ |
| Alternative data | 衛星、信用卡、社交媒體 | 無 | ❌ 但個人投資不需要 |
| 數據版本化 | 可查詢任意時間點的數據快照 | 無 | ⚠️ |

---

## 7. 最值得學習的 5 件事

### 7.1 交易成本安全邊際（Man AHL）

**做法**：回測時用實際交易成本的 **1.5-2×**。

**理由**：回測的交易成本模型永遠是簡化的。市場衝擊、流動性枯竭、price gap 在回測中不會出現。AQR 研究顯示因子回報扣除真實成本後降低 40-60%。

**對我們的影響**：
- 台股 round-trip 成本面值 ≈ 0.585%（買 0.1425% + 賣 0.4425%）
- 加 2× 安全邊際 → 回測用 1.17% round-trip
- 月頻再平衡 × 15 檔 × ~30% turnover = 每月 ~5 筆交易 → 年成本從 ~2% 升到 ~4%
- CAGR +4.37% - 4% 成本 ≈ **+0.37%** — 幾乎不賺錢

**這是最重要的發現**：加上成本安全邊際後，策略的超額報酬可能為零。

**建議**：在 Validator 中加入「2× 成本下仍通過」的 check。evaluate.py 的 fitness 已含 turnover penalty，但不是 2× 成本。

### 7.2 Alpha Combining（WorldQuant）

**做法**：不依賴單一因子。收集數千個弱 alpha（各自 Sharpe ~1.5），用 optimization 組合成一個 portfolio（目標 Sharpe ~2.0+）。

**理由**：單一因子的 alpha 衰減快且不穩定。組合後：
- 分散風險（單一因子失效不致命）
- 提高 Sharpe（低相關因子組合 → √N 效應）
- 降低 turnover（不同因子的交易方向可能抵消）

**對我們的影響**：我們目前是「單因子 top-15 等權」。即使因子有 alpha，這種方式浪費了其他因子的信號。

**建議**：
- 短期：累積 5+ 個通過 L5 的因子後，測試 equal-weight combining（每個因子各選 top-5，合併去重）
- 中期：用 IC-weighted combining（ICIR 高的因子給更多權重）

### 7.3 多 Regime 測試（Man AHL）

**做法**：策略必須在牛市、熊市、高波動、低波動四種環境下都有正回報（或至少可控虧損）。

**理由**：2017-2024 台股基本是牛市。如果因子只在牛市有效，2025 崩潰是必然的。

**對我們的影響**：
- Validator 有 `worst_regime` check 但 regime hedge 是死代碼
- OOS 2025 Sharpe = -1.355 就是 regime 失敗的證據
- 需要在回測中分段評估每個 regime 的 Sharpe，而非只看整體

**建議**：Validator 的 `worst_regime` check 改為分 4 個 regime 各自報告 Sharpe，門檻從「最差 regime > -30%」改為「最差 regime Sharpe > -0.5」。

### 7.4 研究到生產用同一份代碼（Man AHL）

**做法**：研究環境和生產環境共用同一份策略代碼和數據基礎設施。不重寫。

**理由**：重寫 = 引入新 bug。回測和實盤的差異（CAGR 不一致問題）往往來自代碼不同。

**對我們的影響**：
- autoresearch 的 factor.py 和 revenue_momentum.py 是**完全不同的代碼**
- evaluate.py 用等權 top-15，strategy_builder 用 equal_weight（已修），但 revenue_momentum 用 signal_weight
- Validator 的 BacktestConfig 和外部直接跑 BacktestEngine 的 config 有 6+ 個參數不同

**建議**：策略從研究到部署應該是「同一份 factor.py + 固定的 portfolio construction」，不是研究時用 factor.py、部署時用完全不同的 revenue_momentum.py。

### 7.5 Paper Trading 是硬性要求，不是可選步驟

**做法**：
- AQR：至少 6 個月
- Man AHL：3-12 個月
- DE Shaw：6-18 個月（含研究期）
- 沒有任何一家頂級量化基金跳過 paper trading 直接實盤

**對我們的影響**：PRODUCTION_READINESS 報告已指出這一點，但值得再次強調 — **業界沒有任何人跳過這一步**。

---

## 8. 不需要學的

| 項目 | 業界做法 | 為什麼不學 |
|------|---------|-----------|
| Alternative data | 衛星、信用卡、NLP | 個人投資不需要也負擔不起 |
| 高頻交易 | 微秒級延遲、co-location | 完全不同的領域 |
| Alpha combining 大規模優化 | 數千 alpha + mean-variance | 需要先有 5+ 個有效因子 |
| 獨立風控團隊 | 不向交易報告 | 個人專案只有一個人 |
| 自建 execution algo | 50+ 人的團隊 | 用 SimBroker/Shioaji 已足夠 |

---

## 9. 結論

### 本系統的定位

本系統不是也不該試圖成為 Two Sigma 或 Renaissance。它的目標是「個人和家族投資」。

但即使在這個定位下，業界的基本標準仍然適用：

| 標準 | 業界要求 | 我們的狀態 | 能否達到？ |
|------|---------|-----------|:---------:|
| Paper trading | 3-6 個月 | 0 天 | ✅ 開盤後開始 |
| 交易成本安全邊際 | 1.5-2× | 面值 | ✅ 一行代碼 |
| 多 regime 測試 | 分段評估 | 整體平均 | ✅ 小改動 |
| t-stat > 3.0 | 新因子門檻 | 無明確門檻 | ✅ DSR 已接近 |
| Alpha combining | 多因子組合 | 單因子 | ⚠️ 需 5+ 因子 |
| 多市場驗證 | 至少 1 個 | 僅台股 | ❌ 需要數據 |
| 10-20 年回測 | 最低要求 | 7 年 | ⚠️ 數據受限 |

**最誠實的評估**：本系統的過擬合防範做得不錯（6 項統計檢定），但策略本身的 alpha 可能不存在（Sharpe 0.94 < 噪音期望 1.4，加 2× 成本後 CAGR ≈ 0%）。

**下一步不是「優化系統」，而是「驗證 alpha 是否存在」。** 這只有 paper trading 能回答。

---

## 參考

- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
- Tulchinsky, I. (2019). *Finding Alphas: A Quantitative Approach*. Wiley.
- Zuckerman, G. (2019). *The Man Who Solved the Market*. Portfolio/Penguin.
- Asness, C. et al. (2013). Value and Momentum Everywhere. *Journal of Finance*.
- Harvey, C., Liu, Y. & Zhu, H. (2016). ...and the Cross-Section of Expected Returns. *RFS*.
- Novy-Marx, R. & Velikov, M. (2019). Trading Costs of Asset Pricing Anomalies. *AQR Working Paper*.
- Bailey, D. & López de Prado, M. (2014). The Deflated Sharpe Ratio. *SSRN*.
- Man AHL Arctic: https://github.com/man-group/arctic
- WorldQuant BRAIN: https://platform.worldquant.com
