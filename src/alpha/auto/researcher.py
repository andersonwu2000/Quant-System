"""AlphaResearcher — daily factor research wrapping AlphaPipeline."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import pandas as pd

from src.alpha.auto.config import AutoAlphaConfig, FactorScore, ResearchSnapshot
from src.alpha.pipeline import AlphaPipeline, AlphaReport
from src.alpha.regime import MarketRegime, classify_regimes
from src.strategy.research import compute_market_returns

logger = logging.getLogger(__name__)


class AlphaResearcher:
    """Daily factor research — wraps AlphaPipeline.research() and produces ResearchSnapshot."""

    def __init__(self, config: AutoAlphaConfig) -> None:
        self._config = config

    def run(
        self,
        universe: list[str],
        data: dict[str, pd.DataFrame] | None = None,
    ) -> ResearchSnapshot:
        """Execute full factor research for the given universe.

        Parameters
        ----------
        universe : list[str]
            Symbols to research.
        data : dict[str, pd.DataFrame] | None
            Pre-loaded OHLCV data.  If not provided, data is fetched
            via the configured DataFeed for ``lookback`` trading days.

        Returns
        -------
        ResearchSnapshot
        """
        cfg = self._config

        # 1. Fetch data if not provided
        if data is None:
            data = self._fetch_data(universe)

        # Filter data to only include universe symbols that have data
        data = {s: df for s, df in data.items() if s in universe and not df.empty}
        if not data:
            logger.warning("No data available for universe, returning empty snapshot")
            return ResearchSnapshot(
                date=date.today(),
                universe=universe,
                universe_size=len(universe),
            )

        # 2. Run AlphaPipeline.research()
        pipeline = AlphaPipeline(cfg.alpha_config)
        report = pipeline.research(data)

        # 3. Classify current regime
        current_regime = MarketRegime.SIDEWAYS
        try:
            mkt_ret = compute_market_returns(data)
            regime_series = classify_regimes(mkt_ret)
            if not regime_series.empty:
                current_regime = regime_series.iloc[-1]
        except Exception:
            logger.warning(
                "Regime classification failed, defaulting to SIDEWAYS",
                exc_info=True,
            )

        # 4. Build ResearchSnapshot from AlphaReport
        factor_scores = self._report_to_scores(report)

        # Determine which factors are eligible based on decision config
        selected_factors = [
            name for name, score in factor_scores.items() if score.eligible
        ]

        snapshot = ResearchSnapshot(
            date=date.today(),
            regime=current_regime,
            universe=universe,
            universe_size=len(universe),
            factor_scores=factor_scores,
            selected_factors=selected_factors,
            factor_weights=report.composite_weights,
            target_weights={},
        )

        return snapshot

    def _fetch_data(self, universe: list[str]) -> dict[str, pd.DataFrame]:
        """Fetch historical bars for universe symbols using DataFeed factory."""
        from src.data.sources import create_feed

        lookback_days = int(self._config.lookback * 1.5)  # extra margin for holidays
        end = datetime.now()
        start = end - timedelta(days=lookback_days)

        feed = create_feed("yahoo", universe)
        result: dict[str, pd.DataFrame] = {}
        for sym in universe:
            try:
                bars = feed.get_bars(sym, start=start, end=end)
                if not bars.empty:
                    result[sym] = bars
            except Exception:
                logger.warning("Failed to fetch data for %s", sym, exc_info=True)

        return result

    def _report_to_scores(self, report: AlphaReport) -> dict[str, FactorScore]:
        """Extract per-factor FactorScore from an AlphaReport."""
        cfg = self._config
        scores: dict[str, FactorScore] = {}

        for name, ic_result in report.factor_ics.items():
            # Turnover info
            turnover_result = report.factor_turnovers.get(name)
            avg_turnover = turnover_result.avg_turnover if turnover_result else 0.0
            cost_drag = (
                turnover_result.cost_drag_annual_bps if turnover_result else 0.0
            )

            # Decay half-life
            decay_result = report.factor_decays.get(name)
            half_life = (
                self._estimate_half_life(decay_result) if decay_result else 0
            )

            # Quantile results for long/short sharpe
            quantile_result = report.quantile_results.get(name)
            ls_sharpe = (
                quantile_result.long_short_sharpe if quantile_result else 0.0
            )

            # Regime IC
            regime_ic: dict[str, float] = {}
            regime_result = report.regime_ics.get(name)
            if regime_result:
                for regime, ric in regime_result.ic_by_regime.items():
                    regime_ic[regime.value] = ric.ic_mean

            # Eligibility check
            eligible = (
                abs(ic_result.icir) >= cfg.min_icir
                and ic_result.hit_rate >= cfg.min_hit_rate
                and cost_drag <= cfg.max_cost_drag
            )

            scores[name] = FactorScore(
                name=name,
                ic=ic_result.ic_mean,
                icir=ic_result.icir,
                hit_rate=ic_result.hit_rate,
                decay_half_life=half_life,
                turnover=avg_turnover,
                cost_drag_bps=cost_drag,
                regime_ic=regime_ic,
                long_short_sharpe=ls_sharpe,
                eligible=eligible,
            )

        return scores

    @staticmethod
    def _estimate_half_life(decay_result: object) -> int:
        """Estimate factor half-life from decay analysis.

        Uses the first horizon where IC drops below 50% of max IC.
        """
        horizons = getattr(decay_result, "horizons", [])
        ic_by_horizon = getattr(decay_result, "ic_by_horizon", {})

        if not horizons or not ic_by_horizon:
            return 0

        max_ic = max(abs(ic_by_horizon.get(h, 0.0)) for h in horizons)
        if max_ic == 0:
            return 0

        threshold = max_ic * 0.5
        for h in horizons:
            if abs(ic_by_horizon.get(h, 0.0)) < threshold:
                return int(h)
        return int(horizons[-1]) if horizons else 0
