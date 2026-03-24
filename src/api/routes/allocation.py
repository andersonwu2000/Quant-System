"""Tactical Allocation API routes."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth import require_role, verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/allocation", tags=["allocation"])


# ── Schemas ─────────────────────────────────────────────────


class TacticalRequest(BaseModel):
    """戰術配置計算請求。"""

    strategic_weights: dict[str, float] | None = None  # AssetClass → weight
    start: str | None = None  # FRED 數據起始日
    end: str | None = None
    macro_weight: float = Field(default=0.5, ge=0, le=1)
    cross_asset_weight: float = Field(default=0.3, ge=0, le=1)
    regime_weight: float = Field(default=0.2, ge=0, le=1)
    max_deviation: float = Field(default=0.15, ge=0.01, le=0.5)


class TacticalWeightItem(BaseModel):
    asset_class: str
    strategic_weight: float
    tactical_weight: float
    deviation: float


class MacroSignalItem(BaseModel):
    name: str
    value: float


class TacticalResponse(BaseModel):
    weights: list[TacticalWeightItem]
    macro_signals: list[MacroSignalItem]
    regime: str
    cross_asset_signals: dict[str, float]


# ── Endpoints ───────────────────────────────────────────────


@router.post("", response_model=TacticalResponse)
async def compute_tactical_allocation(
    req: TacticalRequest,
    api_key: str = Depends(verify_api_key),
    _role: dict[str, Any] = Depends(require_role("researcher")),
) -> TacticalResponse:
    """計算戰術資產配置。

    結合宏觀因子 + 跨資產信號 + 市場狀態 → 資產類別權重。
    """
    from src.allocation.macro_factors import MacroFactorModel
    from src.allocation.tactical import (
        StrategicAllocation,
        TacticalConfig,
        TacticalEngine,
    )
    from src.alpha.regime import MarketRegime, classify_regimes
    from src.domain.models import AssetClass

    # 1. 解析戰略配置
    ac_map = {
        "EQUITY": AssetClass.EQUITY,
        "ETF": AssetClass.ETF,
        "FUTURE": AssetClass.FUTURE,
    }
    if req.strategic_weights:
        parsed_weights = {}
        for k, v in req.strategic_weights.items():
            ac = ac_map.get(k.upper())
            if ac is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown asset class: {k}. Use EQUITY/ETF/FUTURE.",
                )
            parsed_weights[ac] = v
        strategic = StrategicAllocation(weights=parsed_weights)
    else:
        strategic = StrategicAllocation()

    # 2. 計算宏觀信號
    macro_model = MacroFactorModel()
    try:
        macro_model.load_data(start=req.start, end=req.end)
    except Exception:
        logger.warning("Failed to load FRED data, using zero signals", exc_info=True)

    macro_signals_obj = macro_model.compute_signals()
    macro_dict = macro_signals_obj.to_dict()

    # 3. 判斷市場狀態（用 VIX 或 equity returns 作 proxy）
    regime = MarketRegime.SIDEWAYS
    if macro_model._panel is not None and "vix" in macro_model._panel.columns:
        vix = macro_model._panel["vix"].dropna()
        if len(vix) > 60:
            # 用 VIX 變化作為 market returns 的 proxy（反向）
            vix_ret = -vix.pct_change().dropna()
            regime_series = classify_regimes(vix_ret)
            if not regime_series.empty:
                regime = regime_series.iloc[-1]

    # 4. 跨資產信號（簡化版：用宏觀面板的近似 proxy）
    ca_signals: dict[AssetClass, float] = {}
    # 跨資產信號需要各資產類別的價格序列，此 API 用宏觀 proxy 簡化
    for ac in strategic.weights:
        ca_signals[ac] = 0.0

    # 5. 合成戰術配置
    config = TacticalConfig(
        max_deviation=req.max_deviation,
        macro_weight=req.macro_weight,
        cross_asset_weight=req.cross_asset_weight,
        regime_weight=req.regime_weight,
    )
    engine = TacticalEngine(strategic=strategic, config=config)
    tactical_weights = engine.compute(
        macro_signals=macro_dict,
        cross_asset_signals=ca_signals,
        regime=regime,
    )

    # 6. 組裝回應
    weight_items = []
    for ac, tac_w in tactical_weights.items():
        strat_w = strategic.weights.get(ac, 0.0)
        weight_items.append(TacticalWeightItem(
            asset_class=ac.value,
            strategic_weight=round(strat_w, 4),
            tactical_weight=round(tac_w, 4),
            deviation=round(tac_w - strat_w, 4),
        ))

    macro_items = [
        MacroSignalItem(name=k, value=round(v, 4))
        for k, v in macro_dict.items()
    ]

    ca_out = {ac.value: round(v, 4) for ac, v in ca_signals.items()}

    return TacticalResponse(
        weights=weight_items,
        macro_signals=macro_items,
        regime=regime.value if isinstance(regime, MarketRegime) else str(regime),
        cross_asset_signals=ca_out,
    )
