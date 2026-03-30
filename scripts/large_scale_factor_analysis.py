"""大規模全因子分析 — 全部本地 parquet，多期限 IC/ICIR。

使用 data/market/*.parquet（~895 支台股 + ~210 支其他），不打網路。
報告存到 docs/dev/test/
"""
import warnings
warnings.filterwarnings("ignore")

import time
from pathlib import Path

import pandas as pd

from src.alpha.cross_section import quantile_backtest
from src.alpha.turnover import analyze_factor_turnover
from src.strategy.research import (
    FACTOR_REGISTRY,
    compute_factor_values,
    compute_ic,
)


def compute_forward_returns_union(
    data: dict[str, pd.DataFrame],
    horizon: int = 5,
) -> pd.DataFrame:
    """compute_forward_returns 的聯集版本。

    原版用日期交集（&），大 universe 會得到空集。
    這裡用聯集，每支股票只在自己有資料的日期上計算。
    """
    col_results: dict[str, pd.Series] = {}
    for sym, df in data.items():
        close = df["close"]
        if len(close) <= horizon:
            continue
        future_price = close.shift(-horizon)
        fwd_ret = (future_price / close - 1).dropna()
        if not fwd_ret.empty:
            col_results[sym] = fwd_ret
    if not col_results:
        return pd.DataFrame()
    return pd.DataFrame(col_results)


def load_all_parquet(market_dir: str | None = None, min_bars: int = 500) -> dict[str, pd.DataFrame]:
    """載入所有本地 parquet，過濾掉資料不足的標的。"""
    from src.data.registry import REGISTRY
    data: dict[str, pd.DataFrame] = {}
    if market_dir:
        dirs = [Path(market_dir)]
    else:
        dirs = list(REGISTRY["price"].source_dirs)
    files = []
    for p in dirs:
        if p.exists():
            files.extend(sorted(p.glob("*_1d.parquet")))
    skipped = 0
    for f in files:
        symbol = f.stem.replace("_1d", "")
        # Strip finmind_ prefix to get clean symbol
        if symbol.startswith("finmind_"):
            symbol = symbol[len("finmind_"):]
        # 跳過 ETF 指數（0050, 0056 等）以避免污染因子分析
        try:
            df = pd.read_parquet(f)
            if len(df) >= min_bars:
                data[symbol] = df
            else:
                skipped += 1
        except Exception:
            skipped += 1
    print(f"Loaded {len(data)} stocks ({skipped} skipped, min_bars={min_bars})")
    return data


def main() -> None:
    t_start = time.perf_counter()

    # 1. 載入數據
    data = load_all_parquet()
    tw_only = {s: d for s, d in data.items() if s.endswith(".TW") or s.endswith(".TWO")}
    print(f"TW stocks: {len(tw_only)}")

    # 用台股做分析（一致性）
    data = tw_only

    # 計算日期聯集
    all_dates_set: set[pd.Timestamp] = set()
    for df in data.values():
        all_dates_set.update(df.index)
    union_dates = sorted(all_dates_set)
    print(f"Date range: {union_dates[0]} ~ {union_dates[-1]} ({len(union_dates)} days)")

    # 2. 因子列表
    all_factors = sorted(FACTOR_REGISTRY.keys())
    print(f"Factors: {len(all_factors)}")

    # 3. 多期限 forward returns
    horizons = [5, 10, 20, 60]
    fwd_rets: dict[int, pd.DataFrame] = {}
    for h in horizons:
        t0 = time.perf_counter()
        fwd_rets[h] = compute_forward_returns_union(data, horizon=h)
        print(f"Forward returns {h}d: {fwd_rets[h].shape} ({time.perf_counter()-t0:.1f}s)")

    # 4. 逐因子分析
    rows = []
    failed = []
    for i, name in enumerate(all_factors):
        try:
            t0 = time.perf_counter()
            fv = compute_factor_values(data, name, dates=union_dates)
            if fv.empty:
                failed.append((name, "empty"))
                continue

            # 多期限 IC
            ic_results = {}
            for h in horizons:
                ic = compute_ic(fv, fwd_rets[h])
                ic_results[h] = ic

            # 換手率（用 5d）
            ic_5d = ic_results[5]
            try:
                to = analyze_factor_turnover(
                    fv, n_quantiles=5, holding_period=5,
                    cost_bps=30, gross_ic=ic_5d.ic_mean, factor_name=name,
                )
                turnover = to.avg_turnover
                cost_drag = to.cost_drag_annual_bps
            except Exception:
                turnover = 0.0
                cost_drag = 0.0

            # Quantile backtest（用 20d）
            try:
                qr = quantile_backtest(fv, fwd_rets[20], n_quantiles=5, factor_name=name)
                ls_sharpe = qr.long_short_sharpe
                mono = qr.monotonicity_score
            except Exception:
                ls_sharpe = 0.0
                mono = 0.0

            ic20 = ic_results[20]
            gross_bps = abs(ic20.ic_mean) * 10000
            net_bps = gross_bps - cost_drag

            row = {
                "factor": name,
                "n_dates": fv.shape[0],
                "n_stocks": fv.shape[1],
                "ic_5d": ic_results[5].ic_mean,
                "icir_5d": ic_results[5].icir,
                "ic_10d": ic_results[10].ic_mean,
                "icir_10d": ic_results[10].icir,
                "ic_20d": ic_results[20].ic_mean,
                "icir_20d": ic_results[20].icir,
                "ic_60d": ic_results[60].ic_mean,
                "icir_60d": ic_results[60].icir,
                "hit_20d": ic_results[20].hit_rate,
                "ls_sharpe": ls_sharpe,
                "mono": mono,
                "turnover": turnover,
                "cost_drag_bps": cost_drag,
                "gross_bps": gross_bps,
                "net_bps": net_bps,
                "elapsed": time.perf_counter() - t0,
            }
            rows.append(row)
            status = "OK" if abs(ic20.icir) > 0.1 else "weak"
            print(f"  [{i+1}/{len(all_factors)}] {name:<25} ICIR(20d)={ic20.icir:+.3f} hit={ic20.hit_rate:.1%} [{status}] ({row['elapsed']:.1f}s)")

        except Exception as e:
            failed.append((name, str(e)[:80]))
            print(f"  [{i+1}/{len(all_factors)}] {name:<25} FAILED: {str(e)[:60]}")

    # 5. 結果整理
    df = pd.DataFrame(rows).sort_values("icir_20d", ascending=False, key=abs)

    elapsed_total = time.perf_counter() - t_start
    print(f"\n{'='*80}")
    print(f"完成: {len(rows)}/{len(all_factors)} factors, {len(failed)} failed, {elapsed_total:.0f}s total")
    print(f"Universe: {len(data)} TW stocks")

    # Top factors
    print(f"\n{'='*80}")
    print("Top 15 by |ICIR(20d)|:")
    print(f"{'Factor':<25} {'ICIR(5d)':>9} {'ICIR(10d)':>10} {'ICIR(20d)':>10} {'ICIR(60d)':>10} {'Hit%':>7} {'TO%':>7} {'Net':>7}")
    print("-" * 95)
    for _, r in df.head(15).iterrows():
        print(
            f"{r['factor']:<25} {r['icir_5d']:>+9.3f} {r['icir_10d']:>+10.3f} "
            f"{r['icir_20d']:>+10.3f} {r['icir_60d']:>+10.3f} {r['hit_20d']:>6.1%} "
            f"{r['turnover']:>6.1%} {r['net_bps']:>+6.0f}"
        )

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for name, err in failed:
            print(f"  {name}: {err}")

    # 6. 存檔
    csv_path = "docs/dev/test/large_scale_factor_analysis.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nSaved: {csv_path}")

    return df


if __name__ == "__main__":
    main()
