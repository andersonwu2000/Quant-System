"""DataCatalog — unified data access layer.

All consumers (backtest, paper trading, autoresearch) read data through this.
No in-memory cache — reads from parquet on every call (local-first principle).

Replaces the scattered parquet reading throughout the codebase.
Migration is gradual: each module switches independently.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from src.data.registry import REGISTRY, DatasetDef
from src.data.schemas import pit_filter

logger = logging.getLogger(__name__)

MARKET_DIR = Path("data/market")
FUND_DIR = Path("data/fundamental")


class DataCatalog:
    """Unified data access layer.

    No in-memory cache. Reads parquet from disk on each call.
    PIT filtering applied when pit_date is specified.
    """

    def __init__(self, base_dir: str = "data"):
        self._base = Path(base_dir)

    def _resolve_path(self, dataset: str, symbol: str) -> Path:
        """Get the parquet file path for a symbol+dataset."""
        ds = REGISTRY.get(dataset)
        if ds is None:
            raise KeyError(f"Unknown dataset: {dataset}")
        safe = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
        return ds.storage_dir / f"{safe}_{ds.suffix}.parquet"

    def get(
        self,
        dataset: str,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        pit_date: date | None = None,
    ) -> pd.DataFrame:
        """Get data for a single symbol.

        Args:
            dataset: Dataset name (e.g. "price", "revenue").
            symbol: Stock symbol (e.g. "2330.TW").
            start: Optional start date filter.
            end: Optional end date filter.
            pit_date: If set, only returns data available as of this date (PIT).

        Returns:
            DataFrame (may be empty if file doesn't exist).
        """
        path = self._resolve_path(dataset, symbol)
        if not path.exists():
            return pd.DataFrame()

        try:
            df = pd.read_parquet(path)
        except Exception:
            logger.debug("Failed to read %s", path)
            return pd.DataFrame()

        if df.empty:
            return df

        # Normalize index to DatetimeIndex if possible
        if not isinstance(df.index, pd.DatetimeIndex) and "date" not in df.columns:
            return df

        # Apply date range filter
        if isinstance(df.index, pd.DatetimeIndex):
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            if start:
                df = df[df.index >= pd.Timestamp(start)]
            if end:
                df = df[df.index <= pd.Timestamp(end)]
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            if start:
                df = df[df["date"] >= pd.Timestamp(start)]
            if end:
                df = df[df["date"] <= pd.Timestamp(end)]

        # Apply PIT filter
        if pit_date is not None:
            ds = REGISTRY.get(dataset)
            delay = ds.pit_delay_days if ds else 0
            df = pit_filter(df, pit_date, pit_delay_days=delay)

        return df

    def get_cross_section(
        self,
        dataset: str,
        as_of: date,
        symbols: list[str] | None = None,
        field: str | None = None,
    ) -> pd.DataFrame:
        """Get cross-sectional data for a given date.

        Returns a DataFrame with one row per symbol.
        If field is specified, returns a Series-like DataFrame with that single column.
        """
        if symbols is None:
            symbols = self.available_symbols(dataset)

        rows = []
        for sym in symbols:
            df = self.get(dataset, sym, pit_date=as_of)
            if df.empty:
                continue

            # Get the most recent row as of the date
            if isinstance(df.index, pd.DatetimeIndex):
                mask = df.index <= pd.Timestamp(as_of)
                subset = df[mask]
                if subset.empty:
                    continue
                row = subset.iloc[-1].to_dict()
            elif "date" in df.columns:
                mask = pd.to_datetime(df["date"]) <= pd.Timestamp(as_of)
                subset = df[mask]
                if subset.empty:
                    continue
                row = subset.iloc[-1].to_dict()
            else:
                row = df.iloc[-1].to_dict()

            row["symbol"] = sym
            rows.append(row)

        if not rows:
            return pd.DataFrame()

        result = pd.DataFrame(rows)
        if field and field in result.columns:
            return result[["symbol", field]].set_index("symbol")
        return result.set_index("symbol") if "symbol" in result.columns else result

    def get_panel(
        self,
        dataset: str,
        symbols: list[str],
        start: date,
        end: date,
        field: str = "close",
    ) -> pd.DataFrame:
        """Get panel data (index=date, columns=symbols) for a single field.

        Useful for factor computation across multiple symbols.
        """
        series_dict = {}
        for sym in symbols:
            df = self.get(dataset, sym, start=start, end=end)
            if df.empty:
                continue
            if isinstance(df.index, pd.DatetimeIndex) and field in df.columns:
                series_dict[sym] = df[field]
            elif "date" in df.columns and field in df.columns:
                s = df.set_index("date")[field]
                s.index = pd.to_datetime(s.index)
                series_dict[sym] = s

        if not series_dict:
            return pd.DataFrame()

        return pd.DataFrame(series_dict)

    def available_symbols(self, dataset: str = "price") -> list[str]:
        """List symbols that have data for a given dataset."""
        ds = REGISTRY.get(dataset)
        if ds is None:
            return []
        suffix = f"_{ds.suffix}.parquet"
        if not ds.storage_dir.exists():
            return []
        symbols = []
        for p in sorted(ds.storage_dir.glob(f"*{suffix}")):
            sym = p.stem.replace(f"_{ds.suffix}", "")
            symbols.append(sym)
        return symbols

    def available_datasets(self) -> list[str]:
        """List all registered dataset names."""
        return list(REGISTRY.keys())

    def coverage(self, dataset: str) -> dict:
        """Get coverage stats for a dataset."""
        ds = REGISTRY.get(dataset)
        if ds is None:
            return {"error": f"Unknown dataset: {dataset}"}

        symbols = self.available_symbols(dataset)
        total_universe = len(self.available_symbols("price"))

        return {
            "dataset": dataset,
            "count": len(symbols),
            "universe_total": total_universe,
            "coverage_ratio": len(symbols) / total_universe if total_universe > 0 else 0,
            "min_coverage": ds.min_coverage,
            "meets_threshold": (len(symbols) / total_universe >= ds.min_coverage) if total_universe > 0 else False,
        }


# Module-level convenience instance
_default_catalog: DataCatalog | None = None


def get_catalog() -> DataCatalog:
    """Get the default DataCatalog instance (singleton)."""
    global _default_catalog
    if _default_catalog is None:
        _default_catalog = DataCatalog()
    return _default_catalog
