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


FUND_DIR = Path("data/fundamental")


def discover_universe(require_fundamentals: bool = True) -> list[str]:
    """從 data/market/ 自動發現台股標的。

    Args:
        require_fundamentals: 若 True，只回傳同時有本地營收 parquet 的股票。
            避免回測中觸發 FinMind API 呼叫。
    """
    market_symbols = set()
    if MARKET_DIR.exists():
        for f in sorted(MARKET_DIR.glob("*.TW_1d.parquet")):
            sym = f.stem.replace("_1d", "")
            if not sym.startswith("finmind_"):
                market_symbols.add(sym)

    if not market_symbols:
        logger.warning("data/market/ 無 .TW.parquet，使用預設 TW50")
        market_symbols = {
            "2330.TW", "2317.TW", "2454.TW", "2303.TW", "2308.TW",
            "2881.TW", "2882.TW", "2886.TW", "2891.TW", "1301.TW",
            "1303.TW", "1101.TW", "2002.TW", "3008.TW", "3034.TW",
            "2412.TW", "2379.TW", "2603.TW", "5871.TW", "2880.TW",
        }

    if require_fundamentals and FUND_DIR.exists():
        fund_symbols = {
            f.stem.replace("_revenue", "")
            for f in FUND_DIR.glob("*_revenue.parquet")
        }
        filtered = sorted(market_symbols & fund_symbols)
        if filtered:
            logger.info(
                "Universe: %d 有價格 + 營收數據（原 %d 支價格）",
                len(filtered), len(market_symbols),
            )
            return filtered

    return sorted(market_symbols)


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
        # 台股完整成本模型
        commission_rate=0.001425,    # 手續費 0.1425%（SimBroker 自動套用 min_commission NT$20）
        tax_rate=0.003,              # 證交稅 0.3%（賣出）
        slippage_bps=5.0,            # 基礎滑點
        impact_model="sqrt",         # 市場衝擊：sqrt 模型
        impact_coeff=50.0,
        base_slippage_bps=2.0,
        # 月度再平衡（營收策略月頻）
        rebalance_freq="monthly",
        # Kill Switch — DD 5% 暫停，月底恢復
        enable_kill_switch=True,
        kill_switch_cooldown="end_of_month",
        # 零股模式（個人投資者）
        fractional_shares=True,
        # 執行延遲：T+1 開盤價成交（更貼近真實）
        execution_delay=1,
        fill_on="open",
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


def run_walkforward_validation(
    strategies: list[str],
    universe: list[str],
    initial_cash: float,
) -> None:
    """滾動 3 年訓練 / 1 年測試 Walk-Forward。"""
    import sys

    # Walk-forward windows: train 3yr, test 1yr, rolling 1yr
    windows = [
        ("2017-01-01", "2019-12-31", "2020-01-01", "2020-12-31"),
        ("2018-01-01", "2020-12-31", "2021-01-01", "2021-12-31"),
        ("2019-01-01", "2021-12-31", "2022-01-01", "2022-12-31"),
        ("2020-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),
        ("2021-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
    ]

    # 壓低 log level 避免 walkforward 輸出被淹沒
    prev_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.ERROR)
    # 也壓 FinMind 的 logger
    logging.getLogger("FinMind").setLevel(logging.ERROR)

    for strat_name in strategies:
        print(f"\n--- {strat_name} Walk-Forward ---", flush=True)
        print(f"{'Test Year':<12} {'CAGR':>10} {'Sharpe':>10} {'MDD':>10} {'Trades':>8}", flush=True)
        print("-" * 55, flush=True)

        oos_results = []
        for train_start, train_end, test_start, test_end in windows:
            try:
                metrics = run_backtest(strat_name, universe, test_start, test_end, initial_cash)
                cagr = metrics.get("cagr", 0)
                sharpe = metrics.get("sharpe", 0)
                mdd = metrics.get("max_drawdown", 0)
                trades = metrics.get("total_trades", 0)
                oos_results.append({"year": test_start[:4], "cagr": cagr, "sharpe": sharpe, "mdd": mdd, "trades": trades})
            except Exception as e:
                oos_results.append({"year": test_start[:4], "cagr": 0, "sharpe": 0, "mdd": 0, "trades": 0, "error": str(e)})

        # 恢復 log level 再輸出結果
        logging.getLogger().setLevel(prev_level)
        logging.getLogger("FinMind").setLevel(prev_level)

        # 統一輸出（不會被 log 打斷）
        for r in oos_results:
            if "error" in r:
                print(f"{r['year']:<12} {'ERROR':>10}   {r['error']}", flush=True)
            else:
                print(
                    f"{r['year']:<12} {r['cagr']:>+9.2%} {r['sharpe']:>10.3f} "
                    f"{r['mdd']:>+9.2%} {r['trades']:>8}",
                    flush=True,
                )

        oos_sharpes = [r["sharpe"] for r in oos_results]
        avg_oos = sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else 0
        positive = sum(1 for s in oos_sharpes if s > 0)
        print("-" * 55, flush=True)
        print(f"{'Avg OOS SR':<12} {avg_oos:>10.3f}   Positive: {positive}/{len(oos_sharpes)}", flush=True)

        # 重新壓低 log level 給下一個策略
        logging.getLogger().setLevel(logging.ERROR)
        logging.getLogger("FinMind").setLevel(logging.ERROR)

    # 最終恢復
    logging.getLogger().setLevel(prev_level)
    logging.getLogger("FinMind").setLevel(prev_level)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase L 策略回測")
    parser.add_argument(
        "--strategy",
        choices=[
            "revenue_momentum", "trust_follow",
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
    parser.add_argument(
        "--walkforward", action="store_true",
        help="加跑 Walk-Forward 驗證",
    )
    args = parser.parse_args()

    universe = discover_universe()
    logger.info("Universe: %d 支股票", len(universe))

    strategies = (
        [
            "revenue_momentum", "trust_follow",
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
        print("\n" + "=" * 90)
        print("策略比較")
        print("=" * 90)
        print(f"{'策略':30s} {'CAGR':>10s} {'Sharpe':>10s} {'MDD':>10s} {'Trades':>8s}")
        print("-" * 90)
        for name, m in results.items():
            if "error" in m:
                print(f"{name:30s} {'ERROR':>10s}")
            else:
                cagr = m.get("cagr", 0)
                sharpe = m.get("sharpe", 0)
                mdd = m.get("max_drawdown", 0)
                trades = m.get("total_trades", 0)
                print(f"{name:30s} {cagr:>+9.2%} {sharpe:>10.3f} {mdd:>+9.2%} {trades:>8}")
        print("=" * 90)

    # Walk-Forward validation (if --walkforward flag)
    if args.walkforward and results:
        print("\n" + "=" * 90)
        print("Walk-Forward 驗證（3 年訓練 / 1 年測試）")
        print("=" * 90)
        run_walkforward_validation(strategies, universe, args.cash)


if __name__ == "__main__":
    main()
