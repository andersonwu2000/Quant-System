# 系統現況報告

> **更新**: 2026-04-01
> **版本**: v18.0

---

## 1. Dashboard

| 指標 | 數值 |
|------|------|
| 後端 Python | 170+ 檔 / 40,800+ LOC |
| 測試 | 130+ 檔 / 29,000+ LOC / **1,810 unit + 210 integration/e2e/security/resilience** tests (0 failed) |
| CI | 9 jobs（lint + mypy + test + web + e2e + android + release） |
| API 端點 | 120+（17 路由模組，新增 `/ops`） |
| 因子 | 83（66 技術 + 17 基本面）+ 3 FinLab 品質因子 |
| 策略 | 13（11 standalone + alpha + multi_asset） |
| 最佳化方法 | 14 |
| 風控規則 | 12 |
| 數據源 | 6（Yahoo / FinMind / FRED / Shioaji / TWSE+TPEX / **FinLab**） |
| 數據儲存 | 按來源分離（yahoo/ finmind/ twse/ finlab/）4,800+ files / 660+ MB |
| 數據平台 | DataCatalog + Registry + SecuritiesMaster + QualityGate + RefreshEngine + Schemas + CLI |
| SecuritiesMaster | 3,936 家公司（2,241 active + 1,695 delisted）+ 39 產業分類 |
| 運營架構 | daily_ops + eod_ops + Heartbeat + 通知分級 P0-P3 + Trade Ledger |
| Autoresearch | 400+ 實驗（0 L3+），合併數據生效中，preflight.py 防洩漏 |
| 部署管線 | 日頻 paper trading + kill switch OFF in Validator + 精煉管線（AG Step 2.5） |
| 壓力測試 | 6 台股歷史情景 + 5 成本敏感度 + benchmark 比較（Phase AJ） |

---

## 2. 當前狀態

### 核心策略

| 策略 | Validator | Sharpe | CAGR | 卡在 |
|------|:---------:|:------:|:----:|------|
| revenue_momentum_hedged | 13/15 | 0.926 | 12.8% | oos_sharpe(-0.73), construction_sensitivity(0.596) |

**884 stocks, 16 項檢查（permutation 跳過：手寫策略無 compute_fn）。** Hard/soft 分離後：OOS Sharpe 為軟門檻（不阻擋），construction_sensitivity 0.596 > 0.50 為硬門檻 fail。**硬門檻未全通過，不符合部署條件。**

### 進行中的工作

| 項目 | 狀態 | 文件 |
|------|------|------|
| **Phase 2 乾淨研究** | 🔜 下一步 | 研究記憶已清空，評估標準已凍結 |
| Autoresearch (Docker) | ⏸ 等研究啟動 | `docs/guides/autoresearch-guide-zh.md` |
| Paper Trading | 🟢 運行中 | `docs/paper-trading/` |
| CA 憑證（永豐金） | ⏳ 申請中 | 阻塞 live mode |

**近期完成的計畫：**

| Phase | 名稱 | 完成日期 |
|-------|------|---------|
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
| AL | Trading Safety | 90% | 等 30 天 paper 數據累積 |
| AN | 架構整理（從 AM 獨立） | 0% | 拆 app.py / engine.py / validator.py / singleton |

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
| PBO 系統性惡化（0.78→0.99） | ✅ 已解決 | Rolling OOS + construction_sensitivity ≤ 0.50 + Factor-Level PBO |
| event-driven PBO 的 ThreadPool + shared strategy state | MEDIUM | 並發呼叫 base.on_bar() 可能互相干擾 |
| 3 個殘留 bug（realtime lock, idempotency tz, risk_parity short） | LOW | `docs/dev/CODE_REVIEW_REPORT.md` §10 |
| 跨模組 data dict 不一致（#64-68） | ✅ 已解決 | 2026-04-01 修復 + 85 regression tests |
| vectorized.py 死碼（#69-70） | ✅ 已解決 | 2026-04-01 修復 |
| Reconciliation symbol 格式（#72） | ✅ 已解決 | .TW vs bare 自動 normalize |
| Paper mode 假告警（#73） | ✅ 已解決 | Reconcile 僅 live mode 執行 |
| Validator kill switch 過度觸發（#71） | ✅ 已解決 | enable_kill_switch=False in Validator |

---

## 3. 模組概覽

詳細架構見 `docs/claude/ARCHITECTURE.md`。

| 模組 | 檔案 | LOC | 核心功能 |
|------|:----:|----:|---------|
| `src/api/` | 25 | 6,965 | REST + WebSocket + JWT/RBAC + 16 路由 |
| `src/alpha/` | 31 | 6,663 | Alpha Pipeline + Auto-Alpha（9 子模組）+ FilterStrategy |
| `src/backtest/` | 14 | 6,000+ | Engine + Validator(16項+6描述性) + PBO(CSCV) + WF + 向量化(Z1) + FactorAttribution |
| `src/strategy/` | 19 | 4,689 | 83 因子（tech+fundamental+kakushadze）+ optimizer + registry |
| `src/data/` | 22 | 4,500+ | 6 數據源（+FinLab）+ DataCatalog + Registry + SecuritiesMaster + QualityGate + RefreshEngine + Schemas + CLI |
| `src/reconciliation/` | 3 | 450+ | 每日回測 vs 實盤比對 + 週報（G1）|
| `src/execution/` | 15 | 2,900+ | SimBroker + Sinopac + TWAP + OMS + 零股分流 + **Trade Ledger**（intent log + fill log + crash replay）|
| `src/portfolio/` | 6 | 1,800+ | 14 最佳化方法 + 風險模型(GARCH/PCA) + 幣別對沖 + **overlay**(beta/sector/exposure) + **risk_budget**(3桶inverse-vol) |
| `src/core/` | 7 | 1,215 | 統一模型 + Config + Logging + TradingCalendar + TradingPipeline |
| `src/scheduler/` | 4 | 1,500+ | **daily_ops + eod_ops**（統一運營流程）+ Heartbeat + Trading Pipeline |
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
| `docs/plans/phase-aa-strategy-construction.md` | 策略構建改進計畫 |
| `docs/plans/phase-z-vectorized-backtest.md` | 向量化回測計畫 |
| `docs/PHASE_TRACKER.md` | Phase 進度總覽 |
