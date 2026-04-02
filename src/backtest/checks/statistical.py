"""Statistical validation checks mixin for StrategyValidator.

Contains bootstrap Sharpe, CVaR, PBO (vectorized + event-driven), and permutation test.
Extracted from validator.py to reduce file size.

Assumes the consuming class provides:
    self.config: ValidationConfig
    self._shared_feed: optional feed override for event-driven backtests
    self._pbo_avg_corr: float attribute (set by _compute_pbo_vectorized)
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# PBO construction sensitivity variants: (top_n, weight_mode, rebal_skip)
_PBO_VARIANT_CONFIGS = [
    (8,  "equal",        0), (8,  "signal",       0),
    (12, "equal",        0), (12, "inverse_rank", 0),
    (15, "equal",        0), (15, "signal",       0),
    (15, "inverse_rank", 1), (20, "equal",        0),
    (20, "signal",       1), (20, "inverse_rank", 0),
]


class StatisticalChecks:
    """Mixin providing statistical validation methods."""

    def _bootstrap_sharpe(self, result: "BacktestResult", n_bootstrap: int) -> float:
        """Stationary Bootstrap P(Sharpe > 0) — Politis & Romano (1994).

        Block resampling with geometric block length to preserve
        autocorrelation structure (volatility clustering) in daily returns.
        IID bootstrap would underestimate Sharpe standard error by ~20%.
        """
        from src.backtest.analytics import BacktestResult

        ret_series = getattr(result, 'daily_returns', None)
        if ret_series is None:
            return 0.0

        returns = ret_series.dropna().values
        n = len(returns)
        if n < 20:
            return 0.0

        avg_block = 20  # ~1 month, matches monthly rebalance frequency
        p = 1.0 / avg_block  # geometric distribution parameter
        rng = np.random.default_rng(42)
        positive_count = 0

        for _ in range(n_bootstrap):
            sample = np.empty(n)
            i = 0
            pos = rng.integers(0, n)
            while i < n:
                sample[i] = returns[pos % n]
                i += 1
                pos += 1
                if rng.random() < p:  # with prob p, jump to new random position
                    pos = rng.integers(0, n)

            mean_r = sample.mean()
            std_r = sample.std(ddof=1)
            if std_r > 0:
                sr = mean_r / std_r * np.sqrt(252)
                if sr > 0:
                    positive_count += 1

        return positive_count / n_bootstrap

    @staticmethod
    def _compute_cvar(result: "BacktestResult", alpha: float = 0.05) -> float:
        """CVaR(95%) = worst 5% daily returns average. Returns -1.0 on error (fail-closed)."""
        try:
            rets = result.daily_returns
            if rets is None or len(rets) < 20:
                return -1.0  # fail-closed: insufficient data
            clean_rets = rets.dropna().values
            if len(clean_rets) == 0:
                return -1.0  # fail-closed: all NaN
            sorted_rets = sorted(clean_rets)
            n_tail = max(int(len(sorted_rets) * alpha), 1)
            return float(np.mean(sorted_rets[:n_tail]))
        except Exception:
            return -1.0  # fail-closed

    def _compute_pbo(
        self,
        wf_results: list[dict[str, Any]],
        strategy: "Strategy | None" = None,
        universe: "list[str] | None" = None,
        start: str = "",
        end: str = "",
        compute_fn: Any = None,
    ) -> float:
        """Bailey (2015) CSCV PBO.

        Strategy:
        1. If compute_fn available → vectorized PBO (fast, ~10 sec)
        2. Else → event-driven PBO fallback (slow but always works)
        """
        if strategy is None or universe is None:
            logger.warning("PBO: no strategy/universe, returning pessimistic (1.0)")
            return 1.0

        # Resolve compute_fn from strategy if not passed explicitly
        if compute_fn is None:
            compute_fn = getattr(strategy, '_compute_fn', None)

        # --- Path 1: Vectorized PBO (when compute_fn available) ---
        if compute_fn is not None:
            try:
                return self._compute_pbo_vectorized(compute_fn, universe, start, end)
            except Exception as e:
                logger.warning("PBO vectorized failed (%s), falling back to event-driven", e)

        # --- Path 2: Event-driven fallback (always works, any strategy) ---
        return self._compute_pbo_event_driven(strategy, universe, start, end)

    def _compute_pbo_vectorized(
        self, compute_fn: Any, universe: list[str], start: str, end: str,
    ) -> float:
        """Fast PBO using VectorizedPBOBacktest."""
        from src.backtest.vectorized import VectorizedPBOBacktest
        from src.backtest.overfitting import compute_pbo
        from pathlib import Path
        import time as _time

        import os as _os
        project_root = Path(_os.environ.get("PROJECT_ROOT",
                            str(Path(__file__).resolve().parent.parent.parent)))
        data_dir = project_root / "data" / "market"
        fund_dir = project_root / "data" / "fundamental"

        t0 = _time.time()
        vbt = VectorizedPBOBacktest(
            universe=universe, start=start, end=end,
            data_dir=str(data_dir), fund_dir=str(fund_dir),
        )

        daily_returns_dict: dict[str, pd.Series] = {}
        for top_n, wmode, skip in _PBO_VARIANT_CONFIGS:
            try:
                rets = vbt.run_variant(compute_fn, top_n, wmode, skip)
                if rets is not None and len(rets) > 20:
                    daily_returns_dict[f"n{top_n}_{wmode}_s{skip}"] = rets
            except Exception as e:
                logger.debug("PBO vectorized n%d_%s_s%d failed: %s", top_n, wmode, skip, e)

        if len(daily_returns_dict) < 4:
            raise ValueError(f"Only {len(daily_returns_dict)} variants (need >=4)")

        returns_matrix = pd.DataFrame(daily_returns_dict).fillna(0.0).dropna()
        if len(returns_matrix) < 120:
            raise ValueError(f"Only {len(returns_matrix)} aligned days (need >=120)")

        n_parts = min(16, max(8, len(returns_matrix) // 60))
        if n_parts % 2 != 0:
            n_parts -= 1

        pbo_result = compute_pbo(returns_matrix, n_partitions=n_parts)

        # Avg pairwise correlation — if > 0.8, PBO is unreliable
        corr_matrix = returns_matrix.corr()
        n_vars = len(corr_matrix)
        if n_vars > 1:
            upper = corr_matrix.values[np.triu_indices(n_vars, k=1)]
            avg_corr = float(np.mean(upper))
        else:
            avg_corr = 1.0
        self._pbo_avg_corr = avg_corr

        elapsed = _time.time() - t0
        logger.info("PBO CSCV (vectorized): %.3f (avg_corr=%.3f, %d variants, %d days, %.1fs)",
                     pbo_result.pbo, avg_corr, len(daily_returns_dict), len(returns_matrix), elapsed)
        return pbo_result.pbo

    def _compute_pbo_event_driven(
        self, strategy: "Strategy", universe: list[str], start: str, end: str,
    ) -> float:
        """Fallback PBO using event-driven BacktestEngine (slow but universal)."""
        from src.backtest.engine import BacktestEngine
        from src.backtest.overfitting import compute_pbo
        from src.strategy.base import Context, Strategy as StrategyBase
        import time as _time

        class _VariantStrategy(StrategyBase):
            def __init__(self, base: "Strategy", top_n: int,
                         weight_mode: str = "equal", rebal_skip: int = 0):
                self._base = base
                self._top_n = top_n
                self._weight_mode = weight_mode
                self._rebal_skip = rebal_skip
                self._bar_count = 0
                self._cached_weights: dict[str, float] = {}
                self._name = f"{base.name()}_n{top_n}_{weight_mode}_s{rebal_skip}"

            def name(self) -> str:
                return self._name

            def on_bar(self, ctx: Context) -> dict[str, float]:
                self._bar_count += 1
                if self._rebal_skip > 0 and self._bar_count % (self._rebal_skip + 1) != 1:
                    return dict(self._cached_weights) if self._cached_weights else {}
                weights = self._base.on_bar(ctx)
                if not weights:
                    return dict(self._cached_weights) if self._cached_weights else {}
                sorted_syms = sorted(weights, key=lambda s: weights[s], reverse=True)
                selected = sorted_syms[:self._top_n]
                if not selected:
                    return {}
                if self._weight_mode == "signal":
                    vals = {s: max(weights[s], 0.0) for s in selected}
                    total = sum(vals.values())
                    result = {s: v / total for s, v in vals.items()} if total > 0 \
                        else {s: 1.0 / len(selected) for s in selected}
                elif self._weight_mode == "inverse_rank":
                    n = len(selected)
                    rank_w = {s: (n - i) for i, s in enumerate(selected)}
                    total = sum(rank_w.values())
                    result = {s: v / total for s, v in rank_w.items()}
                else:
                    result = {s: 1.0 / len(selected) for s in selected}
                self._cached_weights = result
                return dict(result)

        t0 = _time.time()
        bt_config = self._make_bt_config(universe, start, end)
        shared_feed = getattr(self, '_shared_feed', None)
        daily_returns_dict: dict[str, pd.Series] = {}

        # Sequential: strategy may have mutable state (e.g. _last_month cache)
        # that is not thread-safe. deepcopy per variant to avoid race conditions.
        import copy
        for top_n, wmode, skip in _PBO_VARIANT_CONFIGS:
            try:
                strategy_copy = copy.deepcopy(strategy)
            except Exception:
                strategy_copy = strategy  # fallback if deepcopy fails
            variant = _VariantStrategy(strategy_copy, top_n, wmode, skip)
            try:
                engine = BacktestEngine()
                result = engine.run(variant, bt_config, feed_override=shared_feed)
                if result.daily_returns is not None and len(result.daily_returns) > 20:
                    daily_returns_dict[f"n{top_n}_{wmode}_s{skip}"] = result.daily_returns
            except Exception as e:
                logger.debug("PBO event-driven n%d_%s_s%d failed: %s", top_n, wmode, skip, e)

        if len(daily_returns_dict) < 4:
            logger.warning("PBO event-driven: only %d variants (need >=4), returning 1.0",
                           len(daily_returns_dict))
            return 1.0

        returns_matrix = pd.DataFrame(daily_returns_dict).fillna(0.0).dropna()
        if len(returns_matrix) < 120:
            logger.warning("PBO event-driven: only %d days (need >=120), returning 1.0",
                           len(returns_matrix))
            return 1.0

        n_parts = min(16, max(8, len(returns_matrix) // 60))
        if n_parts % 2 != 0:
            n_parts -= 1

        pbo_result = compute_pbo(returns_matrix, n_partitions=n_parts)
        elapsed = _time.time() - t0
        logger.info("PBO CSCV (event-driven): %.3f (%d variants, %d days, %.1fs)",
                     pbo_result.pbo, len(daily_returns_dict), len(returns_matrix), elapsed)
        return pbo_result.pbo

    def _permutation_test(
        self, result: "BacktestResult", strategy: "Strategy",
        universe: list[str], start: str, end: str,
        n_permutations: int = 100,
        compute_fn_override: Any = None,
    ) -> float:
        """Permutation test: shuffle factor signal cross-sectionally, compare Sharpe.

        Tests whether the factor's stock SELECTION has predictive power,
        or if the Sharpe could be achieved by random stock picking.
        Uses VectorizedPBOBacktest for speed (~1-2 sec per permutation).

        Returns p-value: fraction of random shuffles with Sharpe >= strategy Sharpe.
        p < 0.10 = signal is real.
        """
        if result.sharpe <= 0:
            return 1.0  # negative Sharpe → any random shuffle is better

        try:
            from src.backtest.vectorized import VectorizedPBOBacktest

            vbt = VectorizedPBOBacktest(
                universe=universe[:150], start=start, end=end,
            )

            # Permutation: shuffle the stock-to-factor-value mapping with a FIXED
            # permutation per trial. Same shuffle applied to ALL dates → preserves
            # the turnover structure of the real factor (same stocks stay together).
            compute_fn = compute_fn_override or getattr(strategy, '_compute_fn', None)
            if compute_fn is None:
                try:
                    from factor import compute_factor as _cf  # type: ignore[import-not-found]
                    compute_fn = _cf
                except ImportError:
                    return 1.0  # fail-closed

            # Get real factor's Sharpe via vectorized backtest
            real_rets = vbt.run_variant(compute_fn, top_n=15, weight_mode="equal")
            if real_rets is None or len(real_rets) < 60:
                return 0.5
            # rf omitted intentionally — permutation p-value is a relative test (real vs shuffled)
            real_sharpe = float(real_rets.mean() / real_rets.std() * np.sqrt(252)) if real_rets.std() > 0 else 0

            # Pre-compute factor values for all rebalance dates (run compute_fn once)
            prices = vbt._price_matrix
            monthly_groups = prices.groupby(prices.index.to_period("M"))
            monthly_first = monthly_groups.apply(lambda g: g.index[0])
            rebal_dates = list(monthly_first.values)

            factor_cache: dict[str, dict[str, float]] = {}  # {date_str: {sym: val}}
            symbols = prices.columns.tolist()
            for date in rebal_dates:
                as_of = pd.Timestamp(date)
                data = vbt._build_factor_data(symbols, as_of)
                try:
                    vals = compute_fn(symbols, as_of, data)
                    if vals:
                        factor_cache[str(date)] = vals
                except Exception:
                    pass

            if len(factor_cache) < 10:
                return 0.5  # not enough dates

            # Derive seeds from factor cache hash (reproducible but not predictable from trial index)
            import hashlib as _hl
            _base_seed = int(_hl.md5(str(sorted(factor_cache.keys())).encode()).hexdigest()[:8], 16)
            random_sharpes = []
            for i in range(n_permutations):
                perm_seed = _base_seed + i
                def shuffled_factor(symbols, as_of, data, _seed=perm_seed, _cache=factor_cache):
                    # Look up pre-computed values, shuffle mapping
                    vals = _cache.get(str(as_of), {})
                    if not vals:
                        return {}
                    syms = sorted(vals.keys())
                    values = [vals[s] for s in syms]
                    idx = list(range(len(syms)))
                    np.random.default_rng(_seed).shuffle(idx)
                    return {syms[j]: values[idx[j]] for j in range(len(syms))}
                try:
                    rets = vbt.run_variant(shuffled_factor, top_n=15, weight_mode="equal")
                    if rets is not None and len(rets) > 60:
                        sr = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0
                        random_sharpes.append(sr)
                except Exception:
                    continue

            if len(random_sharpes) < 50:
                return 0.5  # inconclusive

            p_value = sum(1 for s in random_sharpes if s >= real_sharpe) / len(random_sharpes)
            return p_value

        except Exception as e:
            logger.warning("Permutation test failed: %s", e)
            return 0.5  # inconclusive
