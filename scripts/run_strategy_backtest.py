"""Phase L 策略回測腳本 — 營收動能 + 投信跟單策略 8 年回測。

用法:
    python -m scripts.run_strategy_backtest --strategy revenue_momentum
    python -m scripts.run_strategy_backtest --strategy trust_follow
    python -m scripts.run_strategy_backtest --strategy filter_revenue_momentum
    python -m scripts.run_strategy_backtest --strategy all --start 2017-01-01
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategy.registry import resolve_strategy
from src.alpha.filter_strategy import revenue_momentum_filter, trust_follow_filter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# 台股活躍標的 — data/market/ 中可用的
MARKET_DIR = Path("data/market")


def discover_universe() -> list[str]:
    """從 data/market/ 自動發現所有台股標的。"""
    symbols = []
    if MARKET_DIR.exists():
        for f in sorted(MARKET_DIR.glob("*.TW_1d.parquet")):
            # e.g. "2330.TW_1d.parquet" → "2330.TW"
            sym = f.stem.replace("_1d", "")
            symbols.append(sym)
    if not symbols:
        logger.warning("data/market/ 無 .TW.parquet，使用預設 TW50")
        symbols = [
            "2330.TW", "2317.TW", "2454.TW", "2303.TW", "2308.TW",
            "2881.TW", "2882.TW", "2886.TW", "2891.TW", "1301.TW",
            "1303.TW", "1101.TW", "2002.TW", "3008.TW", "3034.TW",
            "2412.TW", "2379.TW", "2603.TW", "5871.TW", "2880.TW",
        ]
    return symbols


def run_backtest(
    strategy_name: str,
    universe: list[str],
    start: str,
    end: str,
    initial_cash: float,
) -> dict:
    """執行單一策略回測。"""
    # Resolve strategy
    if strategy_name == "filter_revenue_momentum":
        strategy = revenue_momentum_filter()
    elif strategy_name == "filter_trust_follow":
        strategy = trust_follow_filter()
    else:
        strategy = resolve_strategy(strategy_name)

    config = BacktestConfig(
        universe=universe,
        start=start,
        end=end,
        initial_cash=initial_cash,
        commission_rate=0.001425,
        tax_rate=0.003,
        slippage_bps=5.0,
    )

    logger.info("回測 %s: %s ~ %s, %d 支股票", strategy_name, start, end, len(universe))

    engine = BacktestEngine()
    result = engine.run(strategy, config)

    # Print key metrics
    print(f"\n{'='*60}")
    print(f"策略: {strategy_name}")
    print(f"期間: {start} ~ {end}")
    print(f"Universe: {len(universe)} 支")
    print(f"{'='*60}")

    metrics = {
        "total_return": getattr(result, "total_return", 0),
        "cagr": getattr(result, "annual_return", 0),
        "sharpe": getattr(result, "sharpe", 0),
        "sortino": getattr(result, "sortino", 0),
        "max_drawdown": getattr(result, "max_drawdown", 0),
        "volatility": getattr(result, "volatility", 0),
        "total_trades": getattr(result, "total_trades", 0),
        "win_rate": getattr(result, "win_rate", 0),
    }

    for k, v in metrics.items():
        if isinstance(v, float):
            if "return" in k or "cagr" in k or "drawdown" in k:
                print(f"  {k:25s}: {v:+.2%}")
            else:
                print(f"  {k:25s}: {v:.4f}")
        else:
            print(f"  {k:25s}: {v}")

    print(f"{'='*60}\n")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase L 策略回測")
    parser.add_argument(
        "--strategy",
        choices=[
            "revenue_momentum", "trust_follow",
            "filter_revenue_momentum", "filter_trust_follow",
            "momentum_12_1", "all",
        ],
        default="all",
        help="策略名稱",
    )
    parser.add_argument("--start", default="2017-01-01", help="回測起始日期")
    parser.add_argument("--end", default="2025-12-31", help="回測結束日期")
    parser.add_argument(
        "--cash", type=float, default=10_000_000,
        help="初始資金（預設 1,000 萬）",
    )
    args = parser.parse_args()

    universe = discover_universe()
    logger.info("Universe: %d 支股票", len(universe))

    strategies = (
        [
            "revenue_momentum", "trust_follow",
            "filter_revenue_momentum", "filter_trust_follow",
            "momentum_12_1",
        ]
        if args.strategy == "all"
        else [args.strategy]
    )

    results = {}
    for strat_name in strategies:
        try:
            metrics = run_backtest(
                strat_name, universe, args.start, args.end, args.cash,
            )
            results[strat_name] = metrics
        except Exception as e:
            logger.error("策略 %s 回測失敗: %s", strat_name, e)
            results[strat_name] = {"error": str(e)}

    # Comparison table
    if len(results) > 1:
        print("\n" + "=" * 80)
        print("策略比較")
        print("=" * 80)
        print(f"{'策略':30s} {'CAGR':>10s} {'Sharpe':>10s} {'MDD':>10s}")
        print("-" * 80)
        for name, m in results.items():
            if "error" in m:
                print(f"{name:30s} {'ERROR':>10s}")
            else:
                cagr = m.get("cagr", 0)
                sharpe = m.get("sharpe", 0)
                mdd = m.get("max_drawdown", 0)
                print(f"{name:30s} {cagr:>+9.2%} {sharpe:>10.3f} {mdd:>+9.2%}")
        print("=" * 80)


if __name__ == "__main__":
    main()
