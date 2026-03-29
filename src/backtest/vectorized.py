"""Vectorized PBO backtest — fast matrix-based backtest for PBO CSCV.

Phase Z1: replaces the event-driven BacktestEngine for PBO variant
backtests only. Does NOT replace the full BacktestEngine for Validator
checks (Sharpe, CAGR, MDD, etc.) — those keep event-driven for correctness.

Limitations (acceptable for PBO relative ranking):
- close-to-close returns (not open-to-open T+1)
- simplified cost model (fixed commission + sell tax, no sqrt slippage)
- no risk rules / lot size / fill simulation
- revenue not truncated by 40 days (all variants share same bias)
- OHLV = close only (no intraday factors)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Default cost parameters (Taiwan market)
_COMMISSION = 0.001425  # 0.1425%
_TAX = 0.003            # 0.3% sell only


class VectorizedPBOBacktest:
    """Fast vectorized backtest for PBO variant analysis.

    Builds price/volume/revenue matrices once, then runs N variants
    as pure numpy/pandas operations.
    """

    def __init__(
        self,
        universe: list[str],
        start: str,
        end: str,
        data_dir: str | Path = "data/market",
        fund_dir: str | Path = "data/fundamental",
    ):
        self.universe = universe
        self.start = start
        self.end = end
        t0 = time.time()
        self._price_matrix, self._volume_matrix = self._build_market_matrices(
            universe, start, end, Path(data_dir)
        )
        self._revenue = self._load_revenue(universe, Path(fund_dir))
        self._returns = self._price_matrix.ffill().pct_change().replace([np.inf, -np.inf], 0.0)
        logger.info(
            "VectorizedPBO: loaded %d stocks × %d days in %.1fs",
            len(self._price_matrix.columns),
            len(self._price_matrix),
            time.time() - t0,
        )

    @staticmethod
    def _build_market_matrices(
        universe: list[str], start: str, end: str, data_dir: Path,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Build (T × N) price and volume matrices from parquet files."""
        prices: dict[str, pd.Series] = {}
        volumes: dict[str, pd.Series] = {}

        for sym in universe:
            bare = sym.replace(".TW", "").replace(".TWO", "")
            for pattern in [f"{sym}_1d.parquet", f"{sym}.parquet", f"finmind_{bare}.parquet"]:
                path = data_dir / pattern
                if not path.exists():
                    continue
                try:
                    df = pd.read_parquet(path)
                    if "date" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        df = df.set_index("date").sort_index()
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    df.index = pd.to_datetime(df.index.date)
                    df = df[~df.index.duplicated(keep="first")]
                    df = df.loc[start:end]
                    if "close" in df.columns and len(df) > 100:
                        close = df["close"]
                        # Replace 0/negative prices with NaN (data corruption)
                        close = close.where(close > 0)
                        if close.isna().sum() / len(close) > 0.10:
                            continue  # skip stocks with >10% bad prices
                        prices[sym] = close
                        volumes[sym] = df.get("volume", pd.Series(0, index=df.index))
                except Exception:
                    continue
                break

        price_matrix = pd.DataFrame(prices).sort_index()
        volume_matrix = pd.DataFrame(volumes).sort_index().reindex_like(price_matrix)
        return price_matrix, volume_matrix

    @staticmethod
    def _load_revenue(universe: list[str], fund_dir: Path) -> dict[str, pd.DataFrame]:
        """Load revenue data for all symbols."""
        revenue: dict[str, pd.DataFrame] = {}
        for sym in universe:
            bare = sym.replace(".TW", "").replace(".TWO", "")
            for name in [f"{sym}_revenue.parquet", f"{bare}_revenue.parquet"]:
                path = fund_dir / name
                if not path.exists():
                    continue
                try:
                    df = pd.read_parquet(path)
                    if not df.empty and "revenue" in df.columns:
                        df["date"] = pd.to_datetime(df["date"])
                        revenue[sym] = df.sort_values("date")
                except Exception:
                    pass
                break
        return revenue

    def run_variant(
        self,
        compute_factor: Callable,
        top_n: int,
        weight_mode: str = "equal",
        rebal_skip: int = 0,
    ) -> pd.Series:
        """Run one PBO variant, return daily portfolio returns."""
        prices = self._price_matrix
        symbols = prices.columns.tolist()

        # Monthly rebalance dates (aligned with event-driven engine)
        monthly_groups = prices.groupby(prices.index.to_period("M"))
        monthly_first = monthly_groups.apply(lambda g: g.index[0])
        if rebal_skip > 0:
            monthly_first = monthly_first.iloc[::rebal_skip + 1]
        rebal_dates = list(monthly_first.values)

        # Build weight matrix (NaN = not set, will be forward-filled)
        weight_matrix = pd.DataFrame(np.nan, index=prices.index, columns=symbols)

        for date in rebal_dates:
            as_of = pd.Timestamp(date)

            # Build data dict matching compute_factor(symbols, as_of, data) interface
            data = self._build_factor_data(symbols, as_of)

            try:
                values = compute_factor(symbols, as_of, data)
            except Exception:
                continue

            if not values:
                continue

            ranked = sorted(values, key=lambda s: values[s], reverse=True)
            selected = [s for s in ranked[:top_n] if s in symbols]
            if not selected:
                continue

            # Assign weights based on mode
            if weight_mode == "signal":
                vals = {s: max(values[s], 0.0) for s in selected}
                total = sum(vals.values())
                if total <= 0:
                    w = 1.0 / len(selected)
                    for s in selected:
                        weight_matrix.loc[date, s] = w
                else:
                    for s in selected:
                        weight_matrix.loc[date, s] = vals[s] / total
            elif weight_mode == "inverse_rank":
                n = len(selected)
                total = n * (n + 1) / 2
                for i, s in enumerate(selected):
                    weight_matrix.loc[date, s] = (n - i) / total
            elif weight_mode == "score_tilt":
                # Weight by z-score (positive only): higher factor value → more weight
                import numpy as _np
                all_vals = [values[s] for s in selected]
                _mean = _np.mean(all_vals)
                _std = _np.std(all_vals)
                if _std > 1e-10:
                    z = {s: max((values[s] - _mean) / _std, 0.01) for s in selected}
                else:
                    z = {s: 1.0 for s in selected}
                z_total = sum(z.values())
                for s in selected:
                    weight_matrix.loc[date, s] = z[s] / z_total
            else:  # equal
                w = 1.0 / len(selected)
                for s in selected:
                    weight_matrix.loc[date, s] = w

        # Forward-fill using rebalance mask (H-01 fix)
        is_rebal = pd.Series(False, index=weight_matrix.index)
        for d in rebal_dates:
            if d in is_rebal.index:
                is_rebal.loc[d] = True
        for col in weight_matrix.columns:
            weight_matrix[col] = weight_matrix[col].where(is_rebal).ffill().fillna(0)

        # Lot size rounding: weight → shares → round to lot → back to weight
        # Taiwan: 1000 shares = 1 lot. Affects small positions significantly.
        nav = 10_000_000  # assume fixed NAV for lot size calc
        lot_size = 1000
        for date in rebal_dates:
            if date not in prices.index:
                continue
            for col in symbols:
                w = weight_matrix.loc[date, col]
                if w <= 0 or col not in prices.columns:
                    continue
                price = prices.loc[date, col]
                if pd.isna(price) or price <= 0:
                    continue
                shares = w * nav / price
                shares = (shares // lot_size) * lot_size
                weight_matrix.loc[date, col] = shares * price / nav if shares > 0 else 0.0
            # Re-normalize weights to sum to ~1
            row_sum = weight_matrix.loc[date].sum()
            if row_sum > 0:
                weight_matrix.loc[date] /= row_sum

        # Compute portfolio returns with simplified costs (M-03, M-06 fix)
        weight_diff = weight_matrix.diff().fillna(0)
        sells = weight_diff.clip(upper=0).abs()
        buys = weight_diff.clip(lower=0)
        cost_per_bar = (buys * _COMMISSION + sells * (_COMMISSION + _TAX)).sum(axis=1)

        gross_returns = (weight_matrix.shift(1) * self._returns).sum(axis=1)
        return gross_returns - cost_per_bar

    def _build_factor_data(self, symbols: list[str], as_of: pd.Timestamp) -> dict:
        """Build data dict matching compute_factor(symbols, as_of, data) interface.

        #4 fix: pre-build full bars DataFrames once, then slice by as_of.
        Avoids rebuilding 12,000 DataFrames per run.
        """
        # Lazy init: build full bars dict once
        if not hasattr(self, '_bars_cache'):
            prices = self._price_matrix
            volumes = self._volume_matrix
            self._bars_cache: dict[str, pd.DataFrame] = {}
            for s in symbols:
                if s not in prices.columns:
                    continue
                p = prices[s].dropna()
                v = volumes[s].dropna() if s in volumes.columns else pd.Series(0.0, index=p.index)
                if len(p) < 10:
                    continue
                self._bars_cache[s] = pd.DataFrame({
                    "open": p, "high": p, "low": p, "close": p,
                    "volume": v.reindex(p.index, fill_value=0),
                })

        # Slice by as_of (cheap .loc slice, no DataFrame construction)
        bars: dict[str, pd.DataFrame] = {}
        for s, full_df in self._bars_cache.items():
            sliced = full_df.loc[:as_of]
            if len(sliced) >= 10:
                bars[s] = sliced

        return {
            "bars": bars,
            "revenue": self._revenue,
            "institutional": {},
            "pe": {}, "pb": {}, "roe": {},
        }
