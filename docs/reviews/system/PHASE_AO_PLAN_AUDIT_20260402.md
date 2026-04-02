# Phase AO 計畫審計

> 日期: 2026-04-02
> 對象: [phase-ao-institutionalization.md](/D:/Finance/docs/plans/phase-ao-institutionalization.md)
> 結論: 計畫方向正確，但有幾個關鍵定義仍不夠嚴謹，若不先修正，後續實作很容易出現「做了很多，卻沒有得到可驗證制度化成果」的情況。

## Findings

### 1. `AO-3` 把 Phase B 驗收寫成「全成功或全回滾」，這對外部執行流程不成立

位置: [phase-ao-institutionalization.md:60](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L60), [phase-ao-institutionalization.md:79](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L79)

`order generation -> risk approval -> execution -> portfolio mutation -> persistence` 這段一旦碰到 broker / OMS / ledger，系統就不再擁有真正的資料庫交易式回滾能力。  
如果委託已送出、部分成交已發生，計畫中的「要嘛全成功要嘛全回滾」會變成錯誤承諾。

建議改成明確的三態模型:

- `pre_submit_failure`: 可安全中止，無外部副作用
- `submitted_not_persisted`: 不可回滾，必須進 recovery / reconcile
- `persisted_complete`: 完成

驗收條件也應改為:

- Phase B 失敗時，本地狀態不會假裝成功
- 所有外部副作用都有 ledger / audit trail
- 重啟後可由 reconcile 或 replay 恢復到一致狀態

### 2. `AO-5` 將 promotion artifact 綁在 `validator.validate()` 自動輸出，責任邊界混亂

位置: [phase-ao-institutionalization.md:103](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L103), [phase-ao-institutionalization.md:128](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L128), [phase-ao-institutionalization.md:132](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L132)

`validate()` 是研究/驗證行為，不等於 promotion 決策。若每次 `validator.validate()` 都自動寫 `promotion_decision.json`，會出現兩個問題:

- 研究過程中的暫存驗證結果會污染正式 promotion 歷史
- promotion artifact 變成「有跑過 validator」而不是「已被批准部署」

建議拆成兩層 artifact:

- `validation_report.json`: 每次驗證都可產生
- `promotion_decision.json`: 僅由明確的 promotion step 產生

也就是把 `validator` 當成輸入，而不是 decision writer。

### 3. `AO-6` 同時要求 strict raise 與 result status code，但介面契約尚未定清楚

位置: [phase-ao-institutionalization.md:138](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L138), [phase-ao-institutionalization.md:145](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L145), [phase-ao-institutionalization.md:148](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L148)

目前寫法同時要:

- `strict=True` 時直接 raise
- 又要標準化 `ok/missing_symbol/...` status code

這兩個方向都合理，但不能混在同一層 API 契約裡而不先定義。否則呼叫端會不知道該 `try/except` 還是檢查 `status`。

建議二選一:

- `get()` 保持回傳 `DataFrame` / raise，另加 `get_result()`
- 或 `get()` 一律回 `CatalogResult`，由 helper `require_df()` 負責在交易路徑 raise

先把契約定清楚，再做 strict mode，不然會把大量現有呼叫點推進半套狀態。

### 4. `AO-2` 的 family 判定規則過於脆弱，制度化會被命名慣例綁架

位置: [phase-ao-institutionalization.md:45](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L45), [phase-ao-institutionalization.md:56](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L56)

計畫目前寫「用因子名稱前綴或 `learnings.jsonl` 的 direction 欄位」判定家族。這太脆弱，因為:

- 命名規則容易漂移
- `direction` 不等於 factor family
- 同一經濟敘事可用不同命名躲過 budget

建議建立顯式欄位:

- `family`
- `subfamily`
- `economic_thesis`

並把它寫進 factor metadata 或研究輸出，而不是從名稱猜。

### 5. `AO-1` 的雙分數概念正確，但缺少校準方法，容易形成假精確

位置: [phase-ao-institutionalization.md:28](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L28), [phase-ao-institutionalization.md:41](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L41)

把 validator 拆成 `research_score` 與 `deployment_score` 是對的，但目前只定義了欄位，沒定義:

- 分數如何從各 check 聚合
- 是否等權
- hard gate 與 score 的關係
- threshold 如何校準

如果這些不先定義，最後很容易只是把原本的 pass/fail 包成兩個看起來更漂亮的數字。

建議在計畫內補一段 scoring contract:

- hard gate 先行，score 只在 hard gate 通過後比較排序
- 或 score 只做排序，不直接決定 `passed`
- 每個 check 的權重與正規化方式固定成 schema

### 6. `AO-11` 的驗收標準「Route 層至少 50% 改用新 state」不夠可驗證，也不是穩定終態

位置: [phase-ao-institutionalization.md:219](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L219), [phase-ao-institutionalization.md:232](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L232)

`50%` 這種比例型驗收不適合架構重構，因為:

- 很難穩定量測
- 50% 完成時系統仍可能處於雙軌狀態
- 不知道剩下 50% 是哪個風險模組

建議改為按模組切割驗收，例如:

- `orders/risk/portfolio` 三組 route 全部切到 `TradingState`
- `backtest/auto-alpha` 全部切到 `SupportState`
- facade 僅保留一版相容層，禁止新增新呼叫點

### 7. 文件引用路徑錯誤，會讓 Phase AO 的來源追溯失效

位置: [phase-ao-institutionalization.md:10](/D:/Finance/docs/plans/phase-ao-institutionalization.md#L10)

計畫寫的是:

- `docs/reviews/methodology/DEEP_PROJECT_RECOMMENDATIONS_20260402.md`

但目前實際檔案在:

- [DEEP_PROJECT_RECOMMENDATIONS_20260402.md](/D:/Finance/docs/reviews/DEEP_PROJECT_RECOMMENDATIONS_20260402.md)

這不是小問題。AO 本身主打制度化，如果來源鏈接一開始就斷掉，後續 audit trail 會變弱。

## 建議補強

### 1. 先補一頁「制度契約」

建議在 Phase AO 前面新增一節，明確定義:

- 哪些輸出是 research artifact
- 哪些輸出是 promotion artifact
- 哪些流程可重試
- 哪些狀態不可回滾，只能 reconcile
- score、gate、decision 三者的關係

### 2. 把 P0 項目補上 owner / dependency / rollback plan

目前條目夠清楚，但還欠實作治理欄位。P0 至少應加:

- owner
- blocking dependency
- migration risk
- rollback / fallback

沒有這些欄位，Phase AO 會像技術願景，不像可執行制度化計畫。

### 3. 調整施做順序

目前順序大致合理，但我會改成:

1. `AO-1` 定 scoring contract
2. `AO-5` 分離 validation artifact / promotion artifact
3. `AO-3` 定 Phase A / B 與 recovery model
4. `AO-6` 定 DataCatalog 契約
5. `AO-4`、`AO-11` 再進行 state / lock 重構

原因是先把契約與責任邊界定清楚，再做重構，返工會少很多。

## 總評

這份計畫的方向是對的，而且比一般「再多加功能」的 roadmap 成熟得多。真正的問題不是方向，而是幾個最核心的制度化概念還差最後一步精確化:

- `rollback` 其實應該寫成 `reconcile/recovery`
- `promotion artifact` 不應等於 `validation side effect`
- `strict mode` 與 `result model` 需要先確定 API 契約
- `family budget` 不能建立在命名猜測上

如果先把這幾個定義修正，Phase AO 會更像一份可執行的成熟化計畫，而不是一份很好的方向文件。

---

## 補充審計：代碼驗證 + 結構性問題（第二輪）

> 本節基於對 Phase AO 計畫中所有引用路徑、聲明數據、預設行為的逐項代碼驗證。
> 目的：確認計畫描述與代碼現狀一致、標記過度承諾或遺漏、補充結構性觀察。

---

### 8. 計畫所有 13 個 AO 項目的代碼現狀確認

| 項目 | 計畫聲明 | 代碼現狀 | 差距 |
|------|---------|---------|------|
| AO-1 | ValidationReport 新增雙分數 | ValidationReport（validator.py:150）無 research_score/deployment_score | 全新實作 |
| AO-2 | L4 入口加 family budget | evaluate.py 無任何 family/budget 邏輯 | 全新實作 |
| AO-3 | pipeline 拆成 Phase A/B | jobs.py:143 `_execute_pipeline_inner` 是線性單流程 | 重大重構 |
| AO-4 | lock helper 取代直接使用 | state.py 無 helper method，直接 lock 使用約 **20 處**（routes/, scheduler/, bootstrap/） | 影響面大 |
| AO-5 | promotion artifact 自動產出 | `data/promotions/` 目錄**不存在**，paper_deployer.py 無 artifact 邏輯 | 全新實作 |
| AO-6 | DataCatalog strict mode | data_catalog.py `get()` 無 strict 參數，缺值回空 DataFrame | 全新實作 |
| AO-7 | overlay 預設啟用 | overlay.py 存在且可用，trading_pipeline.py 有接口，但**非自動啟用** | 配置改動 |
| AO-8 | survivorship 3,936/1,695 | securities_master.py 有 delisted_date 欄位和 `universe_at()` 方法，但 3,936/1,695 數字**未在代碼中驗證** | 數據驗證 |
| AO-9 | evaluate.py L4 加容量估算 | evaluate.py 無容量相關指標 | 全新實作 |
| AO-10 | 6 個 failure-mode 測試 | `test_failure_modes.py` **不存在** | 全新實作 |
| AO-11 | AppState 拆成 Trading/Support | state.py:222 單一 AppState 含 **14+ 屬性** | 重大重構 |
| AO-12 | OOS loss attribution 框架 | descriptive.py 無 `_compute_loss_attribution()` | 全新實作 |
| AO-13 | Config Dev/Paper/Live profiles | config.py 無 profile 系統，用 mode+env 組合判斷 | 中等改動 |

**觀察**：13 項中有 **9 項是全新實作**、2 項是重大重構、2 項是配置/數據改動。這不是「把已存在的能力制度化」，而是**大量新增功能**。計畫§0 動機寫「差距不在做不出來，而在還沒被壓成可靠系統」，但實際工作量遠超「壓成可靠」的程度。

**建議**：重新校準計畫敘事。承認 AO 包含「制度化」和「補缺」兩類工作，分開估時。

---

### 9. AO-14/15/16/17 的文件結構問題

這四個項目定義在**§6 補充審計項目**（line 358-453），但在**§3 施做順序**（line 294）中已被納入依賴圖：

```
AO-14（金融公式對齊）→ AO-15（IC 方法論）→ AO-16（閾值校準）
```

問題：
- §2 P1 只列到 AO-13，但 AO-14~17 以「補充」形式出現在 §6
- §6 的格式與 §1/§2 不同（沒有明確的修改範圍結構）
- AO-14~17 **實際上是 P1 工作**，卻被放在「補充審計」的文檔位置

**建議**：把 AO-14~17 正式移入 §2 P1，統一格式，否則開發時容易遺漏或認為是「可選」。

---

### 10. AO-4 lock 使用現狀被低估

計畫驗收寫「直接碰 lock 的地方 < 3」，但實際直接使用 lock 的位置約 **20 處**：

- `src/api/routes/execution.py:184` — `async with state.mutation_lock`
- `src/api/routes/alpha.py:69` — `with state.alpha_lock`
- `src/api/routes/backtest.py:82` — `with state.backtest_lock`
- `src/api/bootstrap/monitoring.py:149` — `async with state.mutation_lock`
- `src/scheduler/jobs.py` — 多處 mutation_lock 使用
- 其他 route 文件中的散佈使用

從 20 處降到 < 3 處意味著至少 **17 處代碼需要遷移**到 helper。這不是微調，而是一次全面的調用點重構。

**建議**：
1. 驗收改為分批：「Phase 1: TradingState 相關 routes 全切 helper，Phase 2: 其他」
2. 加一個遷移追蹤表列出所有 20 處，逐個標記完成

---

### 11. AO-16 閾值調整需要回歸驗證，計畫輕描淡寫

計畫 line 400 寫「需跑 Experiment #26 驗證調整後 revenue_acceleration 仍可通過」，但這其實是**最關鍵的風險**：

- `max_market_corr` 從 0.80 → 0.50：revenue 策略的市場相關性如果在 0.50-0.80 之間，就會**直接被硬門檻擋下**
- `min_icir` 從 0.30 → 0.15：方向正確（放寬），但與 L2 gate 的「過嚴」問題連動，降到 0.15 後需要確認不會放進過多噪音因子
- `max_icir` 從 1.00 → 0.50：如果現有已通過的因子有 ICIR 在 0.50-1.00 之間的，會被追溯淘汰

**建議**：
1. 在修改閾值前，先跑一次**全因子回歸測試**：把所有歷史 passed 因子用新閾值重新驗證，列出哪些會翻盤
2. `max_market_corr` 降到 0.50 是最激進的改動，應單獨評估，不要和其他閾值一起改
3. 考慮漸進式調整（如先降到 0.65，觀察一輪，再降到 0.50）

---

### 12. AO-8 的數據可行性未評估

計畫寫「FinLab 有完整下市股數據」但：
- 未確認 FinLab API 是否真的提供**歷史價格**（不只是基本面）給已下市公司
- 未評估數據獲取成本（FinLab 免費版 vs 付費版的 API 限制）
- 未評估補歷史數據的時間範圍（從 2016 回溯？更早？）
- securities_master.py 的 3,936/1,695 數字可能是某次爬取的快照，需要定期更新機制

**建議**：AO-8 應先做一個 spike（技術調研），確認 FinLab 數據可行性後再進入正式開發。

---

### 13. AO-3 與結算雙重計入問題的依賴未明

Phase AO 計畫 §6 底部有一個「待決策：A-10 結算現金雙重計入」（line 415-426），列了三個候選方案但標記「等待審計意見後決定」。

問題：
- AO-3 要把 pipeline 拆成 Phase A/B，而 Phase B 包含 `execution → portfolio mutation`
- 如果 settlement 行為改變（方案 B 或 C），portfolio mutation 的語義會不同
- 這意味著 **AO-3 實際上依賴 settlement 決策**，但依賴圖中沒有畫出這條線

**建議**：
- 先決定 settlement 方案，再做 AO-3
- 推薦**方案 A**（最小改動）：`available_cash` 直接返回 `self.cash`，因為 apply_trades 已即時扣款。理由：NAV 不受影響，且不需要改動 engine 核心邏輯

---

### 14. §4 成功標準過多且未分級

§4 列了 **17 個成功標準**（6 制度化 + 11 可放大性），但沒有區分：
- 哪些是 Phase AO 的 **必要交付** vs **理想交付**
- 哪些有依賴關係（如「Sharpe/Sortino 統一使用 risk_free_rate」依賴 AO-14）
- 哪些可以獨立驗收

當成功標準太多且平行排列時，容易出現「做了 12/17 算不算完成」的模糊狀態。

**建議**：
- 分成 **must-have**（≤8 項）和 **nice-to-have**
- must-have 全部完成才算 Phase AO 可關閉
- 每個標準加一個可驗證的命令或測試（如「`grep -r 'mutation_lock' src/api/routes/ | wc -l` < 3」）

---

### 15. Phase AO 與進行中 Phase 的衝突風險

PLAN_STATUS.md 顯示有 **5 個 Phase 仍在進行中**（AA 80%、AG 75%、AK 85%、AJ 50%、AL 90%）。Phase AO 修改的核心文件（validator.py、jobs.py、state.py、evaluate.py）與這些 Phase 高度重疊：

| AO 項目 | 修改文件 | 衝突 Phase |
|---------|---------|-----------|
| AO-1 | validator.py | AC（已完成但可能有後續） |
| AO-3 | jobs.py | AG（部署管線）、AL（trading safety） |
| AO-4 | state.py | AL（invariant checks 用到 lock） |
| AO-11 | state.py | 同上 |
| AO-16 | validator.py, evaluate.py | AG（factor 部署）、AJ（壓力測試） |

**建議**：
- Phase AO 不應在 AA/AG/AK/AL 全部 close 之前啟動 P0
- 至少等 AL（Trading Safety）完成並通過 30 天 paper 觀察後再動 state.py
- 考慮先做「無代碼衝突」的項目：AO-2（family budget）、AO-5（promotion artifact）、AO-12（loss attribution）、AO-17（CI security）

---

### 16. 施做順序需考慮「先契約後實作」原則

結合 Finding 1-7 和本輪發現，建議的施做順序調整為：

```
── Phase 0：契約與決策（無代碼改動）──
① 決定 settlement 方案（A/B/C）
② 定義 scoring contract（research_score / deployment_score 如何聚合）
③ 定義 DataCatalog API 契約（CatalogResult vs strict raise）
④ 定義 family metadata schema（不靠命名猜測）
⑤ 把 AO-14~17 正式移入 P1 並統一格式

── Phase 1：獨立項目（不碰 state.py / jobs.py）──
AO-2（family budget）
AO-5（promotion artifact，分離 validation/promotion）
AO-12（loss attribution）
AO-14（金融公式對齊）
AO-15（IC 方法論修正）
AO-17（CI 安全掃描）

── Phase 2：閾值校準（需回歸驗證）──
AO-16 — 先做全因子回歸測試，再分批調整
AO-1（雙維度分數，依賴 scoring contract）

── Phase 3：核心重構（等 AL close 後）──
AO-3（pipeline Phase A/B，依賴 settlement 決策）
AO-4（lock helper）
AO-11（AppState 拆分）

── Phase 4：數據與測試──
AO-8（survivorship，先做 spike）
AO-6（DataCatalog strict，依賴 API 契約）
AO-7（overlay 預設化）
AO-9（容量前移）
AO-10（failure-mode tests，依賴 AO-3）
AO-13（config profiles）
```

---

### 17. 缺少退出條件

Phase AO 有成功標準但沒有**退出/終止條件**。如果做到一半發現：
- 閾值調整後所有現有因子都無法通過（AO-16 風險）
- AppState 拆分導致大量 regression（AO-11 風險）
- FinLab 下市股數據不可用（AO-8 風險）

計畫沒有定義何時應暫停、回滾或降級目標。

**建議**：每個高風險項目加一個 **abort criteria**：
- AO-16：如果 revenue_acceleration 在新閾值下無法通過 → 暫停，回到舊閾值，單獨評估 max_market_corr
- AO-11：如果 TradingState 拆分後 integration tests 失敗 > 5 個 → 暫停，用 facade 維持現狀
- AO-8：如果 FinLab spike 確認數據不可用 → 降級為 soft warning（不做 hard gate）

---

## 更新後的總評

Phase AO 的方向仍然正確。但這份審計揭示了幾個結構性落差：

1. **工作量被低估**：13 項中 9 項是全新實作，不只是「制度化」
2. **依賴關係不完整**：settlement 決策 → AO-3、scoring contract → AO-1、AL close → AO-4/11
3. **閾值調整風險最高**：max_market_corr 0.80→0.50 可能直接淘汰現有因子
4. **與進行中 Phase 有衝突**：應等 AL close 後再動核心文件
5. **缺少退出條件**：高風險項目沒有定義 abort criteria

修正這些問題後，Phase AO 才算是一份可以安全執行的制度化計畫。
