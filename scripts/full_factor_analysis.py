"""全因子分析 — 對所有已註冊因子跑 IC/ICIR/淨 Alpha/換手率分析。

使用本地數據 (data/market/)，不打網路。
結果存到 docs/dev/test/factor_analysis.csv
"""

import time
import pickle
import pandas as pd

from src.alpha.pipeline import AlphaPipeline, AlphaConfig, FactorSpec
from src.strategy.research import FACTOR_REGISTRY


def main() -> None:
    # 1. Load local data
    print("Loading local data...")
    with open("data/tw50_5yr.pkl", "rb") as f:
        all_data: dict[str, pd.DataFrame] = pickle.load(f)

    tw50 = [s for s in all_data if s not in ("0050.TW", "0056.TW")]
    data = {s: all_data[s] for s in tw50}
    print(f"Loaded {len(data)} stocks")

    # 2. Get all factor names
    all_factors = sorted(FACTOR_REGISTRY.keys())
    print(f"Total factors in FACTOR_REGISTRY: {len(all_factors)}")
    print(f"Factors: {all_factors}")
    print()

    # 3. Run research on ALL factors
    factor_specs = [FactorSpec(name=f) for f in all_factors]

    config = AlphaConfig(
        factors=factor_specs,
        combine_method="equal",
        holding_period=5,
        n_quantiles=5,
    )

    pipeline = AlphaPipeline(config)

    print(f"Running research on {len(all_factors)} factors...")
    t0 = time.perf_counter()
    report = pipeline.research(data)
    elapsed = time.perf_counter() - t0
    print(f"Research completed in {elapsed:.1f}s")
    print()

    # 4. Build analysis table
    rows = []
    for name in all_factors:
        ic = report.factor_ics.get(name)
        to = report.factor_turnovers.get(name)
        qr = report.quantile_results.get(name)

        if ic is None:
            continue

        turnover_pct = to.avg_turnover if to else 0
        cost_drag = to.cost_drag_annual_bps if to else 0
        gross_alpha_bps = abs(ic.ic_mean) * 10000
        net_alpha = gross_alpha_bps - cost_drag
        ls_sharpe = qr.long_short_sharpe if qr else 0
        monotonicity = qr.monotonicity_score if qr else 0

        rows.append({
            "factor": name,
            "ic": ic.ic_mean,
            "icir": ic.icir,
            "hit_rate": ic.hit_rate,
            "ls_sharpe": ls_sharpe,
            "monotonicity": monotonicity,
            "turnover": turnover_pct,
            "cost_drag_bps": cost_drag,
            "gross_alpha_bps": gross_alpha_bps,
            "net_alpha_bps": net_alpha,
            "viable": net_alpha > 0 and abs(ic.icir) > 0.1 and ic.hit_rate > 0.50,
        })

    df = pd.DataFrame(rows).sort_values("icir", ascending=False, key=abs)

    # 5. Print summary
    print(f"{'Factor':<25} {'IC':>8} {'ICIR':>8} {'Hit%':>7} {'L/S SR':>8} {'Mono':>6} {'TO%':>7} {'CostBps':>8} {'NetBps':>8} {'OK':>4}")
    print("-" * 110)
    for _, r in df.iterrows():
        v = "✓" if r["viable"] else "✗"
        print(
            f"{r['factor']:<25} {r['ic']:>+8.4f} {r['icir']:>+8.4f} {r['hit_rate']:>6.1%} "
            f"{r['ls_sharpe']:>+8.2f} {r['monotonicity']:>+6.2f} {r['turnover']:>6.1%} "
            f"{r['cost_drag_bps']:>7.0f} {r['net_alpha_bps']:>+7.0f} {v:>4}"
        )

    viable = df[df["viable"]]
    print()
    print(f"Total factors analyzed: {len(df)}")
    print(f"Viable (net alpha > 0, |ICIR| > 0.1, hit > 50%): {len(viable)}")
    if not viable.empty:
        print(f"Viable factors: {list(viable['factor'])}")

    # 6. Save
    df.to_csv("docs/dev/test/factor_analysis.csv", index=False)
    print("\nSaved to docs/dev/test/factor_analysis.csv")


if __name__ == "__main__":
    main()
