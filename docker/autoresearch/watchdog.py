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
import time
from datetime import datetime
from pathlib import Path

WORK_DIR = Path("/app/work")
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
        expected = {"factor.py", "results.tsv", "run.log", ".git", ".gitignore", "__pycache__", "reports"}
        actual = {p.name for p in WORK_DIR.iterdir()} if WORK_DIR.exists() else set()
        unexpected = actual - expected
        if unexpected:
            log(f"WARNING: unexpected files in work/: {unexpected}")

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


def _process_pending():
    """Pick up pending validation markers, run Validator, write reports."""
    import json as _json

    pending_dir = WORK_DIR / "pending"
    if not pending_dir.exists():
        return

    markers = sorted(pending_dir.glob("*.json"))
    if not markers:
        return

    # Process one at a time (avoid overloading)
    marker_path = markers[0]
    log(f"Validator: processing {marker_path.name}")

    try:
        marker = _json.loads(marker_path.read_text(encoding="utf-8"))
        results = marker["results"]
        factor_code = marker["factor_code"]

        validator_report = _run_background_validator(results, factor_code)

        if validator_report and validator_report.get("deployed"):
            _write_background_report(results, validator_report, factor_code)
            log(f"Validator: DEPLOYED ({validator_report['n_passed']}/{validator_report['n_total']})")
        else:
            n_p = validator_report.get("n_passed", "?") if validator_report else "?"
            n_t = validator_report.get("n_total", "?") if validator_report else "?"
            log(f"Validator: not deployed ({n_p}/{n_t})")

        # Remove marker after processing
        marker_path.unlink()

    except Exception as e:
        log(f"Validator: failed — {e}")
        # Move to failed/ to avoid retry loop
        failed_dir = pending_dir / "failed"
        failed_dir.mkdir(exist_ok=True)
        marker_path.rename(failed_dir / marker_path.name)


def _run_background_validator(results: dict, factor_code: str) -> dict | None:
    """Run StrategyValidator 15 checks in background."""
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

        config = ValidationConfig(
            n_trials=1, oos_start="2025-01-01", oos_end="2025-12-31",
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

        n_excl_dsr = sum(1 for c in checks if c.passed and c.name != "deflated_sharpe")
        dsr_val = next((float(c.value) for c in checks if c.name == "deflated_sharpe"), 0)
        pbo_val = next((float(c.value) for c in checks if c.name == "pbo"), 1.0)
        deployed = n_excl_dsr >= 13 and dsr_val >= 0.70 and pbo_val <= 0.70

        return {
            "n_passed": n_passed,
            "n_total": n_total,
            "deployed": deployed,
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

    content = (
        f"# Factor Report: {name}\n\n"
        f"> Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"> Status: **DEPLOYED** | Validator: {n_p}/{n_t}\n\n"
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


if __name__ == "__main__":
    main()
