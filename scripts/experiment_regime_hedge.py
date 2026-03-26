"""實驗 #9：空頭偵測 + 倉位調整對 revenue_momentum 的改善效果。

問題：revenue_momentum 在 2025 H1 OOS 為 -7.4%（純多頭，Beta ≈ 1）
假設：加入大盤 regime 偵測（MA200 / MA50），空頭時降低倉位，可改善下行表現
對標：FinLab Beta -0.43 策略（Sortino 3.02）

測試：
1. 原始 revenue_momentum（基線）
2. + MA200 空頭偵測（bear → 30% 倉位）
3. + MA50/MA200 雙均線（death cross → 0% 倉位）
4. + 波動率調整（VIX-like：高波動 → 低倉位）
5. 各方案在 2018-2024 全期 + 2025 H1 OOS 的比較

用法: python -m scripts.experiment_regime_hedge
"""

from __future__ import annotations

import logging
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategy.base import Context, Strategy
from src.strategy.registry import resolve_strategy
from src.strategy.optimizer import equal_weight, OptConstraints

MARKET_DIR = Path("data/market")


def discover_universe() -> list[str]:
    symbols = sorted(p.stem.replace("_1d", "") for p in MARKET_DIR.glob("*.TW_1d.parquet"))
    return [s for s in symbols if not s.startswith("00")]


# ── Regime-hedged wrapper strategy ─────────────────────────────


class RegimeHedgedStrategy(Strategy):
    """Wraps any strategy with regime-aware position sizing."""

    def __init__(
        self,
        inner: Strategy,
        market_proxy: str = "0050.TW",
        bear_scale: float = 0.3,
        sideways_scale: float = 0.6,
        method: str = "ma200",  # "ma200" | "dual_ma" | "volatility"
    ):
        self.inner = inner
        self.market_proxy = market_proxy
        self.bear_scale = bear_scale
        self.sideways_scale = sideways_scale
        self.method = method
        self._regime_name = f"{inner.name()}_{method}_hedge"

    def name(self) -> str:
        return self._regime_name

    def _detect_regime(self, ctx: Context) -> str:
        """Detect market regime from market proxy."""
        try:
            bars = ctx.bars(self.market_proxy, lookback=252)
            if len(bars) < 200:
                return "bull"  # insufficient data, assume bull
            close = bars["close"]
        except Exception:
            return "bull"

        if self.method == "ma200":
            ma200 = float(close.iloc[-200:].mean())
            current = float(close.iloc[-1])
            if current < ma200 * 0.95:
                return "bear"
            elif current < ma200:
                return "sideways"
            return "bull"

        elif self.method == "dual_ma":
            ma50 = float(close.iloc[-50:].mean())
            ma200 = float(close.iloc[-200:].mean())
            current = float(close.iloc[-1])
            if current < ma200 and ma50 < ma200:
                return "bear"  # death cross + below MA200
            elif current < ma200 or ma50 < ma200:
                return "sideways"
            return "bull"

        elif self.method == "volatility":
            # High realized vol → reduce exposure
            returns = close.pct_change().dropna()
            vol_20d = float(returns.iloc[-20:].std() * np.sqrt(252))
            vol_60d = float(returns.iloc[-60:].std() * np.sqrt(252))
            if vol_20d > 0.25:  # >25% annualized vol
                return "bear"
            elif vol_20d > vol_60d * 1.5:  # vol spike
                return "sideways"
            return "bull"

        return "bull"

    def on_bar(self, ctx: Context) -> dict[str, float]:
        weights = self.inner.on_bar(ctx)
        if not weights:
            return weights

        regime = self._detect_regime(ctx)

        if regime == "bear":
            return {k: v * self.bear_scale for k, v in weights.items()}
        elif regime == "sideways":
            return {k: v * self.sideways_scale for k, v in weights.items()}
        return weights


# ── Run experiment ─────────────────────────────────────────────


def run_bt(strategy: Strategy, universe: list[str], start: str, end: str) -> dict:
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
    r = engine.run(strategy, config)
    return {
        "cagr": r.annual_return,
        "sharpe": r.sharpe,
        "sortino": r.sortino,
        "max_dd": r.max_drawdown,
        "total_return": r.total_return,
        "trades": r.total_trades,
        "win_rate": r.win_rate,
    }


def main() -> None:
    t0 = time.time()
    universe = discover_universe()
    # Ensure market proxy is in universe
    if "0050.TW" not in universe:
        universe.append("0050.TW")
    print(f"Universe: {len(universe)} symbols\n")

    base = resolve_strategy("revenue_momentum")

    strategies = {
        "1_baseline": base,
        "2_ma200_hedge": RegimeHedgedStrategy(base, method="ma200", bear_scale=0.3),
        "3_dual_ma_hedge": RegimeHedgedStrategy(base, method="dual_ma", bear_scale=0.0, sideways_scale=0.3),
        "4_vol_hedge": RegimeHedgedStrategy(base, method="volatility", bear_scale=0.2, sideways_scale=0.5),
        "5_ma200_50pct": RegimeHedgedStrategy(base, method="ma200", bear_scale=0.5, sideways_scale=0.8),
    }

    # Test periods
    periods = {
        "full_2018_2024": ("2018-01-01", "2024-12-31"),
        "bear_2022": ("2022-01-01", "2022-12-31"),
        "oos_2025h1": ("2025-01-01", "2025-06-30"),
        "bull_2023": ("2023-01-01", "2023-12-31"),
        "bull_2024": ("2024-01-01", "2024-12-31"),
    }

    results = {}

    for sname, strat in strategies.items():
        print(f"{'='*70}")
        print(f"Strategy: {sname}")
        print(f"{'='*70}")
        results[sname] = {}

        for pname, (start, end) in periods.items():
            t1 = time.time()
            try:
                r = run_bt(strat, universe, start, end)
                dt = time.time() - t1
                results[sname][pname] = r
                print(f"  {pname:20s} CAGR={r['cagr']:+7.2%} SR={r['sharpe']:6.3f} MDD={r['max_dd']:+7.2%} ({dt:.0f}s)")
            except Exception as e:
                print(f"  {pname:20s} ERROR: {e}")
                results[sname][pname] = {"cagr": 0, "sharpe": 0, "max_dd": 0, "error": str(e)}
        print()

    # ── Comparison table ──
    print("\n" + "=" * 90)
    print("COMPARISON TABLE")
    print("=" * 90)

    print(f"\n{'Strategy':25s} | {'Full CAGR':>10s} {'Full SR':>8s} {'Full MDD':>9s} | {'2022 CAGR':>10s} {'2022 MDD':>9s} | {'OOS 2025':>10s}")
    print("-" * 90)

    for sname in strategies:
        full = results[sname].get("full_2018_2024", {})
        bear = results[sname].get("bear_2022", {})
        oos = results[sname].get("oos_2025h1", {})

        fc = full.get("cagr", 0)
        fs = full.get("sharpe", 0)
        fm = full.get("max_dd", 0)
        bc = bear.get("cagr", 0)
        bm = bear.get("max_dd", 0)
        oc = oos.get("cagr", 0)

        print(f"{sname:25s} | {fc:>+9.2%} {fs:>8.3f} {fm:>+8.2%} | {bc:>+9.2%} {bm:>+8.2%} | {oc:>+9.2%}")

    # ── Key findings ──
    print(f"\n{'='*90}")
    print("KEY FINDINGS")
    print("=" * 90)

    baseline_oos = results["1_baseline"].get("oos_2025h1", {}).get("cagr", 0)
    for sname in ["2_ma200_hedge", "3_dual_ma_hedge", "4_vol_hedge", "5_ma200_50pct"]:
        hedge_oos = results[sname].get("oos_2025h1", {}).get("cagr", 0)
        improvement = hedge_oos - baseline_oos
        hedge_full = results[sname].get("full_2018_2024", {}).get("cagr", 0)
        base_full = results["1_baseline"].get("full_2018_2024", {}).get("cagr", 0)
        cost = base_full - hedge_full

        print(f"  {sname:25s}: OOS improvement = {improvement:+.2%}, Full period cost = {cost:+.2%}")

    print(f"\nTotal time: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
