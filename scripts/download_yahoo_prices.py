"""批量下載台股價格數據到 data/market/ — 使用 Yahoo Finance。

用法:
    python -m scripts.download_yahoo_prices --file data/new_tw_stock_ids.txt
    python -m scripts.download_yahoo_prices --symbols 2330 2317
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MARKET_DIR = Path("data/market")


def download_symbol(symbol: str, start: str, end: str) -> int:
    """Download one symbol. Returns number of rows or 0 on failure."""
    tw_sym = f"{symbol}.TW"
    out_path = MARKET_DIR / f"{tw_sym}_1d.parquet"

    if out_path.exists():
        try:
            existing = pd.read_parquet(out_path)
            if not existing.empty and len(existing) > 100:
                return -1  # skip
        except Exception:
            pass

    try:
        ticker = yf.Ticker(tw_sym)
        df = ticker.history(start=start, end=end, auto_adjust=True)

        if df is None or df.empty:
            # Try .TWO (OTC)
            two_sym = f"{symbol}.TWO"
            ticker = yf.Ticker(two_sym)
            df = ticker.history(start=start, end=end, auto_adjust=True)
            if df is None or df.empty:
                return 0
            tw_sym = two_sym
            out_path = MARKET_DIR / f"{two_sym}_1d.parquet"

        # Normalize columns
        df.columns = [c.lower() for c in df.columns]
        if "adj close" in df.columns:
            df = df.drop(columns=["adj close"])

        # Strip timezone
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Filter required columns
        cols = ["open", "high", "low", "close", "volume"]
        available = [c for c in cols if c in df.columns]
        df = df[available]

        if len(df) < 50:
            return 0

        df.to_parquet(out_path)
        return len(df)

    except Exception as e:
        logger.debug("Failed %s: %s", symbol, e)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Yahoo Finance 台股批量下載")
    parser.add_argument("--file", help="股票代碼清單檔案（每行一個）")
    parser.add_argument("--symbols", nargs="*", help="股票代碼列表")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--batch-size", type=int, default=50, help="每批數量")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            symbols = [line.strip() for line in f if line.strip()]
    elif args.symbols:
        symbols = args.symbols
    else:
        print("Please specify --file or --symbols")
        sys.exit(1)

    MARKET_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading {len(symbols)} symbols: {args.start} ~ {args.end}")
    print(f"Output: {MARKET_DIR}/")

    success = 0
    skipped = 0
    failed = 0

    for i, sym in enumerate(symbols):
        result = download_symbol(sym, args.start, args.end)
        if result == -1:
            skipped += 1
        elif result > 0:
            success += 1
            if success % 20 == 0:
                print(f"  [{i+1}/{len(symbols)}] {success} downloaded, {skipped} skipped, {failed} failed")
        else:
            failed += 1

        # Gentle delay every batch to avoid rate limiting
        if (i + 1) % args.batch_size == 0:
            time.sleep(1)

    print(f"\nDone: {success} downloaded, {skipped} skipped, {failed} failed")
    print(f"Total files in {MARKET_DIR}: {len(list(MARKET_DIR.glob('*.parquet')))}")


if __name__ == "__main__":
    main()
