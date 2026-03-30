"""Autoresearch Watchdog — runs alongside the agent container.

Checks every 60 seconds:
1. factor.py exists
2. results.tsv growing (stale = agent stuck)
3. evaluate.py checksum unchanged
4. No unexpected files in work/
5. Consecutive crash detection
6. Saturation + OOS decay detection
7. Disk usage
"""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

WORK_DIR = Path("/app/work")
WATCHDOG_DATA = Path("/app/watchdog_data")  # agent cannot access this
CHECK_INTERVAL = 60
STALE_THRESHOLD = 1800  # 30 min


def sha256(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="ignore").strip().splitlines())


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def main():
    log("Watchdog started")

    eval_checksum = sha256(Path("/app/evaluate.py"))
    log(f"evaluate.py checksum: {eval_checksum[:16]}...")

    last_result_lines = count_lines(WORK_DIR / "results.tsv")
    last_update_time = time.time()
    consecutive_crashes = 0
    last_runlog_mtime = 0.0

    while True:
        time.sleep(CHECK_INTERVAL)

        # 1. factor.py existence
        if not (WORK_DIR / "factor.py").exists():
            log("WARNING: factor.py missing!")

        # 2. results.tsv growth
        current_lines = count_lines(WORK_DIR / "results.tsv")
        if current_lines > last_result_lines:
            last_result_lines = current_lines
            last_update_time = time.time()
            log(f"Progress: results.tsv has {current_lines} entries")
        elif time.time() - last_update_time > STALE_THRESHOLD:
            stale_min = int((time.time() - last_update_time) / 60)
            log(f"STALE: No new results for {stale_min} minutes")

        # 3. evaluate.py integrity
        current_eval = sha256(Path("/app/evaluate.py"))
        if current_eval != eval_checksum:
            log(f"ALERT: evaluate.py checksum changed! was={eval_checksum[:16]}, now={current_eval[:16]}")

        # 4. unexpected files
        expected = {"factor.py", "results.tsv", "run.log", ".git", ".gitignore", "__pycache__", "reports", ".claude"}
        actual = {p.name for p in WORK_DIR.iterdir()} if WORK_DIR.exists() else set()
        unexpected = actual - expected
        if unexpected:
            log(f"WARNING: unexpected files in work/: {unexpected}")
            for name in unexpected:
                p = WORK_DIR / name
                if p.is_file():
                    p.unlink()
                    log(f"REMOVED: {name}")

        # 5. consecutive crash detection (use mtime to avoid false counts)
        run_log = WORK_DIR / "run.log"
        if run_log.exists():
            mtime = run_log.stat().st_mtime
            if mtime > last_runlog_mtime:
                last_runlog_mtime = mtime
                content = run_log.read_text(encoding="utf-8", errors="ignore")
                if "--- CRASH ---" in content:
                    consecutive_crashes += 1
                    log(f"WARNING: evaluate.py crashed ({consecutive_crashes} consecutive)")
                    if consecutive_crashes >= 5:
                        log("ALERT: 5+ consecutive crashes -- agent may be stuck in crash loop!")
                else:
                    consecutive_crashes = 0

        # 6. saturation + OOS decay detection
        results_path = WORK_DIR / "results.tsv"
        if results_path.exists():
            lines = results_path.read_text(
                encoding="utf-8", errors="ignore"
            ).strip().splitlines()[1:]  # skip header
            if len(lines) >= 50:
                recent = lines[-50:]
                discard_count = sum(1 for l in recent if "\tdiscard\t" in l)
                if discard_count >= 50:
                    log("ALERT: 50 consecutive discards -- factor space may be exhausted")
            # OOS decay: consecutive L4-pass but L5-fail
            l4_fail_l5 = 0
            for l in reversed(lines):
                if "L5 OOS fail" in l:
                    l4_fail_l5 += 1
                else:
                    break
            if l4_fail_l5 >= 10:
                log(f"ALERT: {l4_fail_l5} consecutive L4-pass-L5-fail -- possible OOS overfitting")

        # 7. disk usage
        total_size = sum(
            f.stat().st_size for f in WORK_DIR.rglob("*") if f.is_file()
        ) if WORK_DIR.exists() else 0
        if total_size > 100 * 1024 * 1024:
            log(f"WARNING: work/ size = {total_size / 1024 / 1024:.1f}MB")

        # 8. Background Validator: process pending markers
        _process_pending()

        # 9. Factor-Level PBO (Phase AB): compute when enough factors accumulated
        _compute_factor_level_pbo()


def _process_pending():
    """Pick up pending validation markers, run Validator, write reports."""
    import json as _json

    pending_dir = WATCHDOG_DATA / "pending"
    if not pending_dir.exists():
        return

    markers = sorted(pending_dir.glob("*.json"))
    if not markers:
        return

    # Pre-filter: returns dedup BEFORE expensive Validator
    # Among clone groups (corr > 0.85), keep the one with highest ICIR, discard rest.
    import json as _j_pre

    novel: list[Path] = []
    clone_groups: dict[str, list[tuple[Path, float]]] = {}  # ref_stem → [(path, icir)]

    for mp in markers:
        ret_ok, ret_corr, ret_with = _check_returns_dedup(mp.stem)
        if ret_ok:
            novel.append(mp)
        else:
            # Read ICIR from marker to pick best clone
            try:
                m = _j_pre.loads(mp.read_text(encoding="utf-8"))
                icir_vals = m.get("results", {}).get("icir_by_horizon", {})
                median_icir = float(sorted(abs(v) for v in icir_vals.values())[len(icir_vals)//2]) if icir_vals else 0
            except Exception:
                median_icir = 0
            clone_groups.setdefault(ret_with, []).append((mp, median_icir))

    # For each clone group: keep best ICIR, delete rest
    skipped = 0
    promoted = 0
    for ref_stem, clones in clone_groups.items():
        clones.sort(key=lambda x: -x[1])  # best ICIR first
        best_path, best_icir = clones[0]

        # Check if the best clone is better than the existing reference
        ref_path = WATCHDOG_DATA / "factor_returns" / f"{ref_stem}.parquet"
        # Read ref's ICIR from metadata if available
        meta_path = WATCHDOG_DATA / "factor_returns" / "metadata.json"
        ref_icir = 0.0
        if meta_path.exists():
            try:
                meta = _j_pre.loads(meta_path.read_text(encoding="utf-8"))
                ref_icir = abs(meta.get(ref_stem, {}).get("best_icir", 0))
            except Exception:
                pass

        if ref_icir <= 0:
            # C-007: metadata missing — cannot verify, skip all clones (don't promote)
            log(f"Validator: SKIP clone group for {ref_stem} (ref_icir unknown, metadata missing)")
            for cp, _ in clones:
                cp.unlink()
                skipped += 1
        elif best_icir > ref_icir:
            # Best clone has higher ICIR than reference — keep it as novel
            log(f"Validator: PROMOTED {best_path.name} (ICIR {best_icir:.3f} > ref {ref_icir:.3f})")
            novel.append(best_path)
            promoted += 1
            # Delete the rest
            for cp, _ in clones[1:]:
                cp.unlink()
                skipped += 1
        else:
            # Reference is already the best — skip all clones
            for cp, _ in clones:
                cp.unlink()
                skipped += 1

    if skipped > 0 or promoted > 0:
        log(f"Validator: dedup {skipped} clone(s) removed, {promoted} promoted, {len(novel)} novel to validate")

    if not novel:
        return

    # Sort novel by ICIR descending — validate best first
    def _get_icir(mp: Path) -> float:
        try:
            m = _j_pre.loads(mp.read_text(encoding="utf-8"))
            vals = m.get("results", {}).get("icir_by_horizon", {})
            return float(sorted(abs(v) for v in vals.values())[len(vals)//2]) if vals else 0
        except Exception:
            return 0

    novel.sort(key=_get_icir, reverse=True)
    marker_path = novel[0]
    try:
        marker = _json.loads(marker_path.read_text(encoding="utf-8"))
        results = marker["results"]
        factor_code = marker["factor_code"]
        composite = results.get("composite_score", 0)
        log(f"Validator: processing {marker_path.name} (composite {composite})")

        validator_report = _run_background_validator(results, factor_code)

        if validator_report and validator_report.get("deployed"):
            # Returns dedup — final check against ALL factor_returns (not just pending)
            # Pre-filter catches most clones, but can miss if stem doesn't match
            ret_ok, ret_corr, ret_with = _check_returns_dedup(marker_path.stem)
            if not ret_ok:
                log(f"Validator: BLOCKED by returns dedup post-validation (corr={ret_corr:.3f} with {ret_with})")
                validator_report["deployed"] = False
                marker_path.unlink()
                return

            # Gate: Factor-Level PBO must be <= 0.70 (if available)
            # M-002: validate PBO file integrity — stale/corrupt PBO should not auto-pass
            pbo_path = WATCHDOG_DATA / "factor_pbo.json"
            factor_pbo_ok = True
            factor_pbo_val = None
            if pbo_path.exists():
                try:
                    import json as _j2
                    fpbo = _j2.loads(pbo_path.read_text(encoding="utf-8"))
                    if not fpbo or not isinstance(fpbo, dict):
                        log("PBO gate: factor_pbo.json empty or corrupt — skipping PBO check")
                        fpbo = {}
                    factor_pbo_val = fpbo.get("factor_pbo")
                    if factor_pbo_val is not None and factor_pbo_val > 0.70:
                        factor_pbo_ok = False
                except Exception:
                    pass

            if not factor_pbo_ok:
                log(f"Validator: BLOCKED by Factor-Level PBO={factor_pbo_val:.3f} > 0.70 "
                    f"({validator_report['n_passed']}/{validator_report['n_total']})")
            else:
                soft_fails = validator_report.get("soft_fails", [])
                # C-010: delete marker BEFORE deploy to prevent duplicate on crash
                marker_path.unlink()
                _write_background_report(results, validator_report, factor_code)
                _queue_for_deployment(results, validator_report, factor_code)
                pbo_msg = f", factor_pbo={factor_pbo_val:.3f}" if factor_pbo_val is not None else ""
                if soft_fails:
                    log(f"Validator: DEPLOYED ({validator_report['n_passed']}/{validator_report['n_total']}{pbo_msg}) "
                        f"[soft fails: {', '.join(soft_fails)}]")
                else:
                    log(f"Validator: DEPLOYED ({validator_report['n_passed']}/{validator_report['n_total']}{pbo_msg})")
        else:
            n_p = validator_report.get("n_passed", "?") if validator_report else "?"
            n_t = validator_report.get("n_total", "?") if validator_report else "?"
            hard_fails = validator_report.get("hard_fails", []) if validator_report else []
            if hard_fails:
                log(f"Validator: not deployed ({n_p}/{n_t}) [hard fails: {', '.join(hard_fails)}]")
            else:
                log(f"Validator: not deployed ({n_p}/{n_t})")

        # Remove marker (if not already deleted by deploy path above)
        if marker_path.exists():
            marker_path.unlink()

    except Exception as e:
        log(f"Validator: failed — {e}")
        # H-006: retry up to 3 times before moving to failed/
        retry_suffix = ".retry"
        retry_count = marker_path.stem.count(retry_suffix) if marker_path.exists() else 99
        if retry_count < 3 and marker_path.exists():
            retry_path = marker_path.parent / f"{marker_path.stem}{retry_suffix}{marker_path.suffix}"
            marker_path.rename(retry_path)
            log(f"Validator: will retry ({retry_count + 1}/3)")
        else:
            failed_dir = pending_dir / "failed"
            failed_dir.mkdir(exist_ok=True)
        marker_path.rename(failed_dir / marker_path.name)


def _queue_for_deployment(results: dict, validator_report: dict, factor_code: str) -> None:
    """Write deployed factor to deploy_queue/ for host-side processing (Phase AG Step 1).

    No network needed — uses shared watchdog_data/ volume.
    Host scheduler reads deploy_queue/ and calls PaperDeployer.deploy().
    Dedup: hash factor_code to prevent duplicate submissions.
    """
    import hashlib

    deploy_dir = WATCHDOG_DATA / "deploy_queue"
    deploy_dir.mkdir(parents=True, exist_ok=True)

    # Dedup: check submitted_factors.json
    submitted_path = WATCHDOG_DATA / "submitted_factors.json"
    code_hash = hashlib.sha256(factor_code.encode()).hexdigest()  # full SHA256, no truncation
    submitted = {}
    if submitted_path.exists():
        try:
            submitted = json.loads(submitted_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if code_hash in submitted:
        log(f"Deploy: skip duplicate factor (hash={code_hash})")
        return

    # Write deploy marker
    ts = time.strftime("%Y%m%d_%H%M%S")
    marker = {
        "factor_code": factor_code,
        "results": {k: v for k, v in results.items()
                    if k not in ("oos_icir", "oos_positive_months", "oos_total_months")},
        "validator_report": validator_report,
        "timestamp": ts,
        "code_hash": code_hash,
    }
    marker_path = deploy_dir / f"{ts}.json"
    marker_path.write_text(json.dumps(marker, indent=2, default=str), encoding="utf-8")

    # Record hash
    submitted[code_hash] = ts
    submitted_path.write_text(json.dumps(submitted, indent=2), encoding="utf-8")
    log(f"Deploy: queued {marker_path.name} (hash={code_hash})")


def _run_background_validator(results: dict, factor_code: str) -> dict | None:
    """Run StrategyValidator 16 checks in background."""
    import sys
    import os
    import inspect

    os.environ.setdefault("QUANT_MODE", "backtest")
    sys.path.insert(0, "/app")
    sys.path.insert(0, "/app/work")

    try:
        from src.backtest.validator import StrategyValidator, ValidationConfig
        from src.strategy.base import Context, Strategy
        import pandas as pd

        # Reconstruct factor function from code
        factor_module = {}
        exec(factor_code, factor_module)
        compute_factor = factor_module.get("compute_factor")
        if compute_factor is None:
            log("Validator: no compute_factor in factor code")
            return None

        sig = inspect.signature(compute_factor)
        is_3arg = len([p for p in sig.parameters.values()
                       if p.default is inspect.Parameter.empty]) >= 3

        class _FactorStrategy(Strategy):
            _compute_fn = compute_factor  # expose for PBO vectorized access
            def name(self) -> str:
                return "autoresearch_candidate"
            def on_bar(self, ctx: Context) -> dict[str, float]:
                symbols = ctx.universe()
                as_of = pd.Timestamp(ctx.now())
                if is_3arg:
                    revenue = {}
                    for s in symbols:
                        rev = ctx.get_revenue(s, lookback_months=36)
                        if rev is not None and not rev.empty:
                            revenue[s] = rev
                    data = {
                        "bars": {s: ctx.bars(s, lookback=500) for s in symbols},
                        "revenue": revenue,
                        "institutional": {},
                        "pe": {}, "pb": {}, "roe": {},
                    }
                    values = compute_factor(symbols, as_of, data)
                else:
                    values = compute_factor(symbols, as_of)
                if not values:
                    return {}
                sorted_syms = sorted(values, key=lambda s: values[s], reverse=True)
                top_n = max(len(sorted_syms) // 5, 5)
                selected = sorted_syms[:top_n]
                w = 1.0 / len(selected)
                return {s: w for s in selected}

        # Dynamic n_trials from Factor-Level PBO clustering
        _n_trials = 15
        _pbo_path = WATCHDOG_DATA / "factor_pbo.json"
        if _pbo_path.exists():
            try:
                import json as _j3
                _n_ind = _j3.loads(_pbo_path.read_text(encoding="utf-8")).get("n_independent", 15)
                if isinstance(_n_ind, (int, float)) and _n_ind >= 2:
                    _n_trials = int(_n_ind)
            except Exception:
                pass

        config = ValidationConfig(
            n_trials=_n_trials,
            initial_cash=10_000_000, min_universe_size=50, wf_train_years=2,
        )

        # Load universe
        universe_path = Path("/app/data/research/universe.txt")
        if universe_path.exists():
            universe = [l.strip() for l in universe_path.read_text().splitlines() if l.strip()][:150]
        else:
            universe = []
            market_dir = Path("/app/data/market")
            for p in sorted(market_dir.glob("*.parquet"))[:200]:
                sym = p.stem.replace("_1d", "").replace("finmind_", "")
                if not sym.endswith(".TW"):
                    sym += ".TW"
                universe.append(sym)

        strategy = _FactorStrategy()
        validator = StrategyValidator(config)
        report = validator.validate(strategy, universe, "2017-01-01", "2024-12-31",
                                    compute_fn=compute_factor)

        n_passed = report.n_passed
        n_total = report.n_total
        checks = report.checks

        # Hard/soft deployment threshold (Phase AC §7)
        # Hard: must ALL pass (0 tolerance) — checks with statistical power
        # Soft: report but don't block — sanity checks or descriptive metrics
        HARD_CHECKS = {
            "cagr", "sharpe", "annual_cost_ratio", "temporal_consistency",
            "deflated_sharpe", "bootstrap_p_sharpe_positive", "vs_ew_universe",
            "construction_sensitivity", "market_correlation", "permutation_p",
        }
        hard_all_pass = all(c.passed for c in checks if c.name in HARD_CHECKS)
        soft_fails = [c.name for c in checks if c.name not in HARD_CHECKS and not c.passed]
        deployed = hard_all_pass

        hard_fails = [c.name for c in checks if c.name in HARD_CHECKS and not c.passed]

        return {
            "n_passed": n_passed,
            "n_total": n_total,
            "deployed": deployed,
            "hard_fails": hard_fails,
            "soft_fails": soft_fails,
            "checks": [(c.name, c.passed, str(c.value), str(c.threshold)) for c in checks],
        }
    except Exception as e:
        log(f"Validator error: {e}")
        return None


def _write_background_report(results: dict, validator_report: dict, factor_code: str) -> None:
    """Write deployment report to /app/reports/."""
    report_dir = Path("/app/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    import re
    # Extract name from factor docstring
    name = "unknown"
    name_safe = "unknown"
    for line in factor_code.splitlines():
        stripped = line.strip().strip('"').strip("'")
        if stripped and not stripped.startswith(("from ", "import ", "def ", "#", '"""', "'''")) \
                and len(stripped) > 5:
            name = stripped[:80]
            name_safe = re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:60]
            break

    ts = time.strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"{ts}_{name_safe}.md"

    vr = validator_report
    n_p, n_t = vr["n_passed"], vr["n_total"]

    # Show replacement info only if factor actually replaced another (from evaluate.py results)
    _supersedes = ""
    _replaced = results.get("replaced")
    if _replaced:
        _supersedes = f"\n> Replaces: {_replaced}"

    _max_corr = results.get('max_correlation', 0)
    _corr_with = results.get('correlated_with', '')
    _corr_line = f"\n> Nearest factor: {_corr_with} (corr={_max_corr:.3f})" if _corr_with and abs(_max_corr) > 0.10 else ""

    content = (
        f"# Factor Report: {name}\n\n"
        f"> Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"> Status: **DEPLOYED** | Validator: {n_p}/{n_t}{_supersedes}{_corr_line}\n\n"
        f"## Metrics\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Composite Score | {results.get('composite_score', 'N/A')} |\n"
        f"| IC (20d) | {results.get('ic_20d', 'N/A')} |\n"
        f"| Best ICIR | {results.get('best_icir', 'N/A')} ({results.get('best_horizon', '')}) |\n"
        f"| Fitness | {results.get('fitness', 'N/A')} |\n"
        f"| Positive Years | {results.get('positive_years', '?')}/{results.get('total_years', '?')} |\n"
        f"| Turnover | {results.get('avg_turnover', 'N/A')} |\n"
        f"| Large-scale ICIR | {results.get('large_icir_20d', 'N/A')} |\n\n"
        f"## Validator Results ({n_p}/{n_t})\n\n"
        f"| Check | Result | Value | Threshold |\n"
        f"|-------|--------|-------|----------|\n"
    )
    for cname, cpassed, cval, cthresh in vr["checks"]:
        mark = "PASS" if cpassed else "FAIL"
        content += f"| {cname} | {mark} | {cval} | {cthresh} |\n"

    content += f"\n## Factor Code\n\n```python\n{factor_code}```\n"

    report_path.write_text(content, encoding="utf-8")
    log(f"Report written: {report_path.name}")


def _check_returns_dedup(current_stem: str) -> tuple[bool, float, str]:
    """Check if this factor's portfolio returns are a clone of an existing factor.

    Compares the factor_returns parquet matching current_stem against all other
    stored factor_returns. If max |corr| > 0.85 → block as clone.

    Returns (ok, max_corr, correlated_with).
    """
    import pandas as pd

    returns_dir = WATCHDOG_DATA / "factor_returns"
    if not returns_dir.exists():
        return True, 0.0, ""

    # Find current factor's returns
    current_path = None
    for p in returns_dir.glob("*.parquet"):
        if current_stem in p.stem:
            current_path = p
            break

    if current_path is None:
        return True, 0.0, ""  # no returns stored yet, can't check

    try:
        current_df = pd.read_parquet(current_path)
        if "returns" not in current_df.columns or len(current_df) < 50:
            return True, 0.0, ""
        current_ret = current_df["returns"]
    except Exception:
        return True, 0.0, ""

    RETURNS_DEDUP_THRESHOLD = 0.85  # stricter than IC series (0.50)
    max_corr = 0.0
    max_name = ""

    for p in sorted(returns_dir.glob("*.parquet")):
        if p == current_path:
            continue
        try:
            df = pd.read_parquet(p)
            if "returns" not in df.columns or len(df) < 50:
                continue
            existing = df["returns"]
            min_len = min(len(current_ret), len(existing))
            corr = float(current_ret.iloc[:min_len].corr(existing.iloc[:min_len]))
            if abs(corr) > abs(max_corr):
                max_corr = corr
                max_name = p.stem
        except Exception:
            continue

    return abs(max_corr) <= RETURNS_DEDUP_THRESHOLD, max_corr, max_name


_last_factor_pbo_count = 0  # track when to recompute


def _compute_factor_level_pbo():
    """Compute Factor-Level PBO from accumulated factor daily returns.

    Bailey (2014) CSCV with N = all tested factors (not portfolio variants).
    Only runs when >= 20 factors accumulated and new factors added since last run.
    """
    global _last_factor_pbo_count

    returns_dir = WATCHDOG_DATA / "factor_returns"
    if not returns_dir.exists():
        return

    parquets = sorted(returns_dir.glob("*.parquet"))
    n_factors = len(parquets)

    # M-005: cap factor_returns at 500 (delete oldest if exceeded)
    MAX_FACTOR_RETURNS = 500
    if n_factors > MAX_FACTOR_RETURNS:
        to_delete = parquets[:n_factors - MAX_FACTOR_RETURNS]
        for p in to_delete:
            p.unlink()
        parquets = parquets[n_factors - MAX_FACTOR_RETURNS:]
        n_factors = len(parquets)
        log(f"Factor returns cleanup: deleted {len(to_delete)} oldest, kept {n_factors}")

    # Need >= 20 factors, and only recompute every 5 new factors
    if n_factors < 20 or n_factors - _last_factor_pbo_count < 5:
        return

    import pandas as pd
    import numpy as np

    try:
        # Build T×N returns matrix
        daily_returns_dict = {}
        for p in parquets:
            try:
                df = pd.read_parquet(p)
                if "returns" in df.columns and len(df) > 20:
                    daily_returns_dict[p.stem] = df["returns"].copy()  # ensure writable (parquet mmap)
            except Exception:
                continue

        if len(daily_returns_dict) < 20:
            return

        returns_matrix = pd.DataFrame(daily_returns_dict).fillna(0.0).dropna().copy()
        if len(returns_matrix) < 120:
            return

        # Phase AB Phase 3 + AB-4 Step 3: Independent hypothesis clustering
        # Factors with returns correlation > 0.50 are the same "direction"
        # AB-4: hierarchical clustering (captures transitive correlations)
        corr_matrix = returns_matrix.corr().fillna(0.0).copy()  # ensure writable
        from scipy.cluster.hierarchy import linkage, fcluster
        from scipy.spatial.distance import squareform

        dist_arr = (1 - corr_matrix.abs()).clip(lower=0).to_numpy(copy=True, dtype=float)
        np.fill_diagonal(dist_arr, 0)
        dist_matrix = pd.DataFrame(dist_arr, index=corr_matrix.index, columns=corr_matrix.columns)
        condensed = squareform(dist_matrix, checks=False).copy()
        Z = linkage(condensed, method='average')
        labels = fcluster(Z, t=0.50, criterion='distance')  # corr > 0.50 = same cluster

        clusters: list[list[str]] = []
        label_to_members: dict[int, list[str]] = {}
        for col, label in zip(corr_matrix.columns, labels):
            label_to_members.setdefault(int(label), []).append(col)
        clusters = list(label_to_members.values())

        # Pick median factor per cluster (avoid IS selection bias)
        # Using IS-best would bias PBO downward (optimistic = dangerous)
        independent_factors: list[str] = []
        for cluster in clusters:
            # M-003: rank by Sharpe (risk-adjusted) not raw mean return
            def _sharpe(s):
                std = returns_matrix[s].std()
                return returns_matrix[s].mean() / std if std > 0 else 0
            ranked = sorted(cluster, key=_sharpe)
            independent_factors.append(ranked[len(ranked) // 2])

        n_raw = len(daily_returns_dict)
        n_independent = len(independent_factors)
        returns_matrix = returns_matrix[independent_factors]

        if len(returns_matrix.columns) < 4:
            log(f"Factor-Level PBO: only {n_independent} independent directions (need >=4)")
            return

        # Run CSCV
        import sys
        sys.path.insert(0, "/app")
        from src.backtest.overfitting import compute_pbo

        n_parts = min(16, max(8, len(returns_matrix) // 60))
        if n_parts % 2 != 0:
            n_parts -= 1

        result = compute_pbo(returns_matrix, n_partitions=n_parts)
        _last_factor_pbo_count = n_factors

        log(f"Factor-Level PBO: {result.pbo:.3f} "
            f"(N={n_independent} independent / {n_raw} total, "
            f"{len(returns_matrix)} days, {result.n_combinations} combos)")

        # Write to a file for status.ps1 to pick up
        pbo_path = WATCHDOG_DATA / "factor_pbo.json"
        import json
        pbo_path.write_text(json.dumps({
            "factor_pbo": round(result.pbo, 4),
            "n_independent": n_independent,
            "n_total_factors": n_raw,
            "n_clusters": len(clusters),
            "n_days": len(returns_matrix),
            "n_combinations": result.n_combinations,
            "correlation_threshold": 0.50,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2), encoding="utf-8")

    except Exception as e:
        log(f"Factor-Level PBO failed: {e}")


if __name__ == "__main__":
    main()
