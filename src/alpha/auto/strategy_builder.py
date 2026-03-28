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

    # 支援兩種命名：compute_{name}（舊式）或 compute_factor（autoresearch 式）
    compute_fn = getattr(mod, f"compute_{factor_name}", None) or getattr(mod, "compute_factor", None)
    if compute_fn is None:
        raise AttributeError(f"No compute_{factor_name}() or compute_factor() in {factor_path}")

    # 偵測函式簽名：2-arg（舊式）或 3-arg（autoresearch）
    import inspect
    _sig = inspect.signature(compute_fn)
    _n_params = len([p for p in _sig.parameters.values()
                     if p.default is inspect.Parameter.empty])
    _needs_data = _n_params >= 3  # autoresearch factor needs (symbols, as_of, data)

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

            # Phase 1: 流動性篩選
            eligible: list[str] = []
            for sym in ctx.universe():
                try:
                    bars = ctx.bars(sym, lookback=60)
                    if len(bars) < 20:
                        continue
                    vol = float(bars["volume"].iloc[-20:].mean())
                    if vol < min_volume_lots * 1000:
                        continue
                    eligible.append(sym)
                except Exception:
                    continue

            if not eligible:
                self._last_month = month
                self._cached = {}
                return {}

            # Phase 2: batch 計算因子值（一次傳全 universe）
            try:
                if _needs_data:
                    _all_bars: dict[str, pd.DataFrame] = {}
                    _all_rev: dict[str, pd.DataFrame] = {}
                    for sym in eligible:
                        try:
                            _all_bars[sym] = ctx.bars(sym, lookback=252)
                        except Exception:
                            pass
                        try:
                            bare = sym.replace(".TW", "").replace(".TWO", "")
                            rev = ctx.get_revenue(bare, lookback_months=36)
                            if not rev.empty:
                                _all_rev[sym] = rev
                        except Exception:
                            pass
                    _data = {
                        "bars": _all_bars,
                        "revenue": _all_rev,
                        "institutional": {},
                        "pe": {}, "pb": {}, "roe": {},
                    }
                    all_values = compute_fn(eligible, as_of, _data)
                else:
                    all_values = compute_fn(eligible, as_of)
            except Exception:
                all_values = {}

            # Phase 3: 排序選股
            candidates: list[tuple[str, float]] = []
            for sym, val in all_values.items():
                if val is None:
                    continue
                candidates.append((sym, val * direction))

            self._last_month = month
            if not candidates:
                self._cached = {}
                return {}

            candidates.sort(key=lambda x: x[1], reverse=True)
            selected = candidates[:top_n]
            # direction 調整後 top 應為正值；若 direction=-1 且全部為負，
            # 取絕對值作為信號強度以避免 long_only 過濾
            signals = {s: abs(v) for s, v in selected}
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
