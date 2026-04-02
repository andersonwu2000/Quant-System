# Phase AO：制度化與部署成熟度

> 建立日期：2026-04-02
> 狀態：**82% 完成**（14/17 項，AO-3/4/11 等 AL close）
> 優先級：高 — 系統已具備完整功能，需將能力轉為制度
> 前提：Phase AN 架構重構完成；Phase AL 30 天 paper 觀察完成後再動核心文件
> 審計：`docs/reviews/system/PHASE_AO_PLAN_AUDIT_20260402.md`

> **核心原則**：Phase AO 包含「制度化」（把已存在能力正式化）和「補缺」（補齊方法論與安全性缺口）兩類工作。

> **來源**：`docs/reviews/methodology/DEEP_PROJECT_RECOMMENDATIONS_20260402.md` 全專案深度檢視 + Phase AN 遺留項目

---

## 0. 動機

系統成熟度評估在功能面完整，但營運成熟度不足。核心差距：

1. **研究與部署混為一體** — validator 把統計顯著性和可交易性放在同一份 pass/fail
2. **Alpha 來源過度集中** — 所有部署因子都是 revenue 家族，同敘事擁擠風險高
3. **交易流程不夠 fail-closed** — pipeline 單線式，失敗模式不明確
4. **狀態管理過重** — AppState 承擔過多責任，lock 規則靠註解自律
5. **promotion 缺乏 artifact** — 研究結果進 paper/live 沒有統一真相來源

---

## 0b. 制度契約（審計要求：先定義再實作）

在任何代碼改動前，先確立以下契約：

### 輸出分類
- **Research artifact**：validation_report.json — 每次驗證產出，可覆寫，不影響部署
- **Promotion artifact**：promotion_decision.json — 僅由明確的 promotion step 產出，不可由 validate() 自動寫入

### 流程可重試性
- Phase A（data → weights）：可重試，無外部副作用
- Phase B（orders → execution）：三態模型，不可簡單回滾（見 AO-3）

### Score / Gate / Decision 關係
- Hard gate 先行 — 任一 hard gate fail → 直接 FAIL，不計算 score
- Score 只在 hard gate 全通過後用於排序比較，不直接決定 passed
- Decision（promotion）是獨立動作，吃 validation report 但不等於 validation

### Family 判定
- 使用顯式 metadata（`family` + `economic_thesis` 欄位），不靠命名猜測
- 寫進 factor metadata 或 results.tsv，evaluate.py 從此欄位判斷 budget

---

## 1. Phase 0 — 契約與決策（無代碼改動）

在開始任何實作前完成：

1. ✅ 決定 settlement 方案 → **採方案 A**：`available_cash` 直接返回 `self.cash`

2. ✅ Scoring contract：
   - 每個 check 標記 `dimension: "research" | "deployment" | "both"`
   - Research score = 通過的 research checks 數 / 總 research checks 數（等權，不加權）
   - Deployment score = 同理
   - `passed` 不變（仍由 hard gate 決定），score 僅用於策略間排序比較
   - 未來可升級為加權 score，但 v1 用等權避免假精確

3. ✅ DataCatalog API 契約：
   - 現有 `get()` 保持不變（回傳 DataFrame，backward compatible）
   - 新增 `get_result()` 回傳 `CatalogResult(status, df)`
   - 交易路徑用 `require_df(catalog.get_result(...))` 取得 DataFrame 或 raise
   - Status codes: `ok` / `missing_symbol` / `missing_dataset` / `read_error`

4. ✅ Family metadata schema：
   - `results.tsv` 新增 `family` 欄位（必填）
   - 有效值：`revenue` / `value` / `quality` / `low_vol` / `momentum` / `event` / `other`
   - evaluate.py 從 `family` 欄位判斷 budget，不從名稱猜
   - Agent 在 commit message 中標記 `[family: xxx]`，evaluate.py 解析寫入 results.tsv

5. ✅ Phase B 三態模型：
   - `pre_submit_failure`：Phase B 開始前或 risk approval 階段失敗 → 安全中止，無外部副作用
   - `submitted_not_persisted`：委託已送出但 portfolio 未更新 → 不可回滾，寫 ledger，重啟後由 reconcile 恢復
   - `persisted_complete`：portfolio mutation + persistence 都完成 → 正常結束

---

## 2. Phase 1 — 獨立項目（不碰 state.py / jobs.py）

### AO-2：Family budget 強制機制

**問題**：autoresearch 白名單有 5 個家族，但無強制配額。

**目標**：同家族因子進入 L4+ 的數量上限為 3 個。

**修改範圍**：
- Factor metadata：新增顯式 `family` 欄位（不靠名稱前綴猜測）
- `scripts/autoresearch/evaluate.py`：L4 入口讀 `results.tsv` 的 family 欄位，超過 3 → L3_family_budget
- `docker/autoresearch/watchdog.py`：deploy 時也檢查 family budget

**驗收**：revenue 家族有 3 個 L4+ 因子時，新 revenue 因子被自動擋在 L3。

### AO-5：Promotion artifact（分離 validation / promotion）

**問題**：promotion 決策散落各處。validate() 是研究行為，不等於 promotion 決策。

**目標**：建立兩層 artifact：
- `validation_report.json`：每次 validate() 產出，純研究記錄
- `promotion_decision.json`：僅由明確的 promotion step 產出（如 CLI command 或 API endpoint）

**schema（promotion_decision）**：
```json
{
  "strategy_id": "revenue_acceleration_v3",
  "validator_version": "v3.0-AM",
  "validation_report_path": "data/validations/2026-04-02_rev_acc.json",
  "data_snapshot_date": "2026-04-02",
  "universe_snapshot_id": "tw_top200_20260402",
  "code_version": "a19c5e4",
  "decision_basis_version": "AO-1_scoring_v1",
  "research_score": 0.85,
  "deployment_score": 0.72,
  "approved_mode": "paper",
  "blocking_reasons": [],
  "reviewer": "system",
  "timestamp": "2026-04-02T14:30:00+08:00"
}
```

**修改範圍**：
- `src/backtest/validator.py`：validate() 寫 validation_report.json（research artifact）
- 新增 `src/alpha/promotion.py`：`promote()` 函式讀 validation report → 寫 promotion_decision.json
- `src/alpha/auto/paper_deployer.py`：deploy 前讀取 promotion artifact 驗證

**驗收**：validate() 不寫 promotion artifact。promotion 需明確呼叫 promote()。

### AO-12：OOS loss attribution 標準化

**問題**：OOS 退化時缺標準化歸因框架。

**目標**：5 維度自動歸因：因子失效 / 組合失效 / 執行失效 / regime 失效 / 擁擠失效。

**修改範圍**：
- `src/backtest/checks/descriptive.py`：新增 `_compute_loss_attribution()`
- 當 OOS Sharpe < 0 時自動產出

**驗收**：Validator 報告在 OOS 退化時附帶分類歸因。

### AO-14：金融公式對齊

**問題**：Sharpe 忽略無風險利率（analytics 用 0%，optimizer 用 2%）；Sortino 未用 MAR。

**修改範圍**：
- `src/backtest/analytics.py`：Sharpe 統一使用 config `risk_free_rate`（預設 2%）
- `src/backtest/analytics.py`：Sortino 加 MAR 參數（預設 0）

**驗收**：Sharpe/Sortino 與 optimizer 使用相同 risk_free_rate。

### AO-15：IC 方法論修正

**問題**：IC 去重用 Pearson 但 IC 本身用 Spearman；產業中性化均值在非 common 集上算。

**修改範圍**：
- `scripts/autoresearch/evaluate.py`：去重改用 `method='spearman'`
- `scripts/autoresearch/evaluate.py`：產業均值在 common 子集重算

**驗收**：去重與 IC 計算方法一致。

### AO-17：CI 安全掃描

**修改範圍**：
- `.github/workflows/ci.yml`：新增 `pip-audit` + `bandit` 步驟

**驗收**：CI 包含安全掃描，高危漏洞阻擋合併。

---

## 3. Phase 2 — 閾值校準（需回歸驗證）

### AO-16：閾值校準

**前提**：先做全因子回歸測試 — 所有歷史 passed 因子用新閾值重驗，列出哪些翻盤。

| 參數 | 現值 | 建議值 | 風險 |
|------|------|--------|------|
| `max_market_corr` | 0.80 | **0.65→0.50** | **最激進** — 單獨評估，漸進調整 |
| `min_icir` (L2) | 0.30 | 0.15 | 放寬，風險低 |
| `max_icir` (L2) | 1.00 | 0.50 | 收緊，可能淘汰過擬合因子 |
| `risk_free_rate` | 0% | 2% | 連動 AO-14 |

**abort criteria**：revenue_acceleration 在新閾值下無法通過 → 暫停，回到舊閾值，單獨評估 max_market_corr。

### AO-1：Validator 雙維度分數

**前提**：scoring contract 已定義（Phase 0 §2）。

**目標**：ValidationReport 輸出 research_score + deployment_score。

**設計約束**（審計要求）：
- Hard gate 先行 — 任一 hard gate fail → 直接 FAIL，不算 score
- Score 只在 hard gate 全通過後做排序比較
- 每個 check 標記歸屬（research / deployment / both）
- 聚合方式和權重固定在 schema 中

**修改範圍**：
- `src/backtest/validator.py`：ValidationReport 新增雙分數
- `src/backtest/validation_schema.py`：JSON schema 加入雙分數
- `passed` 屬性維持 hard gate 邏輯不變，score 純粹用於排序

**驗收**：revenue_acceleration 產出雙分數報告。Score 不影響 passed 判定。

---

## 4. Phase 3 — 核心重構（等 AL close + 30 天 paper 觀察後）

### AO-3：Pipeline 兩段式 + 三態模型

**前提**：settlement 方案已決定（方案 A）；Phase B 三態模型已定義。

**Phase B 三態模型**（取代原「全回滾」承諾）：
- `pre_submit_failure`：可安全中止，無外部副作用
- `submitted_not_persisted`：不可回滾，必須進 recovery / reconcile
- `persisted_complete`：完成

**修改範圍**：
- `src/scheduler/jobs.py`：拆成 `_phase_a()` + `_phase_b()`
- 新增 `WeightDecision` / `ExecutionResult` dataclass
- Phase B 失敗時：本地狀態不假裝成功 + 所有外部副作用有 ledger + 重啟後可由 reconcile 恢復

**驗收**：Phase A 失敗時 Phase B 不執行。Phase B 在 submitted_not_persisted 狀態有 audit trail。

### AO-4：Lock helper 抽象

**現狀**：直接使用 lock 的位置約 **20 處**。

**目標**：分批遷移到 helper。

**Phase 1**：TradingState 相關 routes（orders/risk/portfolio/execution）全切 helper
**Phase 2**：其他（backtest/alpha/scheduler/bootstrap）

**修改範圍**：
- `src/api/state.py`：新增 `with_trading_mutation()` / `with_portfolio_read()` helper
- 遷移追蹤表列出 20 處，逐個標記
- 補 race-condition tests

**abort criteria**：migration 導致 integration tests 失敗 > 5 個 → 暫停，保持 facade。

**驗收**：TradingState routes 零直接 lock 使用。Race-condition tests 通過。

### AO-11：AppState 拆分

**目標**：按模組切割（非比例）：
- **TradingState**：portfolio, execution, oms, stop_orders, kill_switch, realtime_risk, quote_manager, mutation_lock
- **SupportState**：strategies dict, backtest_lock, alpha_lock, scheduler, auto-alpha

**驗收**（按模組，非比例）：
- `orders/risk/portfolio/execution` routes 全部切到 TradingState
- `backtest/auto-alpha` 全部切到 SupportState
- Facade 僅保留一版相容層，禁止新增呼叫點

**abort criteria**：拆分後 integration tests 失敗 > 5 個 → 暫停，用 facade 維持現狀。

---

## 5. Phase 4 — 數據與測試

### AO-8：Survivorship 數據取得 + gate

**前提**：先做 spike — 確認 FinLab 是否提供已下市公司歷史價格、API 限制、成本。

**目標**：取得下市股歷史數據，建立 survivorship coverage gate。

**abort criteria**：FinLab spike 確認數據不可用 → 降級為 soft warning（不做 hard gate）。

### AO-6：DataCatalog strict mode

**前提**：API 契約已定義（Phase 0 §3）。

**建議契約**：`get()` 一律回傳 `CatalogResult`（含 status + df），由 helper `require_df()` 在交易路徑 raise。

```python
@dataclass
class CatalogResult:
    status: str  # ok / missing_symbol / missing_dataset / read_error
    df: pd.DataFrame
    
def require_df(result: CatalogResult) -> pd.DataFrame:
    if result.status != "ok":
        raise DataNotAvailableError(result.status)
    return result.df
```

**修改範圍**：
- `src/data/data_catalog.py`：新增 `CatalogResult` + `get_result()`
- 現有 `get()` 保持不變（backward compatible）
- 交易路徑改用 `require_df(catalog.get_result(...))`

### AO-7：Overlay 預設化

**目標**：revenue 類策略預設啟用 overlay（position cap 10% + sector cap 30% + beta 0.7-1.1）。

### AO-9：容量研究前移到 evaluate.py

**目標**：L4 閘門加入容量估算（ADV 佔比、建倉/清倉天數、cost/alpha 比率、衰減曲線）。

### AO-10：Failure-mode 整合測試

**前提**：依賴 AO-3 完成（Phase A/B 分段）。

**目標**：6 個 failure-mode 場景（見原計畫）。

### AO-13：Config profiles

**目標**：Dev/Paper/Live profile 驗證，每個 profile 定義必要 secrets 和預設行為。

---

## 6. 施做順序

```
── Phase 0：契約與決策（無代碼改動）──
① settlement 方案 A ✅
② scoring contract
③ DataCatalog API 契約
④ family metadata schema
⑤ Phase B 三態模型

── Phase 1：獨立項目（不碰 state.py / jobs.py）──
AO-2（family budget）→ AO-5（promotion artifact）→ AO-12（loss attribution）
  ↓
AO-14（金融公式）→ AO-15（IC 方法論）→ AO-17（CI 安全掃描）

── Phase 2：閾值校準（需回歸驗證）──
全因子回歸測試 → AO-16（分批調整）→ AO-1（雙維度分數）

── Phase 3：核心重構（等 AL close 後）──
AO-3（pipeline 三態）→ AO-4（lock helper Phase 1）→ AO-11（AppState 拆分）→ AO-4 Phase 2

── Phase 4：數據與測試 ──
AO-8（spike → survivorship）→ AO-6（DataCatalog strict）→ AO-7（overlay）
  ↓
AO-9（容量前移）→ AO-10（failure-mode tests）→ AO-13（config profiles）
```

---

## 7. 成功標準

### Must-have（全部完成才算 AO 可關閉）
- [ ] Factor family metadata 使用顯式欄位，非命名猜測
- [ ] 同家族 L4+ 因子 ≤ 3 個（自動擋）
- [ ] Validation report 和 promotion decision 是分離的 artifact
- [ ] Pipeline Phase A/B 分段，Phase B 用三態模型
- [ ] Lock helper 覆蓋 TradingState routes（零直接 lock 使用）
- [ ] Sharpe/Sortino 統一使用 risk_free_rate
- [ ] IC 去重與 IC 計算用相同方法（Spearman）
- [ ] CI 包含 pip-audit + bandit

### Nice-to-have（提升成熟度但不阻擋關閉）
- [ ] Validator 雙維度分數（research_score + deployment_score）
- [ ] 閾值校準完成（max_market_corr、ICIR 門檻）
- [ ] DataCatalog CatalogResult 契約
- [ ] Revenue 策略預設 overlay
- [ ] Survivorship coverage gate
- [ ] evaluate.py L4 容量估算
- [ ] OOS loss attribution 自動歸因
- [ ] ≥ 6 個 failure-mode 整合測試
- [ ] Config Dev/Paper/Live profiles
- [ ] AppState 拆分（TradingState + SupportState）

**AO-4 / AO-11 邊界說明**：AO-4（lock helper）是 must-have，AO-11（state 拆分）是 nice-to-have。AO 關閉時允許保留 facade，但 must-have 要求 TradingState 邊界收斂完成（orders/risk/portfolio/execution routes 的 lock 使用全部走 helper）。AO-11 的 SupportState 分離可延後到下一個 Phase。

### 成熟度提升目標
- 系統成熟度從 3.5/5 → 4.0+/5
- 營運成熟度從 3.0/5 → 3.5+/5

---

## 8. 退出條件

| 項目 | 風險 | Abort criteria |
|------|------|----------------|
| AO-16 | 閾值調整後現有因子全部無法通過 | revenue_acceleration 不通過 → 暫停，回舊閾值 |
| AO-11 | AppState 拆分導致 regression | integration tests 失敗 > 5 → 暫停，用 facade |
| AO-8 | FinLab 下市股數據不可用 | spike 確認不可用 → 降級為 soft warning |
| AO-4 | Lock 遷移破壞競態保護 | race-condition test 失敗 → 回滾到直接 lock |

---

## 9. 與進行中 Phase 的衝突管理

| AO 項目 | 修改文件 | 衝突 Phase | 處理 |
|---------|---------|-----------|------|
| AO-3 | jobs.py | AG, AL | 等 AL close 後 |
| AO-4 | state.py | AL | 等 AL close 後 |
| AO-5 | validator.py | AG（若 AG 動 validator） | 確認 AG 範圍後再開始 |
| AO-11 | state.py | AL | 等 AL close 後 |
| AO-14 | analytics.py | — | 低衝突，可先做 |
| AO-15 | evaluate.py | AG（若 AG 動 evaluate） | 確認 AG 範圍後再開始 |
| AO-16 | validator.py, evaluate.py | AG | 需回歸測試 |

**原則**：Phase 1 中 AO-2/12/14/17 不碰衝突文件，可立即開始。AO-5/15 需先確認 AG 是否動到 validator.py / evaluate.py，若無衝突亦可先做。Phase 3 等 AL close。

---

## 10. 與 Phase AN 的關係

| AN 遺留項 | AO 承接 |
|-----------|---------|
| AN-2（AppState DI） | AO-11 |
| AN-6（pipeline boundary） | AO-3 |
| AN-31（survivorship data） | AO-8 |
| AN-33（E2E tests） | AO-10 |

---

## 11. 補充審計已修復項目

| # | 問題 | 狀態 |
|---|------|------|
| B-1 | 漲跌停 9.5% → 10% | ✅ 已修 |
| B-2 | prev_close 缺失 fail-open → fail-closed | ✅ 已修 |
| C-1 | API 憑證在 git 歷史 | ✅ 誤報 — .env 從未提交 |
| C-2 | admin 密碼預設值 | ✅ AN 安全修復已處理 |
| A-10 | 結算現金雙重計入 | ✅ 決定方案 A（Phase 0 §1）|

## 12. 設計層級備查（暫不收入）

| # | 問題 | 理由 |
|---|------|------|
| A-2 | CAGR 日曆日 vs 交易日 | 系統內一致，改動影響歷史比較 |
| A-8 | Rolling IC 重疊窗口 | 標注「非獨立」即可 |
| A-11 | Corporate action handler | 大型獨立專案 |
| A-12 | ffill 無下市偵測 | AO-8 涵蓋 |
| B-4 | 持倉上限 MODIFY vs REJECT | 設計選擇 |
| C-4 | WS token in query string | WebSocket 標準做法 |
| D-1 | PE/PBR PIT delay | 日頻用 T-1 已足夠 |
| D-2 | Slippage 未校準 | 需實盤數據 |
| D-3 | OOS 採樣盲區 | L5 已用每日頻率 |
| E-1 | 冪等非多進程安全 | 單實例系統 |
| G | 季度審計 + factor zoo | 營運流程 |
