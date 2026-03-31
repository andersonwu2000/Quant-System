"""Data CLI — unified entry point for data operations.

Usage:
    python -m src.data.cli status                    # all datasets overview
    python -m src.data.cli status --dataset revenue  # single dataset detail
    python -m src.data.cli refresh --dataset price   # incremental update
    python -m src.data.cli refresh --dataset all     # update all datasets
    python -m src.data.cli validate                  # quality gate dry-run
    python -m src.data.cli sync-universe             # populate securities master from parquet
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


def cmd_status(args: argparse.Namespace) -> None:
    """Show data coverage and freshness for all or one dataset."""
    from src.data.registry import REGISTRY

    datasets = [args.dataset] if args.dataset else list(REGISTRY.keys())

    print(f"\n{'Dataset':<22} {'Files':>6} {'Freshest':>12} {'Oldest':>12} {'Size MB':>8}")
    print("-" * 68)

    for ds_name in datasets:
        if ds_name not in REGISTRY:
            print(f"{ds_name:<22} UNKNOWN")
            continue

        ds = REGISTRY[ds_name]
        suffix = ds.suffix

        # Collect files from all source dirs
        files = []
        for source_dir in ds.source_dirs:
            if source_dir.exists():
                files.extend(source_dir.glob(f"*_{suffix}.parquet"))
        count = len(files)
        if count == 0:
            print(f"{ds_name:<22} {'0':>6} {'N/A':>12} {'N/A':>12} {'0':>8}")
            continue

        total_size = sum(f.stat().st_size for f in files) / (1024 * 1024)
        freshest = None
        oldest = None

        # Sample from each source dir: pick largest file (most history) + newest file
        # This ensures we see both the oldest start date and the freshest end date
        sample = []
        for source_dir in ds.source_dirs:
            if not source_dir.exists():
                continue
            dir_files = sorted(source_dir.glob(f"*_{suffix}.parquet"))
            if not dir_files:
                continue
            # Largest file = most history (oldest date)
            by_size = sorted(dir_files, key=lambda f: f.stat().st_size, reverse=True)
            sample.extend(by_size[:10])
            # Most recently modified = freshest date
            by_mtime = sorted(dir_files, key=lambda f: f.stat().st_mtime, reverse=True)
            sample.extend(by_mtime[:5])
        sample = list({f: None for f in sample})  # dedupe preserving order
        for f in sample:
            try:
                df = pd.read_parquet(f)
                if df.empty:
                    continue
                if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
                    last = df.index.max().date()
                    first = df.index.min().date()
                elif "date" in df.columns and len(df) > 0:
                    last = pd.Timestamp(df["date"].max()).date()
                    first = pd.Timestamp(df["date"].min()).date()
                else:
                    continue
                if freshest is None or last > freshest:
                    freshest = last
                if oldest is None or first < oldest:
                    oldest = first
            except Exception:
                continue

        # Include FinLab panel in size + date range if available
        if ds.finlab_panel:
            from src.data.registry import FINLAB_DIR
            panel_path = FINLAB_DIR / ds.finlab_panel
            if panel_path.exists():
                total_size += panel_path.stat().st_size / (1024 * 1024)
                try:
                    pdf = pd.read_parquet(panel_path)
                    if not pdf.empty:
                        p_last = pdf.index.max()
                        p_first = pdf.index.min()
                        if hasattr(p_last, 'date'):
                            p_last = p_last.date()
                            p_first = p_first.date()
                            if freshest is None or p_last > freshest:
                                freshest = p_last
                            if oldest is None or p_first < oldest:
                                oldest = p_first
                        count += len(pdf.columns)  # panel columns = symbols
                except Exception:
                    pass

        freshest_str = freshest.isoformat() if freshest else "N/A"
        oldest_str = oldest.isoformat() if oldest else "N/A"
        print(f"{ds_name:<22} {count:>6} {freshest_str:>12} {oldest_str:>12} {total_size:>8.1f}")

    # Total across all source dirs
    total_files = 0
    total_mb = 0.0
    for d in [Path("data/yahoo"), Path("data/finmind"), Path("data/twse"), Path("data/finlab")]:
        if d.exists():
            dir_files = list(d.rglob("*.parquet"))
            total_files += len(dir_files)
            total_mb += sum(f.stat().st_size for f in dir_files) / (1024 * 1024)
    print("-" * 68)
    print(f"{'TOTAL':<22} {total_files:>6} {'':>12} {'':>12} {total_mb:>8.1f}")
    print()


def cmd_refresh(args: argparse.Namespace) -> None:
    """Refresh one or all datasets."""
    from src.data.refresh import refresh_dataset_sync
    from src.data.registry import REGISTRY

    if args.dataset == "all":
        datasets = list(REGISTRY.keys())
    else:
        datasets = [args.dataset]

    for ds in datasets:
        print(f"\nRefreshing {ds}...")
        report = refresh_dataset_sync(ds, force=args.force)
        print(f"  {report.summary()}")
        if report.failed:
            n_show = min(5, len(report.failed))
            for f in report.failed[:n_show]:
                print(f"    FAILED: {f}")
            if len(report.failed) > n_show:
                print(f"    ... and {len(report.failed) - n_show} more")


def cmd_validate(args: argparse.Namespace) -> None:
    """Run quality gate (dry-run, does not halt trading)."""
    from src.data.quality_gate import pre_trade_quality_gate
    from src.data.refresh import _discover_symbols

    symbols = _discover_symbols()
    if not symbols:
        print("No symbols found in data/market/")
        return

    print(f"Running quality gate on {len(symbols)} symbols...")
    result = pre_trade_quality_gate(symbols, reference_date=args.date)

    print(f"\nResult: {'PASS' if result.passed else 'BLOCKED'}")
    print(f"Universe: {result.universe_size}")
    print(f"Freshest: {result.freshest_date}")

    for check in result.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"  {status} {check.name}: {check.detail}")
        if not check.passed and check.affected_symbols:
            n_show = min(5, len(check.affected_symbols))
            for sym in check.affected_symbols[:n_show]:
                print(f"      - {sym}")
            if len(check.affected_symbols) > n_show:
                print(f"      ... and {len(check.affected_symbols) - n_show} more")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print(f"  WARN: {w}")


def cmd_sync_universe(args: argparse.Namespace) -> None:
    """Populate securities master from existing parquet files."""
    from src.data.master import SecuritiesMaster
    from src.data.store import DataStore

    ds = DataStore()
    master = SecuritiesMaster(ds._engine)
    count = master.sync_from_parquet()
    total = master.count()
    print(f"Synced {count} securities. Total in master: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Data catalog CLI")
    sub = parser.add_subparsers(dest="command")

    # status
    p_status = sub.add_parser("status", help="Show dataset coverage and freshness")
    p_status.add_argument("--dataset", type=str, default=None)

    # refresh
    p_refresh = sub.add_parser("refresh", help="Incremental data refresh")
    p_refresh.add_argument("--dataset", type=str, required=True)
    p_refresh.add_argument("--force", action="store_true", help="Force re-download")

    # validate
    p_validate = sub.add_parser("validate", help="Run quality gate (dry-run)")
    p_validate.add_argument("--date", type=date.fromisoformat, default=date.today())

    # sync-universe
    sub.add_parser("sync-universe", help="Populate securities master from parquet")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "refresh":
        cmd_refresh(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "sync-universe":
        cmd_sync_universe(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
