# Phase AP：AutoResearch 治理與成熟化

> 建立日期：2026-04-02
> 狀態：**92% 完成**（P0 全完成 + P1 全完成，剩 AP-20 需數據源 + P2 中期）
> 優先級：高 — AutoResearch 是新因子工廠主線，資料契約分叉是反覆回歸的根因
> 前提：Phase AO Phase 1 完成
> 審計來源：`docs/reviews/system/AUTO_RESEARCH_REVIEW.md`
> 計畫審計：`docs/reviews/system/PHASE_AP_PLAN_AUDIT_20260402.md`

> **核心原則**：不再擴充因子搜尋能力，而是把研究工廠變成可治理的產品級子系統。從「會挖因子」升級到「可持續、安全、可審計地挖因子」。

---

## 0. 動機

AutoResearch 已經不是原型 — 它有固定評估、40 天延遲、L1-L5 gate、IC dedup、watchdog、Validator + PBO。但系統工程正在接近複雜度拐點：

1. **兩套系統並行** — `scripts/autoresearch/`（因子工廠）和 `src/alpha/auto/`（生產引擎）共用 API namespace，職責不清
2. **資料契約分叉** — evaluate.py、strategy_builder、deployed_executor、Context 各自組裝 data dict，反覆出現「研究能跑、部署失效」的回歸
3. **兩套評估邏輯** — `evaluate.py`（主線）和 `factor_evaluator.py`（舊版）並存，threshold 和 dedup 會漂移
4. **Host 端安全薄弱** — `/submit-factor` 用 `importlib` 動態載入研究代碼，只靠 regex 黑名單防護
5. **Stub endpoint 假完整度** — `/safety-gates` 永遠 all-clear，給使用者虛假信心
6. **缺決策品質監控** — 有流程監控但沒有 gate conversion rate、family entropy、research efficiency

---

## 0b. Critical Bugs（審計第二輪發現，應立即修復）

### AP-C1：eval_server.py variable reference before assignment

**File:** `eval_server.py:251-258`

`ic_source`, `ic_trend`, `best_horizon` 在 line 263-268 才定義，但 line 251 的 metadata dict 已引用。實際行為不是「沿用上一次 evaluate 的值」，而是 library metadata 寫入在 try/except 中觸發例外後被吞掉，造成 metadata 缺失或 library save 靜默失敗。

**修復**：把 extraction 移到 metadata 構建之前，並對 library save failure 加入明確 log，避免靜默失敗。

### AP-C2：Ensemble mode 繞過 L3-L5 gates

**File:** `eval_server.py:300-443`

`/evaluate-ensemble` 只跑 L2（ICIR >= 0.30），不跑 L3 dedup、L4 fitness、L5 OOS。這是最大的 overfitting backdoor。

**修復**：ensemble 至少跑 L3 dedup + L5 OOS，否則停用 endpoint。

### AP-C3：L5 query budget 不是 hard block

**File:** `evaluate.py:1488-1490`

Budget 200 只印 warning 到 stderr，agent 可無限查詢 L5 OOS。

**修復**：超過 budget 後 L5 直接返回 FAIL，不再執行。

---

## 1. P0 — 立即可做（不衝突 AL）

### AP-0：Call-site inventory（AP-1 前置）

**問題**：AP-1 要統一資料契約，但不先列出所有組裝點和呼叫鏈，很容易漏改 Validator 的 `_FactorStrategy` 路徑或 `/submit-factor` 路徑。

**目標**：產出一份完整 inventory，列出每個資料組裝點的：
- 呼叫鏈（誰呼叫誰）
- 使用的 datasets（bars/revenue/per_history/institutional/margin）
- PIT masking 方式（registry delay / 手動截斷 / 無）
- key naming（bare symbol vs `.TW` suffix）

**涵蓋範圍**：
- `scripts/autoresearch/evaluate.py` — `_load_all_data()` + `_mask_data()`
- `src/alpha/auto/strategy_builder.py` — Context 建構
- `src/alpha/auto/deployed_executor.py` — 執行時組裝
- `src/strategy/base.py` Context — `get_revenue()` 等
- `src/backtest/validator.py` — `_FactorStrategy` 內部拉 Context 資料
- `src/api/routes/auto_alpha.py` — `/submit-factor` 的資料準備

**交付物**：`docs/autoresearch/DATA_CONTRACT_INVENTORY.md`

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 低 — 純閱讀分析，不改代碼 |

**驗收**：inventory 覆蓋所有 6 個入口點，每個列出 datasets + PIT + key naming。

### AP-1：FactorDataBundle — 統一資料契約

**問題**：因子 runtime 資料在 4 個地方各自組裝，格式/欄位/PIT 規則不一致。

**現狀（4 個資料組裝點）**：
- `scripts/autoresearch/evaluate.py` — `_load_all_data() + _mask_data()`
- `src/alpha/auto/strategy_builder.py` — 建構 Context 時組裝
- `src/alpha/auto/deployed_executor.py` — 執行時組裝
- `src/strategy/base.py` Context — `get_revenue()` 等方法

**目標**：建立唯一的 `FactorDataBundle` 工廠函式，所有入口共用。

**修改範圍**：
- 新增 `src/data/factor_data.py`：
  ```python
  @dataclass
  class FactorDataBundle:
      bars: dict[str, pd.DataFrame]
      revenue: dict[str, pd.DataFrame]
      per_history: dict[str, pd.DataFrame]
      institutional: dict[str, pd.DataFrame]
      margin: dict[str, pd.DataFrame]
      as_of: pd.Timestamp
      pit_delay_days: dict[str, int]  # per-dataset delay
  
  def build_factor_data(
      symbols: list[str],
      as_of: pd.Timestamp,
      fields: list[str] | None = None,
  ) -> FactorDataBundle:
      """Single source of truth for factor runtime data."""
  ```
- `scripts/autoresearch/evaluate.py`：`_load_all_data() + _mask_data()` 改為呼叫 `build_factor_data()`
- `src/alpha/auto/strategy_builder.py`：改用 `build_factor_data()`
- `src/alpha/auto/deployed_executor.py`：改用 `build_factor_data()`
- 新增 `tests/integration/test_factor_data_consistency.py`：同一因子在 3 個入口拿到的資料一致

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | AP-0 inventory 完成 | **高** — 跨 4 個模組 + evaluate.py（READ ONLY），需逐一改呼叫點 |

**驗收**：evaluate.py、strategy_builder、deployed_executor 共用同一 adapter。跨入口一致性測試通過。現有 L4+ 因子 ICIR 變動 < 5%。

### AP-2：降級 factor_evaluator.py

**問題**：`src/alpha/auto/factor_evaluator.py` 和 `scripts/autoresearch/evaluate.py` 是兩套評估邏輯，threshold 和 dedup 規則會漂移。

**目標**：`evaluate.py` 是唯一評估標準。`factor_evaluator.py` 標記為 legacy。

**修改範圍**：
- `src/alpha/auto/factor_evaluator.py`：頂部加 deprecation warning + 移入 `src/alpha/auto/archive/`
  - 審計確認：**零 call-site**（grep 全 codebase 無 import、無呼叫），可直接標 deprecated
- 文件：更新 autoresearch-guide-zh.md 明確說明唯一標準

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 低 — 零 caller，直接移動 |

**驗收**：`factor_evaluator.py` 在 archive/ 中，主路徑無引用。

### AP-3：Stub endpoint 清理

**問題**：API 控制面有半成品 endpoint，給使用者假完整度。

**需清理的 endpoint**：
- `/safety-gates`：固定回傳 all clear → 標記 `experimental` 或回傳實際狀態
- `/factor-pnl`：固定回傳空列表 → 標記 `experimental`
- `/factor-pool`：沒映射 active/excluded → 標記 `experimental`
- `/run-now`：memory dict 追蹤任務 → 標記 `experimental`

**修改範圍**：
- `src/api/routes/auto_alpha.py`：先修改對應 `response_model`，再加入 `"status": "experimental"` 或 `"warning"` 欄位
- 若不改 schema，就改為返回真實狀態；不能假設直接多回傳欄位就會被客戶端看到

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 低 — 單一檔案 auto_alpha.py |

**驗收**：所有 stub endpoint 的回應都明確標示為 experimental。

### AP-4：AutoResearch Runbook

**問題**：規則散佈在 BUG_HISTORY、LESSONS、EXPERIMENT_STANDARDS、guide、多份 review。新維護者無法快速判斷「現在以哪份為準」。

**目標**：建立一份權威操作手冊 `docs/autoresearch/RUNBOOK.md`。

**內容**：
- 系統邊界（FactorResearchFactory vs ProductionAlphaEngine）
- 唯一評估標準：`evaluate.py`（READ ONLY）
- L1-L5 gate 摘要 + 門檻速查表
- Promotion / deploy 條件
- 緊急停機流程
- Session reset / preflight 規範
- 不可違反的 fail-closed 原則
- 常見故障排除

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 低 — 純文件 |

**驗收**：一份 < 200 行的 RUNBOOK.md，涵蓋所有操作場景。

---

## 2. P1 — 2-4 週

### AP-11：Forward return overlap bias 校正

**問題**：60d horizon 的 IC 每 20 天取一個，但 60d return 跨 3 個 sampling point，自相關被拉高，ICIR 系統性高估。

**修改範圍**：
- `scripts/autoresearch/evaluate.py`：對 60d horizon 改用 60 天 sampling interval，或用 Newey-West SE 替代 `ddof=1 std`
- 至少在 ICIR 計算時做 ESS 校正（目前只在 MAX_ICIR 檢查用）

### AP-12：Git wrapper 改為 allowlist（升至 P0 — 審計建議）

**問題**：agent container 的 git wrapper 是 blocklist，至少 5 種繞過路徑。改動量小（一個 shell script）。

**修改範圍**：
- `docker/autoresearch/Dockerfile.agent`：git wrapper 改為 allowlist
- 只允許：`add`、`commit`、`checkout HEAD~1 -- factor.py`、`tag`、`log`、`diff`、`status`

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 低 — 1 個 shell script，需 docker rebuild |

### AP-13：Credentials mount 改 read-only（升至 P0 — 審計建議）

**問題**：一行 yml 改動，零風險。OAuth token 暴露是真實攻擊面。

**修改範圍**：
- `docker/autoresearch/docker-compose.yml`：改為 `:ro` mount

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 零 — 1 行 yml |

### AP-14：Normalization 計入 multiple comparison

**問題**：5 variants 自動選最佳但未計入多重比較。

**修改範圍**：
- 方案 (a) 固定用 rank（消除自由度）或 (b) `max(5) / sqrt(2 * ln(5))` 校正

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 中 — 改 evaluate.py（READ ONLY），需解鎖 |

### AP-15：Stage 2 重建 _close_matrix

**問題**：Stage 2 載入新 symbols 但 `_close_matrix` 未重建，fallback 慢。

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 低 — evaluate.py 內部改動 |

### AP-16：Program.md 去具體化

**問題**：program.md 列具體門檻，agent 可 reverse-engineer。但 `/evaluate` API 也暴露資訊。

**修改範圍**：
- program.md 移除具體數字
- 盤點 evaluator API 暴露面

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 低 — 純文件 + API response 調整 |

### AP-5：API namespace 分離

**問題**：`/api/v1/auto-alpha/*` 混合了研究工廠和生產引擎的操作。

**目標**：分成兩個 bounded context：
- `/api/v1/factor-research/*` — 新因子挖掘：start/stop agent、submit factor、research status
- `/api/v1/alpha-engine/*` — 已批准因子的部署/監控：deployed list、performance、safety gates

**修改範圍**：
- `src/api/routes/auto_alpha.py` 拆成 `factor_research.py` + `alpha_engine.py`
- 舊 `/auto-alpha/*` 保留 redirect（backward compat）
- 文件與命名收斂：AutoResearch = 因子工廠，AutoAlpha = 生產引擎

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | AP-3 完成 | **高** — 跨 route + 前端，需 backward compat redirect |

**驗收**：兩個 namespace 各自獨立，web/android 客戶端可分別操作。

### AP-6：Host 端 AST 安全檢查

**問題**：`/submit-factor` 用 `importlib` 載入研究代碼，只靠 regex 防護。

**目標**：載入前做 AST 檢查，禁止危險操作。

**AST 黑名單**：
- `import` 語句（只允許 numpy/pandas/math）
- `__` dunder attribute access
- `open()` / `os.*` / `subprocess.*` / `socket.*`
- `eval()` / `exec()` / `compile()`
- `getattr()` / `setattr()` on non-self objects

**修改範圍**：
- 新增 `src/alpha/auto/code_safety.py`：`check_factor_code(source: str) -> list[str]`
- `src/api/routes/auto_alpha.py`：`/submit-factor` 在寫檔前呼叫 AST 檢查
- 失敗 → reject with 具體違規描述

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 中 — 新模組，需測試覆蓋 |

**驗收**：含 `import os` 或 `open()` 或 `__import__('os')` 的因子代碼被拒絕。

### AP-7：研究品質 KPI

**問題**：有流程監控但缺決策品質指標。

**新增指標**：
- `gate_conversion_rate`：L1→L2→L3→L4→L5→Validator→Deploy 的轉化率
- `novelty_rate`：新因子 vs clone vs replace 比率
- `family_entropy`：通過因子的 family 多樣性（Shannon entropy）
- `data_field_usage`：成功因子依賴哪些 dataset
- `research_efficiency`：每 100 次提案的有效部署數

**修改範圍**：
- `docker/autoresearch/watchdog.py`：從 `results.tsv` + `learnings.jsonl` 計算 KPI
- `src/api/routes/auto_alpha.py`：新增 `/research-kpi` endpoint
- 或：`scripts/autoresearch/status.ps1` 加入 KPI 輸出

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | AP-4 runbook 完成 | 低 — watchdog + status.ps1 改動 |

**驗收**：能查詢各 gate 的轉化率和 family 多樣性。

### AP-17：Evaluator 健康監控強化

**問題**：healthcheck 只 ping `/health`，不檢查數據是否可載入。Evaluator 是單線程 Flask，hang 住整個 pipeline 停。

**修改範圍**：
- `docker/autoresearch/eval_server.py`：`/health` 加入數據載入驗證（如檢查 `_data_cache` 是否可用）
- `docker/autoresearch/docker-compose.yml`：healthcheck 加入 timeout + 自動 restart
- watchdog 監控 evaluator 的 `last_request_time`

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | 無 | 低 — docker 配置 + eval_server 改動 |

### AP-18：OOS 確定性與反逆推

**問題**：OOS window 隨日期滾動，同一因子不同天 submit 結果不同。Agent 可推算 OOS dates。

**修改範圍**：
- `scripts/autoresearch/evaluate.py`：OOS window 在 session 啟動時固定（寫入 `watchdog_data/oos_config.json`），不隨日期重算
- evaluate.py 加 KS test：factor 在 IS 和 OOS 的輸出分佈差異 > 0.3 → reject（防 date-conditional logic）
- OOS offset 加 ±30 天隨機化

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | AP-C3 完成 | 中 — 改 evaluate.py OOS 邏輯，影響所有因子結果 |

### AP-20：Universe Survivorship Bias

**問題**：universe.txt 是靜態文件，不含下市股。IC 可能被高估。與 AO-8 獨立：DataBundle 統一格式不等於統一 universe。

**修改範圍**：
- 建立月度歷史 universe 快照（從 TWSE 上市/上櫃名單或 SecuritiesMaster）
- IC 計算用 as_of 日期對應的 universe，不用靜態 universe.txt

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | AO-8 spike 完成 | 中 — 需要歷史 universe 數據源 |

### AP-21：Thresholdout 強化

**問題**：noise scale 固定 0.05 保護力不足；seed 含 factor_hash 可被操控。

**修改範圍**（AP-C3 的後續）：
- noise scale 改為 `0.2 * np.std(ic_series_20d)` 動態計算
- seed 移除 factor_hash，改用 evaluator 啟動時的 session-level random salt
- 合併 AP-6 的 AST complexity check：max 3 data sources, max 2 nested loops

| Owner | Dependency | Blocking risk |
|-------|-----------|---------------|
| Claude | AP-C3 完成 | 中 — 改 evaluate.py L5 + thresholdout 核心 |

---

## 3. P2 — 中期演進

### AP-19：Token Cost Tracking

**問題**：無 API token 消耗追蹤。200 turns 可能消耗大量 token。

**修改範圍**：
- `scripts/autoresearch/status.ps1`：從 agent 日誌提取 token 消耗
- 設定 per-session spending alert

### AP-8：Event log 取代 marker file

**問題**：`pending/`、`deploy_queue/`、`ack/`、`results.tsv` 等檔案同時扮演 workflow state machine 和 artifact storage。

**目標**：SQLite event table 管理 workflow state，檔案只做 artifact storage。

**三張表**：
- `research_runs`：session, factor_name, code_hash, gate_results, status
- `promotion_events`：submitted, validated, blocked, deployed, replaced, expired
- `artifact_registry`：factor code path, report path, return series path, metadata

### AP-9：多 session 支援

**目標**：支援多個研究 agent 並行，共享單一治理層。

### AP-10：部署後回饋閉環

**目標**：部署後 10/20/30 日 ICIR 與 Validator 預估差距回饋到研究工廠，形成閉環。

---

## 4. 施做順序

```
── Critical Bugs（立即修）──
AP-C1（eval_server variable ref）
AP-C2（ensemble L3-L5 gate）
AP-C3（L5 budget hard block）

── P0（立即可做，含審計升級項）──
AP-12（git allowlist — 1 shell script）
AP-13（credentials ro — 1 行 yml）
  ↓
AP-0（call-site inventory）→ AP-1（FactorDataBundle）→ AP-2（直接標 deprecated）
  ↓
AP-3（stub cleanup）→ AP-4（runbook）

── P1（2-4 週）──
AP-21（thresholdout 強化）→ AP-18（OOS 確定性）
  ↓
AP-11（overlap bias）→ AP-14（normalization penalty）→ AP-15（_close_matrix）
  ↓
AP-17（evaluator 監控）→ AP-20（universe survivorship）
  ↓
AP-16（program.md 去具體化）
  ↓
AP-5（API namespace）→ AP-6（AST 安全 + complexity）→ AP-7（KPI）

── P2（中期）──
AP-19（cost tracking）→ AP-8（event log）→ AP-9（多 session）→ AP-10（閉環回饋）
```

---

## 5. 成功標準

### Must-have（AP 可關閉條件）
- [ ] AP-C1~C3 critical bugs 全部修復
- [ ] FactorDataBundle 是唯一資料組裝入口（現有 L4+ 因子在新 bundle 下 ICIR 變動 < 5%）
- [ ] `factor_evaluator.py` 在 `archive/` 中，主路徑零引用
- [ ] 所有 stub endpoint 標記 experimental 或回傳真實數據
- [ ] RUNBOOK.md 存在且 < 200 行
- [ ] L5 query budget 是 hard block（超過 → 直接 FAIL，`grep 'L5_QUERY_BUDGET' evaluate.py` 確認 block 邏輯）
- [ ] Ensemble endpoint 回傳 501 或跑完整 L3+L5 gate
- [ ] Git wrapper 是 allowlist（`grep -c 'case' git-wrapper.sh` == allowlist pattern）
- [ ] Credentials mount read-only（`grep ':ro' docker-compose.yml` 確認）
- [ ] AP 計畫文件與程式引用一致（無不存在的函式名、過時路徑、錯誤 endpoint 假設）

### Nice-to-have
- [ ] Thresholdout 動態 noise scale + secret salt
- [ ] OOS window session-level 固定 + KS test 反逆推
- [ ] Forward return overlap bias 校正
- [ ] Normalization multiple comparison penalty
- [ ] Universe survivorship 歷史快照
- [ ] Evaluator healthcheck 含數據驗證
- [ ] Program.md 移除具體門檻數字
- [ ] Stage 2 _close_matrix 重建
- [ ] API 分 `/factor-research/*` 和 `/alpha-engine/*`
- [ ] Host 端因子載入有 AST + complexity check
- [ ] 研究品質 KPI 可查詢
- [ ] Token cost tracking
- [ ] Event log 取代 marker file workflow
- [ ] 部署後回饋閉環

---

## 6. 退出條件

| 項目 | 風險 | Abort criteria |
|------|------|----------------|
| AP-1 | FactorDataBundle 改動影響 evaluate.py 結果 | 現有 L5 因子在新 bundle 下結果偏差 > 1% → 回滾 |
| AP-5 | API 分離影響前端 | web/android 客戶端 > 3 處 break → 保留舊 namespace |
| AP-6 | AST 檢查過嚴 | 現有已通過因子被誤擋 → 放寬白名單 |

---

## 7. 與其他 Phase 的關係

| 關聯 Phase | 關係 |
|-----------|------|
| AO-5（promotion artifact） | AP-1 的 FactorDataBundle 會被 promotion 流程使用 |
| AO-6（DataCatalog strict） | AP-1 應使用 CatalogResult + require_df |
| AO-2（family budget） | AP-7 的 family_entropy 是 budget 效果的監控 |
| AN-33（E2E tests） | AP-1 的跨入口一致性測試是 E2E 的重要場景 |
