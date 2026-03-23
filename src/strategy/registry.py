"""
策略註冊表 — 集中管理策略名稱到類別的對應，供 API 和 CLI 共用。
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, TYPE_CHECKING

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
    from strategies.rsi_oversold import RsiOversoldStrategy
    from strategies.sector_rotation import SectorRotationStrategy

    return {
        "momentum_12_1": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
        "rsi_oversold": RsiOversoldStrategy,
        "ma_crossover": MaCrossoverStrategy,
        "pairs_trading": PairsTradingStrategy,
        "multi_factor": MultiFactorStrategy,
        "sector_rotation": SectorRotationStrategy,
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
        valid_params = set(inspect.signature(cls.__init__).parameters.keys()) - {"self"}
        filtered = {k: v for k, v in params.items() if k in valid_params}
        return cls(**filtered)
    return cls()
