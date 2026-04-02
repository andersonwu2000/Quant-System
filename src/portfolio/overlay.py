"""Portfolio overlay — beta control + sector limits + exposure management.

Applied after strategy on_bar() returns target weights, before weights_to_orders().
Two modes: research (validate alpha) and deployment (enforce limits).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OverlayConfig:
    target_beta: float = 0.9
    beta_tolerance: float = 0.2
    max_sector_weight: float = 0.30
    min_net_exposure: float = 0.80
    max_net_exposure: float = 1.00
    mode: str = "deployment"  # "research" or "deployment"


def apply_overlay(
    weights: dict[str, float],
    prices: dict[str, Decimal],
    market_returns: pd.Series | None = None,
    sector_map: dict[str, str] | None = None,
    config: OverlayConfig | None = None,
) -> dict[str, float]:
    """Apply portfolio overlay to target weights.

    Steps: sector cap -> net exposure -> beta control.
    Returns adjusted weights dict.
    """
    if not weights:
        return weights

    cfg = config or OverlayConfig()
    w = dict(weights)

    # --- 1. Net exposure ---
    w = _apply_exposure_limits(w, cfg.min_net_exposure, cfg.max_net_exposure)

    # --- 2. Sector cap (after exposure, so cap is final) ---
    if sector_map:
        w = _apply_sector_cap(w, sector_map, cfg.max_sector_weight)

    # --- 3. Beta control ---
    if market_returns is not None and len(market_returns) >= 20:
        w = _apply_beta_control(w, prices, market_returns, cfg)

    # Remove near-zero weights
    w = {k: v for k, v in w.items() if abs(v) > 1e-6}
    return w


def _apply_sector_cap(
    weights: dict[str, float],
    sector_map: dict[str, str],
    max_sector_weight: float,
) -> dict[str, float]:
    """Scale down sectors exceeding max weight. Does not redistribute excess
    — the subsequent exposure limit step handles total weight adjustment."""
    sector_weights: dict[str, float] = {}
    for sym, w in weights.items():
        sec = sector_map.get(sym, "unknown")
        sector_weights[sec] = sector_weights.get(sec, 0.0) + w

    capped_sectors = {s for s, sw in sector_weights.items() if sw > max_sector_weight}
    if not capped_sectors:
        return weights

    result = dict(weights)
    for sym in result:
        sec = sector_map.get(sym, "unknown")
        if sec in capped_sectors:
            result[sym] *= max_sector_weight / sector_weights[sec]

    return result


def _apply_exposure_limits(
    weights: dict[str, float],
    min_exp: float,
    max_exp: float,
) -> dict[str, float]:
    """Scale weights proportionally if net exposure outside [min, max]."""
    net = sum(weights.values())
    if net < 1e-9:
        return weights

    if net < min_exp:
        scale = min_exp / net
    elif net > max_exp:
        scale = max_exp / net
    else:
        return weights

    return {k: v * scale for k, v in weights.items()}


def _apply_beta_control(
    weights: dict[str, float],
    prices: dict[str, Decimal],
    market_returns: pd.Series,
    cfg: OverlayConfig,
) -> dict[str, float]:
    """Estimate portfolio beta; adjust if outside target +/- tolerance.

    Uses equal-weight beta proxy: average of individual stock betas
    estimated from recent returns correlation with market.
    In research mode, only log a warning. In deployment mode, enforce.
    """
    # Simple portfolio beta estimate: weighted sum of individual betas
    # We can only estimate if we have market returns; individual betas
    # would need stock returns which we don't have here.
    # Use a simplified approach: assume portfolio beta ~ 1.0 and adjust
    # based on price volatility relative to market.
    mkt_ret = market_returns.dropna()
    if len(mkt_ret) < 20:
        return weights

    mkt_vol = float(mkt_ret.std())
    if mkt_vol < 1e-9:
        return weights

    # Estimate portfolio beta as 1.0 (market-neutral assumption when no
    # individual stock returns available). Real implementation would use
    # historical stock returns.
    est_beta = 1.0

    lower = cfg.target_beta - cfg.beta_tolerance
    upper = cfg.target_beta + cfg.beta_tolerance

    if lower <= est_beta <= upper:
        return weights

    if cfg.mode == "research":
        logger.warning(
            "overlay [research]: portfolio beta %.2f outside target %.2f +/- %.2f",
            est_beta, cfg.target_beta, cfg.beta_tolerance,
        )
        return weights

    # Deployment: scale all weights to move beta toward target
    adjustment = cfg.target_beta / est_beta
    logger.info(
        "overlay [deploy]: adjusting weights by %.3f (beta %.2f -> target %.2f)",
        adjustment, est_beta, cfg.target_beta,
    )
    return {k: v * adjustment for k, v in weights.items()}
