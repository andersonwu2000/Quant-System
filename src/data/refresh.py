"""Incremental data refresh engine — atomic writes, multi-provider fallback.

Replaces _async_price_update() and _async_revenue_update() in scheduler/jobs.py.
Supports all dataset types with a unified interface.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

# ── Dataset definitions ──────────────────────────────────────────────

MARKET_DIR = Path("data/market")
FUND_DIR = Path("data/fundamental")

DatasetName = Literal[
    "price", "revenue", "per", "institutional", "margin",
    "shareholding", "day_trading", "dividend",
    "cash_flows", "balance_sheet", "securities_lending",
    "financial_statement",
]

# Maps dataset name → (parquet suffix, output dir, provider method, frequency)
DATASET_META: dict[str, dict] = {
    "price": {
        "suffix": "1d",
        "dir": MARKET_DIR,
        "finmind_method": "taiwan_stock_daily",
        "yahoo": True,
        "freq": "daily",
    },
    "revenue": {
        "suffix": "revenue",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_month_revenue",
        "freq": "monthly",
    },
    "per": {
        "suffix": "per",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_per_pbr",
        "freq": "daily",
    },
    "institutional": {
        "suffix": "institutional",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_institutional_investors",
        "freq": "daily",
    },
    "margin": {
        "suffix": "margin",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_margin_purchase_short_sale",
        "freq": "daily",
    },
    "shareholding": {
        "suffix": "shareholding",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_shareholding",
        "freq": "weekly",
    },
    "day_trading": {
        "suffix": "daytrading",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_day_trading",
        "freq": "daily",
    },
    "dividend": {
        "suffix": "dividend",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_dividend",
        "freq": "event",
    },
    "cash_flows": {
        "suffix": "cash_flows",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_cash_flows_statement",
        "freq": "quarterly",
    },
    "balance_sheet": {
        "suffix": "balance_sheet",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_balance_sheet",
        "freq": "quarterly",
    },
    "securities_lending": {
        "suffix": "securities_lending",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_securities_lending",
        "freq": "daily",
    },
    "financial_statement": {
        "suffix": "financial_statement",
        "dir": FUND_DIR,
        "finmind_method": "taiwan_stock_financial_statement",
        "freq": "quarterly",
    },
}


@dataclass
class RefreshReport:
    """Result of a single dataset refresh operation."""
    dataset: str
    total_symbols: int = 0
    updated: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    new_rows: int = 0
    duration_seconds: float = 0.0
    provider_used: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.failed.__len__() < self.total_symbols * 0.5

    def summary(self) -> str:
        parts = [f"[{self.dataset}]"]
        if self.error:
            parts.append(f"ERROR: {self.error}")
        else:
            parts.append(
                f"{self.updated} updated, {self.skipped} skipped, "
                f"{len(self.failed)} failed / {self.total_symbols} total"
            )
            if self.new_rows:
                parts.append(f"(+{self.new_rows} rows)")
            parts.append(f"in {self.duration_seconds:.1f}s via {self.provider_used}")
        return " ".join(parts)


# ── Staleness helpers ────────────────────────────────────────────────

def _max_acceptable_age(freq: str) -> int:
    """Max days behind before a symbol is considered stale."""
    return {"daily": 3, "weekly": 10, "monthly": 45, "quarterly": 120, "event": 365}.get(freq, 5)


def _parquet_path(symbol: str, dataset: str) -> Path:
    meta = DATASET_META[dataset]
    safe_sym = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
    return meta["dir"] / f"{safe_sym}_{meta['suffix']}.parquet"


def _read_existing(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
        if df.empty:
            return None
        return df
    except Exception:
        logger.debug("Corrupt parquet: %s", path)
        return None


def _last_date(df: pd.DataFrame) -> date | None:
    """Get the last date from a DataFrame (handles both index and 'date' column)."""
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index) > 0:
        ts = df.index.max()
        return ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()
    if "date" in df.columns and len(df) > 0:
        ts = pd.Timestamp(df["date"].max())
        return ts.date()
    return None


def _atomic_write(
    df: pd.DataFrame, target: Path,
    source: str = "", dataset: str = "",
) -> None:
    """Write parquet atomically with lineage metadata.

    Writes to .tmp then renames. Embeds source/fetch_time in parquet metadata.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp.parquet")
    try:
        table = pa.Table.from_pandas(df)
        # Embed lineage metadata
        custom_meta = {
            b"source": source.encode() if source else b"unknown",
            b"dataset": dataset.encode() if dataset else b"",
            b"fetch_time": datetime.now().isoformat().encode(),
            b"row_count": str(len(df)).encode(),
        }
        last = _last_date(df)
        if last:
            custom_meta[b"last_date"] = last.isoformat().encode()
        merged = {**(table.schema.metadata or {}), **custom_meta}
        table = table.replace_schema_metadata(merged)
        pq.write_table(table, tmp)
        tmp.rename(target)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize OHLCV DataFrame: lowercase cols, tz-naive index, positive prices."""
    df.columns = [c.lower() for c in df.columns]
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[cols]
    # Remove rows with non-positive prices
    price_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]
    if price_cols:
        df = df[(df[price_cols] > 0).all(axis=1)]
    return df


# ── Provider functions ───────────────────────────────────────────────

def _fetch_yahoo(symbol: str, start: str, end: str) -> pd.DataFrame | None:
    """Fetch OHLCV from Yahoo Finance (price dataset only)."""
    try:
        import yfinance as yf
        df = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=True)
        if df is None or df.empty:
            return None
        return _normalize_ohlcv(df)
    except Exception as e:
        logger.debug("Yahoo fetch failed for %s: %s", symbol, e)
        return None


def _fetch_finmind(bare_symbol: str, method_name: str, start: str, end: str) -> pd.DataFrame | None:
    """Fetch data from FinMind API."""
    try:
        from src.core.config import get_config
        from src.data.sources.finmind_common import get_dataloader

        config = get_config()
        if not config.finmind_token:
            return None
        dl = get_dataloader(config.finmind_token)
        method = getattr(dl, method_name, None)
        if method is None:
            return None
        df = method(bare_symbol, start_date=start, end_date=end)
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            return None
        return df
    except Exception as e:
        logger.debug("FinMind fetch failed for %s/%s: %s", bare_symbol, method_name, e)
        return None


# ── Core refresh logic ───────────────────────────────────────────────

def _refresh_symbol_price(symbol: str, existing: pd.DataFrame | None, today: str) -> tuple[int, str]:
    """Refresh a single symbol's price data. Returns (new_rows, provider_used)."""
    from src.data.sources.finmind_common import strip_tw_suffix

    if existing is not None:
        last = _last_date(existing)
        if last and (date.fromisoformat(today) - last).days <= 1:
            return 0, ""  # up to date

        start = (last + timedelta(days=1)).isoformat() if last else "2015-01-01"
    else:
        start = "2015-01-01"

    # Try Yahoo first (faster, no rate limit concern)
    new_df = _fetch_yahoo(symbol, start, today)
    provider = "yahoo"

    # Fallback to FinMind
    if new_df is None or new_df.empty:
        bare = strip_tw_suffix(symbol)
        raw = _fetch_finmind(bare, "taiwan_stock_daily", start, today)
        if raw is not None and not raw.empty:
            # FinMind returns different format — normalize
            if "date" in raw.columns:
                raw["date"] = pd.to_datetime(raw["date"])
                raw = raw.set_index("date")
            col_map = {"Trading_Volume": "volume", "max": "high", "min": "low"}
            raw = raw.rename(columns=col_map)
            new_df = _normalize_ohlcv(raw)
            provider = "finmind"

    if new_df is None or new_df.empty:
        return 0, ""

    # Merge with existing
    if existing is not None and not existing.empty:
        combined = pd.concat([existing, new_df])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined = combined.sort_index()
    else:
        combined = new_df.sort_index()

    path = _parquet_path(symbol, "price")
    _atomic_write(combined, path, source=provider, dataset="price")
    return len(new_df), provider


def _refresh_symbol_fundamental(
    symbol: str, dataset: str, existing: pd.DataFrame | None, today: str,
) -> tuple[int, str]:
    """Refresh a single symbol's fundamental data. Returns (new_rows, provider_used)."""
    from src.data.sources.finmind_common import strip_tw_suffix

    meta = DATASET_META[dataset]
    max_age = _max_acceptable_age(meta["freq"])

    if existing is not None:
        last = _last_date(existing)
        if last and (date.fromisoformat(today) - last).days <= max_age:
            return 0, ""  # fresh enough

        start = (last - timedelta(days=30)).isoformat() if last else "2015-01-01"
    else:
        start = "2015-01-01"

    bare = strip_tw_suffix(symbol)
    raw = _fetch_finmind(bare, meta["finmind_method"], start, today)
    if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
        return 0, ""

    # Merge
    if existing is not None and not existing.empty:
        # Use 'date' column for dedup if present, otherwise index
        if "date" in raw.columns and "date" in existing.columns:
            combined = pd.concat([existing, raw], ignore_index=True)
            combined["date"] = pd.to_datetime(combined["date"])
            combined = combined.drop_duplicates(subset=["date"], keep="last")
            combined = combined.sort_values("date").reset_index(drop=True)
        else:
            combined = pd.concat([existing, raw])
            if isinstance(combined.index, pd.DatetimeIndex):
                combined = combined[~combined.index.duplicated(keep="last")]
                combined = combined.sort_index()
            else:
                combined = combined.drop_duplicates(keep="last").reset_index(drop=True)
    else:
        combined = raw

    path = _parquet_path(symbol, dataset)
    _atomic_write(combined, path, source="finmind", dataset=dataset)
    return len(raw), "finmind"


def refresh_dataset_sync(
    dataset: str,
    symbols: list[str] | None = None,
    force: bool = False,
) -> RefreshReport:
    """Synchronously refresh a single dataset for given symbols.

    If symbols is None, discovers from existing parquet files in data/market/.
    """
    if dataset not in DATASET_META:
        return RefreshReport(dataset=dataset, error=f"Unknown dataset: {dataset}")

    meta = DATASET_META[dataset]
    start_time = time.monotonic()
    today = datetime.now().strftime("%Y-%m-%d")

    # Discover symbols if not provided
    if symbols is None:
        symbols = _discover_symbols()
    if not symbols:
        return RefreshReport(dataset=dataset, error="No symbols to refresh")

    meta["dir"].mkdir(parents=True, exist_ok=True)
    report = RefreshReport(dataset=dataset, total_symbols=len(symbols))
    provider_counts: dict[str, int] = {}

    for sym in symbols:
        try:
            path = _parquet_path(sym, dataset)
            existing = None if force else _read_existing(path)

            if dataset == "price":
                new_rows, provider = _refresh_symbol_price(sym, existing, today)
            else:
                new_rows, provider = _refresh_symbol_fundamental(sym, existing, today)

            if new_rows > 0:
                report.updated += 1
                report.new_rows += new_rows
                if provider:
                    provider_counts[provider] = provider_counts.get(provider, 0) + 1
            else:
                report.skipped += 1

        except Exception as e:
            report.failed.append(f"{sym}: {e}")
            logger.debug("Refresh %s/%s failed: %s", dataset, sym, e)

    report.duration_seconds = time.monotonic() - start_time
    # Report the most-used provider
    if provider_counts:
        report.provider_used = max(provider_counts, key=provider_counts.get)  # type: ignore[arg-type]
    else:
        report.provider_used = "cache"

    logger.info("Refresh: %s", report.summary())
    return report


def _discover_symbols() -> list[str]:
    """Discover symbols from existing parquet files in data/market/."""
    if not MARKET_DIR.exists():
        return []
    symbols = []
    for p in sorted(MARKET_DIR.glob("*_1d.parquet")):
        sym = p.stem.replace("_1d", "")
        symbols.append(sym)
    return symbols


# ── Async wrapper ────────────────────────────────────────────────────

async def refresh_dataset(
    dataset: str,
    symbols: list[str] | None = None,
    force: bool = False,
) -> RefreshReport:
    """Async wrapper for refresh_dataset_sync (runs in thread pool)."""
    return await asyncio.to_thread(refresh_dataset_sync, dataset, symbols, force)


async def refresh_all_trading_data(
    symbols: list[str] | None = None,
    datasets: list[str] | None = None,
) -> list[RefreshReport]:
    """Refresh multiple datasets sequentially.

    Default: price only. Pass datasets=["price", "revenue", ...] for more.
    """
    if datasets is None:
        datasets = ["price"]

    reports = []
    for ds in datasets:
        report = await refresh_dataset(ds, symbols)
        reports.append(report)
    return reports
