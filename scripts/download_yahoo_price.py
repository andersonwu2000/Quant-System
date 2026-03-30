"""Download OHLCV price data from Yahoo Finance to data/yahoo/.

No API key needed. Rate limit is generous (~2000 req/hr).

Usage:
    python scripts/download_yahoo_price.py                          # all symbols
    python scripts/download_yahoo_price.py --symbols 2330 2317      # specific
    python scripts/download_yahoo_price.py --max 500                # first N
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

YAHOO_DIR = Path("data/yahoo")
REQUEST_DELAY = 0.3  # Yahoo is generous, but be polite


def download_symbol(symbol: str, start: str, end: str) -> int:
    """Download OHLCV for one symbol. Returns row count or 0 on failure."""
    import yfinance as yf

    tw_sym = f"{symbol}.TW" if not symbol.endswith((".TW", ".TWO")) else symbol
    out_path = YAHOO_DIR / f"{tw_sym}_1d.parquet"

    try:
        df = yf.Ticker(tw_sym).history(start=start, end=end, auto_adjust=True)
        if df is None or df.empty:
            return 0

        # Normalize
        df.columns = [c.lower() for c in df.columns]
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[cols]
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]

        if df.empty:
            return 0

        # Write with metadata
        table = pa.Table.from_pandas(df)
        meta = {
            b"source": b"yahoo",
            b"fetch_time": datetime.now().isoformat().encode(),
            b"row_count": str(len(df)).encode(),
            b"last_date": str(df.index.max().date()).encode(),
        }
        table = table.replace_schema_metadata({**(table.schema.metadata or {}), **meta})
        pq.write_table(table, out_path)
        return len(df)

    except Exception as e:
        logger.debug("%s failed: %s", tw_sym, e)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Yahoo Finance price data")
    parser.add_argument("--symbols", nargs="*", help="Bare symbol list (e.g. 2330 2317)")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--max", type=int, default=0, help="Max symbols to download (0=all)")
    args = parser.parse_args()

    if args.symbols:
        symbols = args.symbols
    else:
        sym_file = Path("data/all_tw_stock_ids.txt")
        if not sym_file.exists():
            logger.error("data/all_tw_stock_ids.txt not found")
            return
        symbols = [s.strip() for s in sym_file.read_text().splitlines() if s.strip()]

    if args.max > 0:
        symbols = symbols[:args.max]

    YAHOO_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(symbols)} symbols from Yahoo Finance")
    print(f"Period: {args.start} ~ {args.end}")
    print(f"Output: {YAHOO_DIR}/")

    success = 0
    failed = 0
    for i, sym in enumerate(symbols):
        time.sleep(REQUEST_DELAY)
        rows = download_symbol(sym, args.start, args.end)
        if rows > 0:
            success += 1
            if (i + 1) % 50 == 0:
                logger.info("[%d/%d] %d success, %d failed", i + 1, len(symbols), success, failed)
        else:
            failed += 1

    print(f"\nDone: {success} success, {failed} failed / {len(symbols)} total")


if __name__ == "__main__":
    main()
