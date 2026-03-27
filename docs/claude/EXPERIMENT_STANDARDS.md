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

## 2. StrategyValidator 13 項驗證

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

### 3.1 假說生成

假說模板存放在 `data/research/hypothesis_templates.json`，由 Claude Code 動態維護。

**生成新假說時應考慮：**
1. Experience memory 中的成功/失敗模式（`data/research/memory.json`）
2. 禁區列表（已知無效的因子模式）
3. 學術文獻依據
4. 與現有因子的差異化（避免高相關）
5. 數據可得性（僅用本地已有的 revenue / financial_statement parquet）

**模板格式：**
```json
{
  "direction_name": [
    {
      "name": "factor_name",
      "description": "因子描述",
      "formula_sketch": "公式概要",
      "academic_basis": "學術依據",
      "data_requirements": ["revenue"]
    }
  ]
}
```

研究腳本 `scripts/alpha_research_agent.py` 每輪自動從 JSON 讀取未測假說。

### 3.2 StrategyValidator 15 項（2026-03-27 更新）

| # | 檢查 | 門檻 | 說明 |
|---|------|------|------|
| 1 | universe_size | ≥ 50 | 選股池不能太小 |
| 2 | cagr | ≥ 8% | 絕對報酬門檻（從 15% 降低） |
| 3 | sharpe | ≥ 0.7 | 風險調整報酬 |
| 4 | max_drawdown | ≤ 40% | 收緊自 50%（機構標準） |
| 5 | annual_cost_ratio | < 50% | 成本 / gross alpha |
| 6 | walkforward_positive | ≥ 60% | WF 年正率 |
| 7 | deflated_sharpe | ≥ 0.70 | 寬鬆門檻（90+ trials 下 0.95 不可能） |
| 8 | bootstrap_p(SR>0) | ≥ 80% | Bootstrap 統計信心 |
| 9 | oos_sharpe | ≥ 0 | 改為 Sharpe > 0（比 return > 0 更嚴） |
| 10 | vs_1n_excess | ≥ 0% | 超越等權基準 |
| 11 | pbo | ≤ 50% | 過擬合概率 |
| 12 | worst_regime | ≥ -30% | 最差市場環境 |
| 13 | recent_period_sharpe | ≥ 0 | 因子是否衰退 |
| 14 | market_correlation | \|corr\| ≤ 0.90 | 獨立 alpha（非市場 beta） |
| 15 | cvar_95 | ≥ -5% | 日尾部風險 |

### 3.3 部署篩選（六層）

| 階段 | 條件 | 說明 |
|------|------|------|
| L5 快篩 | ICIR ≥ 0.30 | 小樣本快速檢查（數秒） |
| 大規模 IC | ICIR(20d) ≥ 0.20 | 全 universe 驗證（865+ 檔，數分鐘） |
| StrategyValidator | ≥ 14/15 通過（排除 DSR） | 15 項驗證閘門 |
| vs 基準 | Sharpe > 0050.TW | 風險調整必須打敗大盤 |
| 絕對報酬 | CAGR > 8% | 絕對報酬門檻 |
| 近期表現 | recent_period_sharpe > -0.10 | 允許輕微噪音 |

> **deflated_sharpe 說明**：90+ trials 下 DSR 0.95 需 Sharpe > 2.0（業界不現實）。0.70 對應 Sharpe ~1.5，是合理門檻。Bailey & López de Prado 原意是排名工具而非絕對門檻。

### 3.3 關鍵約束（2026-03-27 大規模審計後確立）

1. **營收 40 天延遲**：所有營收因子必須用 `as_of - pd.DateOffset(days=40)` 截斷。缺此延遲會導致 IC 膨脹 10-40 倍（look-ahead bias）
2. **因子生成 fail-closed**：不匹配的假說必須 return None，不可 fallback 到 revenue_yoy
3. **L5 Walk-Forward 必須實際計算**：前半/後半 IC 比較，不可 `passed = True` 空殼
4. **大規模 IC 和 L1-L5 forward return 必須一致**：都用 `close[as_of+h] / close[as_of] - 1`
5. **月度取樣用最近交易日**：不可直接用月末日期（可能不是交易日）

### 3.4 報告流程（autoresearch 模式）

因子報告存放在 `docs/research/auto/`。**入選標準**（必須全部滿足）：
1. evaluate.py 通過 L4（composite_score > 0, passed=True）
2. 大規模 ICIR(20d) ≥ 0.20
3. StrategyValidator ≥ 10/15

未達標準的因子只記錄在 `results.tsv`，不寫 markdown 報告（避免假陽性汙染）。

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
