"""Strategy Center — Web v2 核心 API。

提供月度選股、空頭偵測、持倉偏差、一鍵再平衡等功能。
取代 v1 分散在 strategies/portfolio/auto-alpha 的多個端點。

Endpoints:
    GET  /strategy/selection/latest  — 最新月度選股結果
    GET  /strategy/selection/history — 歷史選股列表
    GET  /strategy/regime            — 空頭偵測狀態
    GET  /strategy/drift             — 目標 vs 實際持倉偏差
    POST /strategy/rebalance         — 手動觸發再平衡
    GET  /strategy/info              — 當前策略基本資訊
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import verify_api_key, require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strategy", tags=["strategy-center"])

SELECTIONS_DIR = Path("data/paper_trading/selections")
MARKET_DIR = Path("data/market")


# ── Selection endpoints ──────────────────────────────────────────


@router.get("/selection/latest")
async def get_latest_selection(api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    """取得最新月度選股結果。"""
    if not SELECTIONS_DIR.exists():
        return {"date": None, "selections": [], "strategy": "revenue_momentum_hedged"}

    files = sorted(SELECTIONS_DIR.glob("*.json"), reverse=True)
    if not files:
        return {"date": None, "selections": [], "strategy": "revenue_momentum_hedged"}

    with open(files[0]) as f:
        data = json.load(f)

    return data


@router.get("/selection/history")
async def get_selection_history(
    limit: int = 12,
    api_key: str = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """取得歷史選股列表（預設最近 12 個月）。"""
    if not SELECTIONS_DIR.exists():
        return []

    files = sorted(SELECTIONS_DIR.glob("*.json"), reverse=True)[:limit]
    results = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
            results.append({
                "date": data.get("date", f.stem),
                "n_targets": data.get("n_targets", 0),
                "strategy": data.get("strategy", "unknown"),
            })
        except Exception:
            continue

    return results


# ── Regime detection ─────────────────────────────────────────────


@router.get("/regime")
async def get_regime(api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    """取得空頭偵測狀態。

    Returns:
        regime: "bull" | "bear" | "sideways"
        indicators: MA200/MA50/current/vol_20d/vol_60d
        reason: 觸發原因
    """
    try:
        proxy_path = MARKET_DIR / "0050.TW_1d.parquet"
        if not proxy_path.exists():
            return {"regime": "unknown", "reason": "No 0050.TW data", "indicators": {}}

        df = pd.read_parquet(proxy_path)
        if df.empty or len(df) < 200:
            return {"regime": "unknown", "reason": "Insufficient data", "indicators": {}}

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        close = df["close"]
        current = float(close.iloc[-1])
        ma200 = float(close.iloc[-200:].mean())
        ma50 = float(close.iloc[-50:].mean())

        returns = close.pct_change().dropna()
        vol_20d = float(returns.iloc[-20:].std() * np.sqrt(252)) if len(returns) >= 20 else 0
        vol_60d = float(returns.iloc[-60:].std() * np.sqrt(252)) if len(returns) >= 60 else vol_20d

        # Composite detection (same logic as revenue_momentum_hedged)
        ma_threshold = 0.95
        vol_threshold = 0.25
        vol_spike_ratio = 1.5

        ma_bear = current < ma200 * ma_threshold and ma50 < ma200
        vol_bear = vol_20d > vol_threshold

        reasons = []
        if ma_bear:
            reasons.append(f"Price {current:.0f} < MA200×0.95 ({ma200*ma_threshold:.0f}), MA50 < MA200")
        if vol_bear:
            reasons.append(f"Vol 20d {vol_20d:.1%} > {vol_threshold:.0%} threshold")

        if ma_bear or vol_bear:
            regime = "bear"
        elif current < ma200 or vol_20d > vol_60d * vol_spike_ratio:
            regime = "sideways"
            if current < ma200:
                reasons.append(f"Price {current:.0f} < MA200 ({ma200:.0f})")
            if vol_20d > vol_60d * vol_spike_ratio:
                reasons.append(f"Vol spike: 20d {vol_20d:.1%} > 60d×{vol_spike_ratio} ({vol_60d*vol_spike_ratio:.1%})")
        else:
            regime = "bull"
            reasons.append("All clear")

        return {
            "regime": regime,
            "reason": "; ".join(reasons),
            "indicators": {
                "current_price": round(current, 2),
                "ma200": round(ma200, 2),
                "ma50": round(ma50, 2),
                "vol_20d": round(vol_20d, 4),
                "vol_60d": round(vol_60d, 4),
                "price_vs_ma200": round(current / ma200 - 1, 4),
            },
            "last_date": str(df.index[-1].date()),
        }

    except Exception as e:
        logger.warning("Regime detection failed: %s", e)
        return {"regime": "unknown", "reason": str(e), "indicators": {}}


# ── Drift analysis ───────────────────────────────────────────────


@router.get("/drift")
async def get_drift(api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    """計算目標 vs 實際持倉偏差。"""
    from src.api.state import get_app_state

    state = get_app_state()
    portfolio = state.portfolio

    # Load latest selection
    target_weights: dict[str, float] = {}
    if SELECTIONS_DIR.exists():
        files = sorted(SELECTIONS_DIR.glob("*.json"), reverse=True)
        if files:
            try:
                with open(files[0]) as f:
                    data = json.load(f)
                target_weights = data.get("weights", {})
            except Exception:
                pass

    if not target_weights:
        return {"drift": [], "max_drift": 0, "selection_date": None}

    # Current weights
    nav = float(portfolio.nav) if portfolio.nav > 0 else 1
    current_weights: dict[str, float] = {}
    for sym, pos in portfolio.positions.items():
        market_value = float(pos.quantity * pos.last_price)
        current_weights[sym] = market_value / nav

    # Compute drift
    all_symbols = set(target_weights.keys()) | set(current_weights.keys())
    drift_items = []
    for sym in sorted(all_symbols):
        target = target_weights.get(sym, 0)
        actual = current_weights.get(sym, 0)
        diff = actual - target
        drift_items.append({
            "symbol": sym,
            "target_weight": round(target, 4),
            "actual_weight": round(actual, 4),
            "drift": round(diff, 4),
            "status": "new" if actual == 0 and target > 0 else ("exit" if target == 0 and actual > 0 else "held"),
        })

    drift_items.sort(key=lambda x: abs(x["drift"]), reverse=True)
    max_drift = max(abs(d["drift"]) for d in drift_items) if drift_items else 0

    selection_date = None
    if SELECTIONS_DIR.exists():
        files = sorted(SELECTIONS_DIR.glob("*.json"), reverse=True)
        if files:
            selection_date = files[0].stem

    return {
        "drift": drift_items,
        "max_drift": round(max_drift, 4),
        "selection_date": selection_date,
        "n_targets": len(target_weights),
        "n_actual": len(current_weights),
    }


# ── Rebalance trigger ────────────────────────────────────────────


@router.post("/rebalance")
async def trigger_rebalance(
    api_key: str = Depends(require_role("trader")),
) -> dict[str, Any]:
    """手動觸發一鍵再平衡（= monthly_revenue_rebalance 的手動版）。"""
    from src.api.state import get_app_state
    from src.core.config import get_config
    from src.data.sources import create_feed, create_fundamentals
    from src.strategy.base import Context
    from src.strategy.engine import weights_to_orders
    from src.strategy.registry import resolve_strategy

    state = get_app_state()
    config = get_config()

    try:
        strategy = resolve_strategy("revenue_momentum_hedged")

        # Universe: from portfolio positions or market data
        universe = list(state.portfolio.positions.keys())
        if not universe:
            universe = sorted(
                p.stem.replace("_1d", "")
                for p in MARKET_DIR.glob("*.TW_1d.parquet")
                if not p.stem.startswith("00")
            )[:200]  # limit for speed

        feed = create_feed(config.data_source, universe)
        fundamentals = create_fundamentals(config.data_source)

        ctx = Context(
            feed=feed,
            portfolio=state.portfolio,
            fundamentals_provider=fundamentals,
        )

        target_weights = strategy.on_bar(ctx)

        if not target_weights:
            return {"status": "no_targets", "message": "Strategy returned empty weights (possibly bear regime)", "trades": []}

        # Generate orders preview
        prices = {}
        for s in target_weights:
            try:
                prices[s] = feed.get_latest_price(s)
            except Exception:
                pass

        orders = weights_to_orders(
            target_weights=target_weights,
            portfolio=state.portfolio,
            prices=prices,
        )

        # Save selection
        from src.scheduler.jobs import _save_selection_log
        _save_selection_log(target_weights)

        # Risk check + submit
        approved = []
        rejected = []
        for order in orders:
            decision = state.risk_engine.check_order(order, state.portfolio)
            if decision.approved:
                if decision.modified_qty is not None:
                    order.quantity = decision.modified_qty
                approved.append(order)
            else:
                rejected.append({"symbol": order.instrument.symbol, "reason": decision.reason})

        trades = []
        if approved:
            from src.execution.oms import apply_trades
            trade_list = state.execution_service.submit_orders(approved, state.portfolio)
            if trade_list:
                apply_trades(state.portfolio, trade_list)
                trades = [{"symbol": t.symbol, "side": t.side.value, "quantity": float(t.quantity), "price": float(t.price)} for t in trade_list]

        return {
            "status": "completed",
            "n_targets": len(target_weights),
            "n_orders": len(orders),
            "n_approved": len(approved),
            "n_rejected": len(rejected),
            "trades": trades,
            "rejected": rejected,
        }

    except Exception as e:
        logger.exception("Manual rebalance failed")
        raise HTTPException(status_code=500, detail=str(e))


# ── Strategy info ────────────────────────────────────────────────


@router.get("/info")
async def get_strategy_info(api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    """當前策略基本資訊。"""
    return {
        "name": "revenue_momentum_hedged",
        "description": "營收動能 + 複合空頭偵測（MA200 OR vol_spike）",
        "factor": "revenue_yoy (ICIR 0.674, t=16.1)",
        "rebalance": "Monthly (11th)",
        "bear_scale": 0.0,
        "sideways_scale": 0.3,
        "max_holdings": 15,
        "validation": "StrategyValidator 10/13, PBO 0%, WF 7/7 positive",
    }


# ── Data status ──────────────────────────────────────────────────


@router.get("/data-status")
async def get_data_status(api_key: str = Depends(verify_api_key)) -> dict[str, Any]:
    """營收/法人數據更新狀態。"""
    from pathlib import Path

    fund_dir = Path("data/fundamental")
    market_dir = Path("data/market")

    revenue_count = len(list(fund_dir.glob("*_revenue.parquet"))) if fund_dir.exists() else 0
    institutional_count = len(list(fund_dir.glob("*_institutional.parquet"))) if fund_dir.exists() else 0
    market_count = len(list(market_dir.glob("*.TW_1d.parquet"))) if market_dir.exists() else 0

    # Latest revenue date
    latest_revenue_date = None
    if fund_dir.exists():
        sample_files = sorted(fund_dir.glob("*_revenue.parquet"))[:1]
        if sample_files:
            try:
                df = pd.read_parquet(sample_files[0])
                if not df.empty and "date" in df.columns:
                    latest_revenue_date = str(pd.to_datetime(df["date"]).max().date())
            except Exception:
                pass

    return {
        "market_symbols": market_count,
        "revenue_symbols": revenue_count,
        "institutional_symbols": institutional_count,
        "latest_revenue_date": latest_revenue_date,
    }
