"""Download FinLab data to data/finlab/ — survivorship-bias-free historical data.

Free tier: 500MB/month, data up to 2018-12-28, includes delisted stocks.
Panel format: index=date, columns=all stocks (including delisted).

Usage:
    python scripts/download_finlab_data.py              # download all available
    python scripts/download_finlab_data.py --dataset price  # specific dataset
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FINLAB_DIR = Path("data/finlab")

# FinLab dataset keys → our naming
DATASETS = {
    "price": {
        "keys": {
            "price:收盤價": "close",
            "price:開盤價": "open",
            "price:最高價": "high",
            "price:最低價": "low",
            "price:成交股數": "volume",
        },
        "desc": "OHLCV (panel format, includes delisted stocks)",
    },
    "revenue": {
        "keys": {
            "monthly_revenue:當月營收": "revenue",
            "monthly_revenue:去年同月增減(%)": "yoy",
        },
        "desc": "Monthly revenue + YoY growth",
    },
    "valuation": {
        "keys": {
            "price_earning_ratio:本益比": "per",
            "price_earning_ratio:股價淨值比": "pbr",
        },
        "desc": "PER/PBR daily",
    },
    "fundamental": {
        "keys": {
            "fundamental_features:股東權益報酬率": "roe",
        },
        "desc": "ROE and other fundamental features",
    },
    "institutional": {
        "keys": {
            "institutional_investors_trading_summary:投信買賣超股數": "trust_net",
        },
        "desc": "Institutional investor trading",
    },
    "margin": {
        "keys": {
            "margin_transactions:融資使用率": "margin_usage",
        },
        "desc": "Margin transactions",
    },
    "foreign": {
        "keys": {
            "etl:外資持股比例": "foreign_pct",
        },
        "desc": "Foreign ownership ratio",
    },
}


def download_dataset(name: str, keys: dict[str, str]) -> int:
    """Download a dataset group. Returns number of files saved."""
    from finlab import data

    out_dir = FINLAB_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = 0

    for finlab_key, col_name in keys.items():
        logger.info("Fetching %s ...", finlab_key)
        try:
            df = data.get(finlab_key)
            if df is None or df.empty:
                logger.warning("  %s: empty", finlab_key)
                continue

            # Save as panel parquet (index=date, columns=symbols)
            out_path = out_dir / f"{col_name}.parquet"
            table = pa.Table.from_pandas(df)
            meta = {
                b"source": b"finlab",
                b"finlab_key": finlab_key.encode(),
                b"fetch_time": datetime.now().isoformat().encode(),
                b"date_range": f"{df.index.min().date()}~{df.index.max().date()}".encode(),
                b"n_symbols": str(len(df.columns)).encode(),
                b"n_rows": str(len(df)).encode(),
            }
            table = table.replace_schema_metadata({**(table.schema.metadata or {}), **meta})
            pq.write_table(table, out_path)
            logger.info("  %s: %s, %d dates × %d symbols → %s",
                         col_name, f"{df.index.min().date()}~{df.index.max().date()}",
                         len(df), len(df.columns), out_path)
            saved += 1

        except Exception as e:
            logger.error("  %s: FAILED — %s", finlab_key, e)

    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Download FinLab data")
    parser.add_argument("--dataset", choices=list(DATASETS.keys()) + ["all"], default="all")
    args = parser.parse_args()

    FINLAB_DIR.mkdir(parents=True, exist_ok=True)

    if args.dataset == "all":
        targets = list(DATASETS.items())
    else:
        targets = [(args.dataset, DATASETS[args.dataset])]

    total = 0
    for name, ds in targets:
        logger.info("=== %s: %s ===", name, ds["desc"])
        n = download_dataset(name, ds["keys"])
        total += n

    # Also extract symbol list (including delisted) for SecuritiesMaster
    try:
        from finlab import data
        close = data.get("price:收盤價")
        symbols = sorted(close.columns.tolist())
        sym_path = FINLAB_DIR / "all_symbols.txt"
        sym_path.write_text("\n".join(symbols) + "\n", encoding="utf-8")
        logger.info("Saved %d symbols (incl. delisted) to %s", len(symbols), sym_path)
    except Exception as e:
        logger.warning("Failed to save symbol list: %s", e)

    print(f"\nDone: {total} files saved to {FINLAB_DIR}/")


if __name__ == "__main__":
    main()
