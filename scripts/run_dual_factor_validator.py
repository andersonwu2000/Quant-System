"""Run StrategyValidator 15-point check on composite_growth_value factor."""
from __future__ import annotations
import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("QUANT_ENV", "dev")

from src.alpha.auto.strategy_builder import build_from_research_factor
from src.backtest.validator import StrategyValidator, ValidationConfig
from src.data.data_catalog import get_catalog


def main():
    print("Building strategy from composite_growth_value...")
    built = build_from_research_factor(
        factor_name="composite_growth_value",
        top_n=15,
    )
    print(f"Strategy: {built.name}")

    # Build universe
    catalog = get_catalog()
    all_syms = sorted(
        s for s in catalog.available_symbols("price")
        if ".TW" in s and not s.replace(".TW", "").startswith("00")
    )

    # Filter: need enough history
    good = []
    for sym in all_syms[:200]:
        df = catalog.get("price", sym)
        if len(df) >= 500:
            good.append(sym)
    print(f"Universe: {len(good)} symbols (of {len(all_syms)} total)")

    if len(good) < 50:
        print("ERROR: insufficient universe")
        return

    # Configure validator
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
    print("Running Validator (IS: 2018-01-01 to OOS)...")
    print("=" * 70)

    report = validator.validate(
        built.strategy, good, "2018-01-01", "2025-12-31",
        compute_fn=None,
    )

    if report.error:
        print(f"\nERROR: {report.error}")
        return

    # Print results
    print(f"\n{'=' * 70}")
    print(f"Strategy: {built.name}")
    print(f"Result: {'PASSED' if report.passed else 'FAILED'} ({report.n_passed}/{report.n_total})")
    print(f"IS period: {report.actual_is_start} to {report.actual_is_end}")
    print(f"{'=' * 70}")

    for c in report.checks:
        mark = "PASS" if c.passed else "FAIL"
        print(f"  [{mark}] {c.name:30s} {str(c.value):>12s}  (threshold: {c.threshold})")

    # Backtest stats
    if report.backtest_result:
        r = report.backtest_result
        print("\n--- Backtest Summary ---")
        print(f"  CAGR:        {r.annual_return:+.2%}")
        print(f"  Sharpe:      {r.sharpe:.3f}")
        print(f"  Max DD:      {r.max_drawdown:.2%}")
        print(f"  Total Cost:  {r.total_commission:,.0f}")


if __name__ == "__main__":
    main()
