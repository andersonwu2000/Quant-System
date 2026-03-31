"""Import FinLab company data into SecuritiesMaster.

Imports:
- company_basic_info (2,241 active companies): symbol, name, industry, listed_date
- delisted_companies (1,695 delisted): symbol, name, industry, listed_date, delisted_date

Usage:
    python scripts/import_finlab_to_master.py              # import all
    python scripts/import_finlab_to_master.py --dry-run    # show plan only
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_date(val) -> date | None:
    if pd.isna(val) or val is None or str(val).strip() in ("", "NaT"):
        return None
    try:
        return pd.Timestamp(val).date()
    except Exception:
        return None


def _exchange_from_market(market_code: str) -> str:
    if market_code == "sii":
        return "TWSE"
    elif market_code == "otc":
        return "TPEX"
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Import FinLab data into SecuritiesMaster")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from src.data.master import SecuritiesMaster, Security
    from src.data.store import DataStore

    ds = DataStore()
    master = SecuritiesMaster(ds._engine)

    securities: list[Security] = []

    # ── Active companies from company_basic_info ─────────────────────
    info_path = Path("data/finlab/meta/company_basic_info.parquet")
    if info_path.exists():
        info = pd.read_parquet(info_path)
        cols = info.columns.tolist()
        logger.info("Loading %d active companies from company_basic_info", len(info))

        for _, row in info.iterrows():
            symbol_bare = str(row.iloc[0])
            name = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
            industry = str(row.iloc[3]) if pd.notna(row.iloc[3]) else ""
            listed_date = _parse_date(row.iloc[14]) if len(cols) > 14 else None
            market = str(row.iloc[39]) if len(cols) > 39 and pd.notna(row.iloc[39]) else ""

            sym = f"{symbol_bare}.TW"
            securities.append(Security(
                symbol=sym,
                bare_id=symbol_bare,
                name=name,
                exchange=_exchange_from_market(market),
                industry_name=industry,
                listed_date=listed_date,
                status="active",
            ))
    else:
        logger.warning("company_basic_info not found")

    # ── Delisted companies ───────────────────────────────────────────
    dl_path = Path("data/finlab/meta/delisted_companies.parquet")
    if dl_path.exists():
        dl = pd.read_parquet(dl_path)
        cols = dl.columns.tolist()
        logger.info("Loading %d delisted companies", len(dl))

        for _, row in dl.iterrows():
            symbol_bare = str(row.iloc[0])
            name = str(row.iloc[1]) if pd.notna(row.iloc[1]) else ""
            industry = str(row.iloc[16]) if len(cols) > 16 and pd.notna(row.iloc[16]) else ""
            listed_date = _parse_date(row.iloc[11]) if len(cols) > 11 else None
            delisted_date = _parse_date(row.iloc[12]) if len(cols) > 12 else None
            market = str(row.iloc[17]) if len(cols) > 17 and pd.notna(row.iloc[17]) else ""

            # Skip if listed_date missing — can't do PIT without it
            sym = f"{symbol_bare}.TW"
            securities.append(Security(
                symbol=sym,
                bare_id=symbol_bare,
                name=name,
                exchange=_exchange_from_market(market),
                industry_name=industry,
                listed_date=listed_date,
                delisted_date=delisted_date,
                status="delisted",
            ))
    else:
        logger.warning("delisted_companies not found")

    # ── Summary ──────────────────────────────────────────────────────
    active = sum(1 for s in securities if s.status == "active")
    delisted = sum(1 for s in securities if s.status == "delisted")
    with_listed = sum(1 for s in securities if s.listed_date is not None)
    with_delisted = sum(1 for s in securities if s.delisted_date is not None)
    with_industry = sum(1 for s in securities if s.industry_name)

    print(f"Plan: {len(securities)} securities ({active} active, {delisted} delisted)")
    print(f"  With listed_date:   {with_listed}")
    print(f"  With delisted_date: {with_delisted}")
    print(f"  With industry:      {with_industry}")

    if args.dry_run:
        print("Dry run, not saving.")
        return

    count = master.upsert_many(securities)
    total = master.count()
    print(f"\nImported {count} securities. Total in master: {total}")

    # Quick verification
    from datetime import date as d
    uni_2010 = master.universe_at(d(2010, 6, 1))
    uni_2018 = master.universe_at(d(2018, 6, 1))
    uni_now = master.universe_at(d(2026, 3, 31))
    print(f"Universe at 2010-06-01: {len(uni_2010)}")
    print(f"Universe at 2018-06-01: {len(uni_2018)}")
    print(f"Universe at 2026-03-31: {len(uni_now)}")


if __name__ == "__main__":
    main()
