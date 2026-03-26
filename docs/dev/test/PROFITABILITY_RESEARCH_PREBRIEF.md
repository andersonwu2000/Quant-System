# 盈利能力研究預報

> **日期**: 2026-03-26
> **目標**: 系統性驗證系統是否具備統計顯著的盈利能力
> **方法**: Bug 檢查 → 實驗框架 → 盈虧平衡分析 → 台股因子擴展
> **迭代**: 至少 3 輪

---

## 1. 前次回測發現（Round 0 基線）

### 1.1 因子淨 Alpha 掃描結果

| 指標 | 數值 |
|------|------|
| 測試因子數 | 19 |
| 正淨 Alpha 因子 | **2**（momentum, ma_cross）|
| 最佳淨 Alpha | +322 bps/年（momentum）|
| 最差淨 Alpha | -2,381 bps/年（alpha_53，換手率 85%）|

**結論**：Kakushadze 短期因子在台股大型股完全不可用（成本 > alpha）。僅低換手率因子（<6%）存活。

### 1.2 回測績效

| 期間 | 報酬 | Sharpe | DSR | Kill Switch |
|------|------|--------|-----|-------------|
| 2023H2-2024H1 | +24.9% | 2.27 | 0.32 | 無 |
| 2024H2-2025H1 | -16.0% | -1.42 | 0.001 | 觸發 2 次 |
| 完整 2 年 | +8.7% | 0.38 | **0.07** | 觸發 2 次 |

**DSR = 0.07 — 統計不顯著**（19 次試驗校正後）。MinBTL = 21,696 天。

### 1.3 已知問題

| # | 問題 | 影響 |
|---|------|------|
| B1 | Kill switch 觸發後策略完全停止，後續 NAV 只有現金 | 低估 recovery 後的潛在報酬 |
| B2 | DataQuality 將除權息日標記為異常並跳過 | 可能跳過重要交易日 |
| B3 | Period 2 win rate 31% vs Period 1 63%，差異過大 | 可能有 look-ahead bias |
| B4 | `construction.py` max_weight=5% 限制太嚴 | 50 檔 × 5% = 250% 總權重空間夠，但每檔太小不利集中 |

---

## 2. 研究計畫

### Phase T1：Bug 檢查（本輪）

系統性排查可能影響回測真實性的程式碼問題。

| # | 檢查項 | 檔案 | 方法 |
|---|--------|------|------|
| T1.1 | Kill switch 後 NAV 計算是否正確 | `backtest/engine.py` | 讀程式碼追蹤 kill switch 觸發後的控制流 |
| T1.2 | DataQuality 是否誤判除權息日 | `data/quality.py` | 用已知除權息日（如 2330.TW 2024-07-18）驗證 |
| T1.3 | Look-ahead bias 檢查 | `strategy/base.py`, `data/feed.py` | 確認 Context 時間截斷在 on_bar 之前 |
| T1.4 | weights_to_orders 是否正確處理零股 | `strategy/engine.py` | 用 fractional_shares=True 驗證轉換邏輯 |
| T1.5 | SimBroker 滑點模型是否合理 | `execution/broker/simulated.py` | 台股逐筆撮合，5bps 滑點是否偏低 |
| T1.6 | 手續費計算是否完整（含最低手續費 20 元） | `execution/broker/simulated.py` | 台灣券商單筆最低手續費 20 元 |
| T1.7 | forward returns 計算是否有 off-by-one | `strategy/research.py` | 驗證 horizon=5 是否正確跳 5 天 |
| T1.8 | rebalance 頻率是否如預期（daily 是否真的每天） | `backtest/engine.py` | 確認 rebalance_freq 參數生效 |

### Phase T2：實驗框架建立

建立可重複、可比較的多參數回測機制。

#### T2.1 參數空間（全組合窮舉）

| 維度 | 候選值 | 數量 |
|------|--------|------|
| **Universe** | TW50 / TW_MidCap_100 / TW_SmallCap_100 / TW_Full_300 | 4 |
| **Rebalance** | daily / weekly / biweekly / monthly / quarterly | 5 |
| **Holding period** | 1 / 5 / 10 / 20 / 40 / 60 | 6 |
| **因子組合** | momentum / ma_cross / mom+ma / mom+vol / mom+ma+vol / all_viable | 6 |
| **Max weight** | 3% / 5% / 10% / 15% / 20% | 5 |
| **Kill switch** | 3% / 5% / 10% / 關閉 | 4 |
| **Neutralization** | none / market / industry | 3 |
| **Construction** | equal_weight / signal_weight / risk_parity | 3 |

**總組合數**: 4 × 5 × 6 × 6 × 5 × 4 × 3 × 3 = **64,800**

> 每組回測約 30~60 秒，全跑需要 ~540~1,080 小時。
> 策略：先用 coarse grid（每維取 2~3 個代表值）篩選，再對有潛力的區域做 fine grid。

**Coarse grid（第一輪）**:

| 維度 | 候選值 | 數量 |
|------|--------|------|
| Universe | TW50 / TW_Full_300 | 2 |
| Rebalance | weekly / monthly | 2 |
| Holding period | 10 / 20 | 2 |
| 因子組合 | momentum / mom+ma+vol | 2 |
| Max weight | 5% / 15% | 2 |
| Kill switch | 5% / 關閉 | 2 |
| Neutralization | none / market | 2 |
| Construction | equal_weight / risk_parity | 2 |

**Coarse grid 總組合**: 2^8 = **256 組**，預估 ~2~4 小時可完成。

#### T2.2 回測期間（多期間驗證）

每組參數必須在**所有期間**上驗證，不允許只看一段：

| 期間 ID | 起訖 | 天數 | 市場特性 |
|---------|------|------|---------|
| P1 | 2020-01-01 ~ 2021-06-30 | 380 | COVID 崩盤 + V 型反彈 |
| P2 | 2021-07-01 ~ 2022-12-31 | 380 | 台股萬八 → 熊市 |
| P3 | 2023-01-01 ~ 2024-06-30 | 380 | AI 概念牛市 |
| P4 | 2024-07-01 ~ 2025-06-30 | 250 | 震盪 + 關稅衝擊 |
| FULL | 2020-01-01 ~ 2025-06-30 | 1390 | 完整 5.5 年 |

**一致性要求**：
- 策略必須在 **≥3 個子期間** Sharpe > 0 才算穩定
- 任一子期間 MaxDD > 30% 直接淘汰
- FULL 期間 Sharpe 作為最終排名依據

#### T2.3 基準比較

| Benchmark | 說明 | 取得方式 |
|-----------|------|---------|
| 0050.TW 買入持有 | 台灣50 ETF | Yahoo Finance |
| 等權 Universe 月度 rebalance | 同一 universe 等權 | 回測引擎 (1/N strategy) |
| 純現金 | 年化 1.5% | 固定值 |
| 0056.TW 買入持有 | 高股息 ETF | Yahoo Finance |

**超額報酬計算**：`alpha = strategy_return - benchmark_return`，必須 > 0。

#### T2.4 統計校正

每組實驗必須報告：

| 指標 | 門檻 | 說明 |
|------|------|------|
| Sharpe Ratio | > 0.5 | 年化，無風險利率 1.5% |
| Deflated Sharpe | > 0.95 | 校正 **全部實驗次數**（coarse 256 + fine N） |
| PBO | < 0.50 | 非過擬合 |
| vs 0050 超額 | > 0% p.a. | 扣除成本後 |
| 跨期一致性 | ≥3/4 期間 Sharpe > 0 | 穩定性 |
| MaxDD | < 25% | 任一期間 |
| 年化成本 | < gross alpha × 0.5 | 成本效率 |
| Calmar | > 0.5 | 報酬/回撤比 |
| 年化換手率 | < 300% | 可執行性 |

#### T2.5 實作

新增 `src/backtest/experiment.py`：

```python
@dataclass
class ExperimentConfig:
    name: str
    universe: list[str]
    strategy_config: AlphaConfig
    backtest_config: BacktestConfig
    benchmark: str  # "0050.TW" or "equal_weight"

@dataclass
class PeriodConfig:
    period_id: str
    start: str
    end: str
    description: str

@dataclass
class ExperimentResult:
    config: ExperimentConfig
    period_results: dict[str, BacktestResult]  # period_id → result
    benchmark_results: dict[str, float]        # period_id → benchmark return
    deflated_sharpe: float
    passes_criteria: bool
    rejection_reason: str  # "" if passes

def run_experiment_grid(
    configs: list[ExperimentConfig],
    periods: list[PeriodConfig],
    n_workers: int = 4,       # 並行回測數
    total_trials: int | None = None,  # DSR 校正用的總實驗次數
) -> pd.DataFrame:
    """批量執行全組合回測，返回比較表。

    每個 config × 每個 period 各跑一次回測。
    自動計算 DSR、跨期一致性、vs benchmark 超額報酬。
    """

def generate_coarse_grid() -> list[ExperimentConfig]:
    """產生 coarse grid 的 256 組配置。"""

def generate_fine_grid(top_configs: list[ExperimentConfig]) -> list[ExperimentConfig]:
    """根據 coarse grid 結果，對有潛力的區域做 fine grid。"""

def summarize_results(results: pd.DataFrame) -> str:
    """產生人類可讀的實驗摘要報告。"""
```

#### T2.6 結果輸出

每輪實驗產出：
1. `docs/dev/test/round_N_results.csv` — 全部結果表格
2. `docs/dev/test/round_N_summary.md` — 摘要報告（top 10 配置 + 淘汰分析）
3. `docs/dev/test/round_N_figures/` — 績效曲線圖（optional）

### Phase T3：盈虧平衡分析

回答核心問題：**在台股的費用結構下，因子需要多強才能盈利？**

| 費用項 | 數值 | 說明 |
|--------|------|------|
| 手續費（買） | 0.1425% | 可打折至 0.06%（網路下單折讓） |
| 手續費（賣） | 0.1425% | 同上 |
| 證交稅（賣） | 0.30% | 不可減免（ETF 為 0.1%） |
| 最低手續費 | NT$20/筆 | 零股小額交易影響大 |
| **單邊總成本** | **~0.44%** | 買+賣合計 ~0.88% per round-trip |

盈虧平衡計算：
- 月 rebalance（12 次/年）× 50% 換手率 × 0.88% = **5.28% 年化成本**
- 週 rebalance（52 次/年）× 20% 換手率 × 0.88% = **9.15% 年化成本**
- 日 rebalance × 5% 換手率 × 0.88% = **11.4% 年化成本**

**因子 alpha 必須超過成本才能盈利。** Momentum 的 gross alpha ~498 bps = 4.98%，扣除月 rebalance 成本 5.28%，**淨值為負**。

→ 需要更低的 rebalance 頻率（biweekly/monthly）或更高的 alpha（中小型股）。

### Phase T4：台股特有因子（第 2~3 輪）

| 因子 | 數據源 | 預期效果 |
|------|--------|---------|
| 外資買超/賣超 | FinMind `TaiwanStockInstitutionalInvestorsBuySell` | 外資持續買超 → 價格動量（台股特有） |
| 融資融券餘額變化 | FinMind `TaiwanStockMarginPurchaseShortSale` | 融資增 = 散戶追漲信號（反向） |
| 三大法人買賣超 | FinMind `TaiwanStockInstitutionalInvestorsBuySell` | 投信連續買超 = 基金經理人 alpha |
| 董監持股變化 | FinMind `TaiwanStockShareholding` | 內部人減持 = 負面信號 |

---

## 3. 迭代計畫

```
Round 1（本輪）
  T1: Bug 檢查 → 修復 → 重新回測確認基線

Round 2
  T2: 建立實驗框架 → 跑參數 grid → 找到最佳配置
  T3: 盈虧平衡分析 → 確定可行的 rebalance 頻率

Round 3
  T4: 加入台股因子 → 重跑實驗 → 比較改善
  統計驗證: DSR + PBO + vs-benchmark t-test
```

---

## 4. 成功標準

| 指標 | 門檻 | 說明 |
|------|------|------|
| Deflated Sharpe | > 0.95 | 校正後 95% 信心水準 |
| vs 0050.TW 超額報酬 | > 0% | 扣除成本後跑贏 ETF |
| PBO | < 0.50 | 非過擬合 |
| 兩段期間一致性 | 兩段 Sharpe 同號 | 非只在一段有效 |
| 年化成本 | < gross alpha × 0.5 | 成本不超過 alpha 的一半 |

---

## 5. 風險與假設

| 風險 | 緩解 |
|------|------|
| 台股大型股（TW50）alpha 本質很弱 | 擴大到中小型股 |
| 2 年數據太短 | 用 Yahoo Finance 拉 5 年以上 |
| 存活者偏差 | 系統已有 survivorship_bias 偵測 |
| Kill switch 過度保守 | 測試不同閾值（3%/5%/10%/off）|
| 手續費模型不完整（缺最低 20 元） | T1.6 修復 |
