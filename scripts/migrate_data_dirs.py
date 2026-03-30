"""One-time migration: move data from market/fundamental to source-based dirs.

data/market/*_1d.parquet       → data/yahoo/*_1d.parquet
data/fundamental/*             → data/finmind/*

Note on provenance:
  - market/ files are mostly from Yahoo (default data_source="yahoo"),
    but some may have been downloaded via FinMind. Pre-migration files
    lack source metadata so we cannot distinguish them programmatically.
    All are placed in yahoo/ as the predominant source. Going forward,
    refresh engine writes source metadata to new files for accurate tracking.
  - fundamental/ files are all from FinMind.

After migration, data/market/ and data/fundamental/ can be deleted.

Usage:
    python scripts/migrate_data_dirs.py              # dry run
    python scripts/migrate_data_dirs.py --execute    # actual move
"""

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate data dirs to source-based layout")
    parser.add_argument("--execute", action="store_true", help="Actually move files (default: dry run)")
    args = parser.parse_args()

    moves: list[tuple[Path, Path]] = []

    # market/ → yahoo/ (price data, mostly from Yahoo)
    market_dir = Path("data/market")
    yahoo_dir = Path("data/yahoo")
    if market_dir.exists():
        for f in sorted(market_dir.glob("*.parquet")):
            moves.append((f, yahoo_dir / f.name))

    # fundamental/ → finmind/ (all fundamental data from FinMind)
    fund_dir = Path("data/fundamental")
    finmind_dir = Path("data/finmind")
    if fund_dir.exists():
        for f in sorted(fund_dir.glob("*.parquet")):
            moves.append((f, finmind_dir / f.name))

    print(f"Migration plan: {len(moves)} files")
    print(f"  market/ → yahoo/: {sum(1 for s,_ in moves if 'market' in str(s))} files")
    print(f"  fundamental/ → finmind/: {sum(1 for s,_ in moves if 'fundamental' in str(s))} files")

    if not args.execute:
        print("\nDry run. Use --execute to actually move files.")
        # Show first 5
        for src, dst in moves[:5]:
            print(f"  {src} → {dst}")
        if len(moves) > 5:
            print(f"  ... and {len(moves) - 5} more")
        return

    # Execute
    yahoo_dir.mkdir(parents=True, exist_ok=True)
    finmind_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    failed = 0
    for src, dst in moves:
        try:
            # If destination already exists (from ongoing download), skip
            if dst.exists():
                # Keep the larger file (more data)
                if dst.stat().st_size >= src.stat().st_size:
                    src.unlink()
                    moved += 1
                    continue
            shutil.move(str(src), str(dst))
            moved += 1
        except Exception as e:
            print(f"  FAILED: {src} → {dst}: {e}")
            failed += 1

    print(f"\nMigrated: {moved} files, {failed} failed")

    # Clean up empty dirs
    for d in [market_dir, fund_dir]:
        if d.exists() and not any(d.iterdir()):
            d.rmdir()
            print(f"Removed empty directory: {d}")
        elif d.exists():
            remaining = list(d.iterdir())
            print(f"Warning: {d} still has {len(remaining)} items")


if __name__ == "__main__":
    main()
