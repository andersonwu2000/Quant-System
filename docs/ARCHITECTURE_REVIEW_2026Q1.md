# 架構審查報告 — 2026 Q1

> 日期：2026-03-27
> 範圍：全系統（Backend + Pipeline + Risk + Research）
> 觸發：Paper Trading 準備階段的全面代碼審查
> 作者：Claude Code 自動化審查

---

## 1. 審查統計

| 項目 | 數值 |
|------|------|
| 審查涵蓋模組 | 引擎、風控、回測、管線、因子研究、Paper Trading |
| 發現並修復 bug | **88+** |
| 測試數（修復後） | **1,725** |
| 全量測試通過率 | 100%（排除 Sinopac 外部依賴） |

### 按類別分佈

| 類別 | 數量 | 範例 |
|------|:----:|------|
| 公式與計算 | 9 | CAGR off-by-one、DSR kurtosis double correction |
| Look-Ahead Bias | 8 | 營收 40 天延遲缺失（影響所有因子 IC） |
| 風控 | 12 | enum 比較脆弱、批次無累積效應、kill switch 不清倉 |
| 管線與流程 | 14 | 因果鏈斷裂、hardcoded 日期、無 MarketState、舊持倉無法賣出 |
| 並發與狀態 | 7 | Portfolio race condition、crash 後重複再平衡 |
| 語義與數據 | 8 | 日期交集→空結果、PBO 方法學錯誤 |
| Paper Trading | 10 | 無滑價、NAV 凍結、時區混用 |
| 效能 | 1 | 因子計算 175K 次 IO → 快取後 4x 加速 |
| 代碼品質 | 19 | 類型標註、swallowed exceptions、dead code |

---

## 2. 架構問題

### 2.1 Portfolio 全局可變單例

**問題**：`state.portfolio` 是整個系統唯一的 Portfolio 物件，同時被 pipeline（apply_trades）、kill_switch（liquidation）、tick callback（update_market_prices）、API endpoint、risk engine、strategy 讀寫。

**現狀**：加了 `portfolio.lock`（threading.Lock），但只保護 dict 操作。`check_orders` 用 `deepcopy` 做 projected check，tick callback 可能在 submit 和 apply 之間改了 market_price。

**影響**：
- Risk check 時的 NAV 和 apply 時的 NAV 可能不同
- `deepcopy(Portfolio)` 需要自定義 `__deepcopy__`（因為 lock 不可 pickle）

**建議**：Portfolio 分離為 `PositionBook`（持倉紀錄，只在 apply_trades 時改）和 `Valuator`（即時估值，tick 更新）。Risk check 用 PositionBook 的 snapshot。

**優先級**：中（加了 lock 後暫時可用）

### 2.2 策略直讀檔案系統

**問題**：`revenue_momentum.py` 直接 `pd.read_parquet("data/fundamental/...")` 讀營收數據，繞過 `DataFeed` 抽象。回測時策略用 `Context.feed`（有時間因果保證），但營收數據靠策略自己做 40 天截斷。

**影響**：
- 換數據源要改策略代碼
- 回測和實盤的數據路徑可能不同
- 時間因果性不由框架保證，靠策略自己實作

**建議**：`FundamentalsProvider` 應該整合進 `Context`，策略透過 `ctx.get_revenue(symbol)` 取得已截斷的營收數據，不直接讀 parquet。

**優先級**：高（回測 vs 實盤不一致的根源）

### 2.3 回測引擎和實盤管線雙軌（已修）

**問題**：回測和實盤分別實作相同邏輯。

**修復**：Pipeline 改用 `execute_from_weights()`（`trading_pipeline.py`），和回測共用 `weights_to_orders` → `risk_engine.check_orders` → broker 路徑。風控 MarketState 已統一傳入。成本模型從 config 統一讀取。

**殘留**：execution_delay（回測支援 T+1，實盤即時成交）和數據源差異仍存在。

### 2.4 配置分散（部分修復）

**問題**：`commission_rate` 出現在 6 個 config dataclass 裡。

**已修**：`ExecutionConfig` 從 `TradingConfig` 傳入費率，再傳給 `PaperBroker` 和 `SinopacConfig`。`default_rules()` 從 `TradingConfig` 讀門檻。

**殘留**：`BacktestConfig` 和 `SimConfig` 仍有各自的副本。完整的 `CostModel` 物件尚未實作。

### 2.5 自動因子代碼生成

**問題**：因子代碼是字串拼接生成的 Python 檔案，`importlib` 動態載入。每個因子自己讀 parquet（現在有模組級快取）。因子代碼和策略代碼用不同的數據路徑。

**影響**：
- 無法靜態分析
- 每個因子獨立 IO（快取減輕但不消除）
- 因子代碼的「正確性」靠測試而非型別系統

**建議**：中期改為 DSL（Domain Specific Language）定義因子，由框架統一載入數據和計算。短期保持現狀（字串模板 + 快取夠用）。

**優先級**：低（目前能用，重構投入大收益小）

### 2.6 無事件系統

**問題**：所有「事件」是直接函式呼叫。加新行為要改 pipeline 代碼。

**建議**：目前功能不多，直接呼叫夠用。等功能增多後再引入 event bus。

**優先級**：低

### 2.7 時間語義不統一

**問題**：系統混用 UTC、UTC+8、tz-naive datetime、帶 16:00:00 的 timestamp、`.date()` 正規化。

**已修**：RealtimeRiskMonitor 和 pipeline 的市場時段判斷改用 UTC+8。`_load_data` 正規化為 date-only。

**殘留風險**：新數據源如果時間格式不同，`index.intersection()` 可能為空。

**優先級**：中

### 2.8 Pipeline 只取 target 價格（已修）

**問題**：`execute_pipeline` 只取 `target_weights` 裡的股票價格，不取現有持倉的價格。`weights_to_orders` 對不在 target 的持倉股票產生 SELL 訂單時，因為 `price=0` 而跳過。**結果：舊持倉永遠賣不掉。**

**修復**：`all_needed = target_weights ∪ portfolio.positions`，兩邊的價格都取。

**影響**：修復前，Portfolio 會無限累積持倉（每月新增但不賣出舊的）。

### 2.9 風控門檻和策略權重衝突（已修）

**問題**：`default_rules` 改為從 config 讀取後，`max_position_pct=0.05`（5%）和策略 15 支等權（6.7%）衝突，導致 14/15 訂單被拒。

**修復**：`config.max_position_pct` 改為 0.10（10%）。

**教訓**：風控規則的門檻和策略的權重分配必須協調設計，不能獨立修改。

### 2.10 Shioaji Simulation Mode 限制（已修）

**問題**：Simulation mode 不推 tick，且 snapshot API 可能不可用。

**已修**：
- 偵測 `is_simulation` → 啟動 price polling（不再被跳過）
- ShioajiFeed snapshot 失敗 → fallback 到 Yahoo feed
- polling 間隔 60 秒，快取 feed 物件

**殘留**：Yahoo feed 只有收盤價，盤中 NAV 仍無法即時更新（需正式 Shioaji 帳號的 tick 推送）。

---

## 3. 重構計畫

### Phase U：回測/實盤統一

#### U1：統一 execution 路徑 ✅ 已完成

Pipeline 改用 `execute_from_weights()`（`src/core/trading_pipeline.py`），和回測共用 `weights_to_orders` → `risk_engine.check_orders` → `broker.execute/submit` 路徑。

#### U2：統一成本模型 ✅ 已完成

`ExecutionConfig` 加入 `commission_rate`、`tax_rate`、`default_slippage_bps`，從 `TradingConfig` 傳入。`SinopacConfig` 加入 `sim_commission_rate` 等欄位。所有 broker 從 config 讀費率。

#### U3：營收數據進 Context — 🔵 未執行

策略仍直接讀 parquet。需要在 Context 加入 `get_revenue()` 方法。

**預估**：1-2 小時

### Phase V：配置統一

#### V1：單一成本配置源 ✅ 部分完成

`ExecutionConfig` 加入成本欄位，從 `TradingConfig` 傳入 broker。但 `BacktestConfig` 和 `SimConfig` 仍有各自的副本。

#### V2：時間語義統一 ✅ 部分完成

Pipeline 和 RealtimeRiskMonitor 改用 UTC+8。但 parquet index、feed、strategy 仍混用。

### 未執行項目

| 項目 | 原因 | 狀態 |
|------|------|:----:|
| U3 營收數據進 Context | 需要改策略代碼 | 🔵 |
| V1 完整 CostModel 物件 | 需要刪除重複欄位 | 🔵 |
| V2 完整時間統一 | 涉及多模組 | 🔵 |
| Portfolio 分離 | lock 已夠用 | 不做 |
| 因子 DSL | 模板 + 快取夠用 | 不做 |
| Event bus | 直接呼叫夠用 | 不做 |

---

## 4. 執行狀態

### 已完成

| 項目 | 狀態 | 完成日期 | 說明 |
|------|:---:|---------|------|
| U2: 統一成本模型 | ✅ | 2026-03-27 | `CostModel` dataclass，`from_config()` single source |
| V1: 單一成本配置源 | ✅ | 2026-03-27 | PaperBroker/fallback 都用 CostModel |

### 待執行（按順序）

| 項目 | 優先級 | 預估 | 風險 | 保障措施 |
|------|:---:|:---:|------|---------|
| U1: 統一 execution 路徑 | ✅ 完成 | 5 步驟 | OrderExecutor Protocol + execute_from_weights | 1739 tests passed |
| U3: 營收數據進 Context | ✅ API 完成 | ctx.get_revenue() 已建 | 舊策略暫不遷移（漸進式） | 新策略用 ctx.get_revenue() |
| V2: 時間語義統一 | ⏳ 延後 | 2 hr | 中（涉及多模組 index） | 新代碼已統一 tz-naive，舊代碼漸進遷移 |

### 執行約束

1. **每個子項目前**：先在本文件更新「進行中」狀態
2. **每步 commit**：不做大批修改，每個邏輯改動獨立 commit
3. **改動前先跑 test**：確認基線通過
4. **改動後立即 test**：確認沒回歸
5. **風險高的改動**：先在 worktree 分支做，通過後再 merge
6. **完成後**：更新本文件為「已完成」

### Phase W：運營基礎設施（新增）

#### W1：假說生成器（Claude Code 驅動）

**問題**：自動研究 daemon 跑完所有模板假說後停滯。參數變體（zscore 12m/36m 等）只是微調，缺乏真正的新方向。

**目標**：第二個終端的 Claude Code 持續讀取研究結果，用推理能力生成新假說方向。

**架構**：
```
終端 1：alpha_research_agent --daemon
  → 跑因子 → 寫 memory.json → 假說用完 → sleep

終端 2：Claude Code（hypothesis_generator_prompt.txt）
  → 讀 memory.json → 推理 → 寫 hypothesis_templates.json + factor .py
  → 等 10 分鐘 → 讀新結果 → 重複
```

**實作項目**：
| 步驟 | 說明 | 狀態 |
|------|------|:---:|
| W1.1 | hypothesis_generator_prompt.txt（完整指令） | ✅ 已完成 |
| W1.2 | daemon --daemon 模式（無限循環 + 自動變體） | ✅ 已完成 |
| W1.3 | 因子 .py skip-if-exists（不覆寫外部寫入） | ✅ 已完成 |
| W1.4 | memory.json 清空機制 | ✅ 已完成 |
| W1.5 | 假說生成器的自動啟動腳本 | ✅ scripts/start_research.bat |

**預估**：W1.5 約 30 分鐘

#### W2：Paper Trading 監控儀表板

**問題**：Paper trading 運行後無法即時觀察績效，只能手動 curl API。需要自動化監控 + 定期報告。

**目標**：
1. 定時 NAV 快照 + 持倉追蹤
2. 績效 vs 0050 基準比較
3. 異常偵測（drawdown > 3%、NAV 偏離預期）
4. 每日/每週摘要報告

**架構**（已整合進 API Server）：
```
API Server 啟動（paper/live mode）
  → _monitoring_loop() asyncio task（每小時）
    → NAV 快照 → data/paper_trading/snapshots/
    → 異常偵測 → WebSocket broadcast + log
    → 14:00 每日報告 → docs/dev/paper/

scripts/paper_trading_monitor.py 保留為 CLI 工具（手動快照/報告）
```

**實作項目**：
| 步驟 | 說明 | 預估 |
|------|------|:---:|
| W2.1 | scripts/paper_trading_monitor.py — 輪詢 + 快照 | ✅ |
| W2.2 | 每日摘要報告生成（markdown） | ✅ |
| W2.3 | 績效 vs 0050 追蹤 | ✅ |
| W2.4 | 異常偵測 + 通知整合 | ✅ |
| W2.5 | --daemon 模式持續運行 | ✅ |

**預估**：約 3 小時

### 不重構項目（確認合理）

| 項目 | 原因 |
|------|------|
| Portfolio 分離 | lock 已夠用，分離代價大 |
| 因子 DSL | 字串模板 + 快取夠用 |
| Event bus | 功能不多，直接呼叫夠用 |

---

## 5. 已修復問題的完整清單

### 引擎（engine.py, oms.py）— 5 項

1. Kill switch cooldown 月底觸發只有 1 天 → 加最少 5 交易日
2. apply_trades sell overflow 可能產生負持倉 → cap + 警告
3. apply_trades docstring 說純函式但 mutate in-place → 修正
4. _get_prev_close 每 bar 重建 col_index → 用 cache
5. Portfolio.lock + apply_trades 使用 lock → 防 race condition

### 風控（rules.py, engine.py, realtime.py）— 16 項

6. order.side.value == "BUY" 脆弱 enum 比較 × 4 處
7. check_orders 無累積效應 → projected portfolio
8. max_daily_trades 在 check 時 increment → 改為 record_trade
9. max_gross_leverage SELL 對賣空不正確 → 區分減倉/賣空
10. default_rules 門檻硬編碼 10% → 從 config 讀
11. Kill switch 在實盤不清倉 → generate_liquidation_orders + ExecutionService
12. RealtimeRiskMonitor 無 thread safety → portfolio.lock
13. RealtimeRiskMonitor 無自動日期重置 → UTC+8 日期判斷
14. 無 post-trade 風控 → post_trade_check()
15. 無累計回撤限制 → max_cumulative_drawdown (20%)
16. 無行業集中度 → max_sector_concentration (40%)
17. MarketState 為空時所有市場規則失效 → log warning
18. 實盤 nav_sod 未設定 → pipeline 啟動時設
19. Kill switch liquidation 接上 ExecutionService
20. Price polling fallback for simulation mode
21. RealtimeRiskMonitor 用 UTC → UTC+8

### 回測（analytics.py, validator.py）— 6 項

22. CAGR n_days off-by-one → len(nav)-1
23. DSR kurtosis double correction → +3 轉換
24. Cost ratio 用 net return 當分母 → gross alpha
25. PBO 數據不足回傳 0（最樂觀）→ 1.0（最悲觀）
26. Validator 固定用零股 → 從 config 讀 + lot_sizes
27. OOS 日期和 IS 可能重疊 → 自動截斷

### 管線（jobs.py, scheduler/, service.py）— 12 項

28. 營收更新和再平衡靠 35 分鐘 cron gap → chained
29. --start 硬編碼 2024-01-01 → 動態 now-2yr
30. 三條路徑無互斥保證 → asyncio.Lock
31. execute_rebalance 空 portfolio 無 fallback → _get_tw_universe_fallback
32. 無 trade log → _save_trade_log
33. Pipeline 風控 check_order 未傳 MarketState → 傳入
34. Pipeline universe 只用現有持倉 → 全市場
35. _async_revenue_update 丟棄回傳值 → 接收
36. Trade log 在 apply_trades 後才存 → 之前存
37. 月度 idempotency 防 crash 重複再平衡
38. 市場時段檢查用 UTC+8
39. monthly_revenue_update 阻塞 event loop → asyncio.to_thread

### Paper Trading — 10 項

40. PaperBroker 無滑價 → 加 fixed bps
41. PaperBroker 費率硬編碼 → 從 config 讀
42. PaperBroker 不追蹤內部持倉 → 追蹤
43. 缺少價格的股票靜默跳過 → log warning
44. save_portfolio 缺 nav_sod → 加入
45. save_portfolio 缺 pending_settlements → 加入
46. save_portfolio 缺 as_of → 加入
47. Price polling 傳空 universe → 用 portfolio positions
48. Idempotency 阻止營收策略同日重跑 → 允許
49. NAV snapshot 時區 → UTC+8

### 系統性 — 7 項

50. Portfolio 讀寫 race condition → Portfolio.lock + __deepcopy__
51. Crash 後重複再平衡 → _has_completed_run_this_month
52. Trade log 在 apply_trades 後才存 → 之前存（crash recovery）
53. RealtimeRiskMonitor 時區混用 → UTC+8
54. Deprecated 代碼殘留 → 清理
55. Simulation mode polling fallback → 偵測 is_simulation
56. ShioajiFeed snapshot + Yahoo fallback for polling

### 因子研究 — 3 項

57. compute_forward_returns 日期交集→空 → 聯集
58. 因子計算 175K 次 read_parquet → 模組級快取（4x 加速）
59. Large-Scale IC divide by zero → guard base_price > 0

### 代碼品質 — 19 項（code review）

60-78. 類型標註、swallowed exceptions、assert safety、feed cache、redundant wraps、np.asarray 一致性等

### 實際運行發現 — 10 項

79. Pipeline 只取 target 價格 → 舊持倉無法賣出 → 取 target ∪ positions
80. 風控門檻 5% vs 策略 6.7% → 14/15 訂單被拒 → config 改 10%
81. ShioajiFeed snapshot 可能因 session timeout 靜默失敗 → 需 Yahoo fallback
82. Snapshots 目錄為空（asyncio task 重啟後消失）→ pipeline 後主動存
83. pipeline_runs 目錄不存在 → _execute_pipeline_inner 也寫紀錄
84. Selection/trade/reconciliation 無 run_id 關聯 → 所有 artifact 加 run_id
85. empty target_weights 直接 return → 改為關閉所有持倉
86. Large-Scale IC divide by zero（close=0 的下市股）→ guard base_price > 0
87. 因子計算 175K 次 read_parquet（430s/輪）→ 模組級快取（4x 加速，104s/輪）
88. pct_change FutureWarning → fill_method=None

---

## 6. 實驗結果摘要

### 大規模因子分析（實驗 #16）

- 874 支台股 × 54 價格因子：**全部不可行**（換手率 > 40%，成本 > 1300 bps）
- 855 支台股 × 4 營收因子：**revenue_acceleration 最強**（60d ICIR +0.426）
- revenue_yoy 在大 universe 下幾乎無效（ICIR 0.037，被小樣本高估 72%）
- 小樣本嚴重誤導：ivol 方向完全反轉（+0.60 → -0.232）

### 策略驗證

| 版本 | Validator | CAGR | Sharpe | OOS |
|------|:---------:|:----:|:------:|:---:|
| revenue_momentum (15-check) | 12/15 | +9.56% | 0.926 | +34.8% |
| rev_accel_x_zscore (auto) | 12/15 | Large ICIR +0.416 | — | excl DSR 13/15 |

### Paper Trading 現況（2026-03-27）

- 模式：paper（Shioaji simulation）
- 持倉：12 支台股
- NAV：~$9.04M（初始 $10M，-9.6%）
- 已修問題：
  - Portfolio 持久化（atomic write + startup restore）
  - Kill switch 執行清倉 + re-trigger guard
  - Mutation lock 防並發
  - Price polling fallback（ShioajiFeed 失敗 → Yahoo）
  - 風控門檻 5% → 10%（配合策略 6.7%/股）
  - Live mode async fill callback
  - Live mode 拒絕 PaperBroker fallback

---

## 7. 經驗教訓（Top 12）

1. **Look-ahead bias 最隱蔽** — 營收 40 天延遲缺失膨脹 ICIR 72%，結果看起來完全正常
2. **generic fallback 是毒藥** — 「找不到就用預設值」靜默產出錯誤結果
3. **並發問題不在單元測試暴露** — asyncio.Lock 不保護線程，threading.Lock 不保護協程
4. **小樣本高估嚴重** — ivol 50 支 +0.60，874 支 -0.232
5. **風控門檻必須從 config 讀** — 硬編碼和 config 不一致是常見 bug
6. **crash recovery 需要原子性** — trade log 在 apply_trades 之前存
7. **時區必須統一** — UTC vs UTC+8 混用導致 08:00 提前 reset
8. **deepcopy + threading.Lock 不相容** — 需要自定義 __deepcopy__
9. **Shioaji simulation mode 有 quote_manager 但不推 tick** — polling fallback 被跳過
10. **回測和實盤是兩條代碼** — 任何改動要改兩個地方
11. **Pipeline 只取 target 價格會導致舊持倉賣不掉** — 必須取 target ∪ positions 的價格
12. **風控門檻和策略權重必須協調** — 獨立修改一邊會導致大量訂單被拒
