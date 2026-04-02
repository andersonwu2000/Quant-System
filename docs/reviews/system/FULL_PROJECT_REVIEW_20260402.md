# Full Project Review — Engineering + Financial Methodology

> Date: 2026-04-02
> Scope: Full codebase audit (174 Python files, ~29,000 LOC)
> Status: **Review complete** — prioritized action items at bottom

---

## Part I: Engineering

### 1. Architecture & Code Organization

**Strengths:**
- 19 well-separated modules with clear boundaries (api, execution, risk, scheduler, backtest, strategy, data, etc.)
- Unified data layer: all reads route through `DataCatalog` — no direct file I/O bypass
- Panel file caching in `DataCatalog._panel_cache` for 12MB FinLab files (read 2000x)
- Monorepo cohesion: Python backend + React web + Kotlin Android + Alembic migrations

**Weaknesses:**
- **Global singleton overuse**: 9 global `_*` variables with locks (`_config`, `_state`, `_calendar`, `_default_catalog`, etc.). `get_app_state()` called 47+ times; mutation_lock coordination complex.
- **Monolithic AppState**: 15+ attributes including async locks, trading state, risk engine — single initialization failure point.
- No circular dependency check in CI.

**Recommendations:**
- Replace simple globals with `contextvars` for async-aware singleton management
- Split `AppState` into `PortfolioState`, `ExecutionState`, `AnalyticsState` (→ Phase AN scope)
- Add import order check to CI

### 2. Error Handling & Failure Modes

**Strengths:**
- Custom `TradingInvariantError` with explicit non-recovery semantics and Discord notification
- Kill switch fires on invariant violations (disciplined fail-closed)
- 1435 exception handlers across 122 files with consistent patterns
- Audit trail on critical errors: invariant violations logged to DB + Discord

**Issues Found:**

| ID | Issue | Severity | Location |
|----|-------|:--------:|----------|
| E-1 | **Smoke test fail-open**: trading continues if smoke test script throws exception | 🔴 CRITICAL | `scheduler/ops.py:~81` |
| E-2 | **async/sync lock mismatch**: `asyncio.Lock` on AppState + `threading.Lock` on Portfolio sharing state | 🔴 HIGH | `api/state.py` + `execution/service.py` |
| E-3 | Kill switch concurrent trigger (API rebalance + RealtimeRiskMonitor) untested | 🟠 HIGH | `risk/realtime.py:171-182` |
| E-4 | 28+ `.debug("Suppressed exception")` hiding real issues in production | 🟡 MEDIUM | scattered |
| E-5 | No timeout guard on `ExecutionService.submit_orders()` — could block event loop | 🟡 MEDIUM | `execution/service.py` |
| E-6 | Broker reconnect uses fixed timing, no exponential backoff | 🟡 MEDIUM | `SinopacBroker` |

### 3. Configuration Management

**Strengths:**
- Pydantic Settings with strict validation, 60+ typed fields
- Production safety checks: rejects default API key / JWT secret outside dev env
- HMAC constant-time API key comparison
- Docker compose enforces secrets via `?Set` syntax

**Issues Found:**

| ID | Issue | Severity | Location |
|----|-------|:--------:|----------|
| C-1 | Default admin password `Admin1234` with no forced change on first login | 🟠 HIGH | `core/config.py:83` |
| C-2 | Three conflicting cron schedules with unclear precedence | 🟡 MEDIUM | `core/config.py:102-111` |
| C-3 | Broker credentials stored with defaults in config (should be env-only) | 🟡 MEDIUM | `core/config.py` |
| C-4 | Magic numbers in risk thresholds undocumented (`max_position_pct: 0.10`, `fat_finger_pct: 0.05`) | 🟡 LOW | `core/config.py` |

### 4. Data Pipeline

**Strengths:**
- `DataCatalog.get(dataset, symbol)` is the single entry point
- Priority-ordered source: TWSE > Yahoo > FinMind fallback
- Smart dividend adjustment in `_apply_adj_close()`

**Issues Found:**

| ID | Issue | Severity | Location |
|----|-------|:--------:|----------|
| D-1 | PIT (Point-in-Time) filtering not enforced at catalog layer — relies on callers | 🟠 HIGH | `data/catalog.py` |
| D-2 | `catalog.get()` returns empty DataFrame silently on unknown symbols (should raise) | 🟡 MEDIUM | `data/catalog.py` |
| D-3 | `max_ffill_days` in BacktestConfig but not enforced at DataCatalog level | 🟡 LOW | `data/catalog.py` |

### 5. Concurrency & Async

**Issues Found:**

| ID | Issue | Severity | Location |
|----|-------|:--------:|----------|
| A-1 | **Lock ordering undocumented**: `portfolio.lock` (threading) vs `state.mutation_lock` (asyncio) — no formal ordering | 🟠 HIGH | system-wide |
| A-2 | Market data callback queue unbounded — memory leak risk during high-tick sessions | 🟡 MEDIUM | quote manager |
| A-3 | `SinopacBroker._reconnect_thread` never joined on shutdown — leaked threads | 🟡 MEDIUM | `execution/broker/sinopac.py` |

### 6. API Security

**Strengths:**
- Dual auth: API Key (service) + JWT (users) with token revocation
- HMAC constant-time comparison, httpOnly cookie fallback, 5-level RBAC
- Rate limiting 60/min global

**Issues Found:**

| ID | Issue | Severity | Location |
|----|-------|:--------:|----------|
| S-1 | No input validation: `weights: dict[str,float]` accepts NaN/Infinity/negative | 🟠 HIGH | `api/routes/*` |
| S-2 | Rate limiting is global only — one bot can DoS all users | 🟡 MEDIUM | `api/app.py` |
| S-3 | WebSocket no per-subscription permission control | 🟡 MEDIUM | `api/ws.py` |
| S-4 | API keys have no TTL / expiration | 🟡 LOW | auth system |

### 7. Deployment Readiness

**Strengths:**
- Multi-stage Docker, non-root user, health check, PostgreSQL persistence, Alembic migrations

**Issues Found:**

| ID | Issue | Severity | Location |
|----|-------|:--------:|----------|
| P-1 | **No graceful shutdown**: open orders not cancelled, risk monitor not flushed | 🟠 HIGH | `api/app.py` |
| P-2 | No resource limits in docker-compose (CPU/memory unbounded) | 🟡 MEDIUM | `docker-compose.yml` |
| P-3 | DB password in docker-compose visible in source control | 🟡 MEDIUM | `docker-compose.yml` |
| P-4 | Logs stdout-only, lost on container restart | 🟡 MEDIUM | system-wide |

### 8. Test Coverage

**Strengths:**
- 132 test files, 28,259 lines; multi-layer (unit/integration/security/e2e)
- Fixtures block real notifications/persistence/trade ledger
- CI: ruff + mypy + pytest with 60s timeout

**Gaps:**

| Gap | Impact |
|-----|--------|
| Only 1 e2e scenario (single trading day) | Missing: paper→live, broker reconnect, kill switch liquidation, crash recovery |
| No concurrency tests for `mutation_lock` contention | Race conditions undetected |
| No load tests (API 100 req/s, backtest 500-symbol) | Scalability unknown |
| Validator 16 checks only referenced in 3 test files | Gate effectiveness unverified |
| SimBroker lacks realistic rejection scenarios | TWSE quirks untested |

---

## Part II: Financial Methodology

### 9. Factor Research Pipeline

**Strengths:**
- 5-gate evaluation (L0 complexity → L1 IC → L2 ICIR → L3 dedup → L4 fitness → L5 blind OOS)
- 5 normalization variants auto-tested per factor (raw, rank, z-score, winsorize, percentile)
- 40-day revenue lag **enforced** in evaluate.py (agent cannot bypass)
- L5 blind: bucketed ICIR return + Thresholdout + Laplace noise (scale 0.05)
- DSR + PBO + Walk-Forward triple overfitting defense

**Issues:**

| ID | Issue | Severity |
|----|-------|:--------:|
| F-1 | **Factor concentration**: all 4 deployed factors are revenue family — PBO diversity insufficient | 🟠 HIGH |
| F-2 | Autoresearch stalled: 8 recent experiments all L1 fail (IC < 0.02), no new family explored | 🟡 MEDIUM |
| F-3 | L3 correlation 0.65 may be too tight, blocking diverse factors with shared beta exposure | 🟡 MEDIUM |

### 10. Backtesting Methodology

**Strengths:**
- Context isolation: auto-truncates all data to current simulation date
- T+1 execution delay, deterministic (UUID-tracked)
- Taiwan-specific: dual commission 0.1425%, proof tax 0.3%, min fee ¥20/¥1, lot size 1000, odd-lot premium
- √ slippage model calibrated to Taiwan mid-cap liquidity
- 10% ADV order cap, settlement T+0 to T+2 configurable

**Issues:**

| ID | Issue | Severity |
|----|-------|:--------:|
| B-1 | **Survivorship bias**: Yahoo Finance lacks delisted stocks → estimated 3-8% CAGR overstatement | 🟠 HIGH |
| B-2 | **Price limit ±10% not enforced** in Validator backtest → estimated 2-5% CAGR overstatement | 🟠 MEDIUM |
| B-3 | Survivorship: warning-only (no enforcement or dead-stock history available) | 🟡 MEDIUM |

### 11. Risk Management

**Strengths:**
- 12+ pre-trade rules (position weight cap, daily DD limit, fat-finger, max trades)
- Kill switch with month-end cooldown reset
- Real-time NAV tracking, sector/instrument dashboards

**Gaps:**
- No real-time volatility clustering detection
- No intraday CVaR monitoring (only post-hoc)
- No intraday liquidity checks beyond 10% ADV assumption

### 12. Validator Gates — Core Factor Status

**revenue_acceleration (7/7 Hard PASS, 14/16 total):**

| Gate | Type | Threshold | Value | Result |
|------|:----:|-----------|-------|:------:|
| CAGR | HARD | ≥ 8% | 18.99% | ✅ |
| Cost ratio | HARD | < 50% | 3% | ✅ |
| 2× cost safety | HARD | > 0% | 18.32% | ✅ |
| Temporal consistency | HARD | > 0 | +1.532 | ✅ |
| DSR (N=15) | HARD | ≥ 0.70 | 0.887 | ✅ |
| PBO (Bailey) | HARD | ≤ 0.60 | 0.544 | ✅ |
| Market correlation | HARD | ≤ 0.80 | 0.574 | ✅ |
| **MDD** | SOFT | ≤ 40% | **44.35%** | ⚠️ |
| **vs EW universe** | SOFT | ≥ 50% | **25%** | ⚠️ |
| OOS2 Sharpe | SOFT | ≥ 0.30 | 0.652 | ✅ |
| Bootstrap P(SR>0) | SOFT | ≥ 80% | 99.5% | ✅ |

### 13. Key Financial Risks

| Risk | Severity | Mitigation Status |
|------|:--------:|-------------------|
| 2025 OOS loss -22.83% (hedge logic or regime shift?) | 🔴 | ⏳ Paper trading monitoring |
| Factor concentration in revenue family | 🟠 | ⏳ Need diversification |
| Survivorship bias 3-8% overstatement | 🟠 | 🟡 Warning only |
| Price limit not modeled → 2-5% CAGR overstatement | 🟠 | ⏳ Not yet enforced |
| Capacity ceiling ~1-3B TWD (Sharpe → 0.03 at 10x) | 🟡 | ✅ Documented |
| vs EW only 25% (sector concentration?) | 🟡 | ⏳ Overlay built but not enabled |

---

## Part III: Prioritized Action Items

### Priority 1 — This Week (Blockers)

| # | Action | Category | Complexity |
|---|--------|:--------:|:----------:|
| 1 | Smoke test fail-open → fail-closed (E-1) | Engineering | 低 |
| 2 | async/sync lock mismatch fix (E-2) | Engineering | 中 |
| 3 | 2025 OOS loss root cause analysis | Financial | 中 |
| 4 | Graceful shutdown: cancel open orders + flush risk monitor (P-1) | Engineering | 中 |

### Priority 2 — This Month (Important)

| # | Action | Category | Complexity |
|---|--------|:--------:|:----------:|
| 5 | API input validation decorator (S-1) | Engineering | 中 |
| 6 | Kill switch race condition test (E-3) | Engineering | 中 |
| 7 | Lock ordering documentation + enforcement (A-1) | Engineering | 低 |
| 8 | Price limit ±10% in Validator backtest (B-2) | Financial | 中 |
| 9 | Overlay 啟用 (beta target + sector cap) in paper trading | Financial | 低 |
| 10 | Admin password forced change on first login (C-1) | Engineering | 低 |
| 11 | Per-user rate limiting (S-2) | Engineering | 中 |

### Priority 3 — Next Month (Hardening)

| # | Action | Category | Complexity |
|---|--------|:--------:|:----------:|
| 12 | AppState 拆分 (→ Phase AN) | Engineering | 高 |
| 13 | Factor diversification: expand beyond revenue family (F-1) | Financial | 高 |
| 14 | E2E test expansion: paper→live, broker reconnect, crash recovery | Engineering | 高 |
| 15 | Log aggregation (ELK or similar) (P-4) | Engineering | 中 |
| 16 | Market data bounded queue (A-2) | Engineering | 中 |
| 17 | Survivorship bias: acquire delisted stock data (B-1) | Financial | 高 |

### Priority 4 — Ongoing

| # | Action | Category |
|---|--------|:--------:|
| 18 | Autoresearch monitoring: track L1 pass rate by factor family | Financial |
| 19 | Monthly Validator gate review (thresholds still appropriate?) | Financial |
| 20 | Quarterly security audit (auth, API, key rotation) | Engineering |

---

## Overall Assessment

| Dimension | Score | Summary |
|-----------|:-----:|---------|
| **Engineering** | **7.5/10** | Strong architecture and safety design. Main gaps: concurrency safety, input validation, graceful shutdown |
| **Financial Methodology** | **8/10** | Rigorous overfitting defense (DSR+PBO+WF). Main gaps: factor diversity, survivorship bias, price limit modeling |
| **Production Readiness** | **6.5/10** | Viable for paper trading. Needs Priority 1+2 items before live allocation |

**Bottom line**: System foundations are solid. The triple overfitting defense and Taiwan-specific cost modeling are standout strengths. The two biggest risks are (1) engineering: concurrent lock safety and graceful shutdown, and (2) financial: revenue-family concentration and survivorship bias. Complete Priority 1 items before any live trading.
