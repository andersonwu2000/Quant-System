"""Batch download all remaining FinLab datasets.

Downloads financial_statement, etl, fundamental_features, institutional,
dividend, foreign_ownership, margin — all available keys.

Usage:
    python scripts/download_finlab_batch.py
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FINLAB_DIR = Path("data/finlab")

# Category → output subdirectory
DIR_MAP = {
    "financial_statement": "financial_statement",
    "etl": "etl",
    "fundamental_features": "fundamental_features",
    "institutional_investors_trading_summary": "institutional_detail",
    "dividend_tse": "dividend",
    "dividend_otc": "dividend",
    "foreign_investors_shareholding": "foreign_ownership",
    "margin_transactions": "margin_detail",
}


def main() -> None:
    from finlab import data

    all_keys = data.search("")

    # Group keys by category
    categories: dict[str, list[str]] = {cat: [] for cat in DIR_MAP}
    for key in all_keys:
        prefix = key.split(":")[0] if ":" in key else key
        if prefix in categories:
            categories[prefix].append(key)

    total_keys = sum(len(v) for v in categories.values())
    print(f"Plan: {total_keys} keys across {len(categories)} categories")

    total_saved = 0
    total_failed = 0
    total_empty = 0

    for cat, keys in categories.items():
        subdir = DIR_MAP[cat]
        out_dir = FINLAB_DIR / subdir
        out_dir.mkdir(parents=True, exist_ok=True)

        logger.info("=== %s (%d keys) ===", cat, len(keys))

        for i, key in enumerate(keys):
            # Use category prefix + index for predictable filenames
            prefix = f"{cat}_{i:03d}" if cat not in ("dividend_tse", "dividend_otc") else f"{cat}_{i:03d}"
            out_path = out_dir / f"{prefix}.parquet"

            if out_path.exists():
                total_saved += 1
                continue

            try:
                df = data.get(key)
                if df is None or (hasattr(df, "empty") and df.empty):
                    total_empty += 1
                    continue

                table = pa.Table.from_pandas(df)
                meta = {
                    b"source": b"finlab",
                    b"finlab_key": key.encode("utf-8", errors="replace"),
                    b"fetch_time": datetime.now().isoformat().encode(),
                    b"n_rows": str(len(df)).encode(),
                    b"n_cols": str(len(df.columns) if hasattr(df, "columns") else 0).encode(),
                }
                table = table.replace_schema_metadata({**(table.schema.metadata or {}), **meta})
                pq.write_table(table, out_path)
                total_saved += 1

            except Exception as e:
                err = str(e)
                if "VIP" in err or "not exists" in err:
                    total_empty += 1  # VIP-only or removed dataset
                else:
                    total_failed += 1
                    logger.warning("  ERR [%d] %s: %s", i, key[:50], err[:60])

        logger.info("  Progress: %d saved, %d empty, %d failed", total_saved, total_empty, total_failed)

    print(f"\nDone: {total_saved} saved, {total_empty} empty/VIP, {total_failed} failed")


if __name__ == "__main__":
    main()
