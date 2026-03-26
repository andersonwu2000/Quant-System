"""Portfolio API routes — in-memory state + persisted portfolio CRUD."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import verify_api_key, require_role
from src.core.models import Side
from src.api.schemas import (
    PortfolioCreateRequest,
    PortfolioDetailResponse,
    PortfolioListItem,
    PortfolioListResponse,
    PortfolioResponse,
    PositionResponse,
    RebalancePreviewRequest,
    RebalancePreviewResponse,
    SuggestedTrade,
)
from src.api.state import get_app_state
from src.core.config import get_config
from src.data.store import _create_engine, metadata
from src.core.repository import PortfolioRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

_engine: sa.Engine | None = None


def _get_engine() -> sa.Engine:
    """Get or create a cached engine for portfolio persistence."""
    global _engine
    if _engine is None:
        config = get_config()
        url = config.database_url
        if url.startswith("sqlite") and url != "sqlite:///:memory:":
            from pathlib import Path
            db_path = url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = _create_engine(url)
        metadata.create_all(_engine)
    return _engine


def reset_portfolio_engine() -> None:
    """Reset cached engine (for testing)."""
    global _engine
    _engine = None


def _get_repo() -> PortfolioRepository:
    """Create a repository backed by the configured database."""
    return PortfolioRepository(_get_engine())


# ─── Legacy in-memory portfolio endpoints ────────────────

@router.get("", response_model=PortfolioResponse)
async def get_portfolio(api_key: str = Depends(verify_api_key)) -> PortfolioResponse:
    """取得當前投資組合（in-memory）。"""
    state = get_app_state()
    portfolio = state.portfolio

    positions = []
    for symbol, pos in portfolio.positions.items():
        nav = portfolio.nav
        weight = float(pos.market_value / nav) if nav > 0 else 0
        positions.append(PositionResponse(
            symbol=symbol,
            quantity=float(pos.quantity),
            avg_cost=float(pos.avg_cost),
            market_price=float(pos.market_price),
            market_value=float(pos.market_value),
            unrealized_pnl=float(pos.unrealized_pnl),
            weight=weight,
        ))

    nav_float = float(portfolio.nav)
    daily_pnl = float(portfolio.daily_pnl)

    return PortfolioResponse(
        nav=nav_float,
        cash=float(portfolio.cash),
        gross_exposure=float(portfolio.gross_exposure),
        net_exposure=float(portfolio.net_exposure),
        positions_count=len(portfolio.positions),
        daily_pnl=daily_pnl,
        daily_pnl_pct=daily_pnl / nav_float if nav_float > 0 else 0.0,
        positions=positions,
        as_of=str(portfolio.as_of),
    )


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions(api_key: str = Depends(verify_api_key)) -> list[PositionResponse]:
    """取得所有持倉明細。"""
    state = get_app_state()
    portfolio = state.portfolio
    nav = portfolio.nav

    return [
        PositionResponse(
            symbol=symbol,
            quantity=float(pos.quantity),
            avg_cost=float(pos.avg_cost),
            market_price=float(pos.market_price),
            market_value=float(pos.market_value),
            unrealized_pnl=float(pos.unrealized_pnl),
            weight=float(pos.market_value / nav) if nav > 0 else 0,
        )
        for symbol, pos in portfolio.positions.items()
    ]


# ─── Persisted portfolio CRUD ────────────────────────────

@router.get("/saved", response_model=PortfolioListResponse)
async def list_portfolios(
    api_key: str = Depends(verify_api_key),
) -> PortfolioListResponse:
    """List all persisted portfolios."""
    repo = _get_repo()
    items = repo.list_all()
    return PortfolioListResponse(
        portfolios=[PortfolioListItem(**item) for item in items]
    )


@router.post("/saved", response_model=PortfolioDetailResponse, status_code=201)
async def create_portfolio(
    req: PortfolioCreateRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> PortfolioDetailResponse:
    """Create a new persisted portfolio."""
    repo = _get_repo()
    initial_cash = Decimal(str(req.initial_cash))
    portfolio_id = repo.create(
        name=req.name,
        initial_cash=initial_cash,
        strategy_name=req.strategy_name,
    )
    meta = repo.get_meta(portfolio_id)
    if meta is None:
        raise HTTPException(status_code=500, detail="Failed to create portfolio")

    return PortfolioDetailResponse(
        id=portfolio_id,
        name=meta["name"],
        cash=float(meta["cash"]),
        initial_cash=float(meta["initial_cash"]),
        strategy_name=meta["strategy_name"] or "",
        positions=[],
        nav=float(meta["cash"]),
        created_at=meta["created_at"],
    )


@router.get("/saved/{portfolio_id}", response_model=PortfolioDetailResponse)
async def get_saved_portfolio(
    portfolio_id: str,
    api_key: str = Depends(verify_api_key),
) -> PortfolioDetailResponse:
    """Get a persisted portfolio with current positions."""
    repo = _get_repo()
    meta = repo.get_meta(portfolio_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    portfolio = repo.get(portfolio_id)
    positions = []
    nav = float(meta["cash"])
    cash = float(meta["cash"])
    initial_cash = float(meta["initial_cash"])

    if portfolio is not None:
        cash = float(portfolio.cash)
        initial_cash = float(portfolio.initial_cash)
        nav = float(portfolio.nav)
        for symbol, pos in portfolio.positions.items():
            positions.append({
                "symbol": symbol,
                "quantity": float(pos.quantity),
                "avg_cost": float(pos.avg_cost),
                "market_price": float(pos.market_price),
                "market_value": float(pos.market_value),
                "unrealized_pnl": float(pos.unrealized_pnl),
            })

    return PortfolioDetailResponse(
        id=portfolio_id,
        name=meta["name"],
        cash=cash,
        initial_cash=initial_cash,
        strategy_name=meta["strategy_name"] or "",
        positions=positions,
        nav=nav,
        created_at=meta["created_at"],
    )


@router.delete("/saved/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: str,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("trader")),
) -> dict[str, str]:
    """Delete a persisted portfolio and all related data."""
    repo = _get_repo()
    deleted = repo.delete(portfolio_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return {"message": f"Portfolio {portfolio_id} deleted"}


@router.get("/saved/{portfolio_id}/trades")
async def get_portfolio_trades(
    portfolio_id: str,
    start: str | None = None,
    end: str | None = None,
    api_key: str = Depends(verify_api_key),
) -> list[dict[str, Any]]:
    """Get trade history for a portfolio."""
    repo = _get_repo()
    meta = repo.get_meta(portfolio_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return repo.get_trades(portfolio_id, start=start, end=end)


# ─── Rebalance Preview ──────────────────────────────────

@router.post(
    "/saved/{portfolio_id}/rebalance-preview",
    response_model=RebalancePreviewResponse,
)
async def rebalance_preview(
    portfolio_id: str,
    req: RebalancePreviewRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> RebalancePreviewResponse:
    """Run strategy on current holdings and return suggested trades."""
    repo = _get_repo()
    portfolio = repo.get(portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    config = get_config()
    commission_rate = req.commission_rate if req.commission_rate is not None else config.commission_rate
    tax_rate = req.tax_rate if req.tax_rate is not None else config.tax_rate

    def _compute() -> RebalancePreviewResponse:
        from src.data.sources.yahoo import YahooFeed
        from src.strategy.base import Context
        from src.strategy.engine import weights_to_orders
        from src.strategy.registry import resolve_strategy

        # Resolve strategy
        strategy = resolve_strategy(req.strategy, req.params)

        # Fetch current prices for the universe
        feed = YahooFeed(universe=req.universes)
        for symbol in req.universes:
            feed.get_bars(symbol)

        # Build context and run strategy
        ctx = Context(feed=feed, portfolio=portfolio)
        target_weights = strategy.on_bar(ctx)

        # Get current prices
        prices: dict[str, Decimal] = {}
        for symbol in set(list(target_weights.keys()) + list(portfolio.positions.keys())):
            price = feed.get_latest_price(symbol)
            if price > 0:
                prices[symbol] = price

        # Update portfolio market prices so NAV is accurate
        portfolio.update_market_prices(prices)
        nav = portfolio.nav

        # Compute current weights
        current_weights: dict[str, float] = {}
        for symbol in portfolio.positions:
            if nav > 0:
                current_weights[symbol] = float(
                    portfolio.positions[symbol].market_value / nav
                )

        # Use the real weights_to_orders to get consistent results
        orders = weights_to_orders(target_weights, portfolio, prices)

        # Convert orders to suggested trades with cost estimates
        suggested_trades: list[SuggestedTrade] = []
        total_commission = Decimal("0")
        total_tax = Decimal("0")

        for order in orders:
            symbol = order.instrument.symbol
            price = prices.get(symbol, Decimal("0"))
            if price <= 0:
                continue

            side = "BUY" if order.side == Side.BUY else "SELL"
            trade_value = price * order.quantity
            commission = trade_value * Decimal(str(commission_rate))
            tax = trade_value * Decimal(str(tax_rate)) if side == "SELL" else Decimal("0")

            if side == "BUY":
                estimated_cost = float(trade_value + commission)
            else:
                estimated_cost = -float(trade_value - commission - tax)

            suggested_trades.append(SuggestedTrade(
                symbol=symbol,
                side=side,
                quantity=int(order.quantity),
                estimated_price=float(price),
                estimated_cost=estimated_cost,
            ))

            total_commission += commission
            total_tax += tax

        return RebalancePreviewResponse(
            strategy=req.strategy,
            target_weights=target_weights,
            current_weights=current_weights,
            suggested_trades=suggested_trades,
            estimated_total_commission=float(total_commission),
            estimated_total_tax=float(total_tax),
        )

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_compute),
            timeout=60,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Rebalance preview timed out")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result


# ── Portfolio Optimization ─────────────────────────────────────


class OptimizeRequest(BaseModel):
    symbols: list[str]
    start: str
    end: str
    method: str = "mean_variance"  # one of: equal_weight, inverse_vol, risk_parity, mean_variance, black_litterman, hrp, robust, resampled, cvar_optimization, max_drawdown, global_min_variance, max_sharpe, index_tracking, semi_variance
    risk_free_rate: float = 0.015
    target_return: float | None = None
    max_weight: float = 0.30


class OptimizeResponse(BaseModel):
    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    method: str


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_portfolio(req: OptimizeRequest, api_key: str = Depends(verify_api_key), _role: dict = Depends(require_role("researcher"))) -> OptimizeResponse:
    """Run portfolio optimization with specified method."""
    try:
        from src.data.sources.yahoo import YahooFeed
        from src.portfolio.optimizer import PortfolioOptimizer, OptimizerConfig, OptimizationMethod
        import pandas as pd

        feed = YahooFeed(universe=req.symbols)
        returns_data = {}
        for sym in req.symbols:
            bars = feed.get_bars(sym, start=req.start, end=req.end)
            if not bars.empty:
                returns_data[sym] = bars["close"].pct_change().dropna()

        if len(returns_data) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 symbols with data")

        returns_df = pd.DataFrame(returns_data).dropna()
        method_enum = OptimizationMethod(req.method)
        config = OptimizerConfig(method=method_enum, risk_free_rate=req.risk_free_rate, max_weight=req.max_weight)
        if req.target_return is not None:
            config.target_return = req.target_return

        optimizer = PortfolioOptimizer(config=config)
        result = optimizer.optimize(returns_df)

        return OptimizeResponse(
            weights=result.weights,
            expected_return=result.portfolio_return,
            volatility=result.portfolio_risk,
            sharpe_ratio=result.sharpe_ratio,
            method=req.method,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Optimization failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class RiskAnalysisRequest(BaseModel):
    symbols: list[str]
    start: str
    end: str
    weights: dict[str, float] | None = None
    confidence: float = 0.95
    cov_method: str = "ledoit_wolf"  # historical, ewm, ledoit_wolf, factor_model


class RiskAnalysisResponse(BaseModel):
    portfolio_volatility: float
    var_95: float
    cvar_95: float
    risk_contributions: dict[str, float]
    correlations: dict[str, dict[str, float]]


@router.post("/risk-analysis", response_model=RiskAnalysisResponse)
async def portfolio_risk_analysis(req: RiskAnalysisRequest, api_key: str = Depends(verify_api_key), _role: dict = Depends(require_role("researcher"))) -> RiskAnalysisResponse:
    """Compute portfolio risk metrics."""
    try:
        from src.data.sources.yahoo import YahooFeed
        from src.portfolio.risk_model import RiskModel, RiskModelConfig
        import pandas as pd

        feed = YahooFeed(universe=req.symbols)
        returns_data = {}
        for sym in req.symbols:
            bars = feed.get_bars(sym, start=req.start, end=req.end)
            if not bars.empty:
                returns_data[sym] = bars["close"].pct_change().dropna()

        returns_df = pd.DataFrame(returns_data).dropna()
        if returns_df.empty:
            raise HTTPException(status_code=400, detail="No return data")

        # Map cov_method string to RiskModelConfig flags
        cov_config = RiskModelConfig()
        if req.cov_method == "ewm":
            cov_config.ewm_halflife = 63
            cov_config.shrinkage = False
        elif req.cov_method == "historical":
            cov_config.shrinkage = False
        elif req.cov_method == "ledoit_wolf":
            cov_config.shrinkage = True
        elif req.cov_method == "factor_model":
            cov_config.factor_model = True

        rm = RiskModel(config=cov_config)
        cov = rm.estimate_covariance(returns_df)
        corr = rm.estimate_correlation(returns_df)

        weights = req.weights or {s: 1.0 / len(req.symbols) for s in req.symbols}
        port_risk = rm.portfolio_risk(weights, cov)
        risk_contrib = rm.risk_contribution(weights, cov)

        port_returns = sum(returns_df[s] * weights.get(s, 0) for s in returns_df.columns)
        var_val = RiskModel.compute_var(port_returns, req.confidence)
        cvar_val = RiskModel.compute_cvar(port_returns, req.confidence)

        return RiskAnalysisResponse(
            portfolio_volatility=port_risk,
            var_95=var_val,
            cvar_95=cvar_val,
            risk_contributions=risk_contrib,
            correlations={s: {s2: float(corr.loc[s, s2]) for s2 in corr.columns} for s in corr.index},
        )
    except Exception as e:
        logger.error("Risk analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


class HedgeRequest(BaseModel):
    currency_exposure: dict[str, float]  # currency -> amount
    total_nav: float


class HedgeRecommendationResponse(BaseModel):
    currency: str
    exposure_pct: float
    hedge_ratio: float
    hedge_amount: float
    reason: str


@router.post("/hedge-recommendations", response_model=list[HedgeRecommendationResponse])
async def get_hedge_recommendations(req: HedgeRequest, api_key: str = Depends(verify_api_key), _role: dict = Depends(require_role("researcher"))) -> list[HedgeRecommendationResponse]:
    """Get currency hedge recommendations."""
    try:
        from src.portfolio.currency import CurrencyHedger

        hedger = CurrencyHedger()
        exposure = {k: Decimal(str(v)) for k, v in req.currency_exposure.items()}
        recs = hedger.analyze(exposure, Decimal(str(req.total_nav)))

        return [
            HedgeRecommendationResponse(
                currency=r.currency,
                exposure_pct=float(r.gross_exposure / Decimal(str(req.total_nav)) * 100) if req.total_nav > 0 else 0.0,
                hedge_ratio=float(r.hedge_ratio),
                hedge_amount=float(r.hedged_amount),
                reason=r.reason,
            )
            for r in recs
        ]
    except Exception as e:
        logger.error("Hedge analysis failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
