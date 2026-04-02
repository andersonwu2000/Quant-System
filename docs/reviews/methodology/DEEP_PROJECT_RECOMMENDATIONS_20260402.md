# 全專案深度檢視建議

> 日期: 2026-04-02
> 範圍: `src/`, `strategies/`, `apps/`, `tests/`, `docs/`, `scripts/`
> 目的: 留下可執行的金融面與工程面建議，避免再產生重複型 review

## 結論

這個專案已經不是「原型太薄」的問題，而是「能力很多，但離穩定可放大仍差最後一層制度化」。
金融面最明顯的瓶頸是 alpha 來源過度集中、研究結果和可交易容量之間仍有落差、資料偏差仍可能高估績效。
工程面最明顯的瓶頸是狀態管理過於集中、同步與非同步邊界仍脆弱、交易管線的失敗模式還不夠明確。

## 成熟度判斷

如果把專案成熟度粗分成五段:

1. 玩具/原型
2. 可用 MVP
3. 功能完整的進階系統
4. 可穩定 paper 或小規模實盤
5. 成熟、可持續營運的專案

我會把本系統放在 `3.5 / 5` 左右。

這代表它已經明顯超過 MVP，也不是靠幾個腳本拼起來的研究倉庫；它已經具備完整系統的骨架，包含研究、回測、排程、風控、API、前端與行動端。
但它還沒跨過「成熟專案」那條線，原因不是功能不夠，而是最後一層營運化與制度化尚未完全落地。

如果拆開評分，大致會是:

- 功能成熟度: `4.2 / 5`
- 金融方法成熟度: `3.8 / 5`
- 工程成熟度: `3.4 / 5`
- 營運成熟度: `3.0 / 5`

## 距離成熟專案還差在哪裡

### 1. 已經像成熟系統的部分

- 模組邊界大致存在，`api`、`backtest`、`risk`、`execution`、`data`、`scheduler`、`portfolio` 分工清楚
- 回測與驗證方法已經不是單一 Sharpe 導向，而是有 DSR、PBO、walk-forward、bootstrap 等防過擬合設計
- 交易系統不只停留在研究，已經考慮 paper/live、reconcile、kill switch、portfolio persistence
- monorepo 內同時有 backend、web、android、shared package，產品骨架完整
- 測試量體大，表示團隊已經有把 correctness 視為顯性工作

### 2. 還沒達成熟專案門檻的部分

- 研究 realism 還沒完全封裝成預設制度
  - survivorship bias 與 price-limit realism 還沒有完全成為預設 gate
- alpha 池太集中
  - 目前主力仍圍繞 revenue 家族，容易出現同敘事擁擠
- 狀態模型過重
  - `src/api/state.py` 的 `AppState` 承擔過多責任，對長期維護不利
- 交易流程仍偏單線式
  - pipeline 雖然已有保護，但還沒有完全做到分段、可回放、可審計、fail-closed 一致
- async / thread 邊界仍需硬化
  - 目前有註解與部分鎖規則，但還沒完全被程式結構吸收
- promotion 流程不夠正式
  - 研究結果進 paper/live 仍缺統一 artifact 與單一真相來源
- 測試仍偏模組視角
  - 對跨模組故障、競態、重啟恢復、部分成功部分失敗等場景覆蓋仍不足
- 營運證據不足
  - 若沒有長時間穩定 paper trading 或小規模真實資金紀錄，不能算成熟營運級

### 3. 它離成熟不是差「更多功能」，而是差最後 20% 到 30%

這裡最重要的判斷是:

- 不需要重寫
- 不需要先擴張更多功能面
- 需要把現有能力正式制度化

也就是說，差距不是「做不出來」，而是「還沒被壓成可靠系統」。

## 什麼條件下，我會把它視為成熟專案

若以下三大塊都補齊，我會把它從 `3.5 / 5` 提升到 `4.2 / 5` 以上:

### 1. 部署 realism 補齊

- survivorship coverage 被顯式管理
- 漲跌停與流動性限制成為預設模擬假設
- overlay 不再是選配，而是主力策略預設組件
- 容量研究在研究階段就產出，而不是部署後才補

### 2. 交易狀態與流程硬化

- `AppState` 被拆分
- lock discipline 被 helper / abstraction 吸收
- pipeline 變成清楚的兩段或多段流程
- fail-closed、重試、恢復、審計規則一致化

### 3. promotion 與營運制度建立

- 有正式的 strategy promotion artifact
- 有明確的 paper-to-live gate
- 有穩定 paper trading 觀察期
- 有 incident / recovery / rollback 的固定流程

## 對自己的錢與對成熟專案標準，要分開看

如果標準是「可不可以小規模、保守地管自己的錢」:

- 這套系統已經接近可用，但前提是有人持續盯、風險限制保守、不要過度自動化放大

如果標準是「能不能叫成熟專案」:

- 還不行
- 原因不是功能不夠多，而是可靠性、部署現實性、營運紀律還沒被證明到足夠程度

## 我這次重點看了什麼

- 專案定位與現有審查: `README.md`, `docs/SYSTEM_OVERVIEW.md`, `docs/reviews/*`
- 研究與驗證核心: `src/backtest/validator.py`, `src/backtest/checks/*`
- 投組與風控核心: `src/portfolio/optimizer.py`, `src/risk/engine.py`
- 即時交易主流程: `src/core/trading_pipeline.py`, `src/scheduler/jobs.py`
- 應用狀態與持久化: `src/api/state.py`
- 資料存取層: `src/data/data_catalog.py`
- 設定與營運控制: `src/core/config.py`

## 金融面建議

### 1. 把「策略有效」和「可部署」拆成兩套分數

目前 validator 很完整，但 `src/backtest/validator.py` 仍把許多性質不同的問題放進同一份 pass/fail 報告。這對研究篩選有幫助，但對部署決策不夠精準。

建議拆成兩個維度:

- `Research Score`: IC、ICIR、DSR、PBO、bootstrap、regime consistency
- `Deployment Score`: 容量、換手、價量衝擊、持倉集中、相對基準、近期退化

原因:

- 同一個因子可以在研究上成立，但在交易上因容量或 turnover 失去意義。
- 現在 revenue 家族即使研究結果不差，也可能因家族擁擠與相同事件暴露造成部署風險集中。

### 2. 優先做「家族分散」，不是再加同型 revenue 變體

從目前策略與文件看，主力仍偏向 `revenue_momentum`、`revenue_momentum_hedged`、`trust_follow` 這條線。這會帶來兩個問題:

- 研究成功看似穩定，其實是在重複押同一種經濟敘事
- 一旦月營收訊號失效、擁擠、或公告節奏改變，整個 deployed alpha 池會一起受傷

下一批研究不應再優先優化 revenue 衍生式，而應強制配置到不同家族:

- 品質/獲利能力: gross profitability、cash flow quality、accruals
- 風險補償: low vol、beta-managed momentum、residual momentum
- 行為/事件: post-earnings drift、analyst revision proxy、institutional flow persistence
- 橫斷面相對價值: sector-neutral value、composite valuation dispersion

做法上建議在 auto research 流程增加 `family_budget`，限制同家族進入 L4/L5 的數量。

### 3. 把 survivorship bias 和漲跌停限制從「提醒」升級成「預設阻擋」

從現有 review 與 `src/data/data_catalog.py`、`src/backtest/validator.py` 周邊設計看，專案已意識到 PIT 與資料偏差，但仍有「知道風險、尚未系統化封鎖」的情況。

建議:

- 沒有下市股資料時，所有台股長期 CAGR/Sharpe 報表都標記為 `research-only`
- validator 新增 hard/soft gate:
  - `universe_survivorship_coverage`
  - `price_limit_execution_realism`
- 模擬撮合預設納入台股 `±10%` 漲跌停與流動性失真，不要只在報告裡註記

原因很直接: 這類偏差不是噪音，而是會系統性高估策略可行性。

### 4. Overlay 應從選配功能升級成 revenue 策略的預設部件

`src/core/trading_pipeline.py` 已留有 `apply_overlay()` 接口，但從 review 與策略現況看，overlay 還沒有成為真正的部署標準件。

對目前主力策略，至少應固定上三種 overlay:

- 單名持股上限
- sector cap
- beta 或 market correlation 控制

理由:

- revenue 類策略天然容易出現產業聚集
- 若只在 validator 看相對市場相關性，而不在交易前實際壓制，研究與部署仍會脫節

### 5. 把容量研究前移到策略生成階段，而不是部署後再補

`src/portfolio/optimizer.py` 已有多種配置法，但 alpha 真正的瓶頸更可能在容量與執行衝擊，不在最佳化器本身。

建議將以下欄位納入每次研究輸出:

- 預估單日成交額占比
- 平均建倉天數
- 95% 清倉天數
- 成本對 alpha 的侵蝕比率
- 不同資金規模下的 Sharpe/turnover 衰減曲線

這會讓你更早知道某個 alpha 是「可研究不可交易」還是「能直接進 paper」。

### 6. 對 2025 OOS 虧損做正式 loss attribution，不要只看單一 Sharpe 回落

既有 review 已經指出 OOS 退化，但下一步不應只是再 rerun。應該把 loss attribution 標準化，至少拆成:

- 因子失效: rank IC 下滑
- 組合失效: 有 alpha 但被權重/約束稀釋
- 執行失效: turnover、成本、流動性假設過樂觀
- regime 失效: 市場狀態切換
- 擁擠失效: 同類股票同步回撤

如果沒有這張 attribution 表，之後很容易用新因子覆蓋舊問題，卻沒有真的修掉部署瓶頸。

## 工程面建議

### 1. 先拆 `AppState`，再談更多功能

`src/api/state.py` 的 `AppState` 已經同時管理 portfolio、OMS、execution、risk、backtest tasks、alpha tasks、auto-alpha、quote manager、realtime risk monitor 和多把鎖。這是目前最明顯的工程結構壓力點。

建議至少拆成四塊:

- `TradingState`: portfolio, execution, stop orders, kill switch
- `ResearchState`: alpha tasks, auto-alpha config/store
- `OpsState`: scheduler, health, watchdog, notifications
- `RuntimeLocks`: async/thread locks 與取得規則

拆分的目的不是好看，而是降低以下風險:

- 初始化失敗時整體狀態半殘
- 單元測試需要載入過多依賴
- thread 與 async 邊界不清，造成潛在死鎖或遺漏同步

### 2. 將交易主流程明確分成「可失敗」和「不可失敗」兩段

`src/scheduler/jobs.py` 的 pipeline 已有 timeout、idempotency、quality gate，但目前仍是單條流程一路往下跑。建議明確切兩段:

- Phase A: data refresh、quality gate、strategy resolution、weight generation
- Phase B: order generation、risk approval、execution、portfolio mutation、persistence

並對每段定義:

- 輸入輸出資料結構
- 可重試與不可重試錯誤
- 失敗後是否 fail-closed
- 是否允許部分成功

這樣做可以直接改善:

- crash recovery
- 排程重跑一致性
- 實單/模擬路徑比對

### 3. 把 lock discipline 從註解升級成程式結構

`src/api/state.py` 已經有 lock ordering 註解，方向是對的，但現在仍主要靠開發者自律。這種規則只寫在註解裡，長期一定會被破壞。

建議:

- 建立集中式 helper，例如 `with_portfolio_mutation()`、`async with_trading_state_mutation()`
- 禁止 route 與 execution code 直接碰底層 lock
- 為 `mutation_lock`、`portfolio.lock` 補 race-condition tests

原則是把「不要這樣用」改成「根本沒有地方能這樣用」。

### 4. DataCatalog 要更嚴格，不要默默回空資料

`src/data/data_catalog.py` 現在對 missing file、unknown symbol、無法讀檔等情境多半回空 `DataFrame`。這對研究迴圈方便，但對交易系統過度寬鬆。

建議新增 strict 模式:

- research path: 可回空，但必須帶 reason code
- trading path: 對 price/revenue 這種核心資料，缺值直接 raise

同時把結果標準化成類似:

- `status=ok`
- `status=missing_symbol`
- `status=missing_dataset`
- `status=read_error`
- `status=pit_blocked`

這會比大量 `df.empty` 判斷更容易維護，也更容易做監控。

### 5. 設定層應該把營運意圖寫進型別，而不是只靠預設值

`src/core/config.py` 已經做了不少事，但仍混雜了 dev/paper/live 的默認行為。建議往下走兩步:

- 把 `mode` 與 `env` 衍生出的必要條件寫成 profile 驗證
- 把互斥設定顯式化，例如 pipeline cron、revenue cron、rebalance cron 的優先順序

最實際的改善是建立:

- `DevProfile`
- `PaperProfile`
- `LiveProfile`

每個 profile 自己定義:

- 必要 secrets
- 可啟用功能
- 預設風控閾值
- 排程行為

這比單一大 config 靠註解理解安全得多。

### 6. 為「研究結果進部署」建立明確 promotion contract

目前專案已有大量 review、plan、status 文件，但 promotion 邏輯仍分散在 validator、paper trading、scheduler、人工判讀之間。

建議建立一個統一 artifact，例如 `promotion_decision.json`，至少包含:

- strategy id / version
- validator version
- data snapshot id
- universe snapshot id
- capacity bucket
- approved mode: research / paper / live-disabled
- blocking reasons
- reviewer notes

有了這個 contract，web、android、scheduler、報表和審計紀錄都能吃同一份真相來源。

### 7. 測試策略要從「覆蓋模組」升級成「覆蓋故障模式」

測試數量已經很多，但真正高風險的是跨模組故障。建議未來優先把測試配額放在以下情境:

- data refresh 部分失敗但 pipeline 不應繼續
- kill switch 與 API rebalance 同時觸發
- execution 成功但 portfolio persistence 失敗
- portfolio save 成功但 ledger replay 發現重複 fill
- websocket / quote thread 持續進資料時發生 shutdown

原則很簡單: 多數大損失不來自單一函式錯誤，而是來自「兩件事同時出錯」。

## 建議優先順序

### 先做，否則研究和部署都會持續失真

1. 把 survivorship bias 與漲跌停交易現實性納入預設 gate
2. 讓 overlay 成為 revenue 類策略的預設部件
3. 拆分 `AppState`，收斂 lock 使用入口
4. 將 pipeline 明確分段並定義 fail-closed 行為
5. 建立 promotion artifact，避免研究、排程、前端各說各話

### 第二階段，提升可放大性

1. 建立 factor family budget，強制研究分散
2. 前移容量研究，讓研究輸出直接包含容量與衝擊曲線
3. 為 DataCatalog 加 strict result model
4. 建立 profile-based config
5. 改以 failure-mode 為核心擴充整合測試

## 最後判斷

這個專案最值得肯定的地方，是研究、回測、風控、排程、前後端已經被收進同一個 monorepo，方向是對的。
現在最需要的不是再加功能，而是把幾個已經存在的能力正式制度化: `family diversification`、`deployment realism`、`state isolation`、`promotion discipline`。

如果只選一個金融動作與一個工程動作先做，我會選:

- 金融: 強制家族分散，並把漲跌停與 survivorship 變成預設 gate
- 工程: 拆 `AppState`，並把 pipeline 改成明確的 fail-closed 兩段式流程

---

## 補充：深度代碼審計發現（2026-04-02 第二輪）

> 以下是針對具體代碼、公式、閾值的逐項審計結果，補充上面的高層建議。
> 審計範圍涵蓋 backtest engine、analytics、validator、autoresearch pipeline、risk rules、execution broker、config、scheduler、data pipeline 全部核心模組。

---

### A. 金融公式與方法論問題

#### A-1. Sharpe Ratio 忽略無風險利率（analytics.py:305-310）

`daily_return.mean() / daily_return.std() * sqrt(252)` 將無風險利率設為 0。台灣目前銀行定存利率約 1.5-2%，完全忽略會系統性高估 Sharpe 約 0.1-0.2。

**建議**: 從 config 讀取 `risk_free_rate`（已在 optimizer.py:52 有 default 2%），analytics 應該統一使用。

#### A-2. CAGR 用交易日而非日曆日年化（analytics.py:295-300）

`n_years = (len(nav_series)-1) / 252`，但如果回測期包含假期較多的年份（如 2020 COVID 停市），會導致年化不準。

**建議**: 改用 `(end_date - start_date).days / 365.25` 做真正的日曆日年化。

#### A-3. Sortino Ratio 沒用 MAR（analytics.py:312-320）

現行做法把所有負報酬都計入 downside，包含 -0.001% 的微小負日。Sortino & Price (1994) 原文建議用 MAR (Minimum Acceptable Return，通常為 0 或無風險利率)。

**影響**: 當前做法會**高估** downside deviation，導致 Sortino 看起來比實際差。這對策略排序影響不大（一致高估），但對絕對數值的解讀不準。

#### A-4. 市場相關性門檻 0.80 過於寬鬆（validator.py:100）

`max_market_corr=0.80` 意味著允許 R²=0.64，即 64% 的策略變異可被市場解釋。這幾乎不能稱為 alpha。

**建議**: 降到 0.50（R²=0.25），或至少在 Deployment Score 裡對 >0.50 的做黃燈警示。Bailey (2014) 對 pure alpha 建議 |corr| < 0.30。

#### A-5. PBO 門檻 0.60 偏高（validator.py:66）

代碼註解已承認 Bailey 建議 <0.50，但放寬到 0.60。台股因子空間較小可能是理由，但應該**明確記錄放寬理由**，並在 Deployment Score 中額外加權。

#### A-6. IC/ICIR 去重用 Pearson 但 IC 本身是 Spearman（evaluate.py:644）

IC 計算用 Spearman rank correlation，但去重比較用 `pandas .corr()`（默認 Pearson）。兩種相關性度量不一致可能導致近似因子逃過去重。

**建議**: 去重也改用 Spearman（`method='spearman'`）。

#### A-7. 產業中性化的樣本偏差（evaluate.py:594-599）

產業均值在完整產業組上計算，但最終 IC 只用 `common` 子集。如果某些股票因數據缺失被排除，產業均值會偏移。

**建議**: 產業均值應在 `common` 子集上重新計算。

#### A-8. Rolling IC 穩定性檢查用重疊窗口（evaluate.py:1033-1042）

12 個月滾動窗口有嚴重自相關，不是獨立檢驗。50% 正比例的門檻看似合理，但統計顯著性被高估。

**建議**: 用非重疊窗口或 Newey-West 調整，或至少在報告中標注「非獨立檢驗」。

#### A-9. L2 ICIR 門檻校準問題（evaluate.py:68）

- `min_icir=0.30`：學術文獻中 ICIR 0.05-0.15 已算優秀因子。0.30 是極其嚴格的門檻，可能過度篩除有效因子。
- `max_icir=1.00`：ICIR > 0.50 幾乎必然是過擬合或數據洩漏，上限應下調到 0.50。

**建議**: 最低門檻考慮降到 0.15，上限降到 0.50。

#### A-10. 結算現金雙重計入（engine.py:629）

代碼明確註解：`apply_trades()` 已扣減現金，`pending_settlements` 又鎖定同一筆金額。這導致可用現金被**雙重扣減**，策略在結算期間會嚴重低配。

**影響**: 回測結果會低估持倉規模和報酬，與實際交易體驗有差距。

#### A-11. 沒有股票分割/合併/除權調整

整個 codebase 沒有 corporate action adjustment 機制。如果使用 Yahoo adjusted prices 並同時注入股利現金（engine.py:641-660），會有**股利雙重計入**風險。代碼有防護（engine.py:163-169），但這是脆弱的。

**建議**: 建立明確的 `CorporateActionHandler`，統一處理 split、merger、spin-off、ex-dividend price adjustment。

#### A-12. Forward-fill 沒有下市/停牌偵測（engine.py:778,784）

`ffill(limit=5)` 在股票下市後會用最後價格填充 5 天然後變 NaN。但這 5 天的 NAV 計算是虛假的。

**建議**: 加入主動的 delist/suspension 偵測，下市股直接標記為不可交易而非 ffill。

---

### B. 風控與執行模型問題

#### B-1. 漲跌停模擬用 9.5% 而非 10%（simulated.py:134-156）

台股漲跌停是 ±10%，但模擬撮合用 9.5% 作為拒絕門檻。差 0.5% 可能看似保守，但這導致**回測結果與實際市場規則不一致**，是一種隱性偏差。

**建議**: 改為 0.10 與實際規則對齊。

#### B-2. 風控規則在 prev_close 缺失時靜默放行（rules.py:192-194）

`price_circuit_breaker` 在找不到前日收盤價時返回 `Approve()`。這違反 fail-closed 原則。

**建議**: 缺少 prev_close 時返回 `Reject("missing prev_close")`。

#### B-3. 同批次大量下單可繞過日交易上限（rules.py:147）

`max_daily_trades` 的計數在 `record_trade()` 回調時才增加，不是在 check 階段。如果策略一次送出 100 張單，全部會通過檢查。

**建議**: 在 check 階段就把當前 pending count 加入判斷。

#### B-4. 單名持倉上限 MODIFY 而非 REJECT（rules.py:64-75）

超過 5% 持倉上限時，風控把數量裁減到上限內，而不是拒絕。如果策略反覆觸發同一支股票，會逐步堆積到上限。

**建議**: 這是設計選擇，但應加日誌追蹤 MODIFY 頻率，超過閾值（如單月 >5 次）觸發警報。

---

### C. 安全與部署問題

#### C-1. API 憑證已提交到 git（.env）

`.env` 雖在 `.gitignore` 中，但已存在 git 歷史：
- FinMind JWT token
- SinoPac API Key + Secret
- Discord webhook URL

**⚠️ 最高優先級**: 立即輪換所有已暴露憑證，並用 `git filter-branch` 或 BFG 從歷史中清除。

#### C-2. JWT Secret 和 Admin Password 有硬編碼預設值（config.py:85-86）

`jwt_secret = "change-me-in-production"` 和 `admin_password = "Admin1234"` 作為預設值寫在代碼中。雖然 config validator 會在非 dev 環境阻擋，但這仍是不好的實踐。

**建議**: 預設值改為空字串，在 dev 環境也強制從 `.env` 讀取。

#### C-3. CI 缺少安全掃描

- 沒有 `pip-audit` 或類似的依賴漏洞掃描
- 沒有 SAST（如 bandit/semgrep）
- 沒有代碼覆蓋率執行
- 沒有 pre-commit hook 阻擋 secrets

**建議**: 在 `.github/workflows/ci.yml` 加入 `pip-audit` 和 `bandit` 步驟，成本極低但收益大。

#### C-4. WebSocket token 放在 query string（app.py:208-215）

Token 在 URL 中會被 access log、proxy、瀏覽器歷史記錄捕獲。

**建議**: 改用第一則 WebSocket message 傳遞 token，或用 Sec-WebSocket-Protocol header。

---

### D. 數據管線與校準問題

#### D-1. PE/PBR 的 PIT delay 設為 0 天（registry.py:110）

每日 PE 是盤中快照，但標記為 0 天延遲。如果在每日開盤前用前日 PE 做決策，這沒問題；但如果在盤中即時使用，可能有 intraday look-ahead。

**建議**: 至少設為 1 天延遲（用 T-1 的 PE），或明確記錄使用時機。

#### D-2. Slippage 模型未校準到台股微結構

sqrt impact model 的 `impact_coeff=50.0` 產生的滑點範圍（2-7bps）看似合理，但沒有對照台股實際 bid-ask spread 和 tick size 做過校準。

**建議**: 用 SinoPac 的實際逐筆資料做一次校準分析，記錄係數來源。

#### D-3. OOS 採樣間距可能產生盲區（evaluate.py:797-799）

IS 和 OOS 都用 `SAMPLE_FREQ_DAYS` 做子採樣（20 天間距），意味著 IC 是在每 20 天計算一次。如果某些月份的 alpha 集中在月中（如營收公布後的 drift），這個採樣頻率可能系統性遺漏。

**建議**: 至少在 L5 OOS 驗證階段用每日頻率，或用隨機偏移消除系統性盲區。

---

### E. 架構與可靠性補充

#### E-1. 月度策略的冪等檢查非多進程安全（jobs.py:77-84）

`_has_completed_run_this_month()` 只在本地狀態中檢查。如果兩個 scheduler 實例同時啟動（如 Docker restart race），兩者都會跑。

**建議**: 用檔案鎖或資料庫鎖做分散式冪等。

#### E-2. Pipeline 缺少明確的依賴排序

data refresh → strategy → execution 的順序沒有被強制。如果數據更新延遲但策略已啟動，會用過時數據做決策。

**建議**: Phase A（data + quality gate）必須在 Phase B（strategy + execution）之前完成並回傳 OK 才繼續。

#### E-3. 全域異常處理器吞掉具體錯誤（app.py:237）

所有未捕獲異常都返回 `"Internal server error"`。在 production 這是正確的，但在 dev/paper 環境應返回詳細錯誤以加速除錯。

**建議**: 在 dev 環境返回 `traceback`，paper 環境返回 error class name，production 保持 generic。

---

### F. 額外閾值校準建議

| 參數 | 現值 | 建議值 | 理由 |
|------|------|--------|------|
| `max_market_corr` | 0.80 | 0.50 | R²=0.64 太高，不算 alpha |
| `max_pbo` | 0.60 | 0.50 | 與 Bailey (2014) 對齊 |
| `min_icir` (L2) | 0.30 | 0.15 | 學術 ICIR 0.05-0.15 已算優秀 |
| `max_icir` (L2) | 1.00 | 0.50 | >0.50 幾乎必定過擬合 |
| `limit_up_down` | 9.5% | 10.0% | 與台股實際規則對齊 |
| `risk_free_rate` (Sharpe) | 0% | 2% | 與 optimizer 統一 |
| `max_mdd` (soft) | 40% | 25% | 40% 對個人資金管理太寬鬆 |
| `worst_regime` (soft) | -30% ann. | -20% ann. | -30% 是危機級損失 |

---

### G. 未來審計建議

1. **每季做一次 threshold review**：市場環境變化（利率、流動性、波動度）會影響所有閾值的合理性
2. **建立 factor zoo registry**：記錄所有已測試過的因子（含失敗的），避免重複研究、方便 meta-analysis
3. **slippage model 年度校準**：用實際交易數據比對模擬滑點，調整 impact_coeff
4. **OOS period rolling forward**：2025 H1 的 OOS 虧損需要區分「暫時失效」和「結構性失效」，建議設定 6 個月觀察期做正式判定
