"""Cross-source data validation — compare Yahoo vs TWSE vs FinMind prices.

One-time check to verify data consistency across sources.
Reports discrepancies where close prices differ by > 1%.

Usage: python -m scripts.cross_source_validate
"""
from __future__ import annotations
import sys
sys.path.insert(0, '.')
import os
os.environ.setdefault("QUANT_ENV", "dev")

from pathlib import Path
import pandas as pd
import numpy as np


def load_close(source_dir: str, symbol: str) -> pd.Series | None:
    """Load close price series from a source directory."""
    suffix = "_1d.parquet"
    path = Path(source_dir) / f"{symbol}{suffix}"
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        if "close" not in df.columns:
            return None
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        df.index = pd.to_datetime(df.index.date)
        return df["close"].dropna()
    except Exception:
        return None


def compare_sources(sym: str, s1_name: str, s1_dir: str, s2_name: str, s2_dir: str) -> dict | None:
    """Compare close prices between two sources. Returns discrepancy info."""
    c1 = load_close(s1_dir, sym)
    c2 = load_close(s2_dir, sym)
    if c1 is None or c2 is None:
        return None

    # Align on common dates
    common = c1.index.intersection(c2.index)
    if len(common) < 10:
        return None

    c1 = c1[common]
    c2 = c2[common]

    # Compute relative difference
    diff = abs(c1 - c2) / c1.clip(lower=0.01)
    big_diff = diff[diff > 0.01]  # > 1% discrepancy

    if len(big_diff) == 0:
        return None

    return {
        "symbol": sym,
        "sources": f"{s1_name} vs {s2_name}",
        "common_dates": len(common),
        "discrepancies": len(big_diff),
        "pct_discrepant": round(len(big_diff) / len(common) * 100, 1),
        "max_diff_pct": round(float(diff.max()) * 100, 2),
        "worst_date": str(diff.idxmax().date()),
    }


def main():
    sources = {
        "yahoo": "data/yahoo",
        "finmind": "data/finmind",
        "twse": "data/twse",
    }

    # Find symbols present in multiple sources
    sym_sets = {}
    for name, dir_path in sources.items():
        d = Path(dir_path)
        if d.exists():
            syms = set()
            for f in d.glob("*_1d.parquet"):
                syms.add(f.stem.replace("_1d", ""))
            sym_sets[name] = syms
            print(f"{name}: {len(syms)} symbols")

    # Pairwise comparison
    pairs = [("yahoo", "twse"), ("yahoo", "finmind"), ("finmind", "twse")]
    total_checked = 0
    discrepancies = []

    for s1, s2 in pairs:
        if s1 not in sym_sets or s2 not in sym_sets:
            continue
        common_syms = sorted(sym_sets[s1] & sym_sets[s2])
        print(f"\n--- {s1} vs {s2}: {len(common_syms)} common symbols ---")

        for sym in common_syms:
            result = compare_sources(sym, s1, sources[s1], s2, sources[s2])
            total_checked += 1
            if result:
                discrepancies.append(result)

    # Report
    print(f"\n{'=' * 70}")
    print(f"Cross-Source Validation Report")
    print(f"{'=' * 70}")
    print(f"Total comparisons: {total_checked}")
    print(f"Discrepancies (>1%): {len(discrepancies)}")

    if discrepancies:
        print(f"\n{'Symbol':15s} {'Sources':20s} {'Dates':>6s} {'Bad':>4s} {'%Bad':>6s} {'MaxDiff':>8s} {'Worst Date':>12s}")
        print("-" * 75)
        for d in sorted(discrepancies, key=lambda x: -x["pct_discrepant"])[:20]:
            print(f"{d['symbol']:15s} {d['sources']:20s} {d['common_dates']:>6d} {d['discrepancies']:>4d} "
                  f"{d['pct_discrepant']:>5.1f}% {d['max_diff_pct']:>7.1f}% {d['worst_date']:>12s}")

        if len(discrepancies) > 20:
            print(f"  ... and {len(discrepancies) - 20} more")
    else:
        print("No significant discrepancies found.")

    # Save report
    report_path = Path("docs/research/cross_source_validation.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Cross-Source Data Validation Report",
        f"\n> Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}",
        f"\nTotal comparisons: {total_checked}",
        f"Discrepancies (>1%): {len(discrepancies)}",
    ]
    if discrepancies:
        lines.extend([
            "\n| Symbol | Sources | Dates | Discrepant | %Bad | MaxDiff | Worst Date |",
            "|--------|---------|------:|----------:|---------:|--------:|------------|",
        ])
        for d in sorted(discrepancies, key=lambda x: -x["pct_discrepant"]):
            lines.append(
                f"| {d['symbol']} | {d['sources']} | {d['common_dates']} | "
                f"{d['discrepancies']} | {d['pct_discrepant']}% | {d['max_diff_pct']}% | {d['worst_date']} |"
            )
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
