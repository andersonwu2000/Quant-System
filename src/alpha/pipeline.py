"""
Alpha Pipeline — 端到端的因子研究與組合建構流水線。

用一個配置檔定義完整的因子策略，自動串接：
股票池篩選 → 因子計算 → 中性化 → 正交化 → 合成 → 分位數驗證 → 組合建構 → 績效報告
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.alpha.attribution import AttributionResult, attribute_returns
from src.alpha.construction import ConstructionConfig, construct_portfolio, blend_with_decay
from src.alpha.cross_section import QuantileResult, quantile_backtest
from src.alpha.neutralize import NeutralizeMethod, neutralize, standardize, winsorize
from src.alpha.regime import RegimeICResult, classify_regimes, compute_regime_ic
from src.alpha.orthogonalize import factor_correlation_matrix, orthogonalize_sequential, orthogonalize_symmetric
from src.alpha.turnover import TurnoverResult, analyze_factor_turnover
from src.alpha.universe import UniverseConfig, UniverseFilter
from src.data.fundamentals import FundamentalsProvider
from src.strategy.research import (
    FACTOR_REGISTRY,
    FUNDAMENTAL_REGISTRY,
    DecayResult,
    ICResult,
    compute_factor_values,
    compute_forward_returns,
    compute_fundamental_factor_values,
    compute_ic,
    compute_market_returns,
    compute_rolling_ic,
    factor_decay,
)

logger = logging.getLogger(__name__)


@dataclass
class FactorSpec:
    """單因子規格。"""

    name: str  # 因子名稱 (對應 FACTOR_REGISTRY)
    direction: int = 1  # 1=越大越好, -1=越小越好
    kwargs: dict[str, object] = field(default_factory=dict)  # 因子參數覆寫


@dataclass
class AlphaConfig:
    """Alpha Pipeline 配置。"""

    # 股票池
    universe: UniverseConfig = field(default_factory=UniverseConfig)

    # 因子定義
    factors: list[FactorSpec] = field(default_factory=list)

    # 處理流程
    winsorize_bounds: tuple[float, float] = (0.01, 0.99)
    standardize_method: str = "zscore"  # "zscore" | "rank" | "rank_zscore"
    neutralize_method: NeutralizeMethod = NeutralizeMethod.MARKET
    orthogonalize: bool = False
    orthogonalize_method: str = "sequential"  # "sequential" | "symmetric"

    # 合成
    combine_method: str = "equal"  # "equal" | "ic" | "rolling_ic" | "custom"
    combine_weights: dict[str, float] | None = None
    ic_lookback: int = 60

    # 組合建構
    construction: ConstructionConfig = field(default_factory=ConstructionConfig)

    # 回測
    holding_period: int = 5
    n_quantiles: int = 5


@dataclass
class AlphaReport:
    """Alpha Pipeline 完整報告。"""

    config: AlphaConfig
    universe_counts: dict[str, int]  # 每日平均/最少/最多標的數
    # 單因子分析
    factor_ics: dict[str, ICResult] = field(default_factory=dict)
    factor_decays: dict[str, DecayResult] = field(default_factory=dict)
    factor_turnovers: dict[str, TurnoverResult] = field(default_factory=dict)
    factor_correlations: pd.DataFrame = field(default_factory=pd.DataFrame)
    # 分位數回測
    quantile_results: dict[str, QuantileResult] = field(default_factory=dict)
    # 合成 Alpha
    composite_ic: ICResult | None = None
    composite_quantile: QuantileResult | None = None
    composite_weights: dict[str, float] = field(default_factory=dict)
    # Regime 條件分析
    regime_ics: dict[str, RegimeICResult] = field(default_factory=dict)
    regime_series: pd.Series = field(default_factory=pd.Series)
    # 因子歸因
    attribution: AttributionResult | None = None
    # Equal-weight benchmark comparison (DeMiguel 2009)
    vs_equal_weight_sharpe: float | None = None

    def summary(self) -> str:
        lines = [
            "═══════════════════════════════════════",
            "         Alpha Pipeline Report         ",
            "═══════════════════════════════════════",
            "",
            f"Universe: avg {self.universe_counts.get('avg', 0)} instruments "
            f"(min {self.universe_counts.get('min', 0)}, max {self.universe_counts.get('max', 0)})",
            f"Factors: {len(self.config.factors)}",
            "",
        ]

        # 單因子 IC 表
        if self.factor_ics:
            lines.append("── Single Factor IC ──")
            lines.append(f"{'Factor':<20} {'IC':>8} {'ICIR':>8} {'Hit%':>8} {'Turnover':>10} {'Cost(bps)':>10}")
            for name, ic in self.factor_ics.items():
                to = self.factor_turnovers.get(name)
                to_str = f"{to.avg_turnover:.1%}" if to else "N/A"
                cost_str = f"{to.cost_drag_annual_bps:.0f}" if to else "N/A"
                lines.append(
                    f"{name:<20} {ic.ic_mean:>+8.4f} {ic.icir:>+8.4f} {ic.hit_rate:>7.1%} {to_str:>10} {cost_str:>10}"
                )
            lines.append("")

        # 分位數單調性
        if self.quantile_results:
            lines.append("── Quantile Monotonicity ──")
            for name, qr in self.quantile_results.items():
                lines.append(f"  {name}: monotonicity={qr.monotonicity_score:+.2f}, "
                             f"L/S sharpe={qr.long_short_sharpe:.2f}")
            lines.append("")

        # 合成 Alpha
        if self.composite_ic:
            lines.append("── Composite Alpha ──")
            lines.append(f"  IC={self.composite_ic.ic_mean:+.4f}, ICIR={self.composite_ic.icir:+.4f}")
            if self.composite_quantile:
                lines.append(f"  L/S Annual={self.composite_quantile.long_short_annual_return:+.2%}, "
                             f"Sharpe={self.composite_quantile.long_short_sharpe:.2f}, "
                             f"Mono={self.composite_quantile.monotonicity_score:+.2f}")
            if self.composite_weights:
                lines.append(f"  Weights: {self.composite_weights}")

        # Regime IC
        if self.regime_ics:
            lines.append("")
            lines.append("── Regime-Conditional IC ──")
            for name, ric in self.regime_ics.items():
                parts = []
                for regime, ic in ric.ic_by_regime.items():
                    count = ric.regime_counts.get(regime, 0)
                    parts.append(f"{regime.value}={ic.ic_mean:+.4f}(n={count})")
                lines.append(f"  {name}: {', '.join(parts)}")

        # Equal-weight benchmark comparison
        if self.vs_equal_weight_sharpe is not None:
            lines.append(f"  vs EW Sharpe diff: {self.vs_equal_weight_sharpe:+.2f}")

        # Attribution
        if self.attribution:
            lines.append("")
            lines.append("── Factor Attribution ──")
            for fname, contrib in self.attribution.factor_contributions.items():
                lines.append(f"  {fname}: {contrib:+.4f}")
            lines.append(f"  residual: {self.attribution.residual_return:+.4f}")
            lines.append(f"  total: {self.attribution.total_return:+.4f}")

        return "\n".join(lines)


class AlphaPipeline:
    """端到端的 Alpha 研究流水線。"""

    def __init__(self, config: AlphaConfig):
        self.config = config
        self._universe_filter = UniverseFilter(config.universe)
        self._prev_signal: pd.Series | None = None
        self._prev_weights: pd.Series | None = None
        self._rolling_ic_weights: dict[str, float] | None = None

    def research(
        self,
        data: dict[str, pd.DataFrame],
        fundamentals: FundamentalsProvider | None = None,
        industry_map: dict[str, str] | None = None,
        market_caps: pd.DataFrame | None = None,
    ) -> AlphaReport:
        """
        執行完整的 Alpha 研究流程。

        Args:
            data: {symbol: OHLCV DataFrame}
            fundamentals: 基本面數據提供者
            industry_map: symbol → 行業 (用於中性化)
            market_caps: 市值 DataFrame (用於中性化)
        """
        cfg = self.config

        # [1] 股票池篩選 — 取共有日期
        all_dates = _get_common_dates(data)
        if not all_dates:
            return self._empty_report()

        universe_by_date = self._universe_filter.filter_timeseries(data, all_dates, fundamentals)
        counts = [len(v) for v in universe_by_date.values()]
        universe_counts = {
            "avg": int(sum(counts) / max(len(counts), 1)),
            "min": min(counts) if counts else 0,
            "max": max(counts) if counts else 0,
        }

        logger.info("Universe: avg=%d instruments across %d dates", universe_counts["avg"], len(all_dates))

        # [2] 逐因子計算
        raw_factors: dict[str, pd.DataFrame] = {}
        for spec in cfg.factors:
            if spec.name in FACTOR_REGISTRY:
                fv = compute_factor_values(data, spec.name, dates=all_dates, **spec.kwargs)
            elif spec.name in FUNDAMENTAL_REGISTRY and fundamentals is not None:
                symbols = sorted(data.keys())
                fv = compute_fundamental_factor_values(symbols, spec.name, fundamentals, all_dates)
            else:
                logger.warning("Unknown factor: %s (or no fundamentals provider), skipping", spec.name)
                continue
            if not fv.empty:
                if spec.direction == -1:
                    fv = -fv
                raw_factors[spec.name] = fv

        if not raw_factors:
            logger.warning("No valid factors computed")
            return self._empty_report(universe_counts=universe_counts)

        # [3] Winsorize + Standardize
        processed: dict[str, pd.DataFrame] = {}
        for name, fv in raw_factors.items():
            fv = winsorize(fv, cfg.winsorize_bounds[0], cfg.winsorize_bounds[1])
            fv = standardize(fv, cfg.standardize_method)
            processed[name] = fv

        # [4] 中性化
        neutralized: dict[str, pd.DataFrame] = {}
        for name, fv in processed.items():
            try:
                fv = neutralize(fv, cfg.neutralize_method, industry_map, market_caps)
            except ValueError:
                logger.warning("Neutralization failed for %s (missing data), using market neutral", name)
                fv = neutralize(fv, NeutralizeMethod.MARKET)
            neutralized[name] = fv

        # [5] 單因子分析
        factor_ics: dict[str, ICResult] = {}
        factor_decays: dict[str, DecayResult] = {}
        factor_turnovers: dict[str, TurnoverResult] = {}
        quantile_results: dict[str, QuantileResult] = {}

        # 預先計算共用的 forward returns（避免重複計算）
        fwd_cache: dict[str, pd.DataFrame] = {}

        for name, fv in neutralized.items():
            dates_key = str(fv.index[0]) + "_" + str(fv.index[-1]) + "_" + str(len(fv))
            if dates_key not in fwd_cache:
                fwd_cache[dates_key] = compute_forward_returns(
                    data, horizon=cfg.holding_period, dates=list(fv.index)
                )
            fwd = fwd_cache[dates_key]

            # IC
            ic = compute_ic(fv, fwd)
            ic.factor_name = name
            factor_ics[name] = ic

            # 衰減
            decay = factor_decay(data, name, dates=list(fv.index))
            factor_decays[name] = decay

            # 分位數回測
            qr = quantile_backtest(fv, fwd, n_quantiles=cfg.n_quantiles, factor_name=name)
            quantile_results[name] = qr

            # 換手率
            to = analyze_factor_turnover(
                fv,
                n_quantiles=cfg.n_quantiles,
                holding_period=cfg.holding_period,
                cost_bps=cfg.construction.cost_bps,
                gross_ic=ic.ic_mean,
                factor_name=name,
            )
            factor_turnovers[name] = to

        # [5b] Regime 條件分析
        regime_ics: dict[str, RegimeICResult] = {}
        regime_series = pd.Series(dtype=object)
        try:
            mkt_ret = compute_market_returns(data)
            regime_series = classify_regimes(mkt_ret)

            if not regime_series.empty:
                for name, fv in neutralized.items():
                    dates_key = str(fv.index[0]) + "_" + str(fv.index[-1]) + "_" + str(len(fv))
                    cached_fwd = fwd_cache.get(dates_key)
                    fwd = cached_fwd if cached_fwd is not None else compute_forward_returns(
                        data, horizon=cfg.holding_period, dates=list(fv.index)
                    )
                    ric = compute_regime_ic(fv, fwd, regime_series, factor_name=name)
                    regime_ics[name] = ric
        except Exception:
            logger.warning("Regime analysis failed, skipping", exc_info=True)

        # 因子相關矩陣
        corr_matrix = factor_correlation_matrix(neutralized)

        # [6] 正交化
        if cfg.orthogonalize and len(neutralized) > 1:
            if cfg.orthogonalize_method == "symmetric":
                orthogonalized = orthogonalize_symmetric(neutralized)
            else:
                priority = [s.name for s in cfg.factors if s.name in neutralized]
                orthogonalized = orthogonalize_sequential(neutralized, priority)
        else:
            orthogonalized = neutralized

        # [7] 因子合成
        composite_fv, composite_weights = self._combine(orthogonalized, data, factor_ics)

        # [8] 合成因子分析
        composite_ic: ICResult | None = None
        composite_quantile: QuantileResult | None = None

        if composite_fv is not None and not composite_fv.empty:
            fwd = compute_forward_returns(data, horizon=cfg.holding_period, dates=list(composite_fv.index))
            composite_ic = compute_ic(composite_fv, fwd)
            composite_ic.factor_name = "composite"
            composite_quantile = quantile_backtest(
                composite_fv, fwd, n_quantiles=cfg.n_quantiles, factor_name="composite"
            )

        # [8b] Equal-weight benchmark Sharpe comparison (DeMiguel 2009)
        vs_equal_weight_sharpe: float | None = None
        if composite_quantile is not None and composite_fv is not None and not composite_fv.empty:
            try:
                # Equal-weight portfolio: mean of all forward returns across symbols
                ew_fwd = compute_forward_returns(data, horizon=cfg.holding_period, dates=list(composite_fv.index))
                if not ew_fwd.empty:
                    ew_returns = ew_fwd.mean(axis=1).dropna()
                    if len(ew_returns) > 1 and ew_returns.std() > 0:
                        ew_sharpe = float(ew_returns.mean() / ew_returns.std() * np.sqrt(252 / cfg.holding_period))
                        vs_equal_weight_sharpe = composite_quantile.long_short_sharpe - ew_sharpe
                        logger.info(
                            "Composite L/S Sharpe=%.2f, EW Sharpe=%.2f, diff=%.2f",
                            composite_quantile.long_short_sharpe, ew_sharpe, vs_equal_weight_sharpe,
                        )
            except Exception:
                logger.warning("Equal-weight Sharpe comparison failed, skipping", exc_info=True)

        # [9] 因子歸因
        attribution: AttributionResult | None = None
        if composite_quantile is not None and composite_weights and len(quantile_results) > 1:
            try:
                factor_ls_returns = {
                    name: qr.long_short_return
                    for name, qr in quantile_results.items()
                    if not qr.long_short_return.empty
                }
                if factor_ls_returns:
                    attribution = attribute_returns(
                        composite_returns=composite_quantile.long_short_return,
                        factor_returns=factor_ls_returns,
                        composite_weights=composite_weights,
                    )
            except Exception:
                logger.warning("Attribution analysis failed, skipping", exc_info=True)

        return AlphaReport(
            config=cfg,
            universe_counts=universe_counts,
            factor_ics=factor_ics,
            factor_decays=factor_decays,
            factor_turnovers=factor_turnovers,
            factor_correlations=corr_matrix,
            quantile_results=quantile_results,
            composite_ic=composite_ic,
            composite_quantile=composite_quantile,
            composite_weights=composite_weights,
            regime_ics=regime_ics,
            regime_series=regime_series,
            attribution=attribution,
            vs_equal_weight_sharpe=vs_equal_weight_sharpe,
        )

    def generate_weights(
        self,
        data: dict[str, pd.DataFrame],
        current_date: pd.Timestamp,
        current_weights: pd.Series | None = None,
        fundamentals: FundamentalsProvider | None = None,
        industry_map: dict[str, str] | None = None,
        market_caps: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        """
        生產模式：給定當前數據和日期，產出目標權重。
        供 AlphaStrategy.on_bar() 調用。
        """
        cfg = self.config

        # 股票池篩選
        universe = self._universe_filter.filter(data, current_date, fundamentals)
        if not universe:
            return {}

        # 計算因子值
        factor_values: dict[str, pd.Series] = {}
        for spec in cfg.factors:
            if spec.name in FACTOR_REGISTRY:
                fv = compute_factor_values(data, spec.name, dates=[current_date], **spec.kwargs)
            elif spec.name in FUNDAMENTAL_REGISTRY and fundamentals is not None:
                symbols = sorted(data.keys())
                fv = compute_fundamental_factor_values(symbols, spec.name, fundamentals, [current_date])
            else:
                continue
            if not fv.empty:
                row = fv.iloc[0].dropna()
                if spec.direction == -1:
                    row = -row
                # 只保留在 universe 中的標的
                row = row.reindex([s for s in row.index if s in universe]).dropna()
                if not row.empty:
                    factor_values[spec.name] = row

        if not factor_values:
            return {}

        # 合成 Alpha 信號
        alpha_signal = self._combine_signals(factor_values)

        # Alpha 衰減混合
        if cfg.construction.half_life is not None and self._prev_signal is not None:
            alpha_signal = blend_with_decay(alpha_signal, self._prev_signal, cfg.construction.half_life)
        self._prev_signal = alpha_signal

        # 成本感知組合建構
        weights = construct_portfolio(
            alpha_signal=alpha_signal,
            current_weights=current_weights if current_weights is not None else self._prev_weights,
            config=cfg.construction,
        )

        self._prev_weights = pd.Series(weights) if weights else None
        return weights

    def _combine(
        self,
        factor_dict: dict[str, pd.DataFrame],
        data: dict[str, pd.DataFrame],
        factor_ics: dict[str, ICResult],
    ) -> tuple[pd.DataFrame | None, dict[str, float]]:
        """合成多因子。"""
        cfg = self.config
        names = list(factor_dict.keys())

        if len(names) == 0:
            return None, {}

        if len(names) == 1:
            return factor_dict[names[0]], {names[0]: 1.0}

        if cfg.combine_method == "custom" and cfg.combine_weights:
            weights = cfg.combine_weights
        elif cfg.combine_method == "ic":
            # IC 加權（全樣本）
            total_abs_ic = sum(abs(factor_ics[n].ic_mean) for n in names if n in factor_ics)
            if total_abs_ic > 0:
                weights = {n: abs(factor_ics[n].ic_mean) / total_abs_ic for n in names if n in factor_ics}
            else:
                weights = {n: 1.0 / len(names) for n in names}
        elif cfg.combine_method == "rolling_ic":
            # Rolling IC 動態加權 — 逐日根據 trailing IC 加權
            return self._combine_rolling_ic(factor_dict, data)
        else:
            weights = {n: 1.0 / len(names) for n in names}

        # 加權合成
        sorted_dates, sorted_symbols = _intersect_factor_frames(factor_dict)
        if not sorted_dates or not sorted_symbols:
            return None, weights

        composite = pd.DataFrame(0.0, index=sorted_dates, columns=sorted_symbols)
        for name, fv in factor_dict.items():
            w = weights.get(name, 0.0)
            composite += fv.reindex(index=sorted_dates, columns=sorted_symbols).fillna(0) * w

        return composite, weights

    def _combine_rolling_ic(
        self,
        factor_dict: dict[str, pd.DataFrame],
        data: dict[str, pd.DataFrame],
    ) -> tuple[pd.DataFrame | None, dict[str, float]]:
        """Rolling IC 動態加權合成。"""
        cfg = self.config
        names = list(factor_dict.keys())

        sorted_dates, sorted_symbols = _intersect_factor_frames(factor_dict)
        if not sorted_dates or not sorted_symbols:
            return None, {}

        fwd = compute_forward_returns(data, horizon=cfg.holding_period, dates=sorted_dates)

        # 計算每個因子的 rolling IC
        rolling_ics: dict[str, pd.Series] = {}
        for name, fv in factor_dict.items():
            ric = compute_rolling_ic(fv, fwd, window=cfg.ic_lookback)
            if not ric.empty:
                rolling_ics[name] = ric

        equal_weights = {n: 1.0 / len(names) for n in names}

        if not rolling_ics:
            # 退化為等權
            composite = pd.DataFrame(0.0, index=sorted_dates, columns=sorted_symbols)
            for name, fv in factor_dict.items():
                composite += fv.reindex(index=sorted_dates, columns=sorted_symbols).fillna(0) * equal_weights[name]
            self._rolling_ic_weights = equal_weights
            return composite, equal_weights

        # 建構每日權重矩陣（向量化）
        ic_df = pd.DataFrame(rolling_ics).reindex(sorted_dates).abs()
        ic_totals = ic_df.sum(axis=1)
        # 有 IC 的日期按 |IC| 正規化，無 IC 的日期用等權
        weight_df = ic_df.div(ic_totals, axis=0)
        equal_fill = pd.DataFrame(
            {n: [equal_weights[n]] * len(sorted_dates) for n in names},
            index=sorted_dates,
        )
        weight_df = weight_df.fillna(equal_fill)
        # 未出現在 rolling_ics 中的因子填等權
        for n in names:
            if n not in weight_df.columns:
                weight_df[n] = equal_weights[n]

        # 向量化加權合成
        composite = pd.DataFrame(0.0, index=sorted_dates, columns=sorted_symbols)
        for name, fv in factor_dict.items():
            aligned = fv.reindex(index=sorted_dates, columns=sorted_symbols).fillna(0)
            w_series = weight_df[name] if name in weight_df.columns else equal_weights[name]
            composite += aligned.mul(w_series, axis=0)

        avg_weights = {n: float(weight_df[n].mean()) for n in names}
        self._rolling_ic_weights = avg_weights
        return composite, avg_weights

    def _combine_signals(self, factor_values: dict[str, pd.Series]) -> pd.Series:
        """合成單期信號（用於 generate_weights）。"""
        cfg = self.config
        names = list(factor_values.keys())

        if len(names) == 1:
            return factor_values[names[0]]

        if cfg.combine_method == "custom" and cfg.combine_weights:
            weights = cfg.combine_weights
        elif cfg.combine_method == "rolling_ic" and self._rolling_ic_weights:
            weights = self._rolling_ic_weights
        else:
            # 等權
            weights = {n: 1.0 / len(names) for n in names}

        all_symbols = set()
        for s in factor_values.values():
            all_symbols |= set(s.index)
        all_symbols_list = sorted(all_symbols)

        composite = pd.Series(0.0, index=all_symbols_list)
        for name, fv in factor_values.items():
            w = weights.get(name, 0.0)
            aligned = fv.reindex(all_symbols_list, fill_value=0.0)
            composite += aligned * w

        return composite

    def _empty_report(self, universe_counts: dict[str, int] | None = None) -> AlphaReport:
        return AlphaReport(
            config=self.config,
            universe_counts=universe_counts or {"avg": 0, "min": 0, "max": 0},
        )


def _get_common_dates(data: dict[str, pd.DataFrame]) -> list[pd.Timestamp]:
    """取所有標的的共有日期。"""
    all_dates: set[pd.Timestamp] | None = None
    for df in data.values():
        sym_dates = set(df.index)
        all_dates = sym_dates if all_dates is None else all_dates & sym_dates
    return sorted(all_dates or set())


def _intersect_factor_frames(
    factor_dict: dict[str, pd.DataFrame],
) -> tuple[list[pd.Timestamp], list[str]]:
    """取所有因子 DataFrame 的共有日期和標的。"""
    common_dates: set[pd.Timestamp] | None = None
    common_symbols: set[str] | None = None
    for fv in factor_dict.values():
        d = set(fv.index)
        s = set(fv.columns)
        common_dates = d if common_dates is None else common_dates & d
        common_symbols = s if common_symbols is None else common_symbols & s
    return sorted(common_dates or set()), sorted(common_symbols or set())


