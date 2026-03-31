#!/usr/bin/env python3
"""Batch StrategyValidator for autoresearch tagged factors.

Extracts factor.py from each git tag in docker/autoresearch/work/,
saves to src/strategy/factors/research/, runs StrategyValidator 15 checks,
and produces a summary report.

Usage:
    python scripts/run_factor_validation.py
    python scripts/run_factor_validation.py --top 5    # only top 5 by results.tsv
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_tagged_factors(work_dir: Path) -> list[str]:
    """Get all factor-* tags from the autoresearch work git repo."""
    result = subprocess.run(
        ["git", "tag", "-l", "factor-*"],
        cwd=work_dir, capture_output=True, encoding="utf-8", errors="replace",
    )
    return [t.strip() for t in result.stdout.splitlines() if t.strip()]


def get_results_ranking(work_dir: Path) -> dict[str, float]:
    """Parse results.tsv for composite scores (for prioritization)."""
    tsv = work_dir / "results.tsv"
    if not tsv.exists():
        return {}
    scores: dict[str, float] = {}
    with open(tsv, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            desc = row.get("description", "")
            try:
                score = float(row.get("composite_score", 0))
            except ValueError:
                score = 0.0
            if score > 0:
                scores[desc] = score
    return scores


def extract_factor_code(work_dir: Path, tag: str) -> str:
    """Extract factor.py content from a git tag."""
    result = subprocess.run(
        ["git", "show", f"{tag}:factor.py"],
        cwd=work_dir, capture_output=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Cannot extract {tag}: {result.stderr}")
    return result.stdout


def run_validation(factor_name: str, factor_code: str) -> dict:
    """Save factor, build strategy, run StrategyValidator."""
    from src.alpha.auto.strategy_builder import build_from_research_factor
    from src.backtest.validator import StrategyValidator, ValidationConfig

    # Save factor code
    factor_dir = PROJECT_ROOT / "src" / "strategy" / "factors" / "research"
    factor_dir.mkdir(parents=True, exist_ok=True)
    factor_path = factor_dir / f"{factor_name}.py"
    factor_path.write_text(factor_code, encoding="utf-8")

    try:
        # Build strategy
        built = build_from_research_factor(factor_name=factor_name, top_n=15)

        # Build universe from available data
        market_dir = PROJECT_ROOT / "data" / "market"
        import pandas as pd
        universe = []
        for p in sorted(market_dir.glob("*_1d.parquet")):
            sym = p.stem.replace("_1d", "")
            if sym.startswith("finmind_"):
                sym = sym[len("finmind_"):]
            if sym.startswith("00") or ".TW" not in sym:
                continue
            try:
                df = pd.read_parquet(p)
                if len(df) >= 500:
                    universe.append(sym)
            except Exception:
                continue
            if len(universe) >= 150:
                break

        if len(universe) < 50:
            return {"error": f"Only {len(universe)} symbols available (need 50)"}

        # Run validator
        config = ValidationConfig(
            min_cagr=0.08, min_sharpe=0.7, max_drawdown=0.40,
            n_trials=15,  # ~15 independent hypothesis directions (Phase AB)
            initial_cash=10_000_000, min_universe_size=50,
            wf_train_years=2,
        )
        validator = StrategyValidator(config)
        report = validator.validate(built.strategy, universe, "2018-01-01", "2024-06-30")

        checks = {}
        for c in report.checks:
            checks[c.name] = {"passed": c.passed, "value": c.value, "threshold": c.threshold}

        return {
            "passed": report.passed,
            "n_passed": report.n_passed,
            "n_total": report.n_total,
            "checks": checks,
            "error": report.error,
        }

    except Exception as e:
        return {"error": str(e)}
    finally:
        # Clean up factor file
        if factor_path.exists():
            factor_path.unlink()


def main():
    parser = argparse.ArgumentParser(description="Batch validate autoresearch factors")
    parser.add_argument("--top", type=int, default=10, help="Validate top N factors")
    parser.add_argument("--all", action="store_true", help="Validate all tagged factors")
    args = parser.parse_args()

    work_dir = PROJECT_ROOT / "docker" / "autoresearch" / "work"
    if not work_dir.exists():
        print(f"ERROR: work dir not found: {work_dir}")
        sys.exit(1)

    tags = get_tagged_factors(work_dir)
    print(f"Found {len(tags)} tagged factors")

    if not tags:
        print("No tagged factors to validate")
        return

    # Prioritize by results.tsv scores if available
    if not args.all:
        tags = tags[:args.top]
        print(f"Validating top {len(tags)} factors")

    results: list[dict] = []
    report_lines = [
        "# Factor Validation Report",
        "",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Factors tested**: {len(tags)}",
        "**Validator**: 15 checks (CAGR, Sharpe, MDD, WF, DSR, Bootstrap, OOS, Benchmark, PBO, Regime, Recent, Correlation, CVaR, Universe, Cost)",
        "",
        "---",
        "",
    ]

    for i, tag in enumerate(tags):
        clean_name = tag.replace("factor-", "").replace("-", "_")
        print(f"\n[{i+1}/{len(tags)}] Validating {tag} ({clean_name})...")
        t0 = time.time()

        try:
            code = extract_factor_code(work_dir, tag)
            result = run_validation(clean_name, code)
        except Exception as e:
            result = {"error": str(e)}

        elapsed = time.time() - t0
        result["tag"] = tag
        result["name"] = clean_name
        result["elapsed"] = round(elapsed, 1)
        results.append(result)

        if "error" in result and result["error"]:
            print(f"  ERROR: {result['error']}")
        else:
            status = "PASS" if result.get("passed") else "FAIL"
            print(f"  {status} ({result.get('n_passed', 0)}/{result.get('n_total', 0)}) in {elapsed:.1f}s")

    # Summary table
    report_lines.append("## Summary")
    report_lines.append("")
    report_lines.append("| Factor | Result | Score | Details |")
    report_lines.append("|--------|--------|-------|---------|")

    passed_factors = []
    for r in results:
        if r.get("error"):
            report_lines.append(f"| {r['name']} | ERROR | — | {r['error'][:50]} |")
        else:
            status = "PASS" if r.get("passed") else "FAIL"
            score = f"{r.get('n_passed', 0)}/{r.get('n_total', 0)}"
            failed = [k for k, v in r.get("checks", {}).items() if not v.get("passed")]
            detail = ", ".join(failed[:3]) if failed else "all checks passed"
            report_lines.append(f"| {r['name']} | **{status}** | {score} | {detail} |")
            if r.get("passed"):
                passed_factors.append(r)

    report_lines.append("")
    report_lines.append(f"**Passed: {len(passed_factors)}/{len(results)}**")
    report_lines.append("")

    # Detailed results for passed factors
    if passed_factors:
        report_lines.append("## Passed Factors (Detail)")
        report_lines.append("")
        for r in passed_factors:
            report_lines.append(f"### {r['name']}")
            report_lines.append("")
            report_lines.append("| Check | Result | Value | Threshold |")
            report_lines.append("|-------|--------|-------|-----------|")
            for name, check in r.get("checks", {}).items():
                icon = "PASS" if check["passed"] else "FAIL"
                report_lines.append(f"| {name} | {icon} | {check['value']} | {check['threshold']} |")
            report_lines.append("")

    # Write report
    report_dir = PROJECT_ROOT / "docs" / "research"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"factor_validation_{datetime.now().strftime('%Y%m%d')}.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\nReport written to: {report_path}")

    # Also save raw JSON
    json_path = report_dir / f"factor_validation_{datetime.now().strftime('%Y%m%d')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"Raw results: {json_path}")


if __name__ == "__main__":
    main()
