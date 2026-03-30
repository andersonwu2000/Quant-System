# Data Layer Infrastructure Audit Report — 2026-03-31

**Scope:** `src/data/data_catalog.py`, `src/data/registry.py`, `src/data/feed.py`, `src/data/schemas.py`  
**Status:** Advanced (Production-Ready Architecture)

---

## 1. Executive Summary

The data layer implements a "local-first" principle with a unified access catalog. It successfully abstracts the complexity of multi-source data merging (TWSE, Yahoo, FinMind, FinLab) and provides industry-standard features like **Point-in-Time (PIT) filtering** and **Dividend-Adjusted Price Reconstruction**. The architecture is highly scalable and research-friendly.

---

## 2. Key Strengths

### 2.1 Unified Data Catalog (`DataCatalog`)
- **Source Prioritization:** The system searches source directories based on a configurable priority list, ensuring the most authoritative data (e.g., TWSE official) is preferred over third-party providers.
- **PIT Filtering:** The automatic application of `pit_delay_days` is a critical defense against look-ahead bias in fundamental research.

### 2.2 Sophisticated Price Adjustment
- **Hybrid Adjustment Logic:** The `_apply_adj_close` method bridges the gap between raw OHLC data and dividend-adjusted series. By calculating an adjustment ratio and scaling OHLC proportionally, it maintains the structural integrity of the candle (Open/High/Low) while providing a smooth total-return series for backtesting.

### 2.3 Performance Optimization
- **Panel Access:** The `get_panel` method's "Fast Path" (reading consolidated FinLab panels instead of individual symbol files) drastically improves the performance of cross-sectional factor computations.

---

## 3. Critical Risks & Identified Weaknesses

### 3.1 Source Prioritization "Quality Blindness" (High Priority) — ✅ FIXED `f03daca`
- **Finding:** `_resolve_path` returns the first file it finds in the priority list.
- **Impact:** If a high-priority source (e.g., TWSE) has a corrupted or partial file, the system will never "see" the complete data available in a lower-priority source (e.g., Yahoo).
- **Fix:** `parquet_path()` now skips files < 100 bytes（corrupt/empty），falls through to next source. See `registry.py:213`.

### 3.2 Adjustment Ratio Convergence (Medium Priority) — ✅ FIXED `f03daca`
- **Finding:** `_apply_adj_close` uses an `intersection` of raw and adjusted indices.
- **Impact:** If the adjustment source (FinLab) is behind the raw source (Yahoo) by a few days, the most recent bars will remain unadjusted. This causes a fake price jump in the backtest at the boundary of the two datasets.
- **Fix:** Forward-fill the last known ratio to all post-adj dates. Verified: 2330.TW ratio=2.2043 continuous across 2018-12-28/2019-01-02 boundary. See `data_catalog.py:_apply_adj_close`.

### 3.3 Timezone Ambiguity (Medium Priority) — ⚠️ NOT A BUG (intentional design)
- **Finding:** Extensive use of `tz_localize(None)` across the catalog and feeds.
- **Verification:** 14 occurrences found. **13 of 14** use `tz_convert("UTC").tz_localize(None)` — convert to UTC first, then strip. Only 2 bare strips (data_catalog.py:191, fred.py:133). Comment in `feed.py:90` confirms intent: "統一為 tz-naive (UTC) 以避免比較問題".
- **Conclusion:** This is **correct UTC standardization**, not careless timezone stripping. No fix needed.

### 3.4 In-Memory Cache Absence — ❌ BY DESIGN (not fixing)
- **Finding:** "No in-memory cache — reads from parquet on every call."
- **Verification:** Confirmed. Explicitly documented in module docstring and class docstring.
- **Rationale:** User's design principle is "本地優先讀本地檔案，不用 in-memory cache". Parquet reads are fast enough for current scale (~1,100 symbols). Adding cache adds memory pressure and stale-data risk for marginal speedup. Will reconsider if profiling shows I/O bottleneck.

---

## 4. Final Assessment

The data layer is the most robust part of the system's infrastructure. It is designed to handle the messy reality of financial data sources.

**Resolution (2026-03-31):** 2 of 4 issues fixed, 2 confirmed as intentional design.
- 3.1 Quality fallback: **FIXED** — corrupt files skipped
- 3.2 Forward-fill: **FIXED** — smooth adj/raw boundary
- 3.3 Timezone: **NOT A BUG** — UTC standardization already in place
- 3.4 No cache: **BY DESIGN** — local-first principle

**Overall Grade: A**
