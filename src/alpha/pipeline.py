"""
Alpha Pipeline — 端到端的因子研究與組合建構流水線。

用一個配置檔定義完整的因子策略，自動串接：
股票池篩選 → 因子計算 → 中性化 → 正交化 → 合成 → 分位數驗證 → 組合建構 → 績效報告
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from src.alpha.construction import ConstructionConfig, construct_portfolio, blend_with_decay
from src.alpha.cross_section import QuantileResult, quantile_backtest
from src.alpha.neutralize import NeutralizeMethod, neutralize, standardize, winsorize
from src.alpha.orthogonalize import factor_correlation_matrix, orthogonalize_sequential, orthogonalize_symmetric
from src.alpha.turnover import TurnoverResult, analyze_factor_turnover
from src.alpha.universe import UniverseConfig, UniverseFilter
from src.data.fundamentals import FundamentalsProvider
from src.strategy.research import (
    FACTOR_REGISTRY,
    CompositeResult,
    DecayResult,
    ICResult,
    combine_factors,
    compute_factor_values,
    compute_forward_returns,
    compute_ic,
    factor_decay,
)

logger = logging.getLogger(__name__)


@dataclass
class FactorSpec:
    """單因子規格。"""

    name: str  # 因子名稱 (對應 FACTOR_REGISTRY)
    direction: int = 1  # 1=越大越好, -1=越小越好
    kwargs: dict = field(default_factory=dict)  # 因子參數覆寫


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
    combine_method: str = "equal"  # "equal" | "ic" | "custom"
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

    def summary(self) -> str:
        lines = [
            "═══════════════════════════════════════",
            "         Alpha Pipeline Report         ",
            "═══════════════════════════════════════",
            "",
            f"Universe: avg {self.universe_counts.get('avg', 0)} stocks "
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

        return "\n".join(lines)


class AlphaPipeline:
    """端到端的 Alpha 研究流水線。"""

    def __init__(self, config: AlphaConfig):
        self.config = config
        self._universe_filter = UniverseFilter(config.universe)
        self._prev_signal: pd.Series | None = None
        self._prev_weights: pd.Series | None = None

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

        logger.info("Universe: avg=%d stocks across %d dates", universe_counts["avg"], len(all_dates))

        # [2] 逐因子計算
        raw_factors: dict[str, pd.DataFrame] = {}
        for spec in cfg.factors:
            if spec.name not in FACTOR_REGISTRY:
                logger.warning("Unknown factor: %s, skipping", spec.name)
                continue
            fv = compute_factor_values(data, spec.name, dates=all_dates, **spec.kwargs)
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

        for name, fv in neutralized.items():
            # IC
            fwd = compute_forward_returns(data, horizon=cfg.holding_period, dates=list(fv.index))
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
            if spec.name not in FACTOR_REGISTRY:
                continue
            fv = compute_factor_values(data, spec.name, dates=[current_date], **spec.kwargs)
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
            # IC 加權
            total_abs_ic = sum(abs(factor_ics[n].ic_mean) for n in names if n in factor_ics)
            if total_abs_ic > 0:
                weights = {n: abs(factor_ics[n].ic_mean) / total_abs_ic for n in names if n in factor_ics}
            else:
                weights = {n: 1.0 / len(names) for n in names}
        else:
            weights = {n: 1.0 / len(names) for n in names}

        # 加權合成
        common_dates: set | None = None
        common_symbols: set | None = None
        for fv in factor_dict.values():
            d = set(fv.index)
            s = set(fv.columns)
            common_dates = d if common_dates is None else common_dates & d
            common_symbols = s if common_symbols is None else common_symbols & s

        if not common_dates or not common_symbols:
            return None, weights

        sorted_dates = sorted(common_dates)
        sorted_symbols = sorted(common_symbols)

        composite = pd.DataFrame(0.0, index=sorted_dates, columns=sorted_symbols)
        for name, fv in factor_dict.items():
            w = weights.get(name, 0.0)
            composite += fv.reindex(index=sorted_dates, columns=sorted_symbols).fillna(0) * w

        return composite, weights

    def _combine_signals(self, factor_values: dict[str, pd.Series]) -> pd.Series:
        """合成單期信號（用於 generate_weights）。"""
        cfg = self.config
        names = list(factor_values.keys())

        if len(names) == 1:
            return factor_values[names[0]]

        if cfg.combine_method == "custom" and cfg.combine_weights:
            weights = cfg.combine_weights
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
