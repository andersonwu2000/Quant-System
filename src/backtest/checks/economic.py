"""Economic / market validation checks mixin for StrategyValidator.

Methods related to walk-forward analysis, market correlation, regime
breakdown, equal-weight benchmarking, and recent performance.

Assumes the host class provides ``self.config`` (ValidationConfig),
``self._shared_feed``, ``self._make_bt_config()``, ``self._load_0050()``,
and ``self._build_catalog_feed()``.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.backtest.validator import CheckResult

logger = logging.getLogger(__name__)


class EconomicChecks:
    """Mixin: economic / market validation helpers."""

    # ------------------------------------------------------------------
    # Walk-Forward
    # ------------------------------------------------------------------

    def _run_walkforward(
        self,
        strategy,
        universe: list[str],
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        """滾動 Walk-Forward（並行化各年份）。"""
        from src.backtest.engine import BacktestEngine

        cfg = self.config
        start_year = int(start[:4])
        end_year = int(end[:4])
        test_years = list(range(start_year + cfg.wf_train_years, end_year + 1))

        shared_feed = getattr(self, '_shared_feed', None)

        import copy as _copy

        def _run_year(year: int) -> dict[str, Any]:
            try:
                # deepcopy strategy to avoid mutable state race conditions
                try:
                    strat = _copy.deepcopy(strategy)
                except Exception:
                    strat = strategy
                bt_config = self._make_bt_config(universe, f"{year}-01-01", f"{year}-12-31")
                engine = BacktestEngine()
                r = engine.run(strat, bt_config, feed_override=shared_feed)
                return {
                    "year": year,
                    "return": r.total_return,
                    "cagr": r.annual_return,
                    "sharpe": r.sharpe,
                    "max_drawdown": r.max_drawdown,
                    "trades": r.total_trades,
                    "commission": r.total_commission,
                }
            except Exception as e:
                return {"year": year, "sharpe": 0.0, "error": str(e)}

        from concurrent.futures import ThreadPoolExecutor
        import os as _os2
        n_workers = min(len(test_years), int(_os2.environ.get("WF_WORKERS", 4)))
        with ThreadPoolExecutor(max_workers=n_workers) as pool:
            results = list(pool.map(_run_year, test_years))

        return sorted(results, key=lambda r: r["year"])

    # ------------------------------------------------------------------
    # Market correlation
    # ------------------------------------------------------------------

    def _market_correlation(
        self, result, universe: list[str], start: str, end: str,
    ) -> float:
        """計算策略日報酬和市場（0050.TW）的相關性。

        優先讀本地 parquet，fallback Yahoo。取得失敗回傳 1.0（fail-closed）。
        """
        strat_rets = result.daily_returns
        if strat_rets is None or len(strat_rets) < 20:
            return 1.0  # cannot verify independence → assume correlated

        bench = self._load_0050(start, end)
        if bench is None or len(bench) < 20:
            return 1.0

        try:
            bench_rets = bench["close"].pct_change().dropna()
            common = strat_rets.index.intersection(bench_rets.index)
            if len(common) < 20:
                return 1.0
            corr = float(strat_rets.loc[common].corr(bench_rets.loc[common]))
            return corr if np.isfinite(corr) else 1.0
        except Exception:
            return 1.0

    # ------------------------------------------------------------------
    # Regime breakdown
    # ------------------------------------------------------------------

    def _check_regime_breakdown(
        self,
        wf_results: list[dict[str, Any]],
        max_worst_loss: float,
        result=None,
        start: str = "",
        end: str = "",
    ) -> CheckResult:
        """Drawdown-based regime: 策略在市場危機期間（0050 drawdown > 15%）的表現。

        Phase AC: 替換年度切割。市場危機不按日曆年發生。
        """
        from src.backtest.validator import CheckResult

        # Try drawdown-based first
        if result is not None and result.daily_returns is not None:
            try:
                bench = self._load_0050(start, end)
                if bench is not None and len(bench) >= 60:
                    bench_close = bench["close"]
                    bench_cummax = bench_close.cummax()
                    bench_dd = (bench_close - bench_cummax) / bench_cummax
                    # Crisis = market drawdown > 15%
                    crisis_mask = bench_dd < -0.15
                    crisis_dates = bench_dd.index[crisis_mask]

                    if len(crisis_dates) > 10:
                        # Strategy returns during crisis
                        strat_rets = result.daily_returns
                        common = strat_rets.index.intersection(crisis_dates)
                        if len(common) > 5:
                            crisis_return = float((1 + strat_rets.loc[common]).prod() - 1)
                            n_crisis_days = len(common)
                            return CheckResult(
                                name="worst_regime",
                                passed=crisis_return >= max_worst_loss,
                                value=f"{crisis_return:+.2%}",
                                threshold=f">= {max_worst_loss:+.0%}",
                                detail=f"Cumulative return during {n_crisis_days} market crisis days (0050 DD > 15%)",
                            )
            except Exception:
                pass

        # Fallback: worst year from WF results
        cagrs = [r.get("cagr", r.get("return", 0)) for r in wf_results if "error" not in r]
        if not cagrs:
            return CheckResult(
                name="worst_regime",
                passed=False,
                value="N/A",
                threshold=f">= {max_worst_loss:+.0%}",
                detail="No data available — fail-closed",
            )

        worst = min(cagrs)
        worst_year = "?"
        for r in wf_results:
            cagr = r.get("cagr", r.get("return", 0))
            if cagr == worst:
                worst_year = str(r.get("year", "?"))
                break

        return CheckResult(
            name="worst_regime",
            passed=worst >= max_worst_loss,
            value=f"{worst:+.2%}",
            threshold=f">= {max_worst_loss:+.0%}",
            detail=f"Worst year: {worst_year}",
        )

    # ------------------------------------------------------------------
    # Equal-weight benchmark
    # ------------------------------------------------------------------

    def _get_ew_annual(self, universe: list[str], start: str, end: str) -> float | None:
        """Get monthly-rebalanced equal-weight universe annual return.

        Fixes vs old implementation:
        - B: No survivorship bias — delisted stocks keep last price (return=0),
             no minimum bar filter that excludes short-lived stocks.
        - C: Monthly rebalance (not daily) — matches strategy rebalance frequency.
             Each month: equal-weight all available stocks, compound within month.
        """
        from src.data.registry import parquet_path as _ppath

        try:
            # Build close price matrix (all stocks aligned to common dates)
            close_dict: dict[str, pd.Series] = {}
            for sym in universe:
                path = _ppath(sym, "price")
                if not path.exists():
                    continue
                try:
                    df = pd.read_parquet(path)
                    if "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        df = df.set_index("date").sort_index()
                    if "close" in df.columns:
                        sliced = df.loc[start:end]["close"]
                        sliced = sliced.where(sliced > 0)
                        if not sliced.dropna().empty:
                            close_dict[sym] = sliced
                except Exception:
                    pass

            if len(close_dict) < 20:
                return None

            # Align all stocks to common date index, ffill then fill NaN with last known
            # (delisted stocks carry last price → return = 0, not excluded)
            close_df = pd.DataFrame(close_dict).sort_index()
            close_df = close_df.ffill()

            # Monthly rebalance: split into calendar months, equal-weight within each
            daily_returns = close_df.pct_change()
            daily_returns = daily_returns.replace([np.inf, -np.inf], 0.0).fillna(0.0)

            # Group by year-month for monthly rebalancing
            monthly_groups = daily_returns.groupby(pd.Grouper(freq="MS"))
            monthly_returns: list[float] = []

            for _, month_rets in monthly_groups:
                if month_rets.empty:
                    continue
                # Each stock's cumulative return this month
                stock_cum = (1 + month_rets).prod() - 1  # per-stock monthly return
                # Count stocks with valid data this month (had price at month start)
                valid = stock_cum.dropna()
                if len(valid) < 10:
                    continue
                # Equal-weight: average of all stocks' monthly returns
                ew_month = float(valid.mean())
                monthly_returns.append(ew_month)

            if len(monthly_returns) < 3:
                return None

            # Compound monthly returns → total return → annualize
            total = 1.0
            for r in monthly_returns:
                total *= (1 + r)
            total -= 1

            if total <= -1:
                return None
            n_years = max(len(monthly_returns) / 12, 0.5)
            return float((1 + total) ** (1 / n_years) - 1)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # vs EW benchmark (gross)
    # ------------------------------------------------------------------

    def _vs_ew_benchmark_gross(
        self,
        strategy_gross_annual: float,
        universe: list[str],
        start: str,
        end: str,
    ) -> float:
        """計算 GROSS selection alpha = strategy gross - EW gross。

        Both sides are gross (no trading costs) for fair comparison.
        Cost efficiency is tested separately by annual_cost_ratio check.
        """
        from src.data.registry import parquet_path as _ppath

        try:
            # Load daily returns for all universe stocks
            all_returns: list[pd.Series] = []
            for sym in universe:
                path = _ppath(sym, "price")
                if not path.exists():
                    continue
                try:
                    df = pd.read_parquet(path)
                    if "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        df = df.set_index("date").sort_index()
                    if "close" in df.columns:
                        sliced = df.loc[start:end]["close"]
                        sliced = sliced.where(sliced > 0)  # zero close → NaN
                        if len(sliced.dropna()) > 20:
                            rets = sliced.ffill().pct_change().dropna()
                            rets = rets.replace([np.inf, -np.inf], 0.0)
                            all_returns.append(rets)
                except Exception:
                    pass

            if len(all_returns) < 20:
                logger.warning("EW benchmark: only %d stocks loaded", len(all_returns))
                return -999.0

            # Equal-weight daily return = mean of all stock daily returns
            ew_matrix = pd.DataFrame({f"s{i}": r for i, r in enumerate(all_returns)})
            ew_daily = ew_matrix.mean(axis=1).dropna()
            if len(ew_daily) < 60:
                return -999.0

            ew_clean = ew_daily.replace([np.inf, -np.inf], np.nan).dropna()
            ew_clean = ew_clean.clip(lower=-0.5)  # cap extreme daily losses
            if len(ew_clean) < 60:
                return -999.0
            ew_total = float((1 + ew_clean).prod() - 1)
            if ew_total <= -1:
                return -999.0
            n_years = max(len(ew_clean) / 252, 0.5)
            ew_annual = (1 + ew_total) ** (1 / n_years) - 1
            return float(strategy_gross_annual - ew_annual)

        except Exception as e:
            logger.warning("EW benchmark failed: %s", e)
            return -999.0

    # ------------------------------------------------------------------
    # vs 0050.TW benchmark
    # ------------------------------------------------------------------

    def _vs_benchmark(
        self,
        result,
        universe: list[str],
        start: str,
        end: str,
    ) -> float:
        """計算 vs 0050.TW buy-and-hold 的年化超額報酬。

        取得失敗回傳 -999（確保不自動通過）。
        """
        bars = self._load_0050(start, end)
        if bars is None or len(bars) < 20:
            logger.warning("Benchmark 0050.TW unavailable for %s~%s", start, end)
            return -999.0

        try:
            close = bars["close"]
            bench_total = float(close.iloc[-1] / close.iloc[0] - 1)
            n_years = max((len(result.nav_series) - 1) / 252, 0.5) if len(result.nav_series) > 1 \
                else max(len(bars) / 252, 0.5)
            bench_annual = (1 + bench_total) ** (1 / n_years) - 1
            return float(result.annual_return - bench_annual)
        except Exception as e:
            logger.warning("Benchmark calculation failed: %s", e)
            return -999.0

    # ------------------------------------------------------------------
    # Recent performance
    # ------------------------------------------------------------------

    def _check_recent_performance(
        self,
        strategy,
        universe: list[str],
        end: str,
        lookback_days: int,
    ) -> dict[str, Any]:
        """檢查最近 N 交易日的 Sharpe。回傳 dict 含 sharpe + 元資料。"""
        from src.backtest.engine import BacktestEngine

        try:
            calendar_days = int(lookback_days * 365 / 252) + 30
            recent_start = (pd.Timestamp(end) - pd.Timedelta(days=calendar_days)).strftime("%Y-%m-%d")
            bt_config = self._make_bt_config(universe, recent_start, end)
            engine = BacktestEngine()
            feed = self._build_catalog_feed(universe)
            r = engine.run(strategy, bt_config, feed_override=feed)
            if r.nav_series is not None and len(r.nav_series) < 5:
                return {"sharpe": 0.0, "start": recent_start, "end": end,
                        "error": f"Only {len(r.nav_series)} trading days — data likely missing"}
            if r.total_trades == 0:
                return {"sharpe": 0.0, "start": recent_start, "end": end,
                        "error": "0 trades in recent period"}
            return {"sharpe": r.sharpe, "start": recent_start, "end": end}
        except Exception as e:
            logger.warning("Recent performance check failed: %s", e)
            return {"sharpe": 0.0, "start": "", "end": end, "error": str(e)}
