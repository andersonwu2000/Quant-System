"""Data Registry — metadata definitions for all dataset types.

Central registry of what data exists, where it lives, how often it refreshes,
and what PIT delay to apply. Used by refresh engine, quality gate, and CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ── Dataset definition ───────────────────────────────────────────────

@dataclass(frozen=True)
class DatasetDef:
    """Metadata for a single dataset type."""
    name: str                       # "price", "revenue", "institutional", ...
    suffix: str                     # parquet filename suffix
    storage_dir: Path               # "data/market" or "data/fundamental"
    frequency: str                  # "daily", "weekly", "monthly", "quarterly", "event"
    finmind_method: str             # FinMind DataLoader method name
    pit_delay_days: int = 0         # PIT delay for look-ahead bias prevention
    min_coverage: float = 0.0       # min fraction of universe that should have this data
    refresh_cron: str = ""          # cron expression for auto-refresh
    description: str = ""
    yahoo_available: bool = False   # whether Yahoo Finance can provide this data


MARKET_DIR = Path("data/market")
FUND_DIR = Path("data/fundamental")

# ── Registry ─────────────────────────────────────────────────────────

REGISTRY: dict[str, DatasetDef] = {
    "price": DatasetDef(
        name="price",
        suffix="1d",
        storage_dir=MARKET_DIR,
        frequency="daily",
        finmind_method="taiwan_stock_daily",
        pit_delay_days=0,
        min_coverage=0.90,
        refresh_cron="0 8 * * 1-5",
        description="Daily OHLCV",
        yahoo_available=True,
    ),
    "revenue": DatasetDef(
        name="revenue",
        suffix="revenue",
        storage_dir=FUND_DIR,
        frequency="monthly",
        finmind_method="taiwan_stock_month_revenue",
        pit_delay_days=40,
        min_coverage=0.70,
        refresh_cron="0 8 11 * *",
        description="Monthly revenue",
    ),
    "financial_statement": DatasetDef(
        name="financial_statement",
        suffix="financial_statement",
        storage_dir=FUND_DIR,
        frequency="quarterly",
        finmind_method="taiwan_stock_financial_statement",
        pit_delay_days=90,  # conservative: Q1 deadline 5/15 = ~45d, but use 90 for safety
        min_coverage=0.40,
        refresh_cron="0 8 16 5,8,11 *",
        description="Income statement (EPS, ROE, revenue, etc.)",
    ),
    "cash_flows": DatasetDef(
        name="cash_flows",
        suffix="cash_flows",
        storage_dir=FUND_DIR,
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
        storage_dir=FUND_DIR,
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
        storage_dir=FUND_DIR,
        frequency="daily",
        finmind_method="taiwan_stock_per_pbr",
        pit_delay_days=0,
        min_coverage=0.50,
        refresh_cron="0 8 * * 1-5",
        description="Daily PE/PB/dividend yield",
    ),
    "institutional": DatasetDef(
        name="institutional",
        suffix="institutional",
        storage_dir=FUND_DIR,
        frequency="daily",
        finmind_method="taiwan_stock_institutional_investors",
        pit_delay_days=0,
        min_coverage=0.80,
        refresh_cron="0 8 * * 1-5",
        description="Institutional investors (foreign/trust/dealer)",
    ),
    "margin": DatasetDef(
        name="margin",
        suffix="margin",
        storage_dir=FUND_DIR,
        frequency="daily",
        finmind_method="taiwan_stock_margin_purchase_short_sale",
        pit_delay_days=0,
        min_coverage=0.50,
        refresh_cron="0 15 * * 1-5",
        description="Margin purchase / short sale balances",
    ),
    "securities_lending": DatasetDef(
        name="securities_lending",
        suffix="securities_lending",
        storage_dir=FUND_DIR,
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
        storage_dir=FUND_DIR,
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
        storage_dir=FUND_DIR,
        frequency="daily",
        finmind_method="taiwan_stock_day_trading",
        pit_delay_days=0,
        min_coverage=0.10,
        description="Day trading statistics",
    ),
    "dividend": DatasetDef(
        name="dividend",
        suffix="dividend",
        storage_dir=FUND_DIR,
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


def parquet_path(symbol: str, dataset: str) -> Path:
    """Get the parquet file path for a symbol+dataset combination."""
    ds = REGISTRY[dataset]
    safe = symbol.replace("/", "_").replace("\\", "_").replace("..", "_")
    return ds.storage_dir / f"{safe}_{ds.suffix}.parquet"
