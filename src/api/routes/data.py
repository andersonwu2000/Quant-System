"""Data management API routes — quality checks, fundamentals, cache."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth import verify_api_key, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data", tags=["data"])


# ── Quality Check ──────────────────────────────────────────────


class QualityCheckRequest(BaseModel):
    symbol: str
    start: str | None = None
    end: str | None = None

class QualityCheckResponse(BaseModel):
    symbol: str
    status: str  # "PASS" | "SUSPECT" | "REJECT"
    issues: list[str]
    suspect_dates: list[str]
    halted_dates: list[str]

@router.post("/quality-check", response_model=QualityCheckResponse)
async def check_data_quality(
    req: QualityCheckRequest,
    api_key: str = Depends(verify_api_key),
) -> QualityCheckResponse:
    """Validate OHLCV data quality for a symbol."""
    try:
        from src.data.sources.yahoo import YahooFeed
        from src.data.quality import check_bars_with_dividends, detect_halted_dates

        feed = YahooFeed()
        bars = feed.get_bars(req.symbol, start=req.start, end=req.end)
        if bars.empty:
            raise HTTPException(status_code=404, detail=f"No data for {req.symbol}")

        result = check_bars_with_dividends(bars, req.symbol)
        halted = detect_halted_dates(bars)

        return QualityCheckResponse(
            symbol=req.symbol,
            status=result.status.value,
            issues=result.issues,
            suspect_dates=sorted(result.suspect_dates) if result.suspect_dates else [],
            halted_dates=sorted(halted),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Fundamentals ───────────────────────────────────────────────


class FundamentalsResponse(BaseModel):
    symbol: str
    metrics: dict[str, float]
    sector: str

@router.get("/fundamentals/{symbol}", response_model=FundamentalsResponse)
async def get_fundamentals(
    symbol: str,
    date: str | None = None,
    api_key: str = Depends(verify_api_key),
) -> FundamentalsResponse:
    """Get fundamental metrics for a symbol."""
    try:
        from src.data.sources import create_fundamentals
        from src.core.config import get_config

        config = get_config()
        provider = create_fundamentals("finmind", token=config.finmind_token)
        if provider is None:
            raise HTTPException(status_code=503, detail="Fundamentals provider not available")

        metrics = provider.get_financials(symbol, date=date)
        sector = provider.get_sector(symbol)

        return FundamentalsResponse(symbol=symbol, metrics=metrics, sector=sector)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Cache Status ───────────────────────────────────────────────


class CacheStatusResponse(BaseModel):
    market_files: int
    fundamental_files: int
    symbols: list[str]

@router.get("/cache-status", response_model=CacheStatusResponse)
async def get_cache_status(
    api_key: str = Depends(verify_api_key),
) -> CacheStatusResponse:
    """Query local parquet cache status."""
    from pathlib import Path

    market_dir = Path("data/market")
    fund_dir = Path("data/fundamental")

    market_files = list(market_dir.glob("*.parquet")) if market_dir.exists() else []
    fund_files = list(fund_dir.glob("*.parquet")) if fund_dir.exists() else []

    symbols = sorted(set(
        f.stem.replace("_1d", "").replace("finmind_", "")
        for f in market_files
        if f.stem.endswith("_1d")
    ))

    return CacheStatusResponse(
        market_files=len(market_files),
        fundamental_files=len(fund_files),
        symbols=symbols,
    )


# ── Macro Factors (FRED) ──────────────────────────────────────


class MacroDataResponse(BaseModel):
    indicator: str
    values: dict[str, float]

@router.get("/macro/{indicator}", response_model=MacroDataResponse)
async def get_macro_data(
    indicator: str,
    start: str | None = None,
    end: str | None = None,
    api_key: str = Depends(verify_api_key),
) -> MacroDataResponse:
    """Query FRED macro data for an indicator."""
    try:
        from src.data.sources.fred import FredDataSource

        fred = FredDataSource()
        data = fred.get_series(indicator, start=start, end=end)

        if data is None or data.empty:
            raise HTTPException(status_code=404, detail=f"No data for indicator {indicator}")

        values = {str(d.date()) if hasattr(d, 'date') else str(d): float(v) for d, v in data.items() if not (v != v)}
        return MacroDataResponse(indicator=indicator, values=values)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
