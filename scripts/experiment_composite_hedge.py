"""實驗 #10：複合偵測器（MA200 OR vol_spike）+ bear_scale 最佳化。

基於實驗 #9 結論：
- MA200 對趨勢熊市有效（2022 MDD 11.2%→8.5%），對高位回調無效（2025）
- vol_hedge 對高位回調有效（2025 OOS -16%→-8%），對緩慢下跌無效（2022）
- 需要組合兩種偵測方法

測試：
1. composite = MA200 OR vol_spike
2. 不同 bear_scale: 0.0 / 0.2 / 0.3 / 0.5
3. 全期 + 2022 + 2025 OOS + 牛市

用法: python -u -m scripts.experiment_composite_hedge
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

import logging
logging.disable(logging.CRITICAL)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.engine import BacktestConfig, BacktestEngine
from src.strategy.base import Context, Strategy
from src.strategy.registry import resolve_strategy

MARKET_DIR = Path("data/market")


def discover_universe() -> list[str]:
    symbols = sorted(p.stem.replace("_1d", "") for p in MARKET_DIR.glob("*.TW_1d.parquet"))
    return [s for s in symbols if not s.startswith("00")]


class CompositeHedgedStrategy(Strategy):
    """MA200 OR vol_spike 複合偵測 + 倉位調整。"""

    def __init__(
        self,
        inner: Strategy,
        market_proxy: str = "0050.TW",
        bear_scale: float = 0.3,
        sideways_scale: float = 0.6,
        ma_threshold: float = 0.95,   # price < MA200 * threshold → bear
        vol_threshold: float = 0.25,  # 20d vol > threshold → bear
        vol_spike_ratio: float = 1.5, # 20d vol > 60d vol * ratio → sideways
    ):
        self.inner = inner
        self.market_proxy = market_proxy
        self.bear_scale = bear_scale
        self.sideways_scale = sideways_scale
        self.ma_threshold = ma_threshold
        self.vol_threshold = vol_threshold
        self.vol_spike_ratio = vol_spike_ratio

    def name(self) -> str:
        return f"composite_b{self.bear_scale:.0%}"

    def _detect_regime(self, ctx: Context) -> str:
        try:
            bars = ctx.bars(self.market_proxy, lookback=252)
            if len(bars) < 200:
                return "bull"
            close = bars["close"]
            returns = close.pct_change().dropna()
        except Exception:
            return "bull"

        current = float(close.iloc[-1])
        ma200 = float(close.iloc[-200:].mean())
        ma50 = float(close.iloc[-50:].mean())
        vol_20d = float(returns.iloc[-20:].std() * np.sqrt(252)) if len(returns) >= 20 else 0
        vol_60d = float(returns.iloc[-60:].std() * np.sqrt(252)) if len(returns) >= 60 else vol_20d

        # Bear: MA200 trend OR vol spike
        ma_bear = current < ma200 * self.ma_threshold and ma50 < ma200
        vol_bear = vol_20d > self.vol_threshold

        if ma_bear or vol_bear:
            return "bear"

        # Sideways: approaching MA200 OR vol rising
        ma_sideways = current < ma200
        vol_sideways = vol_20d > vol_60d * self.vol_spike_ratio

        if ma_sideways or vol_sideways:
            return "sideways"

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


def run_bt(strategy: Strategy, universe: list[str], start: str, end: str) -> dict:
    config = BacktestConfig(
        universe=universe, start=start, end=end,
        initial_cash=10_000_000, commission_rate=0.001425,
        tax_rate=0.003, slippage_bps=5.0, rebalance_freq="monthly",
    )
    engine = BacktestEngine()
    r = engine.run(strategy, config)
    return {
        "cagr": r.annual_return, "sharpe": r.sharpe, "sortino": r.sortino,
        "max_dd": r.max_drawdown, "total_return": r.total_return,
    }


def main() -> None:
    t0 = time.time()
    universe = discover_universe()
    if "0050.TW" not in universe:
        universe.append("0050.TW")
    print(f"Universe: {len(universe)} symbols\n", flush=True)

    base = resolve_strategy("revenue_momentum")

    # Different bear scales
    strategies = {
        "baseline": base,
        "composite_b0%": CompositeHedgedStrategy(base, bear_scale=0.0, sideways_scale=0.3),
        "composite_b20%": CompositeHedgedStrategy(base, bear_scale=0.2, sideways_scale=0.5),
        "composite_b30%": CompositeHedgedStrategy(base, bear_scale=0.3, sideways_scale=0.6),
        "composite_b50%": CompositeHedgedStrategy(base, bear_scale=0.5, sideways_scale=0.7),
    }

    periods = {
        "full": ("2018-01-01", "2024-12-31"),
        "2022": ("2022-01-01", "2022-12-31"),
        "2025h1": ("2025-01-01", "2025-06-30"),
        "2023": ("2023-01-01", "2023-12-31"),
    }

    all_results = {}
    for sname, strat in strategies.items():
        print(f"--- {sname} ---", flush=True)
        all_results[sname] = {}
        for pname, (s, e) in periods.items():
            t1 = time.time()
            try:
                r = run_bt(strat, universe, s, e)
                dt = time.time() - t1
                all_results[sname][pname] = r
                print(f"  {pname:8s} CAGR={r['cagr']:+7.2%} SR={r['sharpe']:6.3f} Sort={r['sortino']:6.3f} MDD={r['max_dd']:+7.2%} ({dt:.0f}s)", flush=True)
            except Exception as ex:
                print(f"  {pname:8s} ERROR: {ex}", flush=True)

    # Summary
    print(f"\n{'='*95}", flush=True)
    print(f"{'Strategy':20s} | {'Full CAGR':>9s} {'Full SR':>8s} {'Sortino':>8s} | {'2022':>7s} {'2022MDD':>8s} | {'OOS2025':>8s} {'2023':>7s}", flush=True)
    print("-" * 95, flush=True)
    for sname in strategies:
        f = all_results[sname].get("full", {})
        b = all_results[sname].get("2022", {})
        o = all_results[sname].get("2025h1", {})
        g = all_results[sname].get("2023", {})
        print(
            f"{sname:20s} | {f.get('cagr',0):>+8.2%} {f.get('sharpe',0):>8.3f} {f.get('sortino',0):>8.3f}"
            f" | {b.get('cagr',0):>+6.2%} {b.get('max_dd',0):>+7.2%}"
            f" | {o.get('cagr',0):>+7.2%} {g.get('cagr',0):>+6.2%}",
            flush=True,
        )

    print(f"\nTotal time: {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
