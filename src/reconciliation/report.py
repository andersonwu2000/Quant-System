"""Reconciliation reporting — CLI and summary generation.

Usage:
    python -m src.reconciliation.report                  # reconcile all days
    python -m src.reconciliation.report --date 2026-03-30  # single day
    python -m src.reconciliation.report --weekly         # weekly summary
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from src.reconciliation.daily import (
    DailyReconciliation,
    reconcile_all,
    reconcile_date,
    save_reconciliation,
    PAPER_DIR,
)


def print_daily(results: list[DailyReconciliation]) -> None:
    """Print daily reconciliation results."""
    if not results:
        print("No reconciliation data available.")
        return

    print(f"\n{'Date':<12} {'Status':<8} {'Actual':>10} {'Expected':>10} {'Diff':>10} {'Drift':>8} {'Trades':>7} {'Shortfall':>10}")
    print("-" * 85)

    for r in results:
        print(
            f"{r.date:<12} {r.status:<8} "
            f"{r.actual_return_bps:>+9.1f}bp {r.expected_return_bps:>+9.1f}bp "
            f"{r.return_diff_bps:>+9.1f}bp {r.weight_drift_bps:>7.0f}bp "
            f"{r.n_trades:>7} {r.avg_shortfall_bps:>9.1f}bp"
        )
        for w in r.warnings:
            print(f"  WARN: {w}")

    # Summary
    if len(results) > 1:
        diffs = [r.return_diff_bps for r in results if r.nav_start > 0]
        if diffs:
            import statistics
            avg_diff = statistics.mean(diffs)
            max_diff = max(abs(d) for d in diffs)
            print(f"\nSummary: {len(diffs)} days, avg diff={avg_diff:+.1f}bps, max |diff|={max_diff:.1f}bps")
            within_50 = sum(1 for d in diffs if abs(d) <= 50)
            print(f"Within 50bps threshold: {within_50}/{len(diffs)} ({within_50/len(diffs)*100:.0f}%)")


def generate_weekly_report(results: list[DailyReconciliation]) -> dict:
    """Generate weekly summary report."""
    if not results:
        return {"error": "No data"}

    diffs = [r.return_diff_bps for r in results if r.nav_start > 0]
    shortfalls = [r.avg_shortfall_bps for r in results if r.n_trades > 0]
    drifts = [r.weight_drift_bps for r in results if r.target_weights]

    report = {
        "period_start": results[0].date,
        "period_end": results[-1].date,
        "trading_days": len(results),
        "return_diff": {
            "mean_bps": round(sum(diffs) / len(diffs), 2) if diffs else 0,
            "max_abs_bps": round(max(abs(d) for d in diffs), 2) if diffs else 0,
            "within_50bps": sum(1 for d in diffs if abs(d) <= 50),
            "total_days": len(diffs),
        },
        "execution": {
            "mean_shortfall_bps": round(sum(shortfalls) / len(shortfalls), 2) if shortfalls else 0,
            "total_trades": sum(r.n_trades for r in results),
            "total_commission": round(sum(r.total_commission for r in results), 2),
        },
        "weight_drift": {
            "mean_bps": round(sum(drifts) / len(drifts), 2) if drifts else 0,
        },
        "warnings": [w for r in results for w in r.warnings],
    }

    # Save
    out_dir = PAPER_DIR / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"weekly_{results[-1].date}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Paper trading reconciliation")
    parser.add_argument("--date", type=str, help="Reconcile single date (YYYY-MM-DD)")
    parser.add_argument("--weekly", action="store_true", help="Generate weekly report")
    args = parser.parse_args()

    if args.date:
        result = reconcile_date(args.date)
        save_reconciliation(result)
        print_daily([result])
    else:
        results = reconcile_all()
        for r in results:
            save_reconciliation(r)
        print_daily(results)

        if args.weekly and results:
            report = generate_weekly_report(results)
            print(f"\nWeekly report saved. Mean diff: {report['return_diff']['mean_bps']:+.1f}bps")


if __name__ == "__main__":
    main()
