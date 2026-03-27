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
    """從研究因子自動建構策略。

    動態載入 src/strategy/factors/research/{factor_name}.py 中的
    compute_{factor_name}() 函式，包裝成 Strategy 子類。
    """
    import importlib.util
    from pathlib import Path

    import pandas as pd

    from src.strategy.base import Context, Strategy as StrategyBase
    from src.strategy.optimizer import signal_weight, OptConstraints

    factor_path = Path("src/strategy/factors/research") / f"{factor_name}.py"
    if not factor_path.exists():
        raise FileNotFoundError(f"Research factor not found: {factor_path}")

    # Dynamic import
    spec = importlib.util.spec_from_file_location(f"research_{factor_name}", factor_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {factor_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    compute_fn_or_none = getattr(mod, f"compute_{factor_name}", None)
    if compute_fn_or_none is None:
        raise AttributeError(f"No compute_{factor_name}() in {factor_path}")
    compute_fn = compute_fn_or_none

    class ResearchFactorStrategy(StrategyBase):
        """Auto-built strategy from research factor."""

        def __init__(self) -> None:
            self._last_month = ""
            self._cached: dict[str, float] = {}

        def name(self) -> str:
            return f"auto_{factor_name}"

        def on_bar(self, ctx: Context) -> dict[str, float]:
            current_date = ctx.now()
            month = pd.Timestamp(current_date).strftime("%Y-%m")
            if month == self._last_month:
                return self._cached

            as_of = pd.Timestamp(current_date)
            candidates: list[tuple[str, float]] = []

            for sym in ctx.universe():
                try:
                    bars = ctx.bars(sym, lookback=60)
                    if len(bars) < 20:
                        continue
                    vol = float(bars["volume"].iloc[-20:].mean())
                    if vol < min_volume_lots * 1000:
                        continue
                except Exception:
                    continue

                try:
                    values = compute_fn([sym], as_of)
                    val = values.get(sym)
                    if val is None:
                        continue
                    # 不過濾 val 的正負（計數型因子 val=0 也是有效信號）
                    # 用 direction 決定排序方向（direction=1 → 越大越好）
                    candidates.append((sym, val * direction))
                except Exception:
                    continue

            self._last_month = month
            if not candidates:
                self._cached = {}
                return {}

            candidates.sort(key=lambda x: x[1], reverse=True)
            selected = candidates[:top_n]
            signals = {s: v for s, v in selected}
            weights = signal_weight(signals, OptConstraints(max_weight=max_weight, max_total_weight=0.95))
            self._cached = weights
            return weights

    strategy = ResearchFactorStrategy()

    return BuiltStrategy(
        name=f"auto_{factor_name}",
        factor_name=factor_name,
        config={
            "factor_name": factor_name,
            "direction": direction,
            "top_n": top_n,
            "min_volume_lots": min_volume_lots,
            "max_weight": max_weight,
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
