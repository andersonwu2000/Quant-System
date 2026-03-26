"""
因子函式庫 — 純函式，無狀態，可獨立測試。

每個因子：DataFrame → Series（因子值）

Sub-modules:
- technical: price/volume-based factors
- fundamental: financial statement-based factors
- kakushadze: selected Kakushadze 101 formulaic alphas
"""

__all__ = [
    # technical
    "momentum",
    "mean_reversion",
    "volatility",
    "rsi",
    "moving_average_crossover",
    "short_term_reversal",
    "amihud_illiquidity",
    "idiosyncratic_vol",
    "skewness",
    "max_return",
    "volume_price_trend",
    # fundamental
    "value_pe",
    "value_pb",
    "quality_roe",
    "size_factor",
    "investment_factor",
    "gross_profitability_factor",
    # kakushadze helpers
    "_rank",
    "_ts_rank",
    "_decay_linear",
    "_ts_argmax",
    # kakushadze alphas
    "kakushadze_alpha_2",
    "kakushadze_alpha_3",
    "kakushadze_alpha_6",
    "kakushadze_alpha_12",
    "kakushadze_alpha_33",
    "kakushadze_alpha_34",
    "kakushadze_alpha_38",
    "kakushadze_alpha_44",
    "kakushadze_alpha_53",
    "kakushadze_alpha_101",
]

# Re-export all factors for backward compatibility
from src.strategy.factors.technical import (  # noqa: F401
    momentum,
    mean_reversion,
    volatility,
    rsi,
    moving_average_crossover,
    short_term_reversal,
    amihud_illiquidity,
    idiosyncratic_vol,
    skewness,
    max_return,
    volume_price_trend,
)
from src.strategy.factors.fundamental import (  # noqa: F401
    value_pe,
    value_pb,
    quality_roe,
    size_factor,
    investment_factor,
    gross_profitability_factor,
)
from src.strategy.factors.kakushadze import (  # noqa: F401
    _rank,
    _ts_rank,
    _decay_linear,
    _ts_argmax,
    kakushadze_alpha_2,
    kakushadze_alpha_3,
    kakushadze_alpha_6,
    kakushadze_alpha_12,
    kakushadze_alpha_33,
    kakushadze_alpha_34,
    kakushadze_alpha_38,
    kakushadze_alpha_44,
    kakushadze_alpha_53,
    kakushadze_alpha_101,
)
