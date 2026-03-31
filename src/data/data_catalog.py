"""DataCatalog — unified data access layer.

All consumers (backtest, paper trading, autoresearch) read data through this.
No in-memory cache — reads from parquet on every call (local-first principle).

Data is stored by source (data/yahoo/, data/finmind/, data/twse/).
DataCatalog searches source directories in priority order defined by Registry.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from src.data.registry import REGISTRY, FINLAB_DIR, parquet_path as _registry_parquet_path
from src.data.schemas import pit_filter
from src.data.sources.finmind_common import strip_tw_suffix

logger = logging.getLogger(__name__)


class DataCatalog:
    """Unified data access layer.

    No in-memory cache. Reads parquet from disk on each call.
    Searches source directories in priority order (e.g. twse → yahoo → finmind).
    PIT filtering applied when pit_date is specified.
    """

    def __init__(self, base_dir: str = "data"):
        self._base = Path(base_dir)

    def _resolve_path(self, dataset: str, symbol: str) -> Path:
        """Get the parquet file path for a symbol+dataset.

        Searches source_dirs in priority order, returns first existing file.
        Falls back to primary source dir if nothing found.
        """
        return _registry_parquet_path(symbol, dataset)

    def _apply_adj_close(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Replace 'close' column with dividend-adjusted close from FinLab.

        Strategy:
        - Read adj_close panel from finlab for the symbol
        - For dates where adj_close exists, replace close (and scale OHLV proportionally)
        - For dates where adj_close is missing (e.g. post-2018), keep raw close
        - This avoids artificial drops on ex-dividend dates in backtest
        """
        adj_panel_path = FINLAB_DIR / "price" / "adj_close.parquet"
        if not adj_panel_path.exists():
            return df  # no adj data available, return as-is

        bare = strip_tw_suffix(symbol)
        try:
            adj_panel = self._get_panel_cached(str(adj_panel_path))
            if bare not in adj_panel.columns:
                return df  # no adj data for this symbol

            adj_series = adj_panel[bare].dropna()
            if adj_series.empty:
                return df

            # Align indices
            if not isinstance(df.index, pd.DatetimeIndex):
                return df

            common = df.index.intersection(adj_series.index)
            if len(common) == 0:
                return df  # no overlap (e.g. all data is post-2018)

            # Calculate adjustment ratio: adj_close / raw_close
            raw_close = df.loc[common, "close"]
            adj_close = adj_series[common]
            # Avoid division by zero
            mask = raw_close > 0
            ratio = pd.Series(1.0, index=common)
            ratio[mask] = adj_close[mask] / raw_close[mask]

            # Forward-fill: apply last known ratio to dates beyond adj coverage.
            # Without this, there's a fake price jump at the adj/raw boundary.
            post_adj = df.index[df.index > common.max()] if len(common) > 0 else pd.Index([])
            last_ratio = float(ratio.iloc[-1]) if len(ratio) > 0 else 1.0

            # Apply ratio to OHLC (volume stays unchanged)
            df = df.copy()
            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df.loc[common, col] = df.loc[common, col] * ratio
                    if len(post_adj) > 0 and abs(last_ratio - 1.0) > 0.001:
                        df.loc[post_adj, col] = df.loc[post_adj, col] * last_ratio

            n_ffill = len(post_adj) if abs(last_ratio - 1.0) > 0.001 else 0
            logger.debug("Applied adj_close for %s: %d/%d dates adjusted, %d forward-filled (ratio=%.4f)",
                        symbol, len(common), len(df), n_ffill, last_ratio)

        except Exception:
            logger.debug("Failed to apply adj_close for %s", symbol, exc_info=True)

        return df

    # Cache for FinLab panel reads — one file contains ALL symbols,
    # so reading it once and reusing is a huge win (12MB × 2000 lookups → 1 read).
    # This is NOT per-symbol caching (which we avoid) — it's per-panel-file caching.
    _panel_cache: dict[str, pd.DataFrame] = {}

    def _get_panel_cached(self, path: str) -> pd.DataFrame:
        if path not in self._panel_cache:
            self._panel_cache[path] = pd.read_parquet(path)
        return self._panel_cache[path]

    def _read_finlab_panel(self, dataset: str, symbol: str) -> pd.DataFrame | None:
        """Read a single symbol from a FinLab panel parquet (fallback).

        FinLab stores data as panel: index=date, columns=all_symbols.
        Panel files are cached in memory (one read per file, not per symbol).
        """
        ds = REGISTRY.get(dataset)
        if ds is None or not ds.finlab_panel:
            return None

        panel_path = FINLAB_DIR / ds.finlab_panel
        if not panel_path.exists():
            return None

        # Symbol in FinLab uses bare id (e.g. "2330" not "2330.TW")
        bare = strip_tw_suffix(symbol)

        try:
            panel = self._get_panel_cached(str(panel_path))
            if bare not in panel.columns:
                return None
            series = panel[bare].dropna()
            if series.empty:
                return None

            col_name = panel_path.stem  # "close", "revenue", "per", etc.

            # Match output format to what per-symbol parquets provide,
            # so downstream code (evaluate.py, factors) works unchanged.
            if dataset == "revenue":
                # Per-symbol revenue has columns: [date, revenue, yoy_growth, ...]
                # FinLab panel only has raw revenue — compute YoY growth
                df = pd.DataFrame({"date": series.index, "revenue": series.values})
                df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
                df = df.sort_values("date")
                # YoY: compare to same month last year (shift 12 months)
                df["yoy_growth"] = df["revenue"].pct_change(periods=12) * 100
                # Clip extreme values (financial stocks can have near-zero base → inf)
                df["yoy_growth"] = df["yoy_growth"].clip(-500, 5000)
                df["yoy_growth"] = df["yoy_growth"].replace([float("inf"), float("-inf")], float("nan"))
                return df
            elif dataset == "per":
                # Per-symbol per has columns: [date, PER, PBR, dividend_yield]
                df = pd.DataFrame({"date": series.index, "PER": series.values})
                # Also try to add PBR from valuation/pbr.parquet
                pbr_path = FINLAB_DIR / "valuation" / "pbr.parquet"
                if pbr_path.exists():
                    try:
                        pbr_panel = self._get_panel_cached(str(pbr_path))
                        if bare in pbr_panel.columns:
                            pbr_series = pbr_panel[bare].dropna()
                            pbr_df = pd.DataFrame({"date": pbr_series.index, "PBR": pbr_series.values})
                            df = df.merge(pbr_df, on="date", how="left")
                    except Exception:
                        pass
                return df
            elif dataset == "margin":
                df = pd.DataFrame({"date": series.index, "margin_usage": series.values})
                return df
            elif dataset == "price":
                # Price: build full OHLCV from separate panel files
                df = series.to_frame(name="close")
                for extra_col, extra_file in [("open", "open.parquet"), ("high", "high.parquet"),
                                               ("low", "low.parquet"), ("volume", "volume.parquet")]:
                    extra_path = FINLAB_DIR / "price" / extra_file
                    if extra_path.exists():
                        try:
                            extra_panel = self._get_panel_cached(str(extra_path))
                            if bare in extra_panel.columns:
                                df[extra_col] = extra_panel[bare]
                        except Exception:
                            pass
                df.index.name = None
                return df
            else:
                # Generic: include date column for compatibility
                df = pd.DataFrame({"date": series.index, col_name: series.values})
                return df
        except Exception:
            logger.debug("Failed to read finlab panel %s for %s", panel_path, symbol)
            return None

    def _read_finlab_panel_full(self, dataset: str) -> pd.DataFrame:
        """Read the full FinLab panel for a dataset. Returns panel DataFrame."""
        ds = REGISTRY.get(dataset)
        if ds is None or not ds.finlab_panel:
            return pd.DataFrame()
        panel_path = FINLAB_DIR / ds.finlab_panel
        if not panel_path.exists():
            return pd.DataFrame()
        try:
            return self._get_panel_cached(str(panel_path))
        except Exception:
            return pd.DataFrame()

    def get(
        self,
        dataset: str,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
        pit_date: date | None = None,
        adjusted: bool = False,
    ) -> pd.DataFrame:
        """Get data for a single symbol.

        Args:
            dataset: Dataset name (e.g. "price", "revenue").
            symbol: Stock symbol (e.g. "2330.TW").
            start: Optional start date filter.
            end: Optional end date filter.
            pit_date: If set, only returns data available as of this date (PIT).
            adjusted: If True and dataset="price", replace close with
                      dividend-adjusted close from FinLab. Falls back to raw
                      close when adj_close is unavailable for a date range.

        Returns:
            DataFrame (may be empty if file doesn't exist).
        """
        path = self._resolve_path(dataset, symbol)
        if not path.exists():
            # Fallback: try FinLab panel
            df = self._read_finlab_panel(dataset, symbol)
            if df is None or df.empty:
                return pd.DataFrame()
        else:
            try:
                df = pd.read_parquet(path)
            except Exception:
                logger.debug("Failed to read %s", path)
                return pd.DataFrame()

            # Merge FinLab historical panel to extend date range
            # (e.g. FinMind revenue 2019+ merged with FinLab 2005-2018)
            ds = REGISTRY.get(dataset)
            if ds and ds.finlab_panel and dataset != "price":
                finlab_df = self._read_finlab_panel(dataset, symbol)
                if finlab_df is not None and not finlab_df.empty:
                    if "date" in df.columns and "date" in finlab_df.columns:
                        combined = pd.concat([finlab_df, df], ignore_index=True)
                        combined["date"] = pd.to_datetime(combined["date"])
                        combined = combined.drop_duplicates(subset=["date"], keep="last")
                        df = combined.sort_values("date").reset_index(drop=True)

        if df.empty:
            return df

        # If no date info available, return as-is (no date filtering possible)
        if not isinstance(df.index, pd.DatetimeIndex) and "date" not in df.columns:
            if start or end or pit_date:
                logger.warning("Cannot apply date/PIT filter to %s/%s: no date column or DatetimeIndex", dataset, symbol)
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

        # Replace close with adj_close when requested
        if adjusted and dataset == "price" and "close" in df.columns:
            df = self._apply_adj_close(df, symbol)

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
        Prefers FinLab panel data when available (single read vs N reads).
        """
        # Fast path: if FinLab panel exists, read it directly
        ds = REGISTRY.get(dataset)
        if ds and ds.finlab_panel:
            panel = self._read_finlab_panel_full(dataset)
            if not panel.empty:
                # Filter date range
                panel = panel[(panel.index >= pd.Timestamp(start)) & (panel.index <= pd.Timestamp(end))]
                # Map symbols to bare ids
                bare_map = {}
                for sym in symbols:
                    bare = sym.replace(".TW", "").replace(".TWO", "")
                    if bare in panel.columns:
                        bare_map[sym] = bare
                if bare_map:
                    result = panel[list(bare_map.values())]
                    result.columns = [sym for sym, bare in bare_map.items()]
                    # Also try per-symbol sources for symbols not in finlab
                    missing = [s for s in symbols if s not in bare_map]
                    if missing:
                        for sym in missing:
                            df = self.get(dataset, sym, start=start, end=end)
                            if not df.empty and field in df.columns:
                                if isinstance(df.index, pd.DatetimeIndex):
                                    result[sym] = df[field]
                    return result

        # Fallback: per-symbol reads
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
        """List symbols that have data for a given dataset (across all sources + finlab)."""
        ds = REGISTRY.get(dataset)
        if ds is None:
            return []
        suffix = f"_{ds.suffix}.parquet"
        seen: set[str] = set()
        # Per-symbol sources
        for source_dir in ds.source_dirs:
            if not source_dir.exists():
                continue
            for p in source_dir.glob(f"*{suffix}"):
                sym = p.stem.replace(f"_{ds.suffix}", "")
                seen.add(sym)
        # FinLab panel (bare symbols → add .TW suffix)
        if ds.finlab_panel:
            panel = self._read_finlab_panel_full(dataset)
            if not panel.empty:
                for col in panel.columns:
                    sym = f"{col}.TW" if not col.endswith((".TW", ".TWO")) else col
                    seen.add(sym)
        return sorted(seen)

    def available_datasets(self) -> list[str]:
        """List all registered dataset names."""
        return list(REGISTRY.keys())

    def coverage(self, dataset: str) -> dict:
        """Get coverage stats for a dataset (across all sources)."""
        ds = REGISTRY.get(dataset)
        if ds is None:
            return {"error": f"Unknown dataset: {dataset}"}

        symbols = self.available_symbols(dataset)
        total_universe = len(self.available_symbols("price"))

        # Per-source breakdown
        per_source: dict[str, int] = {}
        suffix = f"_{ds.suffix}.parquet"
        for source_dir in ds.source_dirs:
            if source_dir.exists():
                count = len(list(source_dir.glob(f"*{suffix}")))
                source_name = source_dir.name  # "yahoo", "finmind", "twse"
                per_source[source_name] = count

        return {
            "dataset": dataset,
            "count": len(symbols),
            "universe_total": total_universe,
            "coverage_ratio": len(symbols) / total_universe if total_universe > 0 else 0,
            "min_coverage": ds.min_coverage,
            "meets_threshold": (len(symbols) / total_universe >= ds.min_coverage) if total_universe > 0 else False,
            "per_source": per_source,
        }


# Module-level convenience instance
_default_catalog: DataCatalog | None = None


def get_catalog() -> DataCatalog:
    """Get the default DataCatalog instance (singleton)."""
    global _default_catalog
    if _default_catalog is None:
        _default_catalog = DataCatalog()
    return _default_catalog
