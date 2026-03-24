"""
AlphaStrategy 適配器 — 將 AlphaPipeline 包裝為標準 Strategy 子類。

使 AlphaPipeline 產出的權重能直接接入：
- BacktestEngine.run() 回測
- API /backtest 端點
- 未來的 Paper/Live Trading
"""

from __future__ import annotations

import pandas as pd

from src.alpha.pipeline import AlphaConfig, AlphaPipeline
from src.strategy.base import Context, Strategy


class AlphaStrategy(Strategy):
    """Alpha Pipeline 的 Strategy 適配器。"""

    def __init__(
        self,
        config: AlphaConfig | None = None,
        factors: list[str] | None = None,
        **kwargs: object,
    ):
        """
        Args:
            config: 完整的 AlphaConfig (優先使用)
            factors: 快捷方式 — 因子名稱列表，自動建立預設配置
            **kwargs: 覆寫 AlphaConfig 的預設值
        """
        if config is not None:
            self._config = config
        elif factors is not None:
            from src.alpha.pipeline import FactorSpec
            specs = [FactorSpec(name=f) for f in factors]
            self._config = AlphaConfig(factors=specs)
        else:
            # 預設：動量 + 均值回歸 + 波動率
            from src.alpha.pipeline import FactorSpec
            self._config = AlphaConfig(
                factors=[
                    FactorSpec(name="momentum"),
                    FactorSpec(name="mean_reversion"),
                    FactorSpec(name="volatility", direction=-1),
                ],
            )

        self._pipeline = AlphaPipeline(self._config)

    def name(self) -> str:
        factor_names = [f.name for f in self._config.factors]
        return f"alpha_{'_'.join(factor_names)}"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        """從 Alpha Pipeline 產出目標權重。"""
        universe = ctx.universe()
        if not universe:
            return {}

        # 收集數據
        data: dict[str, pd.DataFrame] = {}
        for sym in universe:
            bars = ctx.bars(sym, lookback=max(self._config.universe.min_listing_days, 252) + 60)
            if not bars.empty:
                data[sym] = bars

        if not data:
            return {}

        # 收集行業映射
        industry_map: dict[str, str] | None = None
        fundamentals = None
        if hasattr(ctx, "_fundamentals") and ctx._fundamentals is not None:
            fundamentals = ctx._fundamentals
            industry_map = {}
            for sym in data:
                sector = ctx.sector(sym)
                if sector:
                    industry_map[sym] = sector

        # 取得當前持倉權重
        portfolio = ctx.portfolio()
        current_weights: pd.Series | None = None
        if portfolio.positions:
            nav = float(portfolio.nav)
            if nav > 0:
                w = {}
                for sym, pos in portfolio.positions.items():
                    w[sym] = float(pos.market_value) / nav
                current_weights = pd.Series(w)

        weights = self._pipeline.generate_weights(
            data=data,
            current_date=pd.Timestamp(ctx.now()),
            current_weights=current_weights,
            fundamentals=fundamentals,
            industry_map=industry_map,
        )

        return weights
