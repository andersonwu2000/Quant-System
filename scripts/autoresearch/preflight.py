#!/usr/bin/env python3
"""Autoresearch preflight check — run before every research session.

Two modes:
  python preflight.py --cold    Fresh start: wipe all prior research artifacts
  python preflight.py --warm    Resume: verify integrity, don't wipe

Cold start clears: learnings, l5_query_count, last_evaluated_hash,
  factor_returns, deploy_queue, pending_l5, factor_pbo, audit.log,
  and resets factor.py to baseline.

Warm start checks: all files exist and are consistent, factor.py is
  committed, results.tsv is parseable, evaluate.py is read-only.

Both modes verify: no research info leaks into places agent shouldn't see.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Resolve project root
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
WATCHDOG_DIR = PROJECT_ROOT / "docker" / "autoresearch" / "watchdog_data"

RED = ""
GREEN = ""
YELLOW = ""
RESET = ""
# Enable ANSI colors only if terminal supports it
if sys.stdout.isatty():
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

errors: list[str] = []
warnings: list[str] = []
cleaned: list[str] = []


def ok(msg: str) -> None:
    print(f"  {GREEN}[OK]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[WARN]{RESET} {msg}")
    warnings.append(msg)


def fail(msg: str) -> None:
    print(f"  {RED}[FAIL]{RESET} {msg}")
    errors.append(msg)


def clean(msg: str) -> None:
    print(f"  {GREEN}>{RESET} {msg}")
    cleaned.append(msg)


# ── Cold start: wipe everything ─────────────────────────────────


def cold_start() -> None:
    print("\n=== COLD START: Wiping all prior research artifacts ===\n")

    # 1. learnings.jsonl → empty
    path = WATCHDOG_DIR / "learnings.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    clean("learnings.jsonl → cleared")

    # 2. l5_query_count.json → reset
    path = WATCHDOG_DIR / "l5_query_count.json"
    path.write_text('{"count": 0, "updated": "reset"}', encoding="utf-8")
    clean("l5_query_count.json → reset to 0")

    # 3. last_evaluated_hash.txt → remove
    path = WATCHDOG_DIR / "last_evaluated_hash.txt"
    if path.exists():
        path.unlink()
    clean("last_evaluated_hash.txt → removed")

    # 4. factor_returns/ → clear
    fret_dir = WATCHDOG_DIR / "factor_returns"
    if fret_dir.exists():
        for f in fret_dir.glob("*"):
            f.unlink()
    clean("factor_returns/ → cleared")

    # 5. deploy_queue/ → clear
    dq_dir = WATCHDOG_DIR / "deploy_queue"
    if dq_dir.exists():
        for f in dq_dir.glob("*"):
            f.unlink()
    clean("deploy_queue/ → cleared")

    # 6. Other watchdog artifacts
    for name in ["pending_l5.json", "factor_pbo.json"]:
        path = WATCHDOG_DIR / name
        if path.exists():
            path.unlink()
            clean(f"{name} → removed")

    # 7. audit.log
    audit = SCRIPT_DIR / "audit.log"
    if audit.exists():
        audit.unlink()
        clean("audit.log → removed")

    # 8. results.tsv → header only
    results = SCRIPT_DIR / "results.tsv"
    results.write_text("commit\tcomposite_score\tbest_icir\tlevel\tstatus\tdescription\n",
                       encoding="utf-8")
    clean("results.tsv → reset to header only")

    # 9. factor.py → check it's baseline (don't overwrite — user should commit)
    factor = SCRIPT_DIR / "factor.py"
    if factor.exists():
        content = factor.read_text(encoding="utf-8")
        if "Baseline: 12-1 momentum" in content:
            ok("factor.py is baseline")
        else:
            warn("factor.py is NOT baseline — reset it manually and commit")

    # 10. baseline_ic_series.json → remove (dedup reference from prior round)
    for loc in [WATCHDOG_DIR, SCRIPT_DIR]:
        path = loc / "baseline_ic_series.json"
        if path.exists():
            path.unlink()
            clean(f"{path.relative_to(PROJECT_ROOT)} → removed")

    # 11. work/ directory — Docker agent's working copy (contains its own git repo)
    work_dir = SCRIPT_DIR / "work"
    if work_dir.exists():
        # Reset work/factor.py to baseline
        work_factor = work_dir / "factor.py"
        if work_factor.exists():
            baseline = (
                '"""Alpha factor definition — the ONLY file the agent may edit."""\n'
                'from __future__ import annotations\n'
                'import pandas as pd\n'
                '\n'
                'def compute_factor(symbols: list[str], as_of: pd.Timestamp, data: dict) -> dict[str, float]:\n'
                '    """Baseline: 12-1 momentum (skip most recent month)."""\n'
                '    results: dict[str, float] = {}\n'
                '    for sym in symbols:\n'
                '        try:\n'
                '            bars = data["bars"].get(sym)\n'
                '            if bars is None or bars.empty: continue\n'
                '            b = bars.loc[:as_of]\n'
                '            if len(b) < 252: continue\n'
                '            ret_12m = b["close"].iloc[-21] / b["close"].iloc[-252] - 1\n'
                '            results[sym] = float(ret_12m)\n'
                '        except Exception: continue\n'
                '    return results\n'
            )
            work_factor.write_text(baseline, encoding="utf-8")
            clean("work/factor.py → reset to baseline")

        # Reset work/results.tsv
        work_results = work_dir / "results.tsv"
        if work_results.exists():
            work_results.write_text(
                "commit\tcomposite_score\tbest_icir\tlevel\tstatus\tdescription\n",
                encoding="utf-8",
            )
            clean("work/results.tsv → reset to header only")

        # Reset work git history (squash to single commit)
        work_git = work_dir / ".git"
        if work_git.exists():
            import subprocess
            subprocess.run(
                ["git", "checkout", "--orphan", "clean", "--"],
                cwd=str(work_dir), capture_output=True,
            )
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(work_dir), capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "clean start", "--allow-empty"],
                cwd=str(work_dir), capture_output=True,
            )
            subprocess.run(
                ["git", "branch", "-D", "master"],
                cwd=str(work_dir), capture_output=True,
            )
            subprocess.run(
                ["git", "branch", "-D", "main"],
                cwd=str(work_dir), capture_output=True,
            )
            subprocess.run(
                ["git", "branch", "-m", "main"],
                cwd=str(work_dir), capture_output=True,
            )
            # Prune old objects
            subprocess.run(
                ["git", "gc", "--prune=now"],
                cwd=str(work_dir), capture_output=True,
            )
            clean("work/.git → history wiped (orphan branch)")

        # Remove stray directories (e.g. work/C:/)
        for item in work_dir.iterdir():
            if item.is_dir() and item.name not in (".git", "__pycache__"):
                import shutil
                shutil.rmtree(item, ignore_errors=True)
                clean("work/ stray directory removed")


# ── Warm start: verify integrity ────────────────────────────────


def warm_start() -> None:
    print("\n=== WARM START: Verifying research session integrity ===\n")

    # 1. results.tsv exists and is parseable
    results = SCRIPT_DIR / "results.tsv"
    if results.exists():
        lines = [l for l in results.read_text(encoding="utf-8").strip().split("\n")
                 if l and not l.startswith("#")]
        n_experiments = len(lines) - 1  # minus header
        ok(f"results.tsv: {n_experiments} experiments recorded")
    else:
        fail("results.tsv missing")

    # 2. factor.py exists and is committed
    factor = SCRIPT_DIR / "factor.py"
    if factor.exists():
        ok("factor.py exists")
        # Check if committed
        import subprocess
        diff = subprocess.run(
            ["git", "diff", "--name-only", "--", str(factor)],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        if diff.stdout.strip():
            warn("factor.py has uncommitted changes — commit before running evaluate")
        else:
            ok("factor.py is committed")
    else:
        fail("factor.py missing")

    # 3. learnings.jsonl exists
    path = WATCHDOG_DIR / "learnings.jsonl"
    if path.exists():
        lines = [l for l in path.read_text(encoding="utf-8").strip().split("\n") if l]
        ok(f"learnings.jsonl: {len(lines)} entries")
    else:
        warn("learnings.jsonl missing — will be created on first evaluate")

    # 4. l5_query_count.json exists and is valid
    path = WATCHDOG_DIR / "l5_query_count.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            ok(f"l5_query_count: {data.get('count', '?')} queries")
        except json.JSONDecodeError:
            fail("l5_query_count.json is corrupt")
    else:
        warn("l5_query_count.json missing — will be created")

    # 5. work/ directory consistency
    work_dir = SCRIPT_DIR / "work"
    if work_dir.exists():
        work_factor = work_dir / "factor.py"
        work_results = work_dir / "results.tsv"
        if work_factor.exists():
            ok(f"work/factor.py exists ({work_factor.stat().st_size} bytes)")
        else:
            warn("work/factor.py missing")
        if work_results.exists():
            lines = [l for l in work_results.read_text(encoding="utf-8").strip().split("\n")
                     if l and not l.startswith("#")]
            ok(f"work/results.tsv: {len(lines) - 1} experiments")
        else:
            warn("work/results.tsv missing")


# ── Common checks (both modes) ──────────────────────────────────


def common_checks() -> None:
    print("\n=== COMMON CHECKS ===\n")

    # 1. evaluate.py is read-only
    evaluate = SCRIPT_DIR / "evaluate.py"
    if evaluate.exists():
        import stat
        mode = evaluate.stat().st_mode
        if not (mode & stat.S_IWUSR):
            ok("evaluate.py is read-only")
        else:
            fail("evaluate.py is WRITABLE — set read-only: chmod -w evaluate.py")
    else:
        fail("evaluate.py missing")

    # 2. program.md is read-only
    program = SCRIPT_DIR / "program.md"
    if program.exists():
        import stat
        mode = program.stat().st_mode
        if not (mode & stat.S_IWUSR):
            ok("program.md is read-only")
        else:
            warn("program.md is writable — consider: chmod -w program.md")
    else:
        fail("program.md missing")

    # 3. universe.txt exists
    universe = SCRIPT_DIR / "universe.txt"
    if universe.exists():
        syms = [l.strip() for l in universe.read_text().split("\n")
                if l.strip() and not l.startswith("#")]
        etfs = [s for s in syms if s.replace(".TW", "").startswith("00")]
        ok(f"universe.txt: {len(syms)} symbols, {len(etfs)} ETFs")
        if etfs:
            warn(f"universe.txt contains {len(etfs)} ETFs — should be 0")
    else:
        warn("universe.txt missing — evaluate.py will fallback to catalog scan")

    # 4. Data availability
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.data.data_catalog import DataCatalog
        catalog = DataCatalog(str(PROJECT_ROOT / "data"))
        n = len(catalog.available_symbols("price"))
        ok(f"DataCatalog: {n} symbols with price data")
    except Exception as e:
        warn(f"DataCatalog check failed: {e}")

    # 5. No research info in places agent can read
    # Agent can read: factor.py, results.tsv, program.md
    # Agent should NOT see: specific factor names, ICIR values, past experiment details
    # (except through learnings API which we control)
    program = SCRIPT_DIR / "program.md"
    if program.exists():
        content = program.read_text(encoding="utf-8")
        # Check for hardcoded factor names that would bias research
        bias_terms = ["revenue_acceleration", "per_value", "composite_growth"]
        found = [t for t in bias_terms if t in content]
        if found:
            warn(f"program.md mentions specific factors: {found} — may bias research direction")
        else:
            ok("program.md has no specific factor name leakage")


# ── Main ────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autoresearch preflight check",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="  --cold    Fresh start (wipe all artifacts)\n"
               "  --warm    Resume (verify integrity only)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cold", action="store_true", help="Fresh start: wipe all prior research")
    group.add_argument("--warm", action="store_true", help="Resume: verify integrity only")
    args = parser.parse_args()

    print("=" * 60)
    print("  Autoresearch Preflight Check")
    print("=" * 60)

    if args.cold:
        # Cold start is destructive — require confirmation
        print(f"\n  {RED}WARNING: Cold start will PERMANENTLY DELETE all research artifacts.{RESET}")
        print("  This includes: learnings, results, factor_returns, work/ git history.")
        print()
        confirm = input("  Type 'COLD START' to confirm: ")
        if confirm.strip() != "COLD START":
            print(f"\n  {YELLOW}Aborted.{RESET}")
            sys.exit(1)
        cold_start()
    else:
        warm_start()

    common_checks()

    # Summary
    print("\n" + "=" * 60)
    if cleaned:
        print(f"  Cleaned: {len(cleaned)} items")
    if warnings:
        print(f"  {YELLOW}Warnings: {len(warnings)}{RESET}")
    if errors:
        print(f"  {RED}ERRORS: {len(errors)} — DO NOT START RESEARCH{RESET}")
        for e in errors:
            print(f"    {RED}✗{RESET} {e}")
        sys.exit(1)
    else:
        print(f"  {GREEN}READY — all checks passed{RESET}")
    print("=" * 60)


if __name__ == "__main__":
    main()
