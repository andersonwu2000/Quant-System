"""FactorEvaluator — 多層因子驗證管線。

5 層漸進驗證，早期終止（不浪費時間在注定失敗的因子上）：
L1: 快速 IC（20d，全市場）— 5s
L2: 多期限 ICIR + 成本 — 15s
L3: 相關性 + 年度穩定性 — 10s
L4: Fitness + 池正交性 — 5s
L5: Walk-Forward（只對通過 L4 的跑）— 60s

Fitness 公式（WorldQuant BRAIN 啟發）：
fitness = sqrt(|returns_proxy| / max(turnover, 0.125)) × sharpe_proxy
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """因子評估結果。"""
    factor_name: str
    passed: bool = False
    level_reached: str = ""  # "L1" ~ "L5"
    failure_reason: str = ""

    # L1
    ic_20d: float = 0.0
    # L2
    icir_by_horizon: dict[str, float] = field(default_factory=dict)  # "5d" → ICIR
    best_icir: float = 0.0
    best_horizon: str = ""
    avg_turnover: float = 0.0
    # L3
    max_correlation: float = 0.0
    correlated_with: str = ""
    positive_years: int = 0
    total_years: int = 0
    # L4
    fitness: float = 0.0
    # L5
    wf_avg_sharpe: float = 0.0
    wf_positive_ratio: float = 0.0

    duration_seconds: float = 0.0


def compute_fitness(ic_mean: float, icir: float, turnover: float) -> float:
    """WorldQuant BRAIN 式 fitness 評分。

    fitness = sqrt(|returns_proxy| / max(turnover, 0.125)) × |icir|
    """
    returns_proxy = abs(ic_mean) * 10000  # bps
    to_adj = max(turnover, 0.125)
    if returns_proxy <= 0 or to_adj <= 0:
        return 0.0
    return math.sqrt(returns_proxy / to_adj) * abs(icir)


class FactorEvaluator:
    """多層因子驗證管線。"""

    def __init__(
        self,
        data: dict[str, pd.DataFrame] | None = None,
        existing_factor_ics: dict[str, pd.Series] | None = None,
        min_icir_l1: float = 0.02,
        min_icir_l2: float = 0.15,
        max_turnover: float = 0.90,  # quintile 取樣的 turnover，營收因子天然 70-90%
        max_correlation: float = 0.50,
        min_positive_years: int = 7,
        min_fitness: float = 3.0,
        total_tested: int = 0,  # Harvey (2016) 多重測試校正
    ):
        self.data = data or {}
        self.existing_factor_ics = existing_factor_ics or {}
        self.min_icir_l1 = min_icir_l1
        self.min_icir_l2 = min_icir_l2
        self.max_turnover = max_turnover
        self.max_correlation = max_correlation
        self.min_positive_years = min_positive_years
        self.min_fitness = min_fitness
        self.total_tested = total_tested

    @property
    def adjusted_icir_threshold(self) -> float:
        """Harvey (2016) 多重測試校正：ICIR 門檻隨測試數量提高。

        門檻 = base × sqrt(1 + log(max(N, 1)))
        N=1: 0.15, N=100: 0.26, N=1000: 0.35
        """
        if self.total_tested <= 1:
            return self.min_icir_l2
        return self.min_icir_l2 * math.sqrt(1 + math.log(self.total_tested))

    def evaluate(self, factor_name: str, factor_values: pd.DataFrame) -> EvaluationResult:
        """執行多層驗證。"""
        t0 = time.perf_counter()
        result = EvaluationResult(factor_name=factor_name)

        if factor_values.empty:
            result.failure_reason = "Empty factor values"
            result.level_reached = "L0"
            result.duration_seconds = time.perf_counter() - t0
            return result

        # Build forward returns if not cached
        fwd_cache: dict[int, pd.DataFrame] = {}
        close_panel = pd.DataFrame({
            s: self.data[s]["close"] for s in self.data if "close" in self.data[s].columns
        })

        # L1: 快速 IC（20d）
        fwd_20 = self._get_fwd(close_panel, 20, fwd_cache)
        ic_20d = self._compute_ic(factor_values, fwd_20)
        result.ic_20d = ic_20d
        if abs(ic_20d) < self.min_icir_l1:
            result.level_reached = "L1"
            result.failure_reason = f"|IC_20d| = {abs(ic_20d):.4f} < {self.min_icir_l1}"
            result.duration_seconds = time.perf_counter() - t0
            return result

        # L2: 多期限 ICIR + 成本
        best_icir = 0.0
        best_h = ""
        for horizon in [5, 10, 20, 60]:
            fwd = self._get_fwd(close_panel, horizon, fwd_cache)
            icir = self._compute_icir(factor_values, fwd)
            result.icir_by_horizon[f"{horizon}d"] = icir
            if abs(icir) > abs(best_icir):
                best_icir = icir
                best_h = f"{horizon}d"

        result.best_icir = best_icir
        result.best_horizon = best_h

        # Turnover estimate
        turnover = self._estimate_turnover(factor_values)
        result.avg_turnover = turnover

        adj_threshold = self.adjusted_icir_threshold
        if abs(best_icir) < adj_threshold:
            result.level_reached = "L2"
            result.failure_reason = f"Best ICIR = {best_icir:.4f} < {adj_threshold:.4f} (Harvey-adjusted, N={self.total_tested})"
            result.duration_seconds = time.perf_counter() - t0
            return result
        if turnover > self.max_turnover:
            result.level_reached = "L2"
            result.failure_reason = f"Turnover = {turnover:.2%} > {self.max_turnover:.0%}"
            result.duration_seconds = time.perf_counter() - t0
            return result

        # L3: 相關性 + 年度穩定性
        max_corr, corr_with = self._check_correlation(factor_values, fwd_20)
        result.max_correlation = max_corr
        result.correlated_with = corr_with

        if max_corr > self.max_correlation:
            result.level_reached = "L3"
            result.failure_reason = f"Corr = {max_corr:.3f} with {corr_with} > {self.max_correlation}"
            result.duration_seconds = time.perf_counter() - t0
            return result

        pos_years, total_years = self._yearly_stability(factor_values, fwd_20)
        result.positive_years = pos_years
        result.total_years = total_years

        if pos_years < self.min_positive_years and total_years >= 7:
            result.level_reached = "L3"
            result.failure_reason = f"Positive years = {pos_years}/{total_years} < {self.min_positive_years}"
            result.duration_seconds = time.perf_counter() - t0
            return result

        # L4: Fitness
        fitness = compute_fitness(result.ic_20d, best_icir, turnover)
        result.fitness = fitness

        if fitness < self.min_fitness:
            result.level_reached = "L4"
            result.failure_reason = f"Fitness = {fitness:.2f} < {self.min_fitness}"
            result.duration_seconds = time.perf_counter() - t0
            return result

        # L5: Walk-Forward — 後半 IC 絕對值不能太低（衰減或反轉都不行）
        result.level_reached = "L5"
        try:
            ic_series_20 = self._compute_ic_series(factor_values, fwd_20)
            mid = len(ic_series_20) // 2
            if mid >= 5:
                first_half_ic = float(np.mean(ic_series_20[:mid]))
                second_half_ic = float(np.mean(ic_series_20[mid:]))
                # 後半 IC 絕對值需 > 0.005（不能衰減到零或反轉）
                if abs(second_half_ic) < 0.005:
                    result.passed = False
                    result.failure_reason = (
                        f"WF fail: signal decayed (first={first_half_ic:.3f}, second={second_half_ic:.3f})"
                    )
                    result.duration_seconds = time.perf_counter() - t0
                    return result
                # 後半方向不能和前半相反
                if first_half_ic * second_half_ic < 0:
                    result.passed = False
                    result.failure_reason = (
                        f"WF fail: IC reversal (first={first_half_ic:.3f}, second={second_half_ic:.3f})"
                    )
                    result.duration_seconds = time.perf_counter() - t0
                    return result
                result.passed = True
            else:
                # 數據不足，fail-closed（寧可錯過不冒險）
                result.passed = False
                result.failure_reason = f"WF fail: insufficient IC samples ({len(ic_series_20)})"
        except Exception as e:
            result.passed = False  # fail-closed
            result.failure_reason = f"WF exception: {e}"
        result.duration_seconds = time.perf_counter() - t0
        return result

    # ── Internal methods ───────────────────────────────────────

    def _get_fwd(self, close: pd.DataFrame, horizon: int, cache: dict[int, pd.DataFrame]) -> pd.DataFrame:
        if horizon not in cache:
            cache[horizon] = close.pct_change(horizon, fill_method=None).shift(-horizon)
        return cache[horizon]  # already a DataFrame from pct_change().shift()

    @staticmethod
    def _compute_ic(factor: pd.DataFrame, fwd: pd.DataFrame) -> float:
        """Mean cross-sectional Spearman IC."""
        from scipy.stats import spearmanr

        common_dates = factor.index.intersection(fwd.index)
        common_syms = factor.columns.intersection(fwd.columns)
        if len(common_dates) < 20 or len(common_syms) < 10:
            return 0.0

        ics = []
        for dt in common_dates[::5]:  # sample every 5 days
            f = factor.loc[dt, common_syms].dropna()
            r = fwd.loc[dt, common_syms].dropna()
            common = f.index.intersection(r.index)
            if len(common) < 5:
                continue
            corr, _ = spearmanr(f[common], r[common])
            if not np.isnan(corr):
                ics.append(corr)

        return float(np.mean(ics)) if ics else 0.0

    @staticmethod
    def _compute_ic_series(factor: pd.DataFrame, fwd: pd.DataFrame) -> list[float]:
        """計算 IC 時間序列（每 5 天取樣）。"""
        from scipy.stats import spearmanr

        common_dates = factor.index.intersection(fwd.index)
        common_syms = factor.columns.intersection(fwd.columns)
        if len(common_dates) < 20 or len(common_syms) < 10:
            return []

        ics: list[float] = []
        for dt in common_dates[::5]:
            f = factor.loc[dt, common_syms].dropna()
            r = fwd.loc[dt, common_syms].dropna()
            common = f.index.intersection(r.index)
            if len(common) < 5:
                continue
            corr, _ = spearmanr(f[common], r[common])
            if not np.isnan(corr):
                ics.append(corr)
        return ics

    @staticmethod
    def _compute_icir(factor: pd.DataFrame, fwd: pd.DataFrame) -> float:
        """ICIR = mean(IC) / std(IC)."""
        ics = FactorEvaluator._compute_ic_series(factor, fwd)

        if len(ics) < 5:
            return 0.0
        ic_mean = float(np.mean(ics))
        ic_std = float(np.std(ics, ddof=1))
        return ic_mean / ic_std if ic_std > 0 else 0.0

    @staticmethod
    def _estimate_turnover(factor: pd.DataFrame, n_quantiles: int = 5) -> float:
        """Estimate factor turnover from quintile membership changes.

        使用月頻取樣（每 20 天）而非日頻，避免高估月頻因子的換手率。
        """
        if factor.empty or len(factor) < 20:
            return 0.0

        ranks = factor.rank(axis=1, pct=True)
        top_quintile = ranks >= (1 - 1.0 / n_quantiles)

        changes: float = 0.0
        total: int = 0
        prev = None
        # 月頻取樣（每 20 天），對應月度再平衡
        for i in range(0, len(top_quintile), 20):
            current = set(top_quintile.columns[top_quintile.iloc[i]])
            if prev is not None and len(prev) > 0:
                overlap = len(current & prev)
                union = len(current | prev)
                if union > 0:
                    changes += 1 - overlap / union
                    total += 1
            prev = current

        return changes / total if total > 0 else 0.0

    def _check_correlation(self, factor: pd.DataFrame, fwd_20: pd.DataFrame) -> tuple[float, str]:
        """Check max correlation with existing factors using IC series (not factor-value means).

        Computes the new factor's IC time series, then correlates with baseline IC series.
        """
        if not self.existing_factor_ics:
            return 0.0, ""

        # Compute IC series for the new factor (same method as _compute_ic_series)
        new_ics = self._compute_ic_series(factor, fwd_20)
        if len(new_ics) < 10:
            return 0.0, ""

        new_ic = pd.Series(new_ics)
        max_corr = 0.0
        max_name = ""

        for name, existing_ic in self.existing_factor_ics.items():
            if len(existing_ic) < 10:
                continue
            min_len = min(len(new_ic), len(existing_ic))
            corr = float(new_ic.iloc[:min_len].corr(existing_ic.iloc[:min_len]))
            if abs(corr) > abs(max_corr):
                max_corr = corr
                max_name = name

        return abs(max_corr), max_name

    @staticmethod
    def _yearly_stability(factor: pd.DataFrame, fwd: pd.DataFrame) -> tuple[int, int]:
        """Count years with positive IC."""
        from scipy.stats import spearmanr

        common_dates = factor.index.intersection(fwd.index)
        common_syms = factor.columns.intersection(fwd.columns)

        yearly_ic: dict[int, list[float]] = {}
        for dt in common_dates[::5]:
            year = dt.year if hasattr(dt, 'year') else pd.Timestamp(dt).year
            f = factor.loc[dt, common_syms].dropna()
            r = fwd.loc[dt, common_syms].dropna()
            common = f.index.intersection(r.index)
            if len(common) < 5:
                continue
            corr, _ = spearmanr(f[common], r[common])
            if not np.isnan(corr):
                yearly_ic.setdefault(year, []).append(corr)

        positive = 0
        total = 0
        for year, ics in sorted(yearly_ic.items()):
            if len(ics) >= 5:
                total += 1
                if np.mean(ics) > 0:
                    positive += 1

        return positive, total
