# 回測真實性檢查清單

> 目標：縮小回測與實盤的差距（Quantopian 888 策略 R² < 0.025 的教訓）
> 最後審查：2026-03-28

---

## 已實作 ✅

| 項目 | 實作位置 | 說明 |
|------|---------|------|
| 手續費 0.1425% | `BacktestConfig.commission_rate` | 雙向收費 |
| 證交稅 0.3%（賣出） | `BacktestConfig.tax_rate` | 台股特有，SimBroker 只在 SELL 時收 |
| 滑點 5 bps | `BacktestConfig.slippage_bps` | 預設固定滑點 |
| √ 市場衝擊 | `impact_model="sqrt"` | 大單成交價格不利（SimBroker） |
| T+1 執行延遲 | `execution_delay=1` | 訊號日 T，成交日 T+1 開盤價 |
| Kill Switch 5% | 日度 drawdown > 5% 停止 | 防崩盤 |
| 月度再平衡 | `rebalance_freq="monthly"` | 每月只交易一次 |
| 風控 12+ 條規則 | `RiskEngine` | max position / sector / drawdown / fat finger |
| 空頭偵測 | `composite_b0%` | Bear 時 0% 倉位 |
| 營收 40 天延遲 | `Context.get_revenue` + `evaluate.py` | 營收公布延遲，策略和評估層都強制截斷 |
| 10% ADV 成交量限制 | `weights_to_orders` | 單筆委託不超過日均量 10% |
| 整張交易 | `fractional_shares=False` + `market_lot_sizes={".TW": 1000}` | Validator 使用，反映台股實際交易單位 |
| DSR / PBO / Harvey 修正 | StrategyValidator + factor_evaluator | 多重檢定偏差防護（三層） |
| 倖存者偏差偵測 | `detect_survivorship_bias()` | 掃描資料產出警告（非修正） |

## 部分實作 🟡

### 1. 漲跌停限制（台股 ±10%）

**現狀**：SimBroker 有兩層：
- 流動性檢查（**永遠開啟**）：漲幅 ≥ 9.5% 拒絕買單，跌幅 ≤ -9.5% 拒絕賣單
- 價格上下限（**預設關閉**）：`price_limit_pct=0.0`，需設為 0.10 才啟用 ±10%

**問題**：Validator 的 `_make_bt_config` 沒有設 `price_limit_pct`，所以價格面的硬限制是關閉的。

**建議**：Validator config 加 `price_limit_pct=0.10`（台股預設）。影響估計：營收暴增股常漲停，CAGR 可能下降 2-5%。

### 2. 除權息處理

**現狀**：`enable_dividends=False`（預設關閉）。代碼有完整的除息注入邏輯（`_inject_dividends_impl`），但 Yahoo 的 adjusted price 已經反映除息 — **開啟會 double-count**。

**問題**：要正確模擬除權息需要 raw（未調整）價格。目前用 adjusted price，除息效果已隱含在價格變動中，所以不開啟反而更正確。

**結論**：**當前行為（不開啟）在使用 adjusted price 時是正確的。** 文件中標記為「已處理」，但方式是「隱含在 adjusted price 中」而非「顯式模擬」。

### 3. 倖存者偏差

**現狀**：`detect_survivorship_bias()` 產出警告寫入 `survivorship_warnings`，但不影響回測結果。

**問題**：Yahoo Finance 只有現在還上市的股票。已下市股票（破產、被收購）不在 universe 中。文獻估計影響 3-8%。

**修正需要**：含已下市股票的歷史資料（FinMind 付費方案或 TEJ）。目前無法取得。

**緩解**：
- 偵測函數已就位（會警告有多少股票中途消失）
- 使用大 universe（865+ 支）降低個別下市的影響
- Validator 的 OOS 期間是最近 1.5 年，倖存者偏差較小

## 未實作 ❌

### 4. 交易時段外的訊號

**問題**：營收可能在盤後/盤前公布。策略在 on_bar 收盤時讀到營收，但實盤中盤後公布的營收要等到隔天才能交易。

**影響**：`execution_delay=1`（T+1 執行）部分緩解了這個問題 — 訊號日和成交日已分開。但沒有模擬「盤中 vs 盤後公布」的差異。

**嚴重度**：低。40 天營收延遲已經是保守的（台灣月營收在次月 10 日前公布，40 天延遲比實際更保守）。加上 T+1 執行，訊號時序偏差的影響很小。

---

## 優先級排序（更新）

| # | 項目 | 實現狀態 | 剩餘工作 | 影響 | 優先級 |
|---|------|:--------:|---------|------|:------:|
| 1 | 營收公布延遲 | ✅ 完成 | — | — | — |
| 2 | 成交量限制 | ✅ 完成 | — | — | — |
| 3 | 整張交易 | ✅ 完成 | — | — | — |
| 4 | Selection bias | ✅ 完成 | — | — | — |
| 5 | 漲跌停限制 | 🟡 部分 | Validator 加 `price_limit_pct=0.10` | CAGR -2~5% | **P1** |
| 6 | 除權息 | 🟡 隱含 | 目前用 adjusted price 是正確的 | — | **可接受** |
| 7 | 倖存者偏差 | 🟡 偵測 | 需要含下市股票資料 | 3-8% | **P2**（需外部資料） |
| 8 | 盤後訊號 | ❌ | T+1 已部分緩解 | 極小 | **P3**（低優先） |

**結論**：8 項中 4 項完全實作，2 項部分實作但可接受，1 項有偵測無修正（需外部資料），1 項未實作但影響極小。最有價值的剩餘改進是 #5 漲跌停（加一個參數即可）。
