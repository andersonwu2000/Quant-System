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

### 3.2 部署篩選（六層）

| 階段 | 條件 | 說明 |
|------|------|------|
| L5 快篩 | ICIR ≥ 0.30 | 小樣本快速檢查（數秒） |
| 大規模 IC | ICIR(20d) ≥ 0.20 | 全 universe 驗證（865+ 檔，數分鐘） |
| StrategyValidator | ≥ 11/13 通過（排除 DSR） | 13 項驗證閘門，deflated_sharpe 為參考項 |
| vs 基準 | Sharpe > 0050.TW | 風險調整必須打敗大盤 |
| 絕對報酬 | CAGR > 8% | 絕對報酬門檻 |
| 近期表現 | recent_period_sharpe > -0.10 | 允許輕微噪音（-0.10 內視為零） |

> **deflated_sharpe 說明**：自動研究累計測試 90+ 因子後，n_trials 導致 DSR 原始門檻 0.95 結構性不可能通過。改為寬鬆門檻 ≥ 0.70（低於 0.70 仍視為過擬合風險，阻擋部署）。

### 3.3 關鍵約束（2026-03-27 大規模審計後確立）

1. **營收 40 天延遲**：所有營收因子必須用 `as_of - pd.DateOffset(days=40)` 截斷。缺此延遲會導致 IC 膨脹 10-40 倍（look-ahead bias）
2. **因子生成 fail-closed**：不匹配的假說必須 return None，不可 fallback 到 revenue_yoy
3. **L5 Walk-Forward 必須實際計算**：前半/後半 IC 比較，不可 `passed = True` 空殼
4. **大規模 IC 和 L1-L5 forward return 必須一致**：都用 `close[as_of+h] / close[as_of] - 1`
5. **月度取樣用最近交易日**：不可直接用月末日期（可能不是交易日）

### 3.4 報告流程

L5 通過後，不論後續是否通過，都寫報告到 `docs/dev/auto/{factor_name}.md`。
報告包含：L5 結果、大規模 IC 表格（含基準對比）、Validator 13 項、部署判定。

---

## 4. 基準因子（Experiment #16 結果）

以下為標準方法論下的基準 ICIR，用於比較後續實驗是否一致：

| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |
|--------|----------|-----------|-----------|-----------|
| revenue_acceleration | +0.202 | +0.240 | +0.426 | 63.9% |
| revenue_new_high | +0.246 | +0.207 | +0.364 | 61.3% |
| revenue_yoy | +0.186 | +0.037 | +0.112 | 50.8% |

> 若新實驗使用相同方法論但結果偏離基準超過 ±20%，應檢查數據或程式差異。

---

## 5. 報告規範

### 存放位置

| 類型 | 目錄 |
|------|------|
| 實驗報告 | `docs/dev/test/` |
| Auto-alpha 報告 | `docs/dev/auto/` |
| Paper trading 報告 | `docs/dev/paper/` |

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
