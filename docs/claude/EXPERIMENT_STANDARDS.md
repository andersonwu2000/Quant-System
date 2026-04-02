# 實驗方法論標準（Experiment Standards）

> 本文件定義量化交易系統所有實驗的標準化方法論。
> 不同實驗若使用不同參數會導致結果不可比較（如 #16 vs #17 的 ICIR 差異），
> 因此所有實驗必須遵循本文件的設定，除非有明確理由並在報告中說明偏離項。

---

## 1. 大規模因子 IC 驗證（Large-Scale Factor IC Validation）

| 項目 | 標準 |
|------|------|
| **Universe** | `data/market/*.TW_1d.parquet` 全部台股，排除 ETF（代碼 00xx 開頭），每檔需 ≥ 500 bars |
| **期間** | 2016-01 ~ 2025-12（完整可用歷史） |
| **取樣** | 月頻，每月最後一個營業日 |
| **IC 方法** | Spearman rank correlation（因子值 vs 前瞻報酬） |
| **前瞻報酬** | 5d、20d、60d 三個 horizon |
| **最小截面** | 每月 ≥ 20 檔股票，不足則排除該月 |
| **營收延遲** | 40 日曆天（台灣營收於次月 10 日前公布） |
| **歷史門檻** | 觀察日前需有 ≥ 120 個交易日的歷史資料 |
| **流動性濾除** | 20 日平均成交量 < 1,000 股者排除 |
| **漲跌停濾除** | 單日報酬 > ±10% 者排除（漲跌停不反映真實供需） |

**報告指標：**

- **ICIR** = mean(IC) / std(IC, ddof=1)
- **Hit%** = P(IC > 0)，即 IC 為正的月份佔比

---

## 2. StrategyValidator 16+1 項驗證

| 項目 | 標準 |
|------|------|
| **Universe** | 同上（全台股非 ETF） |
| **回測期間** | 2019-01-01 ~ 2025-12-31 |
| **OOS 期間** | 2025-01-01 ~ 2025-12-31 |
| **初始資金** | $10,000,000 TWD |
| **手續費** | 0.1425% |
| **交易稅** | 0.3%（僅賣出） |
| **換倉頻率** | 月頻 |
| **Kill switch** | 5% 日內最大回撤 |
| **執行延遲** | 1 日，以開盤價成交 |

**通過門檻：**

| 指標 | 門檻 |
|------|------|
| CAGR | ≥ 8% |
| Sharpe | ≥ 0.7 |
| MDD | ≤ 50% |

---

## 3. Auto-Alpha 研究管線

### 3.1 假說生成（Autoresearch 模式）

Agent 在 Docker 容器中自主生成假說，透過 `scripts/autoresearch/program.md` 協議循環。

**資訊來源：**
1. `curl -s http://evaluator:5000/learnings` — 成功模式、失敗模式、forbidden 方向、飽和度（Phase AF）
2. `results.tsv` — 實驗記錄
3. Agent 自身的量化知識

**安全限制：**
- Agent 只能編輯 `factor.py` 和 `results.tsv`
- 不能讀 evaluate.py、watchdog_data、src/
- learnings API 只回傳方向描述和 bucketed 指標（不含精確 ICIR）
- 方向飽和（同方向 ≥10 個變體）在 L3 強制阻擋（correlation-based）

### 3.2 StrategyValidator 16 項（2026-04-02 Phase AM 更新）

**Hard Gates（7 項，全部必須通過）：**

| # | 檢查名 | 門檻 | 說明 |
|---|--------|------|------|
| 1 | cagr | ≥ 8% | 絕對報酬門檻 |
| 2 | annual_cost_ratio | < 50% of gross | 成本 / gross alpha |
| 3 | cost_2x_safety | > 0% CAGR after 2× cost | 成本翻倍安全邊際 |
| 4 | temporal_consistency | score > 0 | sign-magnitude weighted（取代簡單正率） |
| 5 | deflated_sharpe | ≥ 0.70 | DSR，N = n_independent（和 PBO 統一） |
| 6 | construction_sensitivity | ≤ 0.60 | 建構 PBO（放寬自 0.50，含 avg_pairwise_corr 可信度） |
| 7 | market_correlation | \|corr\| ≤ 0.80 | 和 0050.TW 日報酬相關性 |

**Soft Gates（9 項，≥ 3 項 fail 阻擋部署）：**

| # | 檢查名 | 門檻 | 說明 |
|---|--------|------|------|
| 8 | universe_size | ≥ 50 | 選股池大小 |
| 9 | sharpe | ≥ 0.7 | 風險調整報酬（降為 soft，DSR 已涵蓋） |
| 10 | max_drawdown | ≤ 40% | 最大回撤 |
| 11 | bootstrap_p_sharpe_positive | ≥ 80% | P(Sharpe > 0)（降為 soft，和 DSR 重疊） |
| 12 | oos_sharpe | ≥ 0.30 | OOS2 Sharpe（後半段 275 天，Validator 專用） |
| 13 | vs_ew_universe | ≥ 50% windows | Beta-neutral excess vs 月頻 EW（降為 soft） |
| 14 | worst_regime | ≥ -30% | 市場危機期間累計報酬 |
| 15 | sharpe_decay | t > -2.0 | SR(後半) - SR(前半) 的 t-stat（取代 recent_period_sharpe） |
| 16 | cvar_95 | ≥ -5% | Daily CVaR(95%) |

**方法論細節：**
- **OOS 切割**：549 天分兩半。L5（evaluate.py）用 OOS1（前半 ~275 天），Validator 用 OOS2（後半 ~275 天）。消除 double-dipping
- **DSR N 統一**：N = n_independent（從 factor_pbo.json 讀取，correlation clustering threshold=0.50），和 factor-level PBO 同定義
- **temporal_consistency**：score = mean(sign(SR_i) × min(|SR_i|, 2.0))，取代簡單的「SR > 0 年數比例」。更 robust，不被 SR=0.01 污染
- **sharpe_decay**：Lo (2002) SE 計算差值 t-stat。2 年數據 delta=-0.5 → t≈-1.1（不顯著，通過），10 年數據 delta=-0.5 → t≈-2.5（顯著退化，不通過）
- **vs_ew_universe**：月頻再平衡 EW（匹配策略頻率）+ 120d beta neutralization + 下市股 ffill。降為 soft（15 vs 200 集中度不對稱）
- **construction_sensitivity**：PBO ≤ 0.60（放寬自 0.50）。報告 avg_pairwise_corr，> 0.8 標記 LOW CONFIDENCE
- **Soft gate 累積**：≥ 3 個 soft fail → 阻擋部署（soft check 有約束力）
- **行業中性化 IC**：IC 計算前對因子值和 forward return 各減去行業均值
- **Factor Attribution**：Fama-French 風格迴歸（MKT + SMB + HML + MOM），描述性（不擋部署）
- **Permutation Test (#16)**：打亂因子-股票映射，100 次排列。條件式（需有 compute_fn）

### 3.3 Autoresearch 評估閘門（L1-L5 + Stage 2）

定義於 `scripts/autoresearch/evaluate.py`（READ ONLY）。

**期間分割（Rolling，自動依 today 計算）：**
- In-Sample (IS)：2017-01-01 ~ `today - 90d - 549d`（L1-L4 使用）
- Out-of-Sample OOS1：`today - 90d - 548d` ~ `today - 90d - 274d`（L5 使用，agent 不可見）
- Out-of-Sample OOS2：`today - 275d` ~ `today - 1d`（Validator 使用，L5 未見過）
- 例：2026-04-02 → IS ~2024-05, OOS1 ~2024-05~2025-07, OOS2 ~2025-07~2026-04

**Universe：**
- Core：200 支大中型股（依日均成交額排序，ADV ≥ 340M TWD）
- Large：865+ 支全市場（Stage 2 用）
- MIN_SYMBOLS：每日至少 50 支有效股票才計算 IC

**因子自動 normalization：** 每個因子自動測試 [raw, rank, z-score] 三種 normalization，取 best |IC| 的版本進入 L1。

**行業中性化 IC：** IC 計算前對因子值和 forward return 各減去行業均值（FinMind industry_category）。

| 閘門 | 條件 | 說明 | 失敗處理 |
|------|------|------|----------|
| **L0** | factor.py ≤ 80 行 | 複雜度限制（防過擬合） | 直接拒絕 |
| **L1** | \|IC(20d)\| ≥ 0.02 OR \|IC(60d)\| ≥ 0.03 | IS 前 30 日快篩 + slow-alpha bypass。要求 sign(IC_20d)==sign(IC_60d) | 換方向 |
| **L2** | median\|ICIR\| ≥ 0.30, ≤ 1.00 | IS 全期間 median across 4 horizons | 訊號不穩 |
| **L3a** | dedup corr ≤ **0.65** | IC-series 相關性（放寬自 0.50）。替換門檻 **1.15x** ICIR（放寬自 1.3x）。失敗標記 L3_dedup | clone |
| **L3b** | rolling 12-month ≥ **50%** positive | 滾動窗口（取代固定年份）。失敗標記 L3_stability | regime 依賴 |
| **L4** | fitness ≥ 3.0 | WorldQuant BRAIN 公式 | 綜合不足 |
| **L5** | OOS1 IC 方向一致 + 正月 ≥ 50% | **移除 ICIR decay**（留給 Validator DSR）。只看方向 | 過擬合 IS |
| **L5b** | Top quintile > universe (IS+OOS1) | pass/fail | IC 高但不賺錢 |
| **L5c** | 分位單調性 (IS+OOS1) | abs(Spearman) > 0.5 | 信號中間有效 |
| **Stage 2** | large ICIR(20d) | 全市場驗證（參考） | — |

**防過擬合設計：**
- L2 使用 median |ICIR| across 4 horizons（Method D），不取最佳也不固定單一 horizon，消除 selection bias 且不歧視長期因子
- L5a/L5b/L5c 只向 agent 回報 pass/fail，不洩漏具體數值（P-01）
- eval_server 回傳 bucketed ICIR（none/weak/moderate/strong），agent 無法做梯度式優化
- Novelty indicator 回傳 bucketed corr（high/moderate/low），不洩漏精確 correlation
- Thresholdout 加 Laplace 噪音降低每次 L5 查詢的資訊洩漏
- 最終驗證靠 StrategyValidator + paper trading

> **deflated_sharpe 說明**：N = n_independent（聚類後獨立方向數，和 factor-level PBO 統一）。N=15 時 DSR 0.70 對應 Sharpe ~1.3。N 過大（如用全部實驗數 262）會過度懲罰。

### 3.4 關鍵約束（2026-03-27 大規模審計後確立）

1. **營收 40 天延遲**：所有營收因子必須用 `as_of - pd.DateOffset(days=40)` 截斷。缺此延遲會導致 IC 膨脹 10-40 倍（look-ahead bias）
2. **因子生成 fail-closed**：不匹配的假說必須 return None，不可 fallback 到 revenue_yoy
3. **大規模 IC 和 L1-L5 forward return 必須一致**：都用 `close[as_of+h] / close[as_of] - 1`
4. **月度取樣用最近交易日**：不可直接用月末日期（可能不是交易日）

### 3.5 因子淘汰與 clone 處理（2026-03-29 確立）

**四層 dedup 機制：**

| 層 | 位置 | 檢查 | 門檻 | 速度 |
|:--:|------|------|:----:|:----:|
| 1 | evaluate.py L3 | IC series correlation | > 0.65 擋（放寬自 0.50） | 即時 |
| 2 | watchdog pre-filter | Portfolio returns correlation | > 0.85 擋 | 秒級 |
| 3 | watchdog Validator | 17 項策略級驗證（vs_ew_universe 改為 walk-forward） | 全通過才部署 | ~9 min |
| 4 | watchdog PBO | Factor-Level PBO（Bailey CSCV） | > 0.70 擋 | 分鐘級 |

**Clone 群處理（Layer 2 細節）：**
- 同一 reference factor 的 clone 群（returns corr > 0.85）中，**保留 median ICIR 最高的一個送 Validator，其餘刪除 pending marker**
- 如果 best clone ICIR > reference 的 ICIR → 升格為 novel（替換代表）
- **不刪除 factor_returns parquet** — PBO 計算需要完整的試驗歷史

**已知的 accepted selection bias：**
- 部署時選 clone 群中 ICIR 最高的實作版本（工程決策，非過擬合）
- PBO 計算使用 cluster 中位數因子（Bailey 原則，不受部署選擇影響）
- 兩條路徑獨立：PBO 的 N 包含所有 factor_returns（含被跳過的 clone），DSR 正確反映總試驗次數
- Within-cluster selection bias 量級約 3%（觀測值：0.530 vs 0.513），遠小於跨 cluster 不確定性

### 3.5 報告流程（autoresearch 模式）

因子報告存放在 `docs/research/autoresearch/`。

**報告生成條件：** 通過 L5 OOS1 驗證後，evaluate.py 寫 pending marker。Watchdog 背景執行 StrategyValidator（OOS2），7 項 HARD 全過 + soft fail < 3 才部署。

**部署條件（2026-04-02 Phase AM 更新）：** 見 §3.2 表格。

- 硬門檻（7 項）：cagr, annual_cost_ratio, cost_2x_safety, temporal_consistency, deflated_sharpe, construction_sensitivity, market_correlation, permutation_p
- 軟門檻（9 項，≥ 3 fail 阻擋）：universe_size, sharpe, max_drawdown, bootstrap_p, oos_sharpe, vs_ew_universe, worst_regime, sharpe_decay, cvar_95

額外條件：Factor-Level PBO ≤ 0.70（watchdog 獨立計算，Bailey 2014 CSCV，累積 ≥20 因子後生效）

**Thresholdout（Dwork et al. 2015）**：L5 OOS 判定加 Laplace 噪音（scale=0.05），降低每次查詢的資訊洩漏從 1 bit 到 ~0.7 bit。查詢計數存在 watchdog_data/（agent 不可見），budget 200 次。

未通過 L5 的因子只記錄在 `results.tsv`，不寫報告。

---

## 4. 基準因子（Experiment #16 結果）

以下為標準方法論下的基準 ICIR，用於比較後續實驗是否一致：

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |
|--------|----------|-----------|-----------|-----------|
| revenue_acceleration | +0.292 | **+0.438** | **+0.582** | 67.3% |
| revenue_new_high | +0.249 | +0.374 | +0.435 | 67.3% |
| revenue_momentum | +0.135 | +0.296 | +0.441 | 55.8% |
| revenue_yoy | +0.199 | +0.132 | +0.197 | 57.1% |

> 基準更新於 2026-03-27（forward return 修正 + 月末交易日校正後）。

> 若新實驗使用相同方法論但結果偏離基準超過 ±20%，應檢查數據或程式差異。

---

## 5. 報告規範

### 存放位置

| 類型 | 目錄 |
|------|------|
| 實驗報告 | `docs/research/` |
| Auto-alpha 報告 | `docs/research/` |
| Paper trading 報告 | `docs/paper-trading/` |

### 檔案命名

```
YYYYMMDD_NN_description.md
```

- `YYYYMMDD`：實驗日期
- `NN`：當日流水號（01, 02, ...）
- `description`：簡短英文描述，底線分隔

範例：`20260327_01_revenue_factor_ic_validation.md`

### 報告必含項目

1. **方法論聲明**：是否完全遵循本標準，若有偏離需逐項列出
2. **Universe 統計**：實際股票數、月份數
3. **結果表格**：ICIR、Hit% 等指標
4. **與基準比較**：與 §4 基準因子的差異
5. **結論與下一步**
