"""Quick factor analysis — all registered factors, local data only."""
import warnings
warnings.filterwarnings("ignore")

import pickle
import time

import pandas as pd

from src.alpha.cross_section import quantile_backtest
from src.alpha.turnover import analyze_factor_turnover
from src.strategy.research import (
    FACTOR_REGISTRY,
    compute_factor_values,
    compute_forward_returns,
    compute_ic,
)


def main() -> None:
    with open("data/tw50_5yr.pkl", "rb") as f:
        all_data = pickle.load(f)
    data = {s: all_data[s] for s in all_data if s not in ("0050.TW", "0056.TW")}

    all_factors = sorted(FACTOR_REGISTRY.keys())
    print(f"{len(data)} stocks, {len(all_factors)} factors")

    # Factor values
    t0 = time.perf_counter()
    factor_dfs: dict[str, pd.DataFrame] = {}
    for name in all_factors:
        try:
            fv = compute_factor_values(data, name)
            if not fv.empty:
                factor_dfs[name] = fv
        except Exception as e:
            print(f"  {name}: FAILED {e}")
    print(f"Factor values: {len(factor_dfs)}/{len(all_factors)} in {time.perf_counter()-t0:.1f}s")

    # Forward returns
    fwd = compute_forward_returns(data, horizon=5)
    print(f"Forward returns: {fwd.shape}")

    # IC analysis
    rows = []
    for name, fv in sorted(factor_dfs.items()):
        try:
            ic = compute_ic(fv, fwd)
            to = analyze_factor_turnover(fv, n_quantiles=5, holding_period=5, cost_bps=30, gross_ic=ic.ic_mean, factor_name=name)
            qr = quantile_backtest(fv, fwd, n_quantiles=5, factor_name=name)
            cost_drag = to.cost_drag_annual_bps
            gross = abs(ic.ic_mean) * 10000
            net = gross - cost_drag
            viable = net > 0 and abs(ic.icir) > 0.1 and ic.hit_rate > 0.50
            rows.append({
                "factor": name, "ic": ic.ic_mean, "icir": ic.icir, "hit": ic.hit_rate,
                "ls_sr": qr.long_short_sharpe, "mono": qr.monotonicity_score,
                "to": to.avg_turnover, "cost": cost_drag, "gross": gross, "net": net, "ok": viable,
            })
        except Exception as e:
            print(f"  {name}: IC ERROR {str(e)[:60]}")

    df = pd.DataFrame(rows).sort_values("icir", ascending=False, key=abs)

    hdr = f"{'Factor':<25} {'IC':>8} {'ICIR':>8} {'Hit%':>7} {'L/S SR':>8} {'TO%':>7} {'Cost':>7} {'Net':>7} {'OK':>4}"
    print()
    print(hdr)
    print("-" * len(hdr))
    for _, r in df.iterrows():
        v = "Y" if r["ok"] else " "
        print(
            f"{r['factor']:<25} {r['ic']:>+8.4f} {r['icir']:>+8.4f} {r['hit']:>6.1%} "
            f"{r['ls_sr']:>+8.2f} {r['to']:>6.1%} {r['cost']:>6.0f} {r['net']:>+6.0f} {v:>4}"
        )

    viable_df = df[df["ok"]]
    print(f"\nTotal: {len(df)} | Viable: {len(viable_df)}")
    if not viable_df.empty:
        print(f"Viable: {list(viable_df['factor'])}")

    df.to_csv("docs/dev/test/factor_analysis.csv", index=False)
    print("Saved: docs/dev/test/factor_analysis.csv")


if __name__ == "__main__":
    main()
