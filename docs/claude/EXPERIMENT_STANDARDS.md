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

### 3.2 StrategyValidator 16 項（2026-03-28 Phase AC 凍結）

| # | 檢查名 | 門檻 | 說明 | 方法論變更 |
|---|--------|------|------|-----------|
| 1 | universe_size | ≥ 50 | 選股池不能太小 | — |
| 2 | cagr | ≥ 8% | 絕對報酬門檻 | — |
| 3 | sharpe | ≥ 0.7 | 風險調整報酬 | — |
| 4 | max_drawdown | ≤ 40% | 收緊自 50%（機構標準） | — |
| 5 | annual_cost_ratio | < 50% of gross | 成本 / gross alpha | V2: 分母改 gross（非 net） |
| 6 | temporal_consistency | ≥ 60% | WF 年正率（OOS Sharpe > 0 的比例） | 更名自 walkforward_positive |
| 7 | deflated_sharpe | ≥ 0.70 | DSR（N=15 independent directions） | Lo(2002) SE; N 由外部傳入 |
| 8 | bootstrap_p_sharpe_positive | ≥ 80% | P(Sharpe > 0) | Stationary Bootstrap (Politis & Romano 1994, avg_block=20) |
| 9 | oos_sharpe | ≥ 0.30 | Rolling OOS: today-549d ~ yesterday | 滾動 OOS（非固定期間） |
| 10 | vs_ew_universe | ≥ 0% | 超額 vs 等權 universe 平均 | Phase AC: 取代 vs 0050（消除 size premium 偏差） |
| 11 | construction_sensitivity | ≤ 0.50 | 組合建構變異穩定性 | 更名自 pbo（非 Bailey CSCV；真正 PBO 在 watchdog） |
| 12 | worst_regime | ≥ -30% | 市場危機期間累計報酬 | Phase AC: drawdown-based（0050 DD > 15%），非年度 |
| 13 | recent_period_sharpe | ≥ 0 | 最近 252 交易日 Sharpe | — |
| 14 | market_correlation | \|corr\| ≤ 0.80 | 和 0050.TW 日報酬相關性 | 收緊自 0.90 |
| 15 | cvar_95 | ≥ -5% | Daily CVaR(95%) expected shortfall | — |
| 16 | permutation_p | < 0.10 | 排列檢定 p-value | Phase AC 新增：shuffles real factor rankings |

**方法論細節：**
- **Stationary Bootstrap (#8)**：保留時間序列自相關結構，avg_block=20 天（月頻策略）
- **Rolling OOS (#9)**：`oos_end = today - 1d`, `oos_start = today - 549d`，自動滾動避免 holdout leakage
- **等權基準 (#10)**：universe 內所有股票等權持有，衡量選股 alpha（非 size premium）
- **Drawdown Regime (#12)**：0050.TW 回撤 > 15% 的日期集合，測策略在市場危機中的表現
- **Permutation Test (#16)**：保留因子值不變，打亂股票對應（固定 mapping per trial），100 次排列

### 3.3 Autoresearch 評估閘門（L1-L5 + Stage 2）

定義於 `scripts/autoresearch/evaluate.py`（READ ONLY）。

**期間分割（Rolling，自動依 today 計算）：**
- In-Sample (IS)：2017-01-01 ~ `today - 90d - 549d`（L1-L4 使用）
- Out-of-Sample (OOS)：`today - 90d - 548d` ~ `today - 90d`（L5 使用，agent 不可見）
- 例：2026-03-29 → IS 2017-01-01~2024-05-12, OOS 2024-05-13~2025-12-29

**Universe：**
- Core：200 支大中型股（依日均成交額排序，ADV ≥ 340M TWD）
- Large：865+ 支全市場（Stage 2 用）
- MIN_SYMBOLS：每日至少 50 支有效股票才計算 IC

| 閘門 | 條件 | Universe | 說明 | 失敗處理 |
|------|------|----------|------|----------|
| **L0** | factor.py ≤ 80 行 | — | 複雜度限制（防過擬合） | 直接拒絕 |
| **L1** | \|IC(20d)\| ≥ 0.02 | Core 200 | IS 前 30 個日期快篩（~30 秒） | 換方向 |
| **L2** | \|ICIR_20d\| ≥ 0.50 | Core 200 | IS 全期間、固定 20d horizon（Fix #8: 消除 horizon selection bias） | 訊號不穩，試平滑 |
| **L3a** | dedup corr ≤ 0.50 | Core 200 | IC-series 與已知因子相關性 | 因子是 clone |
| **L3b** | positive_years ≥ 4/6.5 | Core 200 | IS 年度穩定性 | regime 依賴 |
| **L4** | fitness ≥ 3.0 | Core 200 | WorldQuant BRAIN 公式 | 綜合不足 |
| **L5** | OOS IC 方向一致 | Core 200 | IS 和 OOS 的 IC 同號 | 過擬合 IS |
| **L5** | OOS ICIR 衰退 ≤ 60% | Core 200 | OOS \|ICIR\| ≥ IS \|ICIR\| × 0.40 | 過擬合 IS |
| **L5** | OOS 正向月 ≥ 50% | Core 200 | 至少半數 OOS 月份 IC > 0 | 不穩定 |
| **Stage 2** | large ICIR(20d)（參考） | Large 865+ | 全市場驗證，不硬擋，記錄於報告 | — |

**防過擬合設計：**
- L2 使用固定 20d horizon ICIR（Fix #8），不取最佳 horizon，消除 Harvey & Liu (2015) 指出的 selection bias
- L5 只向 agent 回報 pass/fail，不洩漏 OOS 具體數值（P-01）
- eval_server 回傳 bucketed ICIR（none/weak/moderate/strong），agent 無法做梯度式優化
- Thresholdout 加 Laplace 噪音降低每次 L5 查詢的資訊洩漏
- 最終驗證靠 StrategyValidator + paper trading

> **deflated_sharpe 說明**：90+ trials 下 DSR 0.95 需 Sharpe > 2.0（業界不現實）。0.70 對應 Sharpe ~1.5，是合理門檻。Bailey & López de Prado 原意是排名工具而非絕對門檻。

### 3.4 關鍵約束（2026-03-27 大規模審計後確立）

1. **營收 40 天延遲**：所有營收因子必須用 `as_of - pd.DateOffset(days=40)` 截斷。缺此延遲會導致 IC 膨脹 10-40 倍（look-ahead bias）
2. **因子生成 fail-closed**：不匹配的假說必須 return None，不可 fallback 到 revenue_yoy
3. **大規模 IC 和 L1-L5 forward return 必須一致**：都用 `close[as_of+h] / close[as_of] - 1`
4. **月度取樣用最近交易日**：不可直接用月末日期（可能不是交易日）

### 3.5 報告流程（autoresearch 模式）

因子報告存放在 `docs/research/autoresearch/`。

**報告生成條件：** 通過 L5 OOS 驗證後，evaluate.py 寫 pending marker 到 watchdog_data/pending/。Watchdog 背景執行 StrategyValidator 17 項，10 項 HARD 全過（deployed=True）才寫報告到 `docs/research/autoresearch/`。

**部署條件（硬/軟門檻，Phase AC §7 + FACTOR_PIPELINE_DEEP_REVIEW）：**

硬門檻 — 統計/結構檢定（防過擬合）：
| Check | 門檻 | 測什麼 |
|-------|------|--------|
| deflated_sharpe | ≥ 0.70 | 多重測試後 Sharpe 是否顯著 |
| bootstrap_p_sharpe_positive | ≥ 80% | P(Sharpe > 0) 含自相關修正 |
| vs_ew_universe | ≥ 0% | 選股 alpha（非 size premium） |
| construction_sensitivity | ≤ 0.50 | portfolio 建構穩定性 |
| market_correlation | ≤ 0.80 | 獨立於大盤（非 beta 搬運） |
| permutation_p | < 0.10 | 信號打亂後 Sharpe 是否下降（條件式：需有 compute_fn） |

硬門檻 — 經濟可行性（確保值得交易）：
| Check | 門檻 | 測什麼 |
|-------|------|--------|
| cagr | ≥ 8% | 最低報酬門檻 |
| sharpe | ≥ 0.7 | 風險調整報酬 |
| annual_cost_ratio | < 50% | 成本不吃掉 alpha |
| temporal_consistency | ≥ 60% | 不依賴單一年份 |

軟門檻（sanity check，統計功效不足，報告但不擋部署）：
| Check | 門檻 | 為什麼是軟門檻 |
|-------|------|---------------|
| oos_sharpe | ≥ 0.30 | SE=0.82，p=0.36（Lo 2002） |
| recent_period_sharpe | ≥ 0 | SE=1.0，50% 拋硬幣 |
| max_drawdown | ≤ 40% | 路徑依賴極強（Magdon-Ismail 2004） |
| worst_regime | ≥ -30% | 描述性，非假設檢定 |
| universe_size | ≥ 50 | 前置條件 |
| cvar_95 | ≥ -5% | 描述性風險度量 |

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
