"""
策略註冊表 — 集中管理策略名稱到類別的對應，供 API 和 CLI 共用。
"""

from __future__ import annotations

import functools
import inspect
import logging
from typing import Any, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.strategy.base import Strategy


@functools.lru_cache(maxsize=1)
def _load_strategy_map() -> dict[str, type[Strategy]]:
    """Lazy import 所有策略類別（結果快取，只執行一次）。"""
    from strategies.ma_crossover import MaCrossoverStrategy
    from strategies.mean_reversion import MeanReversionStrategy
    from strategies.momentum import MomentumStrategy
    from strategies.multi_factor import MultiFactorStrategy
    from strategies.pairs_trading import PairsTradingStrategy
    from strategies.revenue_momentum import RevenueMomentumStrategy
    from strategies.rsi_oversold import RsiOversoldStrategy
    from strategies.sector_rotation import SectorRotationStrategy
    from strategies.trust_follow import TrustFollowStrategy
    from strategies.revenue_momentum_hedged import RevenueMomentumHedgedStrategy
    from strategies.multi_strategy_combo import MultiStrategyCombo
    from src.alpha.strategy import AlphaStrategy
    from src.strategy.multi_asset import MultiAssetStrategy

    return {
        "momentum_12_1": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
        "rsi_oversold": RsiOversoldStrategy,
        "ma_crossover": MaCrossoverStrategy,
        "pairs_trading": PairsTradingStrategy,
        "multi_factor": MultiFactorStrategy,
        "sector_rotation": SectorRotationStrategy,
        "revenue_momentum": RevenueMomentumStrategy,
        "trust_follow": TrustFollowStrategy,
        "revenue_momentum_hedged": RevenueMomentumHedgedStrategy,
        "multi_strategy_combo": MultiStrategyCombo,
        "alpha": AlphaStrategy,
        "multi_asset": MultiAssetStrategy,
    }


# 別名：供 CLI / backtest 向後相容，不出現在策略列表中
_ALIASES: dict[str, str] = {
    "momentum": "momentum_12_1",
}


def list_strategies() -> list[str]:
    """回傳所有可用的策略名稱（不含別名）。"""
    return list(_load_strategy_map().keys())


def resolve_strategy(name: str, params: dict[str, Any] | None = None) -> Strategy:
    """
    根據名稱解析並實例化策略。

    Args:
        name: 策略名稱（需在註冊表中）
        params: 傳給策略建構子的參數（選用）

    Raises:
        ValueError: 未知的策略名稱
    """
    canonical = _ALIASES.get(name, name)
    strategy_map = _load_strategy_map()
    cls = strategy_map.get(canonical)
    if cls is None:
        raise ValueError(
            f"Unknown strategy: {name}. Available: {list(strategy_map.keys())}"
        )

    if params:
        sig = inspect.signature(cls.__init__)
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        if has_var_keyword:
            # Class accepts **kwargs — pass all params through
            return cls(**params)
        valid_params = set(sig.parameters.keys()) - {"self"}
        dropped = {k: v for k, v in params.items() if k not in valid_params}
        if dropped:
            logger.warning(
                "resolve_strategy(%s): unknown parameters ignored: %s", name, list(dropped.keys())
            )
        filtered = {k: v for k, v in params.items() if k in valid_params}
        return cls(**filtered)
    return cls()
