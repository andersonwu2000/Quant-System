# 系統現況報告

> **更新**: 2026-04-02
> **版本**: v23.0（Phase AN+AO+AP 完成 — 架構重構 + 制度化 + AutoResearch 治理）

---

## 1. Dashboard

| 指標 | 數值 |
|------|------|
| 後端 Python | 200+ 檔 / 50,000+ LOC（AN 拆分 + AO 制度化 + AP 治理） |
| 測試 | 135+ 檔 / 30,000+ LOC / **1,820 unit + 218 integration/e2e/security/resilience** tests (0 failed) |
| CI | **10** jobs（lint + **security(pip-audit+bandit)** + mypy + test + web + e2e + android + release） |
| API 端點 | 130+（**18** 路由模組，新增 `/factor-research`） |
| 因子 | 83（66 技術 + 17 基本面）+ 3 FinLab 品質因子 |
| 策略 | 13（11 standalone + alpha + multi_asset） |
| 最佳化方法 | 14 |
| 風控規則 | 12 |
| 數據源 | 6（Yahoo / FinMind / FRED / Shioaji / TWSE+TPEX / **FinLab**） |
| 數據儲存 | 按來源分離（yahoo/ finmind/ twse/ finlab/）4,800+ files / 660+ MB |
| 數據平台 | DataCatalog(**+CatalogResult strict mode**) + Registry + SecuritiesMaster + QualityGate + RefreshEngine + Schemas + CLI |
| SecuritiesMaster | 3,936 家公司（2,241 active + 1,695 delisted）+ 39 產業分類 |
| 運營架構 | daily_ops + eod_ops + Heartbeat + 通知分級 P0-P3 + Trade Ledger |
| Autoresearch | 冷重啟後 8 實驗（1 L2 keep），rank normalization（AP-14）+ family budget ≤3 + **AST code safety** + **API 分離(factor-research)** |
| 部署管線 | 日頻 paper trading + Validator v3.0-AM（7 hard + 9 soft + 7 descriptive）+ overlay + risk-budget + **promotion artifact** |
| 壓力測試 | 6 固定壓力情境 + capacity 1x/3x/5x/10x + 5 regime split + benchmark-relative |
| Validator 版本 | v3.0-AO — 雙維度分數(research/deployment) + loss attribution + 閾值校準(corr 0.65) |

---

## 2. 當前狀態

### 核心策略

| 策略 | Validator | Hard | Sharpe | CAGR | 狀態 |
|------|:---------:|:----:|:------:|:----:|:----:|
| **revenue_acceleration** | **PASSED** | **7/7** | 1.174 | 19.0% | **可進 paper trading** |
| per_value | FAIL | 5/7 | 0.651 | 11.4% | DSR 0.48 + PBO 0.90 |
| revenue_momentum_hedged | 未重測 | — | — | — | 舊版 Validator 結果，需重跑 v3.0-AM |

**revenue_acceleration 是系統第一個通過全部 Hard Gate 的因子。** Experiment #25（2026-04-02）完整報告含 cost-adjusted IR、5 regime split、capacity 衰減、6 壓力情境、benchmark-relative、factor attribution。

### 進行中的工作

| 項目 | 狀態 | 文件 |
|------|------|------|
| Autoresearch | 🟢 冷重啟後運行中（Sonnet 模型） | `docs/guides/autoresearch-guide-zh.md` |
| Paper Trading | 🟢 04-02 清空重啟（30 天重新計數） | `data/paper_trading/` |
| Phase AN 架構拆分 | 🔜 下一步（5 項大型重構） | `docs/plans/phase-an-architecture.md` |
| CA 憑證（永豐金） | ⏳ 申請中 | 阻塞 live mode |

**近期完成的計畫：**

| Phase | 名稱 | 完成日期 |
|-------|------|---------|
| AP | AutoResearch 治理（25 項，92% 完成）— FactorDataBundle + AST + API 分離 | 04-02 |
| AO | 制度化（17 項，82% 完成）— 雙分數 + 閾值校準 + overlay + DataCatalog strict | 04-02 |
| AN | 架構重構（44 項，95% 完成）+ 安全修復 5 項 | 04-02 |
| AM | Validator 方法論 + Alpha 可部署性（21 項） | 04-02 |
| AC | Validator 方法論修正（16 項 + hard/soft 分離） | 04-01 |
| AB | Factor-Level PBO | 03-29 |
| AD | 數據管線自動化 | 04-01 |
| AE | Docker Agent 隔離 | 03-28 |
| AF | 記憶與替換系統 | 03-30 |
| AI | 營運架構 | 04-01 |
| Z1+Z2 | 向量化回測 + Shared Feed | 03-28 |
| Y | 容器化 Autoresearch | 03-28 |
| X | Anti-Overfitting 設計 | 03-28 |
| V | Kill Switch Debug | 03-28 |
| U | Autoresearch 模式重構 | 03-27 |
| R | 代碼整潔 | 03-27 |

**進行中的計畫（4 個）：**

| Phase | 名稱 | 完成度 | 缺什麼 |
|-------|------|:------:|--------|
| AA | 策略建構重構 | 80% | strategy_builder 整合 construction.py |
| AG | 因子部署管線 | 75% | watchdog auto-submit + 精煉 2.5b/2.5d |
| AK | 整合測試體系 | 85% | AK-4 效能基準（上線後） |
| AJ | 壓力測試 | 50% | 台股歷史情景 + 相關性壓力 |
| AL | Trading Safety | 90% | 等 30 天 paper 數據累積（04-02 重啟） |
| AN | 架構 + 金融品質（44 項） | **95%** | AN-2(DI)/AN-4(OpenAPI)/AN-33(E2E) 延後 |
| AO | 制度化與部署成熟度（17 項） | **82%** | 14/17 完成，AO-3/4/11 待 AL close |
| AP | AutoResearch 治理（25 項） | **92%** | P0+P1 全完成（含 API 分離 + AST 安全 + KPI），剩 AP-20(universe 需數據) + P2(4項中期) |

**延後或已取代的計畫：**

| Phase | 名稱 | 狀態 |
|-------|------|------|
| P | Auto-Alpha Research | 被 Phase U 取代 |
| Q | Strategy Refinement | 被 Phase AA+AC 取代 |
| AH | Web 前端改版 | 5/8 頁面完成，暫停 |
| E/N | 實盤 + Paper Trading | 等 CA 憑證 |
| J | 跨資產 Alpha | 等台股研究穩定 |
| N2 | Web Rewrite | 核心 UI 完成，i18n 延後 |
| J | Cross-Asset Automation | 延後（等台股研究穩定） |
| S | Pipeline Unification | 延後（前置條件需重評） |
| Z3 | 引擎加速 | 延後（當前效能可接受） |

### 已知問題

| 問題 | 嚴重度 | 狀態 |
|------|:------:|------|
| OOS Sharpe 統計功效不足 | MEDIUM | SE=0.82，不可修正；已降級為 sanity check |
| event-driven PBO 的 ThreadPool + shared strategy state | MEDIUM | 並發呼叫 base.on_bar() 可能互相干擾 |
| 3 個殘留 bug（realtime lock, idempotency tz, risk_parity short） | LOW | `docs/dev/CODE_REVIEW_REPORT.md` §10 |
| AO-3/4/11 等待 AL close | DEFERRED | Pipeline 兩段式 + Lock helper + AppState 拆分 |
| 結算現金雙重計入 | ✅ 已修 | available_cash 直接返回 cash（方案 A） |
| 漲跌停 9.5% → 10% | ✅ 已修 | simulated.py 對齊台股實際規則 |
| prev_close 缺失 fail-open | ✅ 已修 | 改為 Reject（fail-closed） |
| /ops 端點無認證 | ✅ 已修 | 加 verify_api_key dependency |
| /metrics 暴露敏感數據 | ✅ 已修 | 非 dev 不 expose |
| admin 預設密碼可用於 prod | ✅ 已修 | 非 dev 拒絕 Admin1234 |

---

## 3. 模組概覽

詳細架構見 `docs/claude/ARCHITECTURE.md`。

| 模組 | 檔案 | LOC | 核心功能 |
|------|:----:|----:|---------|
| `src/api/` | 30 | 7,200+ | REST + WebSocket + JWT/RBAC + **18** 路由 + bootstrap/ + **factor_research.py**(AP-5) |
| `src/alpha/` | 34 | 7,000+ | Alpha Pipeline + Auto-Alpha + FilterStrategy + **promotion.py** + **code_safety.py**(AP-6) |
| `src/backtest/` | 18 | 6,000+ | Engine + Validator(**checks/**(statistical/economic/descriptive)) + PBO(CSCV) + WF + 向量化(Z1) + FactorAttribution |
| `src/strategy/` | 19 | 4,689 | 83 因子（tech+fundamental+kakushadze）+ optimizer + registry |
| `src/data/` | 23 | 4,800+ | 6 數據源 + DataCatalog(CatalogResult) + **FactorDataBundle**(AP-1) + Registry + SecuritiesMaster + QualityGate + RefreshEngine |
| `src/reconciliation/` | 3 | 450+ | 每日回測 vs 實盤比對 + 週報（G1）|
| `src/execution/` | 15 | 2,900+ | SimBroker + Sinopac + TWAP + OMS + 零股分流 + **Trade Ledger**（intent log + fill log + crash replay）|
| `src/portfolio/` | 10 | 1,800+ | 14 最佳化方法(**methods/**(basic/classical/advanced)) + 風險模型 + overlay + risk_budget |
| `src/core/` | 7 | 1,215 | 統一模型 + Config + Logging + TradingCalendar + TradingPipeline |
| `src/scheduler/` | 7 | 1,500+ | daily_ops + eod_ops + Heartbeat + **pipeline/**(records/reconcile) |
| `src/risk/` | 5 | 1,075 | 12 規則 + Kill Switch + RealtimeMonitor |
| `src/allocation/` | 4 | 713 | 宏觀因子 + 跨資產信號 + 戰術配置 |
| 其他 | 14 | 961 | CLI + Notifications + Instrument |

---

## 4. 驗證與研究

### 最新 Validator 結果（Experiment #25, 2026-04-02, Phase AM）

> 注意：Phase AM 大幅修改了 Validator 架構（7 hard + 9 soft，OOS 切割，DSR N 統一，行業中性化 IC），與 3/29 結果不可直接比較。

**revenue_acceleration**, 200 支, 2018-2025: **PASSED (7/7 Hard, 14/16 Total)**

| Check | Hard/Soft | Value | Result |
|-------|:---------:|------:|:------:|
| CAGR | Hard | +18.99% | ✅ |
| Cost ratio | Hard | 3% | ✅ |
| Cost 2x safety | Hard | +18.32% | ✅ |
| Temporal consistency | Hard | +1.532 | ✅ |
| Deflated Sharpe (N=15) | Hard | 0.887 | ✅ |
| Construction PBO | Hard | 0.544 | ✅ |
| Market correlation | Hard | 0.574 | ✅ |
| Sharpe | Soft | 1.174 | ✅ |
| Max drawdown | Soft | 44.35% | ⚠ |
| vs EW (beta-neutral) | Soft | 25% | ⚠ |
| Sharpe decay | Soft | t=+28.97 | ✅ |

**per_value**: FAILED (5/7 Hard) — DSR 0.476 + PBO 0.898

詳見 `docs/research/20260402_25_validator_full_audit.md`。

### 因子研究結論

| 結論 | 證據 |
|------|------|
| 台股 alpha 在營收，不在價格 | 4 營收因子 ICIR > 0.15；66 價格因子全 < 0.3 |
| revenue_acceleration 最強 | ICIR(20d) +0.438, ICIR(60d) +0.582 |
| 成本是台股瓶頸 | 換手率 > 10% 的因子全部虧損 |
| 1/N 等權極難打敗 | DeMiguel 2009 在台股完全驗證 |

詳見 `docs/research/RESEARCH_SUMMARY.md`。

### 回測真實性

8 項中 4 項完全實作（營收延遲、ADV cap、整張、selection bias），3 項部分實作（漲跌停、除權息、倖存者偏差），1 項未實作（盤後訊號，影響極小）。

詳見 `docs/research/realism_checklist.md`。

---

## 5. 交易管線

```
Trading Pipeline（唯一入口）
  Cron: QUANT_TRADING_PIPELINE_CRON
  Strategy: QUANT_ACTIVE_STRATEGY

  execute_pipeline(config):
    1. 冪等性檢查 → 2. 數據更新 → 3. strategy.on_bar(ctx)
    → 4. weights_to_orders → 5. RiskEngine → 6. ExecutionService
    → 7. 持久化 → 8. 通知

Autoresearch Pipeline（獨立）
  架構: Karpathy autoresearch（evaluate.py + factor.py + program.md）
  閘門: L1-L4 IS → L5 OOS holdout → Stage 2 大規模 IC → Validator 16 項
  容器化: Docker（Phase Y）
```

詳見 `docs/guides/autoresearch-guide-zh.md`。

---

## 6. Phase 進度

詳見 `docs/PHASE_TRACKER.md`。

| Phase | 狀態 | 說明 |
|-------|:----:|------|
| A~S | ✅ | 基礎建設 → 管線統一 |
| U (Autoresearch) | ✅ | Karpathy pattern + API 整合 |
| X (防過擬合) | ✅ | L5 OOS holdout + 複雜度限制 |
| Y (容器化) | ✅ | Docker + Watchdog |
| Z (向量化) | 🟢 | Z1(PBO)✅ Z2(shared feed)✅ Z3 延後 |
| AA (策略構建) | ✅ | inverse-vol + no-trade zone + cost-aware |
| AB (Factor PBO) | ✅ | Factor-Level PBO |
| AC (Validator 修正) | ✅ | 16 項方法論修正 |

---

## 7. 文件索引

| 文件 | 用途 |
|------|------|
| `docs/claude/ARCHITECTURE.md` | 模組架構、API、前端 |
| `docs/claude/BUG_HISTORY.md` | 60+ 已修復 bug |
| `docs/claude/EXPERIMENT_STANDARDS.md` | 實驗方法論 |
| `docs/research/RESEARCH_SUMMARY.md` | 22 份實驗報告 + 因子結論 |
| `docs/research/realism_checklist.md` | 回測真實性 8 項 |
| `docs/research/factor_validation_20260328.md` | 25 因子批次驗證 |
| `docs/guides/api-reference-zh.md` | 117 API 端點 |
| `docs/guides/autoresearch-guide-zh.md` | Autoresearch 操作 |
| `docs/reviews/CODE_REVIEW_REPORT.md` | 代碼審查（80+ bug） |
| `docs/reviews/AUTORESEARCH_OPERATIONS_REVIEW_2026Q1.md` | Autoresearch 運營檢討 |
| `docs/reviews/autoresearch-alpha/AUTO_ALPHA_PIPELINE_REVIEW.md` | 因子研究管線檢討 |
| `docs/plans/phase-ao-institutionalization.md` | 制度化計畫（17 項） |
| `docs/plans/phase-an-architecture.md` | 架構重構計畫（44 項） |
| `docs/plans/phase-aa-strategy-construction.md` | 策略構建改進計畫 |
| `docs/plans/phase-z-vectorized-backtest.md` | 向量化回測計畫 |
| `docs/reviews/code-quality/SECURITY_REVIEW_20260402.md` | 安全審查（5 critical/high） |
| `docs/reviews/methodology/DEEP_PROJECT_RECOMMENDATIONS_20260402.md` | 全專案深度檢視 |
| `docs/reviews/system/PHASE_AO_PLAN_AUDIT_20260402.md` | AO 計畫審計 |
| `docs/reviews/system/PHASE_AP_PLAN_AUDIT_20260402.md` | AP 計畫審計 |
| `docs/reviews/system/AUTO_RESEARCH_REVIEW.md` | AutoResearch 全面審查 |
| `docs/plans/phase-ap-autoresearch-governance.md` | AP 計畫（25 項） |
| `docs/autoresearch/RUNBOOK.md` | AutoResearch 操作手冊 |
| `docs/autoresearch/DATA_CONTRACT_INVENTORY.md` | 資料契約 6 入口點 inventory |
| `docs/PHASE_TRACKER.md` | Phase 進度總覽 |
