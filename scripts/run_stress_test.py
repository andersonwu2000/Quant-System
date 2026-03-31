"""Run stress tests on composite_growth_value strategy.

Usage: python -m scripts.run_stress_test
"""
from __future__ import annotations
import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("QUANT_ENV", "dev")

from src.backtest.stress_test import (
    run_historical_stress, run_cost_sensitivity, generate_stress_report,
)


def _make_strategy():
    from src.alpha.auto.strategy_builder import build_from_research_factor
    built = build_from_research_factor("composite_growth_value", top_n=15)
    return built.strategy


def _build_universe():
    from src.data.data_catalog import get_catalog
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
    return good


def main():
    print("Building universe...")
    universe = _build_universe()
    print(f"Universe: {len(universe)} symbols")
    print("=" * 70)

    # 1. Historical stress
    print("\n[1/2] Historical Crisis Periods")
    print("-" * 70)
    historical = run_historical_stress(
        strategy_factory=_make_strategy,
        universe=universe,
    )

    # 2. Cost sensitivity
    print("\n[2/2] Cost Sensitivity Analysis")
    print("-" * 70)
    cost = run_cost_sensitivity(
        strategy_factory=_make_strategy,
        universe=universe,
    )

    # Generate report
    path = generate_stress_report(historical, cost)
    print(f"\n{'=' * 70}")
    print(f"Report: {path}")

    # Summary
    print("\n--- Historical Stress Summary ---")
    for name, data in historical.items():
        if "error" in data:
            print(f"  {name}: ERROR — {data['error']}")
        else:
            print(f"  {name}: return={data['total_return']:+.1%}  benchmark={data['benchmark_return']:+.1%}  MDD={data['max_drawdown']:.1%}")

    print("\n--- Cost Sensitivity Summary ---")
    for name, data in cost.items():
        if "error" in data:
            print(f"  {name}: ERROR — {data['error']}")
        else:
            print(f"  {name}: Sharpe={data['sharpe']:.3f}  CAGR={data['cagr']:+.1%}  cost/alpha={data['cost_ratio']:.0%}")


if __name__ == "__main__":
    main()
