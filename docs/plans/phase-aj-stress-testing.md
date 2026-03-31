# Phase AJ：壓力測試 — 金融情景 + 成本敏感度 + 韌性驗證

> 狀態：📋 設計完成，待開發
> 前置：Phase AD（數據平台）✅、Phase AI（運營架構）✅
> 日期：2026-03-31

---

## 1. 目的

回測告訴你策略在「正常市場」表現如何。壓力測試告訴你在「最壞情況」會虧多少。

Paper trading 跑了 10 天，4/11 即將再平衡。在用真金白銀之前，需要知道：
- 台股連續跌停時，策略最大虧損是多少？
- 交易成本翻倍時，策略還賺錢嗎？
- 持倉高度相關時（2020 三月），分散化會失效嗎？
- 系統某個環節故障時，會不會自動做出錯誤決策？

---

## 2. 現有能力

| 能力 | 位置 | 狀態 |
|------|------|:----:|
| 歷史情景回測 | `POST /backtest/stress-test` | ✅ 但缺台股特有情景 |
| Walk-Forward | `POST /backtest/walk-forward` | ✅ |
| PBO（過擬合概率） | `POST /backtest/pbo` | ✅ |
| Kill Switch（5% DD） | `src/risk/kill_switch.py` | ✅ |
| Quality Gate（數據異常） | `src/data/quality_gate.py` | ✅ |
| 因子衰退偵測 | Phase AG AlertManager | ✅ |

---

## 3. 壓力測試設計

### 3.1 金融壓力測試（最高優先）

#### A. 台股歷史極端事件

| 情景 | 時間 | 特徵 | 測試什麼 |
|------|------|------|---------|
| **2008 金融海嘯** | 2008-09 ~ 2009-03 | 台股跌 46%，連續跌停 | MDD、Kill Switch 是否及時 |
| **2015 中國股災** | 2015-06 ~ 2015-08 | 急跌 28%，融資斷頭潮 | 流動性衝擊、margin call 連鎖 |
| **2018 中美貿易戰** | 2018-10 ~ 2018-12 | 外資大量賣超 | 法人面因子是否反轉 |
| **2020 COVID** | 2020-02 ~ 2020-03 | 跌 30% 後 V 轉 | 空頭偵測假陽性（hedged 策略可能過早減倉） |
| **2021 五月本土疫情** | 2021-05 | 單週跌 8.5%，融資使用率驟降 | 短期衝擊恢復能力 |
| **2022 升息+通膨** | 2022-01 ~ 2022-10 | 緩慢下跌 25%，成長股重挫 | 營收因子在熊市的表現 |

> FinLab 數據覆蓋 2007-2018，可以測 2008 和 2015。
> Yahoo 數據覆蓋 2015-2026，可以測所有 2015 之後的事件。

#### B. 合成極端情景

| 情景 | 方法 | 測試什麼 |
|------|------|---------|
| **連續跌停 5 天** | 持倉全部每天 -10% | Kill Switch 在第幾天觸發？最終虧多少？ |
| **Flash crash** | 單日 -15% 後隔天 +10% | 策略是否在最低點被迫賣出？ |
| **流動性枯竭** | volume 降為正常的 10% | 滑價模型的成本膨脹多少？能成交嗎？ |
| **外資連續賣超 30 天** | institutional_net 全為負 | 法人因子信號完全反轉時的行為 |
| **營收全面衰退** | 全 universe revenue YoY < 0 | 營收因子失效時策略怎麼辦？ |

#### C. 成本敏感度分析

```python
# 基準成本
commission = 0.1425%
sell_tax = 0.3%
slippage = 5bps

# 壓力情景
scenarios = {
    "base":     {"commission": 0.1425, "tax": 0.3, "slippage": 5},
    "2x_cost":  {"commission": 0.285,  "tax": 0.3, "slippage": 10},
    "3x_slip":  {"commission": 0.1425, "tax": 0.3, "slippage": 15},
    "day_trade": {"commission": 0.1425, "tax": 0.15, "slippage": 5},  # 當沖減稅
    "worst":    {"commission": 0.285,  "tax": 0.3, "slippage": 20},
}

# 每個情景跑完整回測，比較 Sharpe 和 CAGR
```

**核心問題**：策略的 alpha 有多少被交易成本吃掉？成本翻倍後還有正報酬嗎？

#### D. 相關性壓力測試

```python
# 正常時期：持倉間 pairwise correlation ~0.3
# 壓力時期（2020-03）：correlation 飆升到 ~0.8

# 測試：
# 1. 計算歷史上持倉相關性最高的時期
# 2. 在那些時期的 portfolio volatility 和 MDD
# 3. 分散化收益（diversification ratio）在壓力時是否崩塌
```

### 3.2 工程韌性測試（中優先）

| 測試 | 方法 | 預期行為 |
|------|------|---------|
| **數據源全部故障** | Mock Yahoo/FinMind/TWSE 回傳空 | Quality Gate BLOCK + Discord 通知 |
| **Pipeline 中途崩潰** | 在 execute_from_weights 中 raise | Pipeline 標記 failed + 下次重跑 |
| **磁碟寫入失敗** | Mock parquet write 拋異常 | 原子寫入不損壞現有檔案 |
| **Portfolio JSON 損壞** | 寫入亂碼到 portfolio_state.json | Startup 偵測 + 使用 backup |
| **Trade ledger 斷電** | Kill process after intent, before fill | 重啟後偵測 unmatched intents |
| **Discord webhook 失敗** | Mock notifier.send 拋異常 | 不影響交易流程（通知是 best-effort） |

### 3.3 參數敏感度（低優先）

| 參數 | 範圍 | 目的 |
|------|------|------|
| max_holdings | 5, 10, 15, 20 | 持股集中度 vs 分散化 |
| rebalance_frequency | daily, weekly, monthly | 頻率 vs 交易成本 |
| revenue_lookback | 3m, 6m, 12m | 營收因子窗口敏感度 |
| hedge_threshold | 0.3, 0.5, 0.7 | 空頭偵測靈敏度 |
| kill_switch_dd | 3%, 5%, 8% | 停損寬鬆度 |

---

## 4. 實作方式

### 4.1 壓力測試框架

```python
# src/backtest/stress.py

@dataclass
class StressScenario:
    name: str
    start: str
    end: str
    description: str
    # Optional overrides
    commission: float | None = None
    slippage_bps: float | None = None
    synthetic: bool = False  # True = 合成情景
    price_modifier: Callable | None = None  # 修改價格的函式

TW_STRESS_SCENARIOS = [
    StressScenario("2008_financial_crisis", "2008-09-01", "2009-03-31", "金融海嘯"),
    StressScenario("2015_china_crash", "2015-06-01", "2015-08-31", "中國股災"),
    StressScenario("2020_covid", "2020-02-01", "2020-04-30", "COVID 崩盤"),
    StressScenario("2022_rate_hike", "2022-01-01", "2022-10-31", "升息通膨"),
    StressScenario("limit_down_5d", ..., synthetic=True, price_modifier=...),
]

async def run_stress_suite(strategy, scenarios) -> StressReport:
    """跑所有壓力情景，生成報告。"""
```

### 4.2 成本敏感度分析

```python
# src/backtest/cost_sensitivity.py

async def cost_sensitivity_analysis(
    strategy, universe, start, end,
    cost_scenarios: dict[str, dict],
) -> pd.DataFrame:
    """多組成本參數跑回測，比較結果。
    Returns DataFrame: scenario → (sharpe, cagr, mdd, cost_ratio)
    """
```

### 4.3 相關性壓力分析

```python
# src/backtest/correlation_stress.py

def correlation_regime_analysis(
    portfolio_symbols: list[str],
    start: str, end: str,
) -> dict:
    """分析持倉相關性的時間變化。
    找出相關性最高/最低的時期，計算 diversification ratio。
    """
```

---

## 5. 執行計畫

### Phase 1：台股歷史壓力測試（P0）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 1a | StressScenario 資料結構 + 6 個台股歷史情景 | `src/backtest/stress.py` |
| 1b | run_stress_suite 串接現有 BacktestEngine | `src/backtest/stress.py` |
| 1c | 合成情景（連續跌停、flash crash、流動性枯竭） | `src/backtest/stress.py` |
| 1d | 壓力測試報告生成（markdown） | `src/backtest/stress.py` |
| 1e | CLI 入口 `python -m src.backtest.stress` | `src/backtest/stress.py` |

### Phase 2：成本敏感度 + 相關性分析（P1）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 2a | 成本敏感度（5 組參數 × 完整回測） | `src/backtest/cost_sensitivity.py` |
| 2b | 相關性時變分析（rolling correlation） | `src/backtest/correlation_stress.py` |
| 2c | 參數敏感度網格（max_holdings × rebalance_freq） | 擴展 `POST /backtest/grid-search` |

### Phase 3：工程韌性測試（P2）

| 步驟 | 內容 | 檔案 |
|------|------|------|
| 3a | 數據故障情景測試 | `tests/integration/test_data_failure.py` |
| 3b | Pipeline 崩潰恢復測試 | `tests/integration/test_crash_recovery.py` |
| 3c | Trade ledger 斷電測試 | `tests/integration/test_ledger_replay.py` |

---

## 6. 成功標準

| 指標 | 目標 |
|------|------|
| 6 個歷史情景全部有結果 | MDD 和 Kill Switch 觸發時間已知 |
| 成本 2x 後 Sharpe | > 0（還有正報酬） |
| 連續跌停 5 天 MDD | 已知，且 Kill Switch 在 Day 1-2 觸發 |
| 相關性壓力時 diversification ratio | 已量化，知道分散化何時失效 |
| 工程測試覆蓋 | Quality Gate + 原子寫入 + ledger replay 全通過 |

---

## 7. 不做的事

| 項目 | 原因 |
|------|------|
| Monte Carlo 模擬 | 有 PBO + bootstrap 已足夠 |
| API 負載測試（locust/k6） | 單人系統，不需要 |
| 跨市場壓力（外匯衝擊） | 只做台股，暫不考慮 |
| 逐筆撮合壓力 | 日頻策略不需要 tick-level |

---

## 8. 產出物

1. **壓力測試報告** — `docs/research/stress_test_report.md`
2. **成本敏感度表** — 策略在不同成本下的 Sharpe/CAGR
3. **相關性分析圖** — 持倉 rolling correlation heatmap
4. **風險邊界** — 已知「策略在 X 情景下最多虧 Y%」

---

## 9. 嚴格審批（2026-04-01）

### 判定：✅ 設計合理，範圍正確。2 個事實修正 + 1 個範圍確認。

---

### 事實修正

**1. `src/backtest/stress_test.py` 已存在，計畫未提及**

已有 `StressScenario` dataclass + 4 個 modifier（bear_market、high_volatility、flash_crash、regime_change）+ `run_stress_test()` + `ALL_SCENARIOS` + API endpoint `POST /backtest/stress-test`。

計畫 §4.1 提出新建 `src/backtest/stress.py`，但 `stress_test.py` 已有同樣的架構。應該是**擴展現有的 `stress_test.py`**（加台股歷史情景），不是新建。

**修正**：Phase 1 的 1a-1e 改為擴展 `stress_test.py`，加入 `TW_STRESS_SCENARIOS`（歷史日期區間）+ 合成情景。

**2. §7 「Monte Carlo — 有 PBO + bootstrap 已足夠」需要更精確**

PBO 測的是過擬合概率，bootstrap 測的是 Sharpe 置信區間。兩者都不做「未來路徑模擬」。Monte Carlo 的價值是回答「如果未來 1000 種可能走勢，策略虧超過 X% 的概率是多少」。

但對月頻策略，歷史壓力情景（§3.1A 的 6 個事件）已經涵蓋了最差情境，比 Monte Carlo 的隨機路徑更有經濟意義。所以不做 Monte Carlo 的結論正確，但理由應改為「歷史情景比隨機路徑更有金融意義」而非「PBO 已足夠」。

---

### 範圍確認：不需要另外考慮

**Monte Carlo 模擬** — 不做。理由如上。6 個真實歷史事件 + 5 個合成極端情景 > 隨機路徑。

**訂單流程測試** — 已在 Phase AK-2 覆蓋。`test_pipeline_integration.py` 有 18 個 test 驗證 strategy → weights → orders → risk → broker → apply_trades。Phase AJ 不需重複。

**風控測試** — 已有：
- `test_risk.py`（12 tests）：max_position_weight（MODIFY capping）、fat_finger、max_notional
- `test_pipeline_integration.py`：kill switch detection、concentrated position rejection
- Phase AJ §3.1B 的「連續跌停 5 天」本身就是風控壓力測試（驗證 Kill Switch 觸發時機）

這三項都不需要在 Phase AJ 額外考慮。Phase AJ 專注**金融情景壓力**和**成本敏感度**是正確的範圍。

---

### §3.2 工程韌性測試 → 搬到 Phase AK-6

Phase AJ §3.2 的 6 個工程測試（數據故障、pipeline 崩潰、磁碟寫入失敗等）和 Phase AK-6 韌性測試完全重疊。不應在兩個 Phase 重複。

**建議**：Phase AJ 刪除 §3.2 和 Phase 3（步驟 3a-3c）。這些歸 Phase AK-6。Phase AJ 只做金融壓力（Phase 1-2）。

---

### 做得好的部分

1. **§3.1A 的 6 個台股歷史事件**選擇精準 — 涵蓋急跌（2008/2015/2020）、緩跌（2022）、V 轉（2020）、外資主導（2018）
2. **§3.1B 合成情景**覆蓋了歷史未出現但合理的極端（連續跌停、流動性枯竭）
3. **§3.1C 成本敏感度**是最被低估的測試 — 很多策略回測好看但成本一扣就虧
4. **§6 成功標準**具體可驗證 — 不是「表現良好」而是「成本 2x 後 Sharpe > 0」
5. **§7 不做的事**全部正確

---

### 實作改善（2026-04-01 補充）

**6. 新增「因子失效壓力」測試**

計畫測市場壓力（跌停、成本），但沒測因子本身失效。revenue_acceleration（成長）和 per_value（價值）理論上互補，但 2022 成長股重挫時可能同時反轉。新增：
- 單獨回測 2022-01 ~ 2022-10 看雙因子 composite 行為
- 計算 composite factor IC 在每個壓力期是否變負
- 納入 §3.1A 情景的因子層級診斷（不只看 portfolio MDD，也看 IC 方向）

**7. §3.3 參數敏感度改為聚焦 2-3 個關鍵參數**

5 參數 × 4 值 = 1024 組合不可行。只測 `max_holdings × rebalance_frequency`（2 參數 × 4 值 = 16 組合），其他參數固定。省時且抓到最大影響。

**8. 所有壓力測試加 0050.TW benchmark 對比**

壓力結果必須跟 0050.TW 比。「策略跌 25%」不代表差 — 如果 0050 跌 30%，策略跑贏 5%。每個情景的報告加一行 benchmark MDD / return。

**9. §3.2 工程韌性測試移除（歸 Phase AK-6）**

Phase AJ 只做金融壓力（Phase 1-2）。§3.2 的 6 個工程測試和 Phase AK-6 完全重疊，刪除避免重複。Phase 3（步驟 3a-3c）一併移除。

**10. 擴展現有 `stress_test.py` 而非新建**

`src/backtest/stress_test.py` 已有 StressScenario + 4 個 modifier + `run_stress_test()` + API endpoint。Phase 1 改為擴展此檔，加入 TW_STRESS_SCENARIOS。
