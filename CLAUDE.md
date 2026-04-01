# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Reference Documents（子文件系統）

CLAUDE.md 只保留**行為規範和開發規則**。技術細節分拆到 `docs/claude/` 目錄：

| 文件 | 用途 | 何時讀取 |
|------|------|---------|
| `docs/claude/ARCHITECTURE.md` | 系統架構、模組邊界、API、前端、策略列表 | 修改代碼、新增模組、理解系統結構時 |
| `docs/claude/EXPERIMENT_STANDARDS.md` | 實驗方法論標準、部署門檻、基準因子 | 跑實驗、寫報告、評估因子時 |
| `docs/claude/SYSTEM_STATUS_REPORT.md` | 模組清單、測試覆蓋、功能矩陣、缺陷追蹤 | 完成任何功能變更後更新 |
| `docs/claude/BUG_HISTORY.md` | 60+ 已修復 bug 按類別分類 | 修改關鍵檔案前查閱 |
| `docs/plans/` | 各 Phase 獨立計畫書（A~Z） | 規劃新工作時 |
| `docs/research/` | 實驗報告 + 研究總結 | 因子分析、策略驗證時 |
| `docs/guides/autoresearch-guide-zh.md` | Autoresearch 操作指南 | 啟動/停止/監控自動研究時 |
| `docs/claude/CHECKLISTS.md` | 研究啟動 / 代碼修改 / 事故處理 checklist | **每次操作前必讀** |
| `docs/claude/LESSONS_FOR_AUTONOMOUS_AGENTS.md` | 自主 agent 開發的 20 條經驗教訓 | 設計 agent 系統、跨項目傳承時 |

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

**每次修改代碼前，先查 `docs/claude/CHECKLISTS.md` 底部的 Quick Reference 找到對應的變更類型 checklist。**

**每次修改代碼後，必須做三層檢查才能 commit：**

### 1. 公式正確性
- 分子分母單位是否一致（年化 vs 累計、算術 vs 幾何）
- 除法是否有 zero guard
- NaN/inf 是否會傳播
- ddof=0 vs ddof=1 是否和其他模組一致
- **實作學術方法時：是否讀過原論文？每個參數的定義是否對齊原文？**（PBO 教訓：N 的定義錯了三次）

### 2. 流程連通性
- 新函式是否真的被呼叫（grep 確認有 caller）
- 參數是否傳對（不是硬編碼的固定值代替動態值）
- 結果是否存回（save/persist 是否在修改後呼叫）
- Pipeline 是否完整（A→B→C 每一步都連通）

### 3. 語義一致性
- 函式名/docstring 描述的和代碼做的是否一致
- 變數名暗示的含義和實際值是否一致
- Comment 說的邏輯和代碼邏輯是否一致

### 4. 端到端驗證（新功能必做）
- 新函式/新路徑寫完後**立刻跑一次**，不是只做文件審計
- Docker 相關修改必須 `docker compose build && docker exec ... python` 實際測試
- 涉及多模組串接的功能（如 evaluate.py → Validator → report），必須跑完整流程確認每一步都通
- 使用 base class 的 API 前**先讀 base class 定義**（不要猜 attribute 名稱）
- 異常/失敗路徑也要測（傳 None、空 list、不存在的路徑）
- 如果跑不通就**不要 commit**，先修到能跑再提交

### 關鍵檔案（修改前必須看 `.claude/hooks/pre-edit-check.md`）
- `src/backtest/analytics.py` — Sharpe/Sortino/CAGR/MDD/DSR
- `src/backtest/validator.py` — 16 項驗證閘門（11 hard + 6 soft）
- `src/backtest/engine.py` — NAV/cash/settlement/execution
- `src/execution/broker/simulated.py` — 成本模型
- `src/strategy/research.py` — IC/ICIR/forward returns
- `src/alpha/cross_section.py` — quantile backtest
- `src/scheduler/jobs.py` — 交易管線流程

### 歷史 Bug（60+ 個已修復）

詳見 `docs/claude/BUG_HISTORY.md`。修改關鍵檔案前務必查閱對應類別。

### 經驗總結

1. **Look-ahead bias 是最隱蔽的錯誤** — 營收 40 天延遲缺失導致所有因子 IC 膨脹 72%（0.188 → 0.674），結果看起來完全正常
2. **generic fallback 是毒藥** — 任何「找不到就用預設值」的設計都會靜默產出錯誤結果，改用 fail-closed
3. **並發問題不會在單元測試中暴露** — asyncio.Lock 不保護線程，threading.Lock 不保護協程。需要統一的 Portfolio.lock
4. **小樣本高估嚴重** — ivol 50 支 ICIR +0.60，874 支反轉為 -0.232。revenue_yoy 296 支 ICIR 0.188，855 支降為 0.037
5. **生成式代碼需要驗證** — 自動產出的因子代碼可以是任何東西，必須 fail-closed（數據不足 → 不通過，而非自動通過）
6. **風控規則門檻必須從 config 讀** — 硬編碼門檻和 config 不一致是常見 bug 來源
7. **crash recovery 需要原子性** — trade log 必須在 apply_trades 之前存，portfolio 必須存完整狀態（含 pending_settlements）
8. **時區必須統一** — 台股用 UTC+8 做日期判斷，混用 UTC 會導致 08:00 提前 reset
9. **deepcopy + threading.Lock 不相容** — Portfolio 加了 lock 後 check_orders 的 deepcopy 會 crash，需要自定義 __deepcopy__
10. **PBO 方法學：三次實作三次錯** — v1 noise perturbation（假策略）→ v2 event-driven 10 variants（測 portfolio sensitivity 不是 factor selection）→ v3 vectorized（加速了錯誤的計算）。根因：沒讀 Bailey 原論文就實作，代碼審計只查算法正確性不查方法論定義。**教訓：實作學術方法前必須讀原論文，確認每個參數的定義（尤其是 N 代表什麼），不能只靠二手資料或直覺**
11. **兩套數據路徑不同步是 bug 溫床** — evaluate.py 和 strategy_builder.py 各自載入數據，symbol 格式不一致（`bare` vs `.TW`）導致 revenue 全部找不到。修改一處必須 grep 所有數據載入點
12. **異常時必須 fail-closed** — Validator 的 OOS/benchmark/correlation 異常回傳 0.0 會自動通過門檻。所有驗證函式異常時應回傳最差值（-999 / 1.0）確保不自動通過
13. **base class API 要用 public method** — `Strategy.name()` 是 abstractmethod，不能用 `name = "str"` 覆蓋。`Context.now()` 不是 `ctx.current_time`。改之前先讀 base class 定義
14. **Docker 容器依賴要一次裝齊** — 一個一個追 ModuleNotFoundError 浪費時間。直接從 pyproject.toml 的 dependencies 安裝，或用 `pip freeze` 鎖定
15. **自主 agent 的安全靠隔離不靠指令** — prompt 說「不要改」agent 還是會改。OS 唯讀被 git reset 繞過。只有 Docker volume mount 是真正的硬保護

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
make test                    # pytest tests/ -v (1,707 tests)
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

# === Alpha Research (autoresearch 模式) ===
cd scripts/autoresearch && python evaluate.py                   # 跑一次因子評估
claude -p scripts/autoresearch/program.md                       # 啟動 Claude Code 自動研究
python -m scripts.large_scale_factor_check                      # 大規模 IC 驗證（獨立）
```

## Auto-Alpha Research Pipeline（autoresearch 模式）

採用 Karpathy autoresearch 架構（3 個文件取代舊的 1800 行 agent）：

```
scripts/autoresearch/
├── evaluate.py    ← 固定（READ ONLY）— L1-L4 閘門 + 大規模 IC + 去重
├── factor.py      ← Agent 唯一可改 — compute_factor(symbols, as_of, data)
├── program.md     ← 研究協議 — 永不停止 + 簡單性準則
└── results.tsv    ← 實驗記錄 — commit | score | icir | level | status
```

**使用方式**：`claude -p scripts/autoresearch/program.md`

**Agent 循環**：改 factor.py → commit → 跑 evaluate.py → 記錄 → keep/discard → 重複

**安全設計**：
- 40 天營收延遲在 **evaluate.py 強制**（agent 無法繞過）
- evaluate.py 是 READ ONLY — 評估標準不可改
- IC-series 去重防止 clone 因子
- 大規模 IC 驗證（865+ 支）防小樣本偏差
- 通過因子用 **StrategyValidator 16 項**（hard/soft 分離）最終驗證

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
