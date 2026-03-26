"""Experiment grid framework — parallel backtesting across parameter combinations."""

from __future__ import annotations

import itertools
import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.alpha.pipeline import AlphaConfig, FactorSpec
from src.backtest.analytics import deflated_sharpe
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.alpha.strategy import AlphaStrategy

logger = logging.getLogger(__name__)


@dataclass
class PeriodConfig:
    """A backtest evaluation period."""

    period_id: str
    start: str
    end: str
    description: str


@dataclass
class ExperimentConfig:
    """One experiment configuration (one point in the parameter grid)."""

    name: str
    universe: list[str]
    factors: list[str]
    rebalance_freq: str = "monthly"  # daily/weekly/monthly
    holding_period: int = 20
    max_weight: float = 0.05
    kill_switch_pct: float | None = 0.05  # None = disabled
    neutralize: str = "none"  # none/market/industry
    construction: str = "equal_weight"  # equal_weight/signal_weight/risk_parity
    initial_cash: float = 10_000_000
    fractional_shares: bool = True


@dataclass
class ExperimentResult:
    """Result of one (config, period) backtest run."""

    config_name: str
    period_id: str
    total_return: float
    annual_return: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    total_trades: int
    total_commission: float
    win_rate: float
    var_95: float
    cvar_95: float
    benchmark_return: float = 0.0
    excess_return: float = 0.0


# Default periods from the research prebrief
DEFAULT_PERIODS = [
    PeriodConfig("P1", "2020-01-01", "2021-06-30", "COVID crash + V recovery"),
    PeriodConfig("P2", "2021-07-01", "2022-12-31", "Bull to bear"),
    PeriodConfig("P3", "2023-01-01", "2024-06-30", "AI bull"),
    PeriodConfig("P4", "2024-07-01", "2025-06-30", "Volatile + tariff"),
    PeriodConfig("FULL", "2020-01-01", "2025-06-30", "Full 5.5 years"),
]


def _run_single_backtest(args: tuple[dict[str, Any], dict[str, Any], list[str]]) -> dict[str, Any]:
    """Run a single backtest — designed for ProcessPoolExecutor."""
    config_dict, period_dict, universe = args

    # Reconstruct objects (can't pickle complex objects across processes)
    factors = [FactorSpec(name=f) for f in config_dict["factors"]]

    alpha_config = AlphaConfig(
        factors=factors,
        combine_method="equal",
        holding_period=config_dict["holding_period"],
    )
    # Set construction max_weight
    alpha_config.construction.max_weight = config_dict["max_weight"]

    strategy = AlphaStrategy(config=alpha_config)

    bt_config = BacktestConfig(
        universe=universe,
        start=period_dict["start"],
        end=period_dict["end"],
        initial_cash=config_dict["initial_cash"],
        fractional_shares=config_dict["fractional_shares"],
        rebalance_freq=config_dict["rebalance_freq"],
        commission_rate=0.001425,
        tax_rate=0.003,
    )

    # Handle kill switch
    if config_dict.get("kill_switch_pct") is None:
        bt_config.enable_kill_switch = False

    try:
        engine = BacktestEngine()
        result = engine.run(strategy, bt_config)

        return {
            "config_name": config_dict["name"],
            "period_id": period_dict["period_id"],
            "total_return": result.total_return,
            "annual_return": result.annual_return,
            "sharpe": result.sharpe,
            "sortino": result.sortino,
            "calmar": result.calmar,
            "max_drawdown": result.max_drawdown,
            "total_trades": result.total_trades,
            "total_commission": result.total_commission,
            "win_rate": result.win_rate,
            "var_95": result.var_95,
            "cvar_95": result.cvar_95,
            "success": True,
            "error": "",
        }
    except Exception as e:
        logger.warning("Backtest failed for %s / %s: %s", config_dict["name"], period_dict["period_id"], e)
        return {
            "config_name": config_dict["name"],
            "period_id": period_dict["period_id"],
            "success": False,
            "error": str(e),
        }


def generate_coarse_grid() -> list[ExperimentConfig]:
    """Generate 256 coarse grid configurations (2^8).

    Each of 8 dimensions has 2 values, yielding 2^8 = 256 combinations.
    Universe symbols must be filled by the caller via the returned configs'
    ``universe`` field or via ``universes`` dict in ``run_experiment_grid``.
    """
    grid: dict[str, list[Any]] = {
        "universe_name": ["TW50", "TW300"],
        "rebalance_freq": ["weekly", "monthly"],
        "holding_period": [10, 20],
        "factors": [
            ["momentum"],
            ["momentum", "ma_cross", "volatility"],
        ],
        "max_weight": [0.05, 0.15],
        "kill_switch_pct": [0.05, None],
        "neutralize": ["none", "market"],
        "construction": ["equal_weight", "risk_parity"],
    }

    configs: list[ExperimentConfig] = []
    keys = list(grid.keys())
    values = list(grid.values())

    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        factor_label = "_".join(params["factors"])
        ks_label = f"{params['kill_switch_pct']}" if params["kill_switch_pct"] is not None else "off"
        name = (
            f"{params['universe_name']}_{params['rebalance_freq']}_"
            f"{params['holding_period']}d_{factor_label}_"
            f"{params['max_weight']}w_ks{ks_label}_"
            f"{params['neutralize']}_{params['construction']}"
        )
        configs.append(
            ExperimentConfig(
                name=name,
                universe=[],  # filled by caller with actual symbols
                factors=params["factors"],
                rebalance_freq=params["rebalance_freq"],
                holding_period=params["holding_period"],
                max_weight=params["max_weight"],
                kill_switch_pct=params["kill_switch_pct"],
                neutralize=params["neutralize"],
                construction=params["construction"],
            )
        )

    return configs


def run_experiment_grid(
    configs: list[ExperimentConfig],
    periods: list[PeriodConfig] | None = None,
    universes: dict[str, list[str]] | None = None,
    n_workers: int | None = None,
    progress_callback: Any = None,
) -> pd.DataFrame:
    """Run full experiment grid with parallel backtesting.

    Args:
        configs: List of experiment configurations.
        periods: Backtest periods (default: 5 standard periods).
        universes: ``{"TW50": [...symbols...], "TW300": [...]}``.
        n_workers: Number of parallel workers (default: CPU count - 2).
        progress_callback: Optional ``callback(completed, total)``.

    Returns:
        DataFrame with one row per (config, period) combination.
    """
    if periods is None:
        periods = DEFAULT_PERIODS
    if n_workers is None:
        n_workers = max(1, mp.cpu_count() - 2)

    # Build task list
    tasks: list[tuple[dict[str, Any], dict[str, Any], list[str]]] = []
    for config in configs:
        # Resolve universe
        universe = config.universe
        if not universe and universes:
            for univ_name, symbols in universes.items():
                if univ_name in config.name:
                    universe = symbols
                    break

        config_dict = {
            "name": config.name,
            "factors": config.factors,
            "rebalance_freq": config.rebalance_freq,
            "holding_period": config.holding_period,
            "max_weight": config.max_weight,
            "kill_switch_pct": config.kill_switch_pct,
            "neutralize": config.neutralize,
            "construction": config.construction,
            "initial_cash": config.initial_cash,
            "fractional_shares": config.fractional_shares,
        }

        for period in periods:
            period_dict = {
                "period_id": period.period_id,
                "start": period.start,
                "end": period.end,
            }
            tasks.append((config_dict, period_dict, universe))

    total = len(tasks)
    logger.info("Starting experiment grid: %d tasks on %d workers", total, n_workers)

    results: list[dict[str, Any]] = []
    completed = 0

    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = {pool.submit(_run_single_backtest, task): task for task in tasks}
        for future in as_completed(futures):
            completed += 1
            try:
                result = future.result(timeout=300)  # 5 min timeout per backtest
                results.append(result)
            except Exception as e:
                task = futures[future]
                results.append(
                    {
                        "config_name": task[0]["name"],
                        "period_id": task[1]["period_id"],
                        "success": False,
                        "error": str(e),
                    }
                )

            if progress_callback:
                progress_callback(completed, total)
            elif completed % 50 == 0 or completed == total:
                logger.info("Progress: %d/%d (%.0f%%)", completed, total, completed / total * 100)

    df = pd.DataFrame(results)
    logger.info("Experiment grid complete: %d results", len(df))
    return df


def analyze_results(df: pd.DataFrame, total_trials: int | None = None) -> pd.DataFrame:
    """Analyze experiment results: rank by Sharpe, check consistency, compute DSR.

    Args:
        df: Raw results DataFrame from ``run_experiment_grid``.
        total_trials: Number of independent trials for DSR correction.
            Defaults to the number of unique config names.

    Returns:
        Summary DataFrame sorted by full-period Sharpe, with pass/fail flag.
    """
    if total_trials is None:
        total_trials = df["config_name"].nunique()

    # Only successful runs
    success_col = df.get("success")
    if success_col is not None:
        successful = df[success_col == True].copy()  # noqa: E712
    else:
        successful = df.copy()

    if successful.empty:
        return pd.DataFrame()

    summary_rows: list[dict[str, Any]] = []
    for config_name, group in successful.groupby("config_name"):
        periods_with_data = group[group["period_id"] != "FULL"]
        full_period = group[group["period_id"] == "FULL"]

        if full_period.empty:
            continue

        full = full_period.iloc[0]

        # Count periods with positive Sharpe
        positive_periods = int((periods_with_data["sharpe"] > 0).sum())
        total_periods = len(periods_with_data)

        # DSR on FULL period Sharpe
        dsr = deflated_sharpe(
            observed_sharpe=full.get("sharpe", 0),
            n_trials=total_trials,
            T=max(int(full.get("total_trades", 252)), 252),
        )

        # Worst drawdown across all periods
        worst_dd = float(group["max_drawdown"].max())

        # Consistency check
        passes = (
            positive_periods >= 3
            and full.get("sharpe", 0) > 0
            and worst_dd < 0.25
            and dsr > 0.05  # relaxed for exploration
        )

        summary_rows.append(
            {
                "config_name": config_name,
                "full_return": full.get("total_return", 0),
                "full_annual": full.get("annual_return", 0),
                "full_sharpe": full.get("sharpe", 0),
                "full_sortino": full.get("sortino", 0),
                "full_calmar": full.get("calmar", 0),
                "full_max_dd": full.get("max_drawdown", 0),
                "full_trades": full.get("total_trades", 0),
                "full_commission": full.get("total_commission", 0),
                "full_win_rate": full.get("win_rate", 0),
                "positive_periods": positive_periods,
                "total_periods": total_periods,
                "consistency": f"{positive_periods}/{total_periods}",
                "worst_dd": worst_dd,
                "dsr": dsr,
                "passes": bool(passes),
            }
        )

    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary = summary.sort_values("full_sharpe", ascending=False)

    return summary


def summarize_results(summary: pd.DataFrame) -> str:
    """Generate human-readable experiment summary."""
    lines = [
        "=" * 70,
        "EXPERIMENT GRID RESULTS",
        "=" * 70,
        "",
        f"Total configurations tested: {len(summary)}",
        f"Passing configurations: {int(summary['passes'].sum())}",
        "",
    ]

    if summary["passes"].any():
        lines.append("TOP 10 PASSING CONFIGURATIONS:")
        lines.append("-" * 70)
        top = summary[summary["passes"]].head(10)
        for _, row in top.iterrows():
            lines.append(f"  {row['config_name'][:60]}")
            lines.append(
                f"    Return={row['full_annual']:+.1%} Sharpe={row['full_sharpe']:.2f} "
                f"DD={row['full_max_dd']:.1%} DSR={row['dsr']:.3f} "
                f"Consistency={row['consistency']}"
            )
        lines.append("")

    if not summary["passes"].any():
        lines.append("WARNING: NO CONFIGURATIONS PASSED ALL CRITERIA")
        lines.append("")
        lines.append("BEST 5 (by Sharpe, even if failing):")
        for _, row in summary.head(5).iterrows():
            lines.append(f"  {row['config_name'][:60]}")
            lines.append(
                f"    Return={row['full_annual']:+.1%} Sharpe={row['full_sharpe']:.2f} "
                f"DD={row['full_max_dd']:.1%} DSR={row['dsr']:.3f} "
                f"Consistency={row['consistency']}"
            )

    return "\n".join(lines)
