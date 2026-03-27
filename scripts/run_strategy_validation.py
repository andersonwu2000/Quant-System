"""Phase L 策略嚴格驗證 — Walk-Forward + PBO + 統計檢驗。

用法: python -m scripts.run_strategy_validation
"""

from __future__ import annotations

import logging
import sys
import time
import warnings
from pathlib import Path

import numpy as np
from scipy import stats

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategy.registry import resolve_strategy


MARKET_DIR = Path("data/market")


def discover_universe() -> list[str]:
    symbols = sorted(p.stem.replace("_1d", "") for p in MARKET_DIR.glob("*.TW_1d.parquet"))
    return [s for s in symbols if not s.startswith("00")]


def run_backtest(strategy_name: str, universe: list[str], start: str, end: str) -> dict:
    config = BacktestConfig(
        universe=universe,
        start=start,
        end=end,
        initial_cash=10_000_000,
        commission_rate=0.001425,
        tax_rate=0.003,
        slippage_bps=5.0,
        rebalance_freq="monthly",
    )
    engine = BacktestEngine()
    strat = resolve_strategy(strategy_name)
    r = engine.run(strat, config)
    return {
        "cagr": r.annual_return,
        "sharpe": r.sharpe,
        "sortino": r.sortino,
        "max_dd": r.max_drawdown,
        "total_return": r.total_return,
        "volatility": r.volatility,
        "trades": r.total_trades,
        "win_rate": r.win_rate,
        "equity_curve": getattr(r, "equity_curve", None),
    }


# ── Walk-Forward ──────────────────────────────────────────────────


def walk_forward(strategy_name: str, universe: list[str], periods: list[tuple[str, str]]) -> list[dict]:
    """Run strategy on multiple non-overlapping OOS periods."""
    results = []
    for start, end in periods:
        print(f"  WF period {start} ~ {end}...", end=" ", flush=True)
        t0 = time.time()
        r = run_backtest(strategy_name, universe, start, end)
        dt = time.time() - t0
        print(f"CAGR={r['cagr']:+.2%} Sharpe={r['sharpe']:.3f} ({dt:.0f}s)")
        r["period"] = f"{start}~{end}"
        results.append(r)
    return results


# ── PBO (Probability of Backtest Overfitting) ─────────────────────


def compute_pbo(strategy_name: str, universe: list[str], n_trials: int = 16) -> float:
    """Simplified PBO: run strategy on N random subperiods, check Sharpe consistency.

    PBO = fraction of trials where IS rank doesn't predict OOS rank.
    Simplified version: split 2018-2024 into N half-year blocks, CSCV.
    """
    # Define half-year blocks
    blocks = [
        ("2018-01-01", "2018-06-30"), ("2018-07-01", "2018-12-31"),
        ("2019-01-01", "2019-06-30"), ("2019-07-01", "2019-12-31"),
        ("2020-01-01", "2020-06-30"), ("2020-07-01", "2020-12-31"),
        ("2021-01-01", "2021-06-30"), ("2021-07-01", "2021-12-31"),
        ("2022-01-01", "2022-06-30"), ("2022-07-01", "2022-12-31"),
        ("2023-01-01", "2023-06-30"), ("2023-07-01", "2023-12-31"),
        ("2024-01-01", "2024-06-30"), ("2024-07-01", "2024-12-31"),
    ]

    # Run each block
    block_sharpes = []
    for start, end in blocks:
        print(f"  PBO block {start}~{end}...", end=" ", flush=True)
        try:
            r = run_backtest(strategy_name, universe, start, end)
            block_sharpes.append(r["sharpe"])
            print(f"Sharpe={r['sharpe']:.3f}")
        except Exception as e:
            print(f"ERROR: {e}")
            block_sharpes.append(0.0)

    # CSCV: for each combination of S/2 blocks as IS, rest as OOS
    n_blocks = len(block_sharpes)
    half = n_blocks // 2
    sharpes = np.array(block_sharpes)

    rng = np.random.RandomState(42)
    n_overfit = 0

    for _ in range(min(n_trials, 100)):
        perm = rng.permutation(n_blocks)
        is_idx = perm[:half]
        oos_idx = perm[half:]

        is_sharpe = sharpes[is_idx].mean()
        oos_sharpe = sharpes[oos_idx].mean()

        # Overfit if IS looks good but OOS is bad
        if is_sharpe > 0 and oos_sharpe <= 0:
            n_overfit += 1

    pbo = n_overfit / min(n_trials, 100)
    return pbo


# ── Statistical Tests ─────────────────────────────────────────────


def statistical_tests(wf_results: list[dict]) -> dict:
    """Run statistical tests on walk-forward results."""
    sharpes = [r["sharpe"] for r in wf_results]
    cagrs = [r["cagr"] for r in wf_results]

    # t-test: Sharpe > 0
    t_stat, p_value = stats.ttest_1samp(sharpes, 0)

    # Bootstrap 95% CI for mean Sharpe
    rng = np.random.RandomState(42)
    n_boot = 1000
    boot_means = []
    for _ in range(n_boot):
        sample = rng.choice(sharpes, size=len(sharpes), replace=True)
        boot_means.append(np.mean(sample))
    ci_lo = np.percentile(boot_means, 2.5)
    ci_hi = np.percentile(boot_means, 97.5)

    return {
        "mean_sharpe": np.mean(sharpes),
        "std_sharpe": np.std(sharpes),
        "mean_cagr": np.mean(cagrs),
        "t_stat": t_stat,
        "p_value": p_value,
        "ci_95_lo": ci_lo,
        "ci_95_hi": ci_hi,
        "n_positive_sharpe": sum(1 for s in sharpes if s > 0),
        "n_periods": len(sharpes),
    }


# ── Main ──────────────────────────────────────────────────────────


def main() -> None:
    t0_total = time.time()
    universe = discover_universe()
    print(f"Universe: {len(universe)} symbols\n")

    strategy = "revenue_momentum"

    # 1. Full period backtest
    print("=" * 70)
    print("1. Full Period Backtest (2018-2024)")
    print("=" * 70)
    full = run_backtest(strategy, universe, "2018-01-01", "2024-12-31")
    print(f"  CAGR: {full['cagr']:+.2%}")
    print(f"  Sharpe: {full['sharpe']:.3f}")
    print(f"  Sortino: {full['sortino']:.3f}")
    print(f"  Max DD: {full['max_dd']:+.2%}")
    print(f"  Trades: {full['trades']}")
    print(f"  Win Rate: {full['win_rate']:.1%}")

    # 2. Walk-Forward (annual periods)
    print(f"\n{'=' * 70}")
    print("2. Walk-Forward (Annual OOS Periods)")
    print("=" * 70)
    wf_periods = [
        ("2018-01-01", "2018-12-31"),
        ("2019-01-01", "2019-12-31"),
        ("2020-01-01", "2020-12-31"),
        ("2021-01-01", "2021-12-31"),
        ("2022-01-01", "2022-12-31"),
        ("2023-01-01", "2023-12-31"),
        ("2024-01-01", "2024-12-31"),
    ]
    wf_results = walk_forward(strategy, universe, wf_periods)

    # 3. Statistical Tests
    print(f"\n{'=' * 70}")
    print("3. Statistical Tests")
    print("=" * 70)
    stats_result = statistical_tests(wf_results)
    print(f"  Mean Sharpe: {stats_result['mean_sharpe']:.3f} ± {stats_result['std_sharpe']:.3f}")
    print(f"  Mean CAGR: {stats_result['mean_cagr']:+.2%}")
    print(f"  t-stat (Sharpe > 0): {stats_result['t_stat']:.3f}")
    print(f"  p-value: {stats_result['p_value']:.4f}")
    print(f"  95% CI Sharpe: [{stats_result['ci_95_lo']:.3f}, {stats_result['ci_95_hi']:.3f}]")
    print(f"  Positive Sharpe: {stats_result['n_positive_sharpe']}/{stats_result['n_periods']}")

    # 4. PBO
    print(f"\n{'=' * 70}")
    print("4. PBO (Probability of Backtest Overfitting)")
    print("=" * 70)
    pbo = compute_pbo(strategy, universe, n_trials=50)
    print(f"  PBO: {pbo:.1%}")
    print(f"  {'PASS' if pbo < 0.5 else 'FAIL'} (threshold: < 50%)")

    # 5. OOS validation (2025 H1)
    print(f"\n{'=' * 70}")
    print("5. OOS Validation (2025 H1)")
    print("=" * 70)
    oos = run_backtest(strategy, universe, "2025-01-01", "2025-06-30")
    print(f"  CAGR: {oos['cagr']:+.2%}")
    print(f"  Sharpe: {oos['sharpe']:.3f}")
    print(f"  Return: {oos['total_return']:+.2%}")

    # 6. Summary
    print(f"\n{'=' * 70}")
    print("VALIDATION SUMMARY — revenue_momentum")
    print("=" * 70)
    checks = [
        ("CAGR > 15%", full["cagr"] > 0.15, f"{full['cagr']:+.2%}"),
        ("Sharpe > 0.7", full["sharpe"] > 0.7, f"{full['sharpe']:.3f}"),
        ("Max DD < 50%", full["max_dd"] < 0.50, f"{full['max_dd']:+.2%}"),
        ("WF mean Sharpe > 0", stats_result["mean_sharpe"] > 0, f"{stats_result['mean_sharpe']:.3f}"),
        ("p-value < 0.05", stats_result["p_value"] < 0.05, f"{stats_result['p_value']:.4f}"),
        ("PBO < 50%", pbo < 0.5, f"{pbo:.1%}"),
        ("OOS 2025 H1 > 0", oos["total_return"] > 0, f"{oos['total_return']:+.2%}"),
    ]

    for name, passed, value in checks:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name:30s} = {value}")

    passed_count = sum(1 for _, p, _ in checks if p)
    print(f"\n  Result: {passed_count}/{len(checks)} checks passed")
    print(f"  Total time: {time.time() - t0_total:.0f}s")


if __name__ == "__main__":
    main()
