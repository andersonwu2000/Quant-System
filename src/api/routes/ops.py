"""Operations API — single entry point for system status overview.

Endpoints:
  GET /ops/status         — full system status (one-click overview)
  GET /ops/positions      — simplified position list
  GET /ops/daily-summary  — today's P&L, trades, data freshness
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["Operations"], dependencies=[Depends(verify_api_key)])


@router.get("/status")
async def ops_status() -> dict:
    """Full system status — one endpoint to see everything."""
    from src.core.config import get_config

    config = get_config()
    result: dict = {
        "timestamp": datetime.now().isoformat(),
        "mode": config.mode,
        "strategy": config.active_strategy,
        "rebalance_frequency": config.rebalance_frequency,
    }

    # Portfolio
    try:
        from src.api.state import get_app_state
        state = get_app_state()
        p = state.portfolio
        result["portfolio"] = {
            "nav": float(p.nav) if p.nav else 0,
            "cash": float(p.cash) if p.cash else 0,
            "n_positions": len(p.positions),
            "positions": {
                sym: {"qty": float(pos.quantity), "price": float(pos.market_price)}
                for sym, pos in p.positions.items()
            },
        }
    except Exception:
        result["portfolio"] = {"error": "unavailable"}

    # Scheduler
    try:
        from src.api.state import get_app_state
        state = get_app_state()
        sched = state.scheduler
        result["scheduler"] = {"running": sched.is_running if sched else False}
    except Exception:
        result["scheduler"] = {"running": False}

    # Data freshness (quick scan)
    try:
        from src.data.data_catalog import get_catalog
        cat = get_catalog()
        price_syms = cat.available_symbols("price")
        result["data"] = {
            "price_symbols": len(price_syms),
            "revenue_symbols": len(cat.available_symbols("revenue")),
        }
    except Exception:
        result["data"] = {"error": "unavailable"}

    # Recent pipeline run
    try:
        runs_dir = Path("data/paper_trading/pipeline_runs")
        if runs_dir.exists():
            runs = sorted(runs_dir.glob("*.json"), reverse=True)
            if runs:
                import json
                last = json.loads(runs[0].read_text(encoding="utf-8"))
                result["last_pipeline"] = {
                    "run_id": last.get("run_id"),
                    "status": last.get("status"),
                    "n_trades": last.get("n_trades", 0),
                    "started_at": last.get("started_at"),
                }
    except Exception:
        pass

    # Trading calendar
    try:
        from src.core.calendar import get_tw_calendar
        cal = get_tw_calendar()
        today = date.today()
        result["calendar"] = {
            "today": str(today),
            "is_trading_day": cal.is_trading_day(today),
            "next_trading_day": str(cal.next_trading_day(today)),
        }
    except Exception:
        pass

    return result


@router.get("/positions")
async def ops_positions() -> dict:
    """Simplified position list with current prices."""
    try:
        from src.api.state import get_app_state
        state = get_app_state()
        p = state.portfolio
        positions = []
        for sym, pos in p.positions.items():
            qty = float(pos.quantity)
            price = float(pos.market_price)
            cost = float(pos.avg_cost)
            pnl = (price - cost) * qty if qty > 0 and cost > 0 else 0
            positions.append({
                "symbol": sym,
                "qty": qty,
                "price": price,
                "avg_cost": cost,
                "pnl": round(pnl, 2),
                "weight": round(qty * price / float(p.nav), 4) if p.nav and float(p.nav) > 0 else 0,
            })
        return {
            "nav": float(p.nav) if p.nav else 0,
            "cash": float(p.cash) if p.cash else 0,
            "n_positions": len(positions),
            "positions": sorted(positions, key=lambda x: -abs(x["pnl"])),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/daily-summary")
async def ops_daily_summary() -> dict:
    """Today's summary: P&L, trades, data status, reconciliation."""
    import json

    today_str = date.today().isoformat()
    result: dict = {"date": today_str}

    # Portfolio NAV
    try:
        from src.api.state import get_app_state
        state = get_app_state()
        result["nav"] = float(state.portfolio.nav) if state.portfolio.nav else 0
        result["cash"] = float(state.portfolio.cash) if state.portfolio.cash else 0
        result["n_positions"] = len(state.portfolio.positions)
    except Exception:
        pass

    # Today's trades
    trades_dir = Path("data/paper_trading/trades")
    if trades_dir.exists():
        today_trades = list(trades_dir.glob(f"{today_str}*.json"))
        if today_trades:
            try:
                data = json.loads(today_trades[0].read_text(encoding="utf-8"))
                result["trades"] = {
                    "n_trades": data.get("n_trades", 0),
                    "avg_shortfall_bps": data.get("avg_shortfall_bps", 0),
                    "total_commission": data.get("total_commission", 0),
                }
            except Exception:
                pass

    # Today's reconciliation
    recon_path = Path("data/paper_trading/reconciliation") / f"{today_str}.json"
    if recon_path.exists():
        try:
            data = json.loads(recon_path.read_text(encoding="utf-8"))
            result["reconciliation"] = {
                "status": data.get("status"),
                "return_diff_bps": data.get("return_diff_bps", 0),
                "weight_drift_bps": data.get("weight_drift_bps", 0),
            }
        except Exception:
            pass

    # Data freshness
    try:
        from src.data.data_catalog import get_catalog
        cat = get_catalog()
        result["data_symbols"] = {
            "price": len(cat.available_symbols("price")),
            "revenue": len(cat.available_symbols("revenue")),
        }
    except Exception:
        pass

    return result
