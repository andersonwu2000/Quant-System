"""Auto Strategy Builder — 將通過驗證的因子自動包裝成可交易策略。

從 Phase P 研究結果或手動指定的因子，自動建構 FilterStrategy 配置，
產出可直接回測或部署到 Paper Trading 的策略實例。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.alpha.filter_strategy import FilterCondition, FilterStrategy, FilterStrategyConfig
from src.strategy.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class BuiltStrategy:
    """自動建構的策略描述。"""
    name: str
    factor_name: str
    config: dict[str, Any]
    strategy: Strategy
    source: str  # "auto_research" | "manual"
    created_at: str = ""
    validation_score: int = 0  # StrategyValidator 通過項數


def build_from_research_factor(
    factor_name: str,
    direction: int = 1,
    top_n: int = 15,
    min_volume_lots: int = 300,
    max_weight: float = 0.10,
) -> BuiltStrategy:
    """從研究因子自動建構 FilterStrategy。

    Parameters
    ----------
    factor_name : 因子名稱（需在 src/strategy/factors/research/ 中有對應 .py）
    direction : 因子方向（+1 = 高分好，-1 = 低分好）
    top_n : 取前 N 檔
    min_volume_lots : 最低日均量（張）
    max_weight : 單一持股上限
    """
    operator = "gt" if direction > 0 else "lt"
    threshold = 0.0  # 基本門檻：因子值 > 0（正向）

    config = FilterStrategyConfig(
        filters=[
            FilterCondition(
                factor_name=factor_name,
                operator=operator,
                threshold=threshold,
            ),
            FilterCondition(
                factor_name="volume_20d_avg",
                operator="gt",
                threshold=float(min_volume_lots),
            ),
        ],
        rank_by=factor_name,
        top_n=top_n,
        rebalance="monthly",
        max_weight=max_weight,
    )

    strategy = FilterStrategy(config)

    return BuiltStrategy(
        name=f"auto_{factor_name}",
        factor_name=factor_name,
        config={
            "factor_name": factor_name,
            "direction": direction,
            "top_n": top_n,
            "min_volume_lots": min_volume_lots,
            "max_weight": max_weight,
            "operator": operator,
        },
        strategy=strategy,
        source="auto_research",
        created_at=datetime.now().isoformat(),
    )


def build_revenue_variant(
    min_yoy: float = 10.0,
    max_holdings: int = 20,
    enable_hedge: bool = True,
) -> BuiltStrategy:
    """建構 revenue_momentum 變體（用於參數搜索）。"""
    from strategies.revenue_momentum import RevenueMomentumStrategy

    strategy = RevenueMomentumStrategy(
        max_holdings=max_holdings,
        min_yoy_growth=min_yoy,
        weight_method="signal",
        enable_regime_hedge=enable_hedge,
    )

    return BuiltStrategy(
        name=f"rev_mom_yoy{min_yoy:.0f}_n{max_holdings}{'_hedge' if enable_hedge else ''}",
        factor_name="revenue_yoy",
        config={
            "min_yoy_growth": min_yoy,
            "max_holdings": max_holdings,
            "enable_regime_hedge": enable_hedge,
        },
        strategy=strategy,
        source="manual",
        created_at=datetime.now().isoformat(),
    )


def save_built_strategy(built: BuiltStrategy, output_dir: str = "data/research/strategies") -> str:
    """存策略配置到 JSON。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{built.name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "name": built.name,
            "factor_name": built.factor_name,
            "config": built.config,
            "source": built.source,
            "created_at": built.created_at,
            "validation_score": built.validation_score,
        }, f, indent=2, ensure_ascii=False)
    return str(path)
