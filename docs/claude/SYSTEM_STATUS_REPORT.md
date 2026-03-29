# 系統現況報告

> **更新**: 2026-03-29
> **版本**: v15.0

---

## 1. Dashboard

| 指標 | 數值 |
|------|------|
| 後端 Python | 153 檔 / 35,870 LOC |
| 測試 | 114 檔 / 25,870 LOC / **1,544** test functions |
| CI | 9 jobs（lint + mypy + test + web + e2e + android + release） |
| API 端點 | 117（16 路由模組） |
| 因子 | 83（66 技術 + 17 基本面） |
| 策略 | 13（11 standalone + alpha + multi_asset） |
| 最佳化方法 | 14 |
| 風控規則 | 12 |
| 數據源 | 4（Yahoo / FinMind / FRED / Shioaji） |
| 本地 parquet | 895 支台股價格 + 408 基本面檔 |
| Autoresearch | 233 實驗, 25 tagged 因子, best ICIR 0.95 |

---

## 2. 當前狀態

### 核心策略

| 策略 | Validator | Sharpe | CAGR | 卡在 |
|------|:---------:|:------:|:----:|------|
| revenue_momentum_hedged | 13/15 | 0.926 | 12.8% | oos_sharpe(-0.73), construction_sensitivity(0.596) |

**884 stocks, 15 項檢查（permutation 跳過：手寫策略無 compute_fn）。** 2 項 fail：OOS Sharpe（軟門檻）+ construction_sensitivity 0.596 > 0.50（硬門檻，PBO fillna 修正後惡化）。**不符合部署條件。**

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
| AC | Validator 方法論修正（16 項） | 03-29 |
| AB | Factor-Level PBO | 03-29 |
| AA | 策略構建（no-trade + 非對稱成本） | 03-28 |
| Z1+Z2 | 向量化回測 + Shared Feed | 03-28 |
| Y | 容器化 Autoresearch | 03-28 |
| X | Anti-Overfitting 設計（被 AC 實作） | 03-28 |
| V | Kill Switch Debug | 03-28 |
| U | Autoresearch 模式重構 | 03-27 |

**延後或已取代的計畫：**

| Phase | 名稱 | 狀態 |
|-------|------|------|
| P | Auto-Alpha Research | 被 Phase U 取代 |
| Q | Strategy Refinement | 被 Phase AA+AC 取代 |
| R | Codebase Hygiene | R7-R9 待完成（Paper Trading 前置） |
| N | Paper Trading 30 天驗證 | N1-N3 完成，N5 卡 CA cert |
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

---

## 3. 模組概覽

詳細架構見 `docs/claude/ARCHITECTURE.md`。

| 模組 | 檔案 | LOC | 核心功能 |
|------|:----:|----:|---------|
| `src/api/` | 25 | 6,965 | REST + WebSocket + JWT/RBAC + 16 路由 |
| `src/alpha/` | 31 | 6,663 | Alpha Pipeline + Auto-Alpha（9 子模組）+ FilterStrategy |
| `src/backtest/` | 13 | 5,448 | Engine + Validator(16項) + PBO(CSCV) + WF + 向量化(Z1) |
| `src/strategy/` | 19 | 4,689 | 83 因子（tech+fundamental+kakushadze）+ optimizer + registry |
| `src/data/` | 15 | 2,752 | 4 數據源 + 品質檢查 + LocalMarketData |
| `src/execution/` | 14 | 2,666 | SimBroker + Sinopac + TWAP + OMS + 零股分流 |
| `src/portfolio/` | 4 | 1,596 | 14 最佳化方法 + 風險模型(GARCH/PCA) + 幣別對沖 |
| `src/core/` | 7 | 1,215 | 統一模型 + Config + Logging + TradingCalendar + TradingPipeline |
| `src/scheduler/` | 2 | 1,127 | Trading Pipeline（統一入口）+ 3 排程路徑 |
| `src/risk/` | 5 | 1,075 | 12 規則 + Kill Switch + RealtimeMonitor |
| `src/allocation/` | 4 | 713 | 宏觀因子 + 跨資產信號 + 戰術配置 |
| 其他 | 14 | 961 | CLI + Notifications + Instrument |

---

## 4. 驗證與研究

### 最新 Validator 結果（Post-Audit Rerun, 2026-03-29）

revenue_momentum_hedged, 884 支, 2018-2025:

| Check | Value | Result |
|-------|------:|:------:|
| CAGR | +12.83% | ✅ |
| Sharpe | 0.926 | ✅ |
| MDD | -29.88% | ✅ |
| Cost ratio | 22% | ✅ |
| Temporal consistency | 75% | ✅ |
| DSR | 0.924 | ✅ |
| Bootstrap (Stationary) | 99.7% | ✅ |
| **OOS Sharpe** | **-0.728** | **❌** |
| vs EW universe | +8.66% | ✅ |
| **Construction sensitivity** | **0.596** | **❌** |
| Worst regime (DD-based) | -10.81% | ✅ |
| Recent Sharpe | 2.447 | ✅ |
| Market corr | 0.536 | ✅ |
| CVaR 95 | -2.22% | ✅ |
| Permutation p | skipped | — |

**13/15 通過（permutation 跳過）。** 2 項 fail：OOS Sharpe（軟門檻）+ construction_sensitivity（硬門檻，PBO fillna 修正後 0.408→0.596）。詳見 `docs/research/20260329_validator_post_audit.md`。

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
