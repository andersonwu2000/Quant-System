# AutoResearch System Code Review Report — 2026-03-31

**Scope:** `scripts/autoresearch/evaluate.py`, `docker/autoresearch/watchdog.py`, `scripts/autoresearch/factor.py`  
**Status:** Highly Advanced (Scientific Grade)

---

## 1. Executive Summary

The AutoResearch system is the "alpha factory" of the project. Its evaluation harness (`evaluate.py`) is exceptionally well-designed, incorporating academic-grade anti-overfitting techniques and industrial best practices for factor research. The integration of `Thresholdout` and `DSR` sets it apart from typical retail trading systems.

## 2. Key Strengths

### 2.1 Information Leakage Protection
- **Mandatory Revenue Delay:** Hard-coded 40-day delay for fundamental data ensures that backtests cannot "cheat" by using financials before they were publicly available.
- **Unified Masking:** The `_mask_data` function acts as a security sandbox, ensuring the factor function only sees data point-in-time.

### 2.2 Advanced Anti-Overfitting (The "Gold Standard")
- **Thresholdout Integration:** By adding Laplace noise to OOS comparisons and tracking a "query budget," the system prevents the research agent from "mining the holdout set."
- **Rolling OOS:** The system uses a rolling 1.5-year OOS window, ensuring that the most recent market regimes are used for validation.
- **Monotonicity Testing:** The use of Bootstrap-based MR tests ensures that factor performance is not driven by a few outliers but by a consistent ordinal relationship.

### 2.3 Efficient Research Pipeline
- **L1 Early Exit:** Significantly reduces compute waste by rejecting "zero-signal" factors within seconds.
- **Factor Replacement (Phase AF):** Implements a systematic way to replace decaying factors with newer, higher-ICIR variants while maintaining library diversity.

---

## 3. Risks & Identified Weaknesses

### 3.1 Static Market Cap Leakage (High Priority) ✅ FIXED
- **Finding:** `market_cap` is loaded as a latest-value snapshot in `_load_all_data` and is not truncated in `_mask_data`.
- **Impact:** Factors using market cap as a feature (e.g., size-neutralization or small-cap tilt) will have look-ahead bias, as they "know" which stocks will become large/small in the future.
- **Fix (2026-03-31):** `_mask_data` now returns `"market_cap": {}` (disabled, same as pe/pb/roe). `program.md` updated to mark market_cap as DISABLED. Agent should use `close × volume` as size proxy (already PIT-safe via bars truncation).

### 3.2 Thresholdout Budget Persistence (Medium Priority) — Won't Fix
- **Finding:** The L5 query counter is stored in a JSON file.
- **Risk:** If the persistent volume is lost or the file is tampered with (if the agent gains file system access), the overfit protection is reset.
- **审批判定 (2026-03-31):** Won't fix. Agent 在 Docker 內無法存取 `watchdog_data/`（獨立 volume + `network_mode: none`）。Volume 丟失只讓 budget 歸零（多幾次 OOS query），不是安全漏洞。改用 DB 是過度設計。

### 3.3 Indirect Complexity Bypass (Medium Priority) — Won't Fix
- **Finding:** Complexity is checked via line count of `factor.py`.
- **Risk:** Agents can bypass this by importing large external libraries or using string obfuscation/dynamic execution (`exec`).
- **審批判定 (2026-03-31):** Won't fix. `program.md` 明確禁止 `exec`/`eval`/外部 import。Docker 環境沒有額外套件可 import。80 行限制是引導簡潔的 soft gate，安全靠 `_mask_data`（數據隔離）和 L1-L5 gates。

### 3.4 IC-Series Correlation vs. Returns Correlation — Not a Bug
- **Finding:** L3 primarily checks IC-series correlation.
- **審批判定 (2026-03-31):** 不成立。evaluate.py line 922 已有 mandatory slow path：IC corr ≤ 0.20 時**自動**計算 returns correlation（line 1373-1408）。這不是可選的，是 always-on 的。報告者未讀完代碼。

---

## 4. Final Recommendations

1.  ~~**Fix Market Cap Look-ahead:**~~ ✅ Fixed 2026-03-31. `_mask_data` now returns empty dict for market_cap.
2.  ~~**Harden Thresholdout:**~~ Won't fix. Docker volume isolation is sufficient.
3.  ~~**Expand Dedup Logic:**~~ Not applicable. Only one evaluator runs at a time (single-agent architecture).

**Overall Grade: A**
The system is scientifically sound and robust. Market Cap leakage was the only real issue and has been fixed.

---

## 5. 審批記錄 (2026-03-31)

| # | 判定 | 理由 |
|---|------|------|
| 3.1 | ✅ 真實，已修 | `_mask_data` 直傳 market_cap 未截斷 → 改為 `{}` |
| 3.2 | Won't fix | Docker volume 隔離已足夠 |
| 3.3 | Won't fix | 80 行是 soft gate，安全靠數據隔離 |
| 3.4 | 不成立 | Returns correlation 已是 mandatory slow path |
