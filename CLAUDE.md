# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Reference Documents（子文件系統）

CLAUDE.md 只保留**行為規範和開發規則**。技術細節分拆到 `docs/claude/` 目錄：

| 文件 | 用途 | 何時讀取 |
|------|------|---------|
| `docs/claude/ARCHITECTURE.md` | 系統架構、模組邊界、API、前端、策略列表 | 修改代碼、新增模組、理解系統結構時 |
| `docs/claude/EXPERIMENT_STANDARDS.md` | 實驗方法論標準、部署門檻、基準因子 | 跑實驗、寫報告、評估因子時 |
| `docs/claude/SYSTEM_STATUS_REPORT.md` | 模組清單、測試覆蓋、功能矩陣、缺陷追蹤 | 完成任何功能變更後更新 |
| `docs/dev/plans/` | 各 Phase 獨立計畫書（A~S） | 規劃新工作時 |

### 文件維護規則

1. **修改代碼後** → 更新 `docs/claude/SYSTEM_STATUS_REPORT.md` 受影響的段落
2. **修改架構後** → 更新 `docs/claude/ARCHITECTURE.md` 對應的模組描述
3. **修改實驗方法後** → 更新 `docs/claude/EXPERIMENT_STANDARDS.md`，所有後續實驗遵循新標準
4. **新增子文件** → 在本表格中加入指引
5. **子文件內容過時** → 立即更新，不要等；過時的文件比沒有文件更危險

---

## Release Rules

- **GitHub Release 必須包含 APK**：每次建立 GitHub Release 時，一定要建置 Android debug APK (`apps/android` → `./gradlew.bat assembleDebug`) 並上傳為 release asset，命名格式為 `quant-trading-v{VERSION}.apk`。

## Maintenance Rules

After completing any feature addition, bug fix, refactoring, architecture change, or dependency update, **update `docs/claude/SYSTEM_STATUS_REPORT.md`** to reflect the changes. Sections to check and update:
- **Module inventory** (§3–§5): file counts, LOC, new/removed modules
- **Strategy list** (§6): if strategies were added/removed
- **Test coverage** (§8): new test files, updated test counts
- **CI/CD** (§9): pipeline changes
- **Known defects** (§11): resolved or newly discovered issues
- **Feature matrix** (§12): completion status changes
- **Gap analysis** (§13–§14): items that have been addressed

Keep updates minimal — only touch sections affected by the change.

## Mandatory Code Review（強制覆核）

**每次修改代碼後，必須做三層檢查才能 commit：**

### 1. 公式正確性
- 分子分母單位是否一致（年化 vs 累計、算術 vs 幾何）
- 除法是否有 zero guard
- NaN/inf 是否會傳播
- ddof=0 vs ddof=1 是否和其他模組一致

### 2. 流程連通性
- 新函式是否真的被呼叫（grep 確認有 caller）
- 參數是否傳對（不是硬編碼的固定值代替動態值）
- 結果是否存回（save/persist 是否在修改後呼叫）
- Pipeline 是否完整（A→B→C 每一步都連通）

### 3. 語義一致性
- 函式名/docstring 描述的和代碼做的是否一致
- 變數名暗示的含義和實際值是否一致
- Comment 說的邏輯和代碼邏輯是否一致

### 關鍵檔案（修改前必須看 `.claude/hooks/pre-edit-check.md`）
- `src/backtest/analytics.py` — Sharpe/Sortino/CAGR/MDD/DSR
- `src/backtest/validator.py` — 13 項驗證閘門
- `src/backtest/engine.py` — NAV/cash/settlement/execution
- `src/execution/broker/simulated.py` — 成本模型
- `src/strategy/research.py` — IC/ICIR/forward returns
- `src/alpha/cross_section.py` — quantile backtest
- `src/scheduler/jobs.py` — 交易管線流程

### 歷史教訓（40+ 個已修復的 bug，按類別）

**公式與計算（7 個）：**
1. Sharpe 幾何/算術混用（analytics.py）
2. Sortino 下行偏差只算負值（analytics.py）
3. factor_evaluator ICIR ddof 不一致（factor_evaluator.py）
4. beat_magnitude 13 月 vs 12 月 off-by-one（alpha_research_agent.py）
5. rev_breakout 包含當月 → 永遠回傳 0（alpha_research_agent.py）
6. rev_accel_2nd_derivative 算一階非二階導數（alpha_research_agent.py）
7. forward return off-by-one: after[h-1] vs after[h]（alpha_research_agent.py）

**Look-Ahead Bias（8 個）：**
8. 自動因子代碼無 40 天營收延遲（alpha_research_agent.py）— 所有因子 IC 被高估
9. trust_follow.py 營收無 40 天延遲
10. 5 個研究因子檔案缺 40 天延遲（rev_consecutive_beat 等）
11. L5 Walk-Forward 是空殼（passed=True），不做實際檢查（factor_evaluator.py）

**流程與連通性（10 個）：**
12. Validator benchmark 用 momentum 非 0050（validator.py）
13. Validator bootstrap 用不存在的屬性（validator.py）
14. Auto-research Validator 用固定策略非因子策略（alpha_research_agent.py）
15. 因子生成 generic fallback 產出 revenue_yoy 偽因子（alpha_research_agent.py）
16. L3 相關性檢查比較 factor-value mean vs IC series（factor_evaluator.py）
17. _compute_baseline_factor_ics 未計算 revenue_yoy IC（alpha_research_agent.py）
18. weights_to_orders 未傳 volumes/market_lot_sizes（jobs.py, strategy_center.py）
19. _shares_to_lots 靜默改變訂單數量（sinopac.py）
20. _async_revenue_update 丟棄回傳值（jobs.py）

**並發與狀態管理（5 個）：**
21. Kill switch 不 apply_trades → 無限循環（app.py）— **CRITICAL**
22. Kill switch 無 re-trigger guard → 每 5 秒重觸發（app.py）
23. Rebalance/Pipeline 無 mutation_lock（strategy_center.py, jobs.py）
24. Shioaji 線程 vs asyncio 事件循環競爭（realtime.py）
25. Portfolio 狀態無持久化，重啟丟失（state.py）

**語義錯誤（5 個）：**
26. Validator cost_ratio 累計 vs 年化（validator.py）
27. Validator 日曆日 vs 交易日（validator.py）
28. cross_section 日期錯位（cross_section.py）
29. engine _col_index 跨矩陣快取碰撞（engine.py）
30. pos.last_price 屬性不存在（strategy_center.py）

### 經驗總結

1. **Look-ahead bias 是最隱蔽的錯誤** — 營收 40 天延遲缺失導致所有因子 IC 膨脹 10-40 倍，結果看起來完全正常
2. **generic fallback 是毒藥** — 任何「找不到就用預設值」的設計都會靜默產出錯誤結果，改用 fail-closed
3. **並發問題不會在單元測試中暴露** — asyncio.Lock 不保護線程，threading.Lock 不保護協程
4. **小樣本高估嚴重** — L5 的 ICIR 0.860 在 865 支大 universe 下可能只有 0.104
5. **生成式代碼需要驗證** — 自動產出的因子代碼可以是任何東西，必須有沙箱或校驗

## Project Overview

Multi-asset portfolio research and optimization system covering TW stocks, US stocks, ETFs (incl. bond/commodity ETF proxies), TW futures, US futures. Bond/commodity exposure via ETFs, not direct trading. No retail FX (Taiwan regulatory restriction). Current stage: equity alpha research layer complete, expanding to multi-asset architecture. Long-term goal: platform for individual investors and family asset management.

Monorepo: Python backend + React web + Android native (Kotlin/Compose). Targets Taiwan stock market defaults (commission 0.1425%, sell tax 0.3%) but works with any market via Yahoo Finance or FinMind.

**Monorepo structure:**
- `src/`, `tests/`, `strategies/`, `migrations/` — Python backend (~160 files, ~29,000 LOC)
- `apps/web/` — React 18 + Vite + Tailwind dashboard (incl. Alpha Research page)
- `apps/android/` — Android native (Kotlin + Jetpack Compose + Material 3)
- `apps/shared/` — `@quant/shared` TypeScript package (types, API client, WS manager, format utils)

**Documentation:** See Reference Documents table above.

## Commands

```bash
# === Backend ===
make test                    # pytest tests/ -v (1,401 tests)
make lint                    # ruff check + mypy strict
make dev                     # API with hot reload (port 8000)
make api                     # production API
make backtest ARGS="--strategy momentum -u AAPL -u MSFT --start 2023-01-01 --end 2024-12-31"
make migrate                 # alembic upgrade head
make seed                    # python scripts/seed_data.py

# Single test
pytest tests/unit/test_risk.py -v
pytest tests/unit/test_risk.py::TestMaxPositionWeight::test_approve_within_limit -v

# CLI
python -m src.cli.main backtest --strategy momentum -u AAPL --start 2023-01-01 --end 2024-12-31
python -m src.cli.main server
python -m src.cli.main status
python -m src.cli.main factors

# === Frontend ===
make install-apps            # bun install (all frontend packages)
make web                     # web dev server (port 3000)
cd apps/android && ./gradlew assembleDebug  # Android debug APK
make web-build               # production build
make web-typecheck           # tsc --noEmit
make web-test                # vitest
cd apps/android && ./gradlew lintDebug  # Android lint

# === Full stack ===
make start                   # backend + web in parallel
scripts/start.bat            # Windows: backend + web in separate windows

# === Docker ===
docker compose up -d         # API (port 8000) + PostgreSQL
docker compose down          # stop all services

# === Alpha Research ===
python -m scripts.alpha_research_agent --rounds 20 --interval 5   # 自動因子研究
python -m scripts.large_scale_factor_check                        # 大規模 IC 驗證
```

## Auto-Alpha Research Pipeline

因子從假說到部署的完整流程（詳見 `docs/claude/EXPERIMENT_STANDARDS.md`）：

```
假說生成 → 因子實作 → L5 快篩 (ICIR≥0.30)
  → 大規模 IC 驗證 (865+ 支, ICIR(20d)≥0.20)
  → StrategyValidator (≥11/13, excl DSR; DSR≥0.70)
  → 部署檢查 (Sharpe>0050, CAGR>8%, recent_sharpe>-0.10)
  → Paper Trading (5% NAV, 30 天觀察)
```

**關鍵約束**：
- 所有營收因子必須有 **40 天公布延遲**（`as_of - pd.DateOffset(days=40)`）
- 因子生成器不匹配的假說必須 **fail-closed**（return None），不可 fallback
- Portfolio mutation 必須持有 **state.mutation_lock**（asyncio.Lock）
- Shioaji 線程中的 portfolio 操作必須排程到 **event loop**

**假說生成**：由 Claude Code 根據 experience memory (`data/research/memory.json`) 和學術文獻動態生成。不使用硬編碼模板。生成新假說時應考慮：
1. 已測試因子的成功/失敗模式
2. 禁區列表（forbidden regions）
3. 學術文獻依據
4. 與現有因子的差異化（避免高相關）

## Architecture Quick Reference

See `docs/claude/ARCHITECTURE.md` for full details.

**Key patterns:**
- Strategy returns `dict[str, float]` weights, not orders
- Risk rules are pure function factories (no inheritance)
- All monetary values use `Decimal`
- DatetimeIndex normalized to tz-naive
- Local-first data: read `data/market/*.parquet`, download only if missing

**Configuration:** All via `QUANT_` env vars or `.env`. See `src/core/config.py`.

**Security:** JWT + API Key, 5-level roles, PBKDF2 passwords, audit logging.
