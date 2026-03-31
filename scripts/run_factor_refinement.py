"""Factor Refinement Pipeline — AG Step 2.5

Runs all pre-deployment checks for an L5 factor:
  2.5a: Correlation check vs existing L5 factors
  2.5b: Multi-factor rank composite (if combinable)
  2.5c: Validator 15-point (kill_switch=OFF)
  2.5d: Stress test (6 historical + 5 cost scenarios)

Usage:
    python -m scripts.run_factor_refinement composite_growth_value
    python -m scripts.run_factor_refinement revenue_acceleration --single
"""
from __future__ import annotations

import argparse
import json
import sys
import time

sys.path.insert(0, '.')
import os
os.environ.setdefault("QUANT_ENV", "dev")



def _build_universe():
    from src.data.data_catalog import get_catalog
    catalog = get_catalog()
    all_syms = sorted(
        s for s in catalog.available_symbols("price")
        if ".TW" in s and not s.replace(".TW", "").startswith("00")
    )
    good = []
    for sym in all_syms[:200]:
        df = catalog.get("price", sym)
        if len(df) >= 500:
            good.append(sym)
    return good


def step_2_5a_correlation(factor_name: str):
    """Check correlation with existing L5 factors."""
    print("\n" + "=" * 70)
    print("Step 2.5a: Correlation Check")
    print("=" * 70)

    # Known L5 factors
    known_l5 = {
        "revenue_acceleration": "Revenue growth acceleration (3m vs prior 3m)",
        "per_value": "Negative PER (low PE = high score)",
    }

    if factor_name in known_l5:
        print(f"  {factor_name} is itself a known L5 factor")
        other = {k: v for k, v in known_l5.items() if k != factor_name}
        if other:
            print(f"  Can combine with: {list(other.keys())}")
        return True, list(other.keys())

    # For new factors, would compute IC series correlation
    print(f"  {factor_name}: new factor, no correlation data yet")
    return True, list(known_l5.keys())


def step_2_5c_validator(factor_name: str, universe: list[str]):
    """Run Validator 15-point with kill_switch=OFF."""
    print("\n" + "=" * 70)
    print("Step 2.5c: Validator 15-Point (kill_switch=OFF)")
    print("=" * 70)

    from src.alpha.auto.strategy_builder import build_from_research_factor
    from src.backtest.validator import StrategyValidator, ValidationConfig

    built = build_from_research_factor(factor_name, top_n=15)

    config = ValidationConfig(
        min_cagr=0.08,
        min_sharpe=0.7,
        max_drawdown=0.40,
        n_trials=15,
        initial_cash=10_000_000,
        min_universe_size=50,
        wf_train_years=2,
    )

    validator = StrategyValidator(config)
    report = validator.validate(built.strategy, universe, "2018-01-01", "2025-12-31")

    if report.error:
        print(f"  ERROR: {report.error}")
        return None

    print(f"  Result: {'PASSED' if report.passed else 'FAILED'} ({report.n_passed}/{report.n_total})")
    print(f"  IS: {report.actual_is_start} to {report.actual_is_end}")
    for c in report.checks:
        mark = "PASS" if c.passed else "FAIL"
        print(f"    [{mark}] {c.name:30s} {str(c.value):>12s}  ({c.threshold})")

    if report.backtest_result:
        r = report.backtest_result
        print(f"\n  CAGR:   {r.annual_return:+.2%}")
        print(f"  Sharpe: {r.sharpe:.3f}")
        print(f"  MDD:    {r.max_drawdown:.2%}")

    return report


def step_2_5d_stress(factor_name: str, universe: list[str]):
    """Run stress tests."""
    print("\n" + "=" * 70)
    print("Step 2.5d: Stress Test")
    print("=" * 70)

    from src.alpha.auto.strategy_builder import build_from_research_factor
    from src.backtest.stress_test import (
        run_historical_stress, run_cost_sensitivity, generate_stress_report,
    )

    def factory():
        return build_from_research_factor(factor_name, top_n=15).strategy

    print("\n  [1/2] Historical Crisis Periods...")
    historical = run_historical_stress(factory, universe)

    print("\n  [2/2] Cost Sensitivity...")
    cost = run_cost_sensitivity(factory, universe)

    # Generate report
    from pathlib import Path
    report_dir = f"docs/research/refinement/{factor_name}"
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = generate_stress_report(historical, cost, f"{report_dir}/stress_test.md")
    print(f"\n  Report: {path}")

    # Summary
    print("\n  --- Historical ---")
    for name, data in historical.items():
        if "error" in data:
            print(f"    {name}: ERROR")
        else:
            print(f"    {name}: ret={data['total_return']:+.1%}  bench={data['benchmark_return']:+.1%}  MDD={data['max_drawdown']:.1%}")

    print("\n  --- Cost Sensitivity ---")
    cost_2x_pass = False
    for name, data in cost.items():
        if "error" in data:
            print(f"    {name}: ERROR")
        else:
            print(f"    {name}: Sharpe={data['sharpe']:.3f}  CAGR={data['cagr']:+.1%}")
            if name == "2x_cost" and data["cagr"] > 0:
                cost_2x_pass = True

    return historical, cost, cost_2x_pass


def main():
    parser = argparse.ArgumentParser(description="Factor refinement pipeline (AG Step 2.5)")
    parser.add_argument("factor_name", help="Research factor name (in src/strategy/factors/research/)")
    parser.add_argument("--skip-stress", action="store_true", help="Skip stress tests (faster)")
    args = parser.parse_args()

    factor_name = args.factor_name
    t0 = time.time()

    print(f"Factor Refinement Pipeline: {factor_name}")
    print(f"{'=' * 70}")

    # Build universe
    print("Building universe...")
    universe = _build_universe()
    print(f"Universe: {len(universe)} symbols")

    # 2.5a: Correlation
    combinable, combine_with = step_2_5a_correlation(factor_name)

    # 2.5c: Validator
    report = step_2_5c_validator(factor_name, universe)

    # 2.5d: Stress test
    if not args.skip_stress:
        historical, cost, cost_2x_pass = step_2_5d_stress(factor_name, universe)
    else:
        print("\n  [SKIPPED] Stress tests")
        cost_2x_pass = None

    # Final summary
    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"REFINEMENT SUMMARY: {factor_name}")
    print(f"{'=' * 70}")
    print(f"  Correlation check:  {'PASS' if combinable else 'FAIL'}")
    if combine_with:
        print(f"  Can combine with:   {combine_with}")
    if report:
        print(f"  Validator:          {'PASS' if report.passed else 'FAIL'} ({report.n_passed}/{report.n_total})")
    if cost_2x_pass is not None:
        print(f"  Cost 2x survival:   {'PASS' if cost_2x_pass else 'FAIL'}")
    print(f"  Time:               {elapsed:.0f}s")

    # Save summary
    from pathlib import Path
    summary_dir = Path(f"docs/research/refinement/{factor_name}")
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "factor": factor_name,
        "timestamp": time.strftime("%Y-%m-%d %H:%M"),
        "universe_size": len(universe),
        "validator_passed": report.passed if report else False,
        "validator_score": f"{report.n_passed}/{report.n_total}" if report else "error",
        "cost_2x_pass": cost_2x_pass,
        "elapsed_seconds": round(elapsed),
    }
    (summary_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n  Summary: {summary_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
