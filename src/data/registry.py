"""Data Registry — metadata definitions for all dataset types.

Central registry of what data exists, where it lives, how often it refreshes,
and what PIT delay to apply. Used by refresh engine, quality gate, and CLI.

Storage is organized by source:
  data/yahoo/     — Yahoo Finance (per-symbol parquet)
  data/finmind/   — FinMind API (per-symbol parquet)
  data/twse/      — TWSE/TPEX OpenAPI (per-symbol parquet)
  data/finlab/    — FinLab (panel parquet: index=date, columns=all symbols)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# ── Source directories ───────────────────────────────────────────────

YAHOO_DIR = Path("data/yahoo")
FINMIND_DIR = Path("data/finmind")
TWSE_DIR = Path("data/twse")
FINLAB_DIR = Path("data/finlab")

# ── Dataset definition ───────────────────────────────────────────────

@dataclass(frozen=True)
class DatasetDef:
    """Metadata for a single dataset type."""
    name: str                       # "price", "revenue", "institutional", ...
    suffix: str                     # parquet filename suffix
    source_dirs: tuple[Path, ...]   # per-symbol sources to search, in priority order
    frequency: str                  # "daily", "weekly", "monthly", "quarterly", "event"
    finmind_method: str             # FinMind DataLoader method name
    pit_delay_days: int = 0         # PIT delay for look-ahead bias prevention
    min_coverage: float = 0.0       # min fraction of universe that should have this data
    refresh_cron: str = ""          # cron expression for auto-refresh
    description: str = ""
    yahoo_available: bool = False   # whether Yahoo Finance can provide this data
    finlab_panel: str = ""          # path to FinLab panel parquet (e.g. "price/close.parquet")


# ── Registry ─────────────────────────────────────────────────────────

REGISTRY: dict[str, DatasetDef] = {
    "price": DatasetDef(
        name="price",
        suffix="1d",
        source_dirs=(YAHOO_DIR, FINMIND_DIR, TWSE_DIR),  # Yahoo first (full history), TWSE last (daily snapshot only)
        frequency="daily",
        finmind_method="taiwan_stock_daily",
        pit_delay_days=0,
        min_coverage=0.90,
        refresh_cron="0 8 * * 1-5",
        description="Daily OHLCV",
        yahoo_available=True,
        finlab_panel="price/close.parquet",
    ),
    "revenue": DatasetDef(
        name="revenue",
        suffix="revenue",
        source_dirs=(FINMIND_DIR,),
        frequency="monthly",
        finmind_method="taiwan_stock_month_revenue",
        pit_delay_days=40,
        min_coverage=0.70,
        refresh_cron="0 8 11 * *",
        description="Monthly revenue",
        finlab_panel="revenue/revenue.parquet",
    ),
    "financial_statement": DatasetDef(
        name="financial_statement",
        suffix="financial_statement",
        source_dirs=(FINMIND_DIR,),
        frequency="quarterly",
        finmind_method="taiwan_stock_financial_statement",
        pit_delay_days=90,
        min_coverage=0.40,
        refresh_cron="0 8 16 5,8,11 *",
        description="Income statement (EPS, ROE, revenue, etc.)",
    ),
    "cash_flows": DatasetDef(
        name="cash_flows",
        suffix="cash_flows",
        source_dirs=(FINMIND_DIR,),
        frequency="quarterly",
        finmind_method="taiwan_stock_cash_flows_statement",
        pit_delay_days=90,
        min_coverage=0.30,
        refresh_cron="0 8 16 5,8,11 *",
        description="Cash flow statement",
    ),
    "balance_sheet": DatasetDef(
        name="balance_sheet",
        suffix="balance_sheet",
        source_dirs=(FINMIND_DIR,),
        frequency="quarterly",
        finmind_method="taiwan_stock_balance_sheet",
        pit_delay_days=90,
        min_coverage=0.30,
        refresh_cron="0 8 16 5,8,11 *",
        description="Balance sheet",
    ),
    "per": DatasetDef(
        name="per",
        suffix="per",
        source_dirs=(FINMIND_DIR,),
        frequency="daily",
        finmind_method="taiwan_stock_per_pbr",
        pit_delay_days=0,
        min_coverage=0.50,
        refresh_cron="0 8 * * 1-5",
        description="Daily PE/PB/dividend yield",
        finlab_panel="valuation/per.parquet",
    ),
    "institutional": DatasetDef(
        name="institutional",
        suffix="institutional",
        source_dirs=(TWSE_DIR, FINMIND_DIR),
        frequency="daily",
        finmind_method="taiwan_stock_institutional_investors",
        pit_delay_days=0,
        min_coverage=0.80,
        refresh_cron="0 8 * * 1-5",
        description="Institutional investors (foreign/trust/dealer)",
        finlab_panel="institutional/trust_net.parquet",
    ),
    "margin": DatasetDef(
        name="margin",
        suffix="margin",
        source_dirs=(FINMIND_DIR,),
        frequency="daily",
        finmind_method="taiwan_stock_margin_purchase_short_sale",
        pit_delay_days=0,
        min_coverage=0.50,
        refresh_cron="0 15 * * 1-5",
        description="Margin purchase / short sale balances",
        finlab_panel="margin/margin_usage.parquet",
    ),
    "securities_lending": DatasetDef(
        name="securities_lending",
        suffix="securities_lending",
        source_dirs=(FINMIND_DIR,),
        frequency="daily",
        finmind_method="taiwan_stock_securities_lending",
        pit_delay_days=0,
        min_coverage=0.20,
        refresh_cron="0 15 * * 1-5",
        description="Securities lending (short pressure / rates)",
    ),
    "shareholding": DatasetDef(
        name="shareholding",
        suffix="shareholding",
        source_dirs=(FINMIND_DIR,),
        frequency="weekly",
        finmind_method="taiwan_stock_shareholding",
        pit_delay_days=0,
        min_coverage=0.30,
        refresh_cron="0 8 * * 1",
        description="Director/supervisor shareholding",
    ),
    "day_trading": DatasetDef(
        name="day_trading",
        suffix="daytrading",
        source_dirs=(FINMIND_DIR,),
        frequency="daily",
        finmind_method="taiwan_stock_day_trading",
        pit_delay_days=0,
        min_coverage=0.10,
        description="Day trading statistics",
    ),
    "dividend": DatasetDef(
        name="dividend",
        suffix="dividend",
        source_dirs=(FINMIND_DIR,),
        frequency="event",
        finmind_method="taiwan_stock_dividend",
        pit_delay_days=0,
        min_coverage=0.30,
        refresh_cron="0 8 1 * *",
        description="Dividend distributions",
    ),
}


def get_dataset(name: str) -> DatasetDef:
    """Get dataset definition by name. Raises KeyError if not found."""
    return REGISTRY[name]


def list_datasets() -> list[DatasetDef]:
    """List all registered datasets."""
    return list(REGISTRY.values())


def parquet_path(symbol: str, dataset: str, source: str | None = None) -> Path:
    """Get the parquet file path for a symbol+dataset.

    If source is specified, returns path in that source dir.
    Otherwise returns the first existing file across source_dirs priority,
    or the primary (first) source dir if no file exists yet.
    """
    ds = REGISTRY[dataset]
    safe = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
    filename = f"{safe}_{ds.suffix}.parquet"

    if source:
        source_dir = _source_name_to_dir(source)
        return source_dir / filename

    # Search by priority — skip corrupt/empty files (< 100 bytes).
    # Among existing files, prefer the largest (most history).
    MIN_FILE_SIZE = 100
    candidates: list[tuple[int, Path]] = []
    for d in ds.source_dirs:
        p = d / filename
        if p.exists() and p.stat().st_size >= MIN_FILE_SIZE:
            candidates.append((p.stat().st_size, p))

    if candidates:
        # Return largest file (most data)
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]

    # Not found anywhere — return primary source dir
    return ds.source_dirs[0] / filename


def write_path(symbol: str, dataset: str, source: str) -> Path:
    """Get the write path for a specific source. Always deterministic."""
    ds = REGISTRY[dataset]
    safe = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
    source_dir = _source_name_to_dir(source)
    source_dir.mkdir(parents=True, exist_ok=True)
    return source_dir / f"{safe}_{ds.suffix}.parquet"


def all_source_paths(symbol: str, dataset: str) -> list[tuple[str, Path]]:
    """Get all possible paths across sources for a symbol+dataset.

    Returns list of (source_name, path) tuples.
    """
    ds = REGISTRY[dataset]
    safe = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
    filename = f"{safe}_{ds.suffix}.parquet"
    result = []
    for d in ds.source_dirs:
        source_name = _dir_to_source_name(d)
        result.append((source_name, d / filename))
    return result


def _source_name_to_dir(source: str) -> Path:
    return {"yahoo": YAHOO_DIR, "finmind": FINMIND_DIR, "twse": TWSE_DIR, "finlab": FINLAB_DIR}[source]


def _dir_to_source_name(d: Path) -> str:
    return {YAHOO_DIR: "yahoo", FINMIND_DIR: "finmind", TWSE_DIR: "twse", FINLAB_DIR: "finlab"}.get(d, "unknown")
