# Reviews Index

> All reviews from 2026-03-29 system audit. Read this file first.

## Code Quality（代碼品質）

| Report | What it covers | Key findings |
|--------|---------------|-------------|
| [code-quality/CODE_REVIEW_20260329.md](code-quality/CODE_REVIEW_20260329.md) | sinopac, oms, validator, analytics, scheduler | 9 CRITICAL + 8 HIGH all fixed. M-07 cache TTL ✅ 已修. Open: M-08,M-09 |
| [code-quality/FULL_SYSTEM_CODE_REVIEW_20260329.md](code-quality/FULL_SYSTEM_CODE_REVIEW_20260329.md) | engine, data sources, config, API, risk, cross_section | 19 valid (M-1 invalid). Fixed: H-3,H-4,H-5 + 3 quick fixes. Open: H-1,H-2,H-6,CR-2 |
| [code-quality/BACKTEST_MECHANISM_AUDIT_20260329.md](code-quality/BACKTEST_MECHANISM_AUDIT_20260329.md) | Backtest engine internals, 14 bugs | All 14 fixed |

## Methodology（方法論）

| Report | What it covers | Key findings |
|--------|---------------|-------------|
| [methodology/FACTOR_METHODOLOGY_AUDIT_20260329.md](methodology/FACTOR_METHODOLOGY_AUDIT_20260329.md) | IC/ICIR calculation, thresholds, neutralization | 7 correct. #8 horizon bias ✅ Method D. #9 ICIR threshold ✅ raised to 0.30. #10 resolved. #11 low-pri |
| [methodology/FACTOR_PIPELINE_DEEP_REVIEW_20260329.md](methodology/FACTOR_PIPELINE_DEEP_REVIEW_20260329.md) | Holdout degradation, 16-check Validator effectiveness | Holdout 62x over Dwork budget, SR < noise expectation |
| [methodology/AUTORESEARCH_VS_FINLAB_REVIEW_20260329.md](methodology/AUTORESEARCH_VS_FINLAB_REVIEW_20260329.md) | FinLab comparison, memory system, replacement mechanism | 3x efficiency from memory, we lead in OOS protection |

## System（系統就緒度）

| Report | What it covers | Key findings |
|--------|---------------|-------------|
| [system/PRODUCTION_READINESS_20260329.md](system/PRODUCTION_READINESS_20260329.md) | Can we rely on this for real money? | **No.** Need 90 days paper trading |
| [system/DEFERRED_ISSUES_INVENTORY_20260329.md](system/DEFERRED_ISSUES_INVENTORY_20260329.md) | 47 deferred/accepted-risk items across all plans | 3 critical-path blockers, 6 审批 disagreements |
| [system/UNIT_TEST_AUDIT_20260329.md](system/UNIT_TEST_AUDIT_20260329.md) | Test quality, not just coverage | 1766 tests but would miss 35+ historical bugs |
| [system/AA_AG_EXECUTION_GAP_AUDIT_20260329.md](system/AA_AG_EXECUTION_GAP_AUDIT_20260329.md) | Phase AA-AG execution status + strategy generation | regime hedge ✅ disabled, CAGR gap ✅ explained (3 causes), no-trade zone ✅ exists, cache TTL ✅ fixed |
| [system/STALE_CONCLUSIONS_AUDIT_20260329.md](system/STALE_CONCLUSIONS_AUDIT_20260329.md) | Are Phase M/AA numbers still valid? | No. Old code had formula bugs. Numbers need re-run |

## 2026-03-30 Update

| Report | What it covers | Key findings |
|--------|---------------|-------------|
| [code-quality/BUG_HUNT_20260330.md](code-quality/BUG_HUNT_20260330.md) | Post-update bug scan: scheduler, oms, engine, evaluate, watchdog, risk | 4C+5H+9M → 2C verified not-bug, 2C+5H+8M fixed. 1M fixed prior session. **All resolved** |

## 2026-04-02 Full Review

| Report | What it covers | Key findings |
|--------|---------------|-------------|
| [system/FULL_PROJECT_REVIEW_20260402.md](system/FULL_PROJECT_REVIEW_20260402.md) | Full codebase audit: engineering (7.5/10) + financial methodology (8/10) | E-1 smoke test fail-open 🔴, E-2 lock mismatch 🔴, factor concentration 🟠, survivorship bias 🟠. 20 prioritized action items |

## Archive

Superseded reports moved to `archive/`. Historical reference only.
