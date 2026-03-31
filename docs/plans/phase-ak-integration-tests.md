# Phase AK: Pre-Live Test Strategy

> Status: ✅ AK-1 + AK-2 已驗收（2026-03-31）
> Created: 2026-03-31
> Goal: 建立完整測試體系，確保從因子發現到實盤交易的全管線正確性、效能、安全性

---

## 背景

2026-03-31 單日發現 9 個跨模組 bug（data dict 不一致、死碼、symbol 格式、假警報等），根因是各模組獨立開發後缺乏整合測試。現有 1,700+ 單元測試覆蓋單模組正確性，但模組間接口、端到端流程、效能基準、安全性幾乎零覆蓋。

**系統規模**：~30,000 LOC Python + React + Android，15 項策略驗證閘門，Docker autoresearch 3 容器。

---

## 測試金字塔

```
                    ┌─────────┐
                    │   E2E   │  ~5%   完整交易日模擬
                   ─┼─────────┼─
                  │  Security  │  ~5%   API 安全、沙箱逃逸
                 ─┼────────────┼─
               │  Performance   │  ~5%   延遲基準、吞吐量
              ─┼────────────────┼─
            │    Integration      │  ~15%  模組間接口、資料一致性
           ─┼──────────────────────┼─
         │        Unit (existing)    │  ~70%  1,700+ 測試（不動）
         └───────────────────────────┘
```

---

## 目錄結構

```
tests/
├── unit/                        # 現有 1,700+（不動）
├── integration/                 # AK-2: 模組間接口
│   ├── conftest.py              # 共用 fixtures（合成市場資料、mock broker）
│   ├── test_data_consistency.py
│   ├── test_factor_to_strategy.py
│   ├── test_deployment_lifecycle.py
│   ├── test_restart_recovery.py
│   ├── test_reconciliation.py
│   └── test_alerts.py
├── e2e/                         # AK-3: 端到端
│   ├── test_full_trading_day.py
│   ├── test_paper_to_live.py
│   └── test_autoresearch_cycle.py
├── performance/                 # AK-4: 效能基準
│   ├── test_backtest_throughput.py
│   ├── test_factor_evaluation.py
│   └── test_api_latency.py
├── security/                    # AK-5: 安全
│   ├── test_api_auth.py
│   ├── test_factor_sandbox.py
│   └── test_input_validation.py
├── resilience/                  # AK-6: 韌性/混沌
│   ├── test_broker_disconnect.py
│   ├── test_data_feed_failure.py
│   └── test_container_crash.py
└── fixtures/                    # 共用測試資料
    ├── synthetic_prices.parquet
    ├── synthetic_revenue.parquet
    └── known_factor_results.json
```

---

## AK-1: 測試基礎設施 ✅ 已驗收

### 1.1 conftest.py 共用 Fixtures

| Fixture | Scope | 用途 |
|---------|-------|------|
| `synthetic_bars` | session | 確定性價格序列（固定 seed, 100 支 × 500 天） |
| `synthetic_revenue` | session | 月營收（含 yoy_growth, 40 天延遲可驗證） |
| `synthetic_per` | session | 每日 PER/PBR（含 FinLab panel 格式） |
| `mock_portfolio` | function | 有 10 支持倉的 Portfolio（每次測試隔離） |
| `mock_sinopac` | function | Mock SinopacBroker（可注入斷線/延遲） |
| `temp_data_dir` | function | 臨時 data/ 目錄（測試後清除） |
| `known_factor` | session | revenue_acceleration 因子函式 + 已知 IC 結果 |

### 1.2 測試資料策略

| 類型 | 用途 | 管理方式 |
|------|------|---------|
| **確定性合成資料** | 單元/整合測試 | 固定 seed 生成，存 `tests/fixtures/`，版本控制 |
| **真實資料子集** | 回測驗證 | 10 支股 × 3 年，從 `data/` 提取 snapshot |
| **Monte Carlo 模擬** | 壓力/韌性測試 | 動態生成（黑天鵝、flash crash、連續跌停） |

### 1.3 CI/CD 門檻

```
PR Merge Gate (< 3 min):
  ├── ruff check + mypy strict
  ├── Unit tests (1,700+)
  └── Integration tests (AK-2, ~22 tests)

Deploy Gate (< 15 min):
  ├── E2E tests (AK-3)
  ├── Performance benchmarks vs baseline (AK-4)
  └── Security scan (AK-5)

Nightly (< 60 min):
  ├── Full regression (all layers)
  ├── Resilience tests (AK-6)
  └── Backtest validation (已知結果交叉驗證)
```

---

## AK-2: 整合測試（59 tests, P0）✅ 已驗收

> 驗證 2026-03-31 發現的 bug 不再復發。實際實作 59 tests（超過計畫的 22）。

### Layer 1: 數據一致性（4 tests）

| Test | 驗證 |
|------|------|
| 1.1 Data dict key 一致性 | evaluate.py `_mask_data` 的 key 集合 = _FactorStrategy / strategy_builder / deployed_executor / vectorized.py / run_full_factor_analysis 的 data dict key |
| 1.2 Context vs DataCatalog | `Context.get_revenue("2330.TW")` 行數 = `DataCatalog.get("revenue", "2330.TW")` 行數（FinLab panel 有合併） |
| 1.3 Context 新方法 | `get_per_history` 返回 PER/PBR；`get_institutional` 返回 trust_net；`get_margin` 返回 margin_usage；全部截止到 `ctx.now()` |
| 1.4 權重公式一致性 | 三處都用 `min(0.95/n, 0.10)` + 流動性 300 手 + 月度換倉 |

### Layer 2: 因子→策略全流程（3 tests）

| Test | 驗證 |
|------|------|
| 2.1 revenue_acceleration 端到端 | L5 PASS → _FactorStrategy 返回有效權重 → strategy_builder 返回有效權重 |
| 2.2 per_value 端到端 | 依賴 per_history 的因子在 Validator wrapper 中不 crash |
| 2.3 API submit-factor | POST → 因子存檔 → Validator 跑完 → 返回結果 |

### Layer 3: 部署生命週期（5 tests）

| Test | 驗證 |
|------|------|
| 3.1 Deploy → Execute → NAV | deployed.json 寫入 → 權重生成 → NAV 更新 → paper trade 記錄 |
| 3.2 Monthly rebalance | 同月=沿用權重，跨月=重算 |
| 3.3 Kill switch | MDD > 3% → status="killed" |
| 3.4 30 天過期 | deploy_date 31 天前 → status="expired" |
| 3.5 API 管理端點 | GET /deployed、GET /deployed/{name}/history、POST /deployed/{name}/stop |

### Layer 4: 重啟恢復（4 tests）

| Test | 驗證 |
|------|------|
| 4.1 Portfolio 持久化 | save → load → positions/cash 完全一致 |
| 4.2 Pipeline 冪等性 | 已完成的 run → 再次呼叫 → 跳過 |
| 4.3 Deployed 冪等性 | 同月重啟 → _should_rebalance = False |
| 4.4 Ledger crash recovery | ledger 有 fill 但 portfolio 未存 → load 時 replay 補上 |

### Layer 5: 對帳與格式（3 tests）

| Test | 驗證 |
|------|------|
| 5.1 混合 symbol 格式 | .TW vs bare → matched/mismatched/system_only/broker_only 全正確 |
| 5.2 Mode guard (scheduler) | paper mode → reconcile 跳過 |
| 5.3 Mode guard (API) | paper mode → POST /reconcile 返回 400 |

### Layer 6: 監控告警（3 tests）

| Test | 驗證 |
|------|------|
| 6.1 Paper mode 無告警 | Discord notifier 不被呼叫 |
| 6.2 Live mode 差異告警 | Mock broker 持倉不一致 → notifier 被呼叫 |
| 6.3 Kill switch 告警 | MDD > 3% → logger.warning |

---

## AK-3: 端到端測試（3 tests, P1）

> 模擬完整交易日，從開盤到關機

### Test E2E-1: 完整交易日模擬

```
07:50 daily_ops 觸發
  → 交易日檢查 ✓
  → TWSE snapshot（mock）→ 資料寫入
  → Yahoo refresh（mock）→ 資料更新
  → execute_pipeline
    → 策略產生權重
    → SimBroker 模擬成交
    → Portfolio 更新 + 存檔
  → deployed strategies 日頻執行
13:30 eod_ops 觸發
  → reconcile 跳過（paper mode）
  → daily summary 產出
驗證：Portfolio 持倉 > 0, NAV 變化合理, pipeline_runs 記錄存在
```

### Test E2E-2: Paper → Live 切換

```
1. Paper mode 跑一天 → 確認 reconcile 跳過
2. 切換 config.mode = "live"
3. Mock SinopacBroker 連線
4. 再跑一天 → 確認 reconcile 執行、summary 送 Discord
5. 切回 paper → 確認 reconcile 又跳過
```

### Test E2E-3: Autoresearch 完整循環

```
1. 準備 factor.py（revenue_acceleration）
2. 呼叫 evaluator API → L1-L5 評估
3. 結果寫入 results.tsv
4. 若通過 → pending marker 寫入
5. process_deploy_queue → 部署
6. execute_deployed_strategies → 日頻執行
驗證：全流程無 crash，每步輸出格式正確
```

---

## AK-4: 效能測試（P2）

> 確保關鍵路徑不退化，用 pytest-benchmark 追蹤

### 4.1 回測引擎吞吐量

| 指標 | 基準 | 方法 |
|------|------|------|
| BacktestEngine.run() | < 30s（200 支 × 8 年） | pytest-benchmark, 固定資料 |
| evaluate.py L1-L5 | < 120s（200 支 universe） | pytest-benchmark |
| Factor IC 計算 | < 0.5s / date | 單次 _compute_ic + _compute_forward_returns |

### 4.2 API 延遲

| 端點 | p95 基準 | 方法 |
|------|---------|------|
| GET /portfolio/status | < 100ms | Locust（10 concurrent） |
| POST /execution/reconcile | < 5s | Locust |
| GET /auto-alpha/deployed | < 200ms | Locust |

### 4.3 效能退化門檻

- CI 每次比較歷史基準，**偏差 > 30% 阻止合併**
- 每週生成效能趨勢報告

---

## AK-5: 安全測試（P2）

> OWASP API Security Top 10 for Fintech

### 5.1 認證與授權

| Test | 驗證 |
|------|------|
| JWT 過期 | 過期 token → 401 |
| API Key 無效 | 錯誤 key → 401 |
| 角色越權 | trader 呼叫 admin 端點 → 403 |
| BOLA | 用戶 A 存取用戶 B 的 portfolio → 403 |

### 5.2 Factor 沙箱安全

| Test | 驗證 |
|------|------|
| os/subprocess import | submit-factor 拒絕含 `import os` 的代碼 |
| open() 呼叫 | 拒絕含 `open(` 的代碼 |
| importlib 繞過 | 拒絕含 `importlib` 的代碼 |
| \_\_import\_\_ | 拒絕含 `__import__` 的代碼 |
| exec/eval | 拒絕含 `exec(`/`eval(` 的代碼 |

### 5.3 輸入驗證

| Test | 驗證 |
|------|------|
| SQL injection | symbol 參數含 `'; DROP TABLE` → 無害 |
| XSS | 策略名稱含 `<script>` → 被 sanitize |
| 超大請求 | 10MB factor code → 拒絕 |
| 負數金額 | 下單數量 -1000 → 拒絕 |

---

## AK-6: 韌性測試（P3）

> 混沌工程：系統在故障下的行為

### 6.1 券商斷線

| 場景 | 預期 |
|------|------|
| 下單途中 Sinopac timeout | 訂單標記 pending，不重複送單 |
| query_positions 失敗 | reconcile 記錄 error，不 auto-correct |
| 連線後立刻斷 | 重試 3 次後放棄，記錄告警 |

### 6.2 資料源故障

| 場景 | 預期 |
|------|------|
| TWSE API 503 | 跳過 snapshot，用本地資料繼續 |
| Yahoo API rate limit | 增量更新失敗，pipeline 用既有資料 |
| FinLab panel 檔案損壞 | DataCatalog fallback 到 per-symbol 檔案 |

### 6.3 Docker 容器 crash

| 場景 | 預期 |
|------|------|
| Agent 容器被 kill | loop.ps1 偵測 + 重啟，factor.py 不受影響 |
| Evaluator crash mid-evaluation | Agent 收到 error，retry 或 skip |
| Watchdog crash | 不影響 agent/evaluator，deployment queue 暫停 |

### 6.4 資料不一致

| 場景 | 預期 |
|------|------|
| Revenue 含 inf/NaN | 因子 clip 到 [-500%, 5000%]，不傳播 |
| 價格為 0 或負數 | 替換為 NaN，>10% 壞資料 → 排除該股 |
| 空 universe (< 50 支) | fail-closed，不執行交易 |

---

## 實施路線

| 階段 | 內容 | 預估 | 實際 | 狀態 |
|:----:|------|:----:|:----:|:----:|
| **AK-1** | conftest + fixtures | 0 | conftest.py (session fixtures) | ✅ |
| **AK-2** | test_data_consistency | 4 | 12 | ✅ |
| **AK-2** | test_factor_to_strategy | 3 | 7 | ✅ |
| **AK-2** | test_deployment_lifecycle | 5 | 9 | ✅ |
| **AK-2** | test_restart_recovery | 4 | 9 | ✅ |
| **AK-2** | test_reconciliation_formats | 3 | 11 | ✅ |
| **AK-2** | test_alerts | 3 | 3 | ✅ |
| **AK-2** | test_bug_regressions | — | 8 | ✅（額外） |
| **AK-3** | 端到端測試 | 3 | — | ⏳ |
| **AK-4** | 效能基準 | 6 | — | ⏳ |
| **AK-5** | 安全測試 | 13 | — | ⏳ |
| **AK-6** | 韌性測試 | 10 | — | ⏳ |
| | | **計畫 54** | **實際 59 new + 66 existing = 125 integration** | |

---

## 工具清單

| 工具 | 用途 | 安裝 |
|------|------|------|
| pytest | 測試框架（已有） | — |
| pytest-benchmark | 效能基準追蹤 | `pip install pytest-benchmark` |
| hypothesis | Property-based testing（金融計算不變量） | `pip install hypothesis` |
| locust | API 負載測試 | `pip install locust` |
| OWASP ZAP | 自動化安全掃描 | Docker image |
| coverage | 覆蓋率報告 | `pip install coverage` |

---

## 覆蓋率目標

| 類別 | 現況 | 目標 |
|------|:----:|:----:|
| 單元測試 | 1,810 tests | 維持 |
| 整合測試 | 125 tests（66 existing + 59 new） | ✅ 達成 |
| E2E | 0 | 3 tests |
| 效能基準 | 0 | 6 benchmarks |
| 安全測試 | 0 | 13 tests |
| 韌性測試 | 0 | 10 tests |
| **程式碼覆蓋率** | **未量測** | **≥ 80%** |

---

## Live 前 Checklist

- [ ] AK-2 Layer 1-6 全部 PASS（22 integration tests）
- [ ] AK-3 E2E 3 tests PASS
- [ ] AK-5 安全測試 13 tests PASS
- [ ] 程式碼覆蓋率 ≥ 80%
- [ ] 取得 Sinopac 憑證
- [ ] Paper mode 跑 30 天觀察期
- [ ] 觀察期間 0 假警報
- [ ] 觀察期 NAV 追蹤與手動計算一致（< 1% 誤差）
- [ ] 切換 config.mode = "live" 並確認 reconciliation CLEAN
- [ ] Sinopac 斷線韌性測試通過

---

## 參考來源

- QuantStart — Backtesting Systematic Trading Strategies
- Two Sigma — Treating Data as Code (dbt 框架)
- Lopez de Prado — Combinatorial Purged Cross-Validation (CPCV)
- OWASP API Security Top 10
- QASource / TestSigma — Trading Application Testing
- CircleCI — CI/CD for Banking
- Exactpro — Market Data Systems Testing
- Hypothesis — Property-Based Testing for Python
- Locust — Load Testing Framework
- Taiwan FSC — 證券商內控內稽規範

---

## 嚴格審批（2026-03-31）

### 判定：設計品質高。3 個事實修正 + 2 個範圍建議。AK-2 可立即開始。

---

### 事實修正

**1. 現有測試數 1,700+ 應為 1,810+**

背景段和覆蓋率表多處寫「1,700+」，但今天修完所有 bug 後已有 1,810 個 test（加上既有 integration tests 共 1,815）。

**2. 已有 66 個 integration tests，不是 0**

`tests/integration/` 已有 `test_api.py`（58 tests）和 `test_pipeline_integration.py`（8 tests）。覆蓋率表寫「整合測試 0」不準確。新增的 22 個應定位為**補充現有 66 個的空白區域**（數據一致性、部署生命週期、對帳格式），而非從零開始。

**3. AK-2 Layer 1.1 的 5 處 data dict 需要驗證是否仍然不一致**

計畫說「2026-03-31 發現 9 個跨模組 bug」，但今天已做了大量修復（evaluate.py market_cap 禁用、strategy_builder data dict 擴展、deployed_executor 加 per_history/margin 等）。部分 bug 可能已修。測試仍要寫（防止 regression），但「根因」描述需要更新。

---

### 範圍建議

**4. AK-4/AK-5/AK-6 不應在 live 前 checklist**

- AK-4（效能）：pytest-benchmark + Locust 是好東西，但效能基準需要穩定後才有意義。現在每天都在改代碼，基準會不斷失效。建議降為「上線後持續追蹤」
- AK-5（安全）：Factor 沙箱測試有價值（5.2），但 OWASP ZAP 掃描對 localhost-only 系統是過度。建議只保留 5.1（auth）和 5.2（sandbox），刪除 5.3（input validation 已有 Pydantic）
- AK-6（韌性）：混沌工程概念正確，但 10 個韌性測試 × 需要 mock broker 斷線/容器 crash 等場景，測試維護成本高。建議降為 P3

Live 前 checklist 只需要：AK-2（22 integration）+ AK-3（3 E2E）+ 5.2（sandbox）+ 30 天 paper。

**5. 時間預估偏樂觀但可接受**

10 天 54 個測試 ≈ 每天 5.4 個。考慮到有些測試需要複雜 fixture（mock broker、Docker 容器），AK-3 和 AK-6 可能各多 1 天。但整體可控。

---

### 做得好的部分

1. **測試金字塔**分層清晰 — unit 70% / integration 15% / E2E+perf+security 15%
2. **AK-2 的 22 個測試**精準對應今天的 9 個 bug — 不是泛泛的「提高覆蓋率」，而是針對已知斷點
3. **conftest.py 設計**合理 — session-scoped 合成數據 + function-scoped mock
4. **CI/CD 門檻分三層**（PR < 3min, Deploy < 15min, Nightly < 60min）— 不阻塞開發速度
5. **Live 前 Checklist** 完整 — 涵蓋測試、憑證、觀察期、告警驗證
6. **目錄結構**和 pytest 慣例一致

---

### 修正後的 Live 前 Checklist

- [ ] AK-2 Layer 1-6 全部 PASS（22 integration tests）
- [ ] AK-3 E2E 3 tests PASS
- [ ] AK-5.2 Factor sandbox tests PASS
- [ ] 取得 Sinopac 憑證
- [ ] Paper mode 跑 30 天觀察期
- [ ] 觀察期間 0 假警報
- [ ] 觀察期 NAV 追蹤與手動計算一致（< 1% 誤差）
- [ ] 切換 config.mode = "live" 並確認 reconciliation CLEAN
