"""基本面 + 籌碼面因子 IC 分析 — 讀取本地 data/fundamental/ parquet 數據。

用法: python -m scripts.run_fundamental_analysis
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.registry import REGISTRY, parquet_path as _ppath

def _glob_dataset(dataset: str, pattern: str) -> list[Path]:
    """Glob across all source dirs for a dataset."""
    ds = REGISTRY[dataset]
    result: list[Path] = []
    for d in ds.source_dirs:
        if d.exists():
            result.extend(d.glob(pattern))
    return result
OUT_CSV = "docs/dev/test/fundamental_factor_analysis.csv"


# ── 讀取價格面板 ──────────────────────────────────────────────────


def load_price_panel() -> pd.DataFrame:
    """讀取所有本地 parquet 價格數據，構建 close 面板。"""
    symbols = []
    for p in _glob_dataset("price", "*_1d.parquet"):
        sym = p.stem.replace("_1d", "")
        if sym.startswith("finmind_"):
            sym = sym[len("finmind_"):]
        if ".TW" not in sym:
            continue
        if sym in ("0050.TW", "0056.TW"):
            continue
        symbols.append((sym, p))

    all_close = {}
    for sym, p in symbols:
        try:
            df = pd.read_parquet(p)
            if not df.empty and "close" in df.columns:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                all_close[sym] = df["close"]
        except Exception:
            continue

    panel = pd.DataFrame(all_close)
    panel = panel.sort_index().dropna(how="all")
    # Normalize index to date-only (remove time component for alignment)
    panel.index = pd.to_datetime(panel.index.date)
    panel = panel[~panel.index.duplicated(keep="first")]
    print(f"Price panel: {panel.shape[1]} symbols, {panel.shape[0]} dates")
    print(f"  Range: {panel.index[0].date()} ~ {panel.index[-1].date()}")
    return panel


def compute_forward_returns(close_panel: pd.DataFrame, horizon: int = 20) -> pd.DataFrame:
    """計算 N 日前瞻報酬。"""
    return close_panel.pct_change(horizon).shift(-horizon)


# ── 基本面因子面板建構 ─────────────────────────────────────────────


def build_per_panel(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """從 PER parquet 建構 PE/PB/dividend_yield 日頻面板。"""
    panels: dict[str, dict[str, pd.Series]] = {
        "pe_ratio": {}, "pb_ratio": {}, "dividend_yield": {},
    }
    for sym in symbols:
        p = _ppath(sym, "per")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        if "PER" in df.columns:
            s = pd.to_numeric(df["PER"], errors="coerce")
            panels["pe_ratio"][sym] = s
        if "PBR" in df.columns:
            s = pd.to_numeric(df["PBR"], errors="coerce")
            panels["pb_ratio"][sym] = s
        if "dividend_yield" in df.columns:
            s = pd.to_numeric(df["dividend_yield"], errors="coerce")
            panels["dividend_yield"][sym] = s

    result = {}
    for name, data in panels.items():
        if data:
            result[name] = pd.DataFrame(data).sort_index()
    return result


def build_revenue_panel(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """從月營收 parquet 建構 revenue_yoy 和 revenue_momentum 面板。"""
    yoy_data: dict[str, pd.Series] = {}
    momentum_data: dict[str, pd.Series] = {}

    for sym in symbols:
        p = _ppath(sym, "revenue")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "revenue" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        # YoY: compare same month previous year
        rev = df.set_index("date")["revenue"].astype(float)
        yoy = rev.pct_change(12) * 100  # 12 months back
        yoy_data[sym] = yoy

        # Momentum: count consecutive months with positive YoY
        streak = pd.Series(0.0, index=yoy.index)
        count = 0.0
        for i, val in enumerate(yoy):
            if pd.notna(val) and val > 0:
                count += 1
            else:
                count = 0
            streak.iloc[i] = min(count, 12)
        momentum_data[sym] = streak

    result = {}
    if yoy_data:
        result["revenue_yoy"] = pd.DataFrame(yoy_data).sort_index()
    if momentum_data:
        result["revenue_momentum"] = pd.DataFrame(momentum_data).sort_index()
    return result


def build_institutional_panel(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """從法人買賣超 parquet 建構 foreign_net / trust_net 面板。"""
    foreign_data: dict[str, pd.Series] = {}
    trust_data: dict[str, pd.Series] = {}

    for sym in symbols:
        p = _ppath(sym, "institutional")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df["buy"] = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
        df["sell"] = pd.to_numeric(df["sell"], errors="coerce").fillna(0)
        df["net"] = df["buy"] - df["sell"]

        # Foreign investor
        foreign = df[df["name"].str.contains("Foreign_Investor", na=False)]
        if not foreign.empty:
            fg = foreign.groupby("date")["net"].sum()
            # 20-day rolling sum, normalized by rolling volume
            fg_20d = fg.rolling(20, min_periods=5).sum()
            # Normalize by rolling abs sum for cross-sectional comparability
            abs_sum = fg.abs().rolling(20, min_periods=5).sum()
            normalized = fg_20d / abs_sum.replace(0, np.nan)
            foreign_data[sym] = normalized

        # Trust (投信)
        trust = df[df["name"].str.contains("Investment_Trust", na=False)]
        if not trust.empty:
            tg = trust.groupby("date")["net"].sum()
            tg_20d = tg.rolling(20, min_periods=5).sum()
            abs_sum = tg.abs().rolling(20, min_periods=5).sum()
            normalized = tg_20d / abs_sum.replace(0, np.nan)
            trust_data[sym] = normalized

    result = {}
    if foreign_data:
        result["foreign_net"] = pd.DataFrame(foreign_data).sort_index()
    if trust_data:
        result["trust_net"] = pd.DataFrame(trust_data).sort_index()
    return result


def build_margin_panel(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """從融資融券 parquet 建構 margin_change 面板。"""
    data: dict[str, pd.Series] = {}
    for sym in symbols:
        p = _ppath(sym, "margin")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "MarginPurchaseTodayBalance" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        balance = pd.to_numeric(df["MarginPurchaseTodayBalance"], errors="coerce")
        # 20-day change ratio
        chg = balance.pct_change(20)
        data[sym] = chg

    if data:
        return {"margin_change": pd.DataFrame(data).sort_index()}
    return {}


def build_shareholding_panel(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """從董監持股 parquet 建構 director_change 面板。"""
    data: dict[str, pd.Series] = {}
    for sym in symbols:
        p = _ppath(sym, "shareholding")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "ForeignInvestmentSharesRatio" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        ratio = pd.to_numeric(df["ForeignInvestmentSharesRatio"], errors="coerce")
        # 20-day change in foreign holding ratio
        chg = ratio.diff(20)
        data[sym] = chg

    if data:
        return {"foreign_holding_chg": pd.DataFrame(data).sort_index()}
    return {}


def build_revenue_advanced_panel(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """從月營收建構 revenue_acceleration 和 revenue_new_high 面板。"""
    accel_data: dict[str, pd.Series] = {}
    new_high_data: dict[str, pd.Series] = {}

    for sym in symbols:
        p = _ppath(sym, "revenue")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "revenue" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").set_index("date")
        rev = df["revenue"].astype(float)

        if len(rev) < 12:
            continue

        # Acceleration: 3M avg / 12M avg
        avg3 = rev.rolling(3, min_periods=3).mean()
        avg12 = rev.rolling(12, min_periods=12).mean()
        accel = avg3 / avg12.replace(0, np.nan)
        accel_data[sym] = accel

        # New high: 3M avg >= rolling 12M max of 3M avg
        rolling_max_3m = avg3.rolling(12, min_periods=12).max()
        is_high = (avg3 >= rolling_max_3m * 0.99).astype(float)
        new_high_data[sym] = is_high

    result = {}
    if accel_data:
        result["revenue_acceleration"] = pd.DataFrame(accel_data).sort_index()
    if new_high_data:
        result["revenue_new_high"] = pd.DataFrame(new_high_data).sort_index()
    return result


def build_trust_cumulative_panel(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """從法人買賣超建構 trust_10d_cumulative 面板。"""
    data: dict[str, pd.Series] = {}
    for sym in symbols:
        p = _ppath(sym, "institutional")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df["buy"] = pd.to_numeric(df["buy"], errors="coerce").fillna(0)
        df["sell"] = pd.to_numeric(df["sell"], errors="coerce").fillna(0)
        df["net"] = df["buy"] - df["sell"]

        trust = df[df["name"].str.contains("Investment_Trust", na=False)]
        if trust.empty:
            continue
        tg = trust.groupby("date")["net"].sum()
        # 10-day cumulative
        data[sym] = tg.rolling(10, min_periods=5).sum()

    if data:
        return {"trust_10d_cumulative": pd.DataFrame(data).sort_index()}
    return {}


def _load_volume_panel() -> pd.DataFrame | None:
    """讀取成交量面板。"""
    all_vol = {}
    for p in _glob_dataset("price", "*_1d.parquet"):
        sym = p.stem.replace("_1d", "")
        if sym.startswith("finmind_"):
            sym = sym[len("finmind_"):]
        if ".TW" not in sym or sym in ("0050.TW", "0056.TW"):
            continue
        try:
            df = pd.read_parquet(p)
            if not df.empty and "volume" in df.columns:
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                all_vol[sym] = df["volume"]
        except Exception:
            continue
    if not all_vol:
        return None
    panel = pd.DataFrame(all_vol).sort_index()
    panel.index = pd.to_datetime(panel.index.date)
    panel = panel[~panel.index.duplicated(keep="first")]
    return panel


def build_daytrading_panel(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """從當沖 parquet 建構 daytrading_ratio 面板。"""
    data: dict[str, pd.Series] = {}
    for sym in symbols:
        p = _ppath(sym, "daytrading")
        if not p.exists():
            continue
        df = pd.read_parquet(p)
        if df.empty or "Volume" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        vol = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)
        # Need total volume from price data
        price_p = _ppath(sym, "price")
        if not price_p.exists():
            continue
        price_df = pd.read_parquet(price_p)
        if price_df.empty or "volume" not in price_df.columns:
            continue
        if not isinstance(price_df.index, pd.DatetimeIndex):
            price_df.index = pd.to_datetime(price_df.index)
        price_df.index = pd.to_datetime(price_df.index.date)
        price_df = price_df[~price_df.index.duplicated(keep="first")]
        total_vol = price_df["volume"]
        # Align and compute ratio
        combined = pd.DataFrame({"dt_vol": vol, "total_vol": total_vol}).dropna()
        if combined.empty:
            continue
        ratio = combined["dt_vol"] / combined["total_vol"].replace(0, np.nan)
        # 20-day rolling average
        data[sym] = ratio.rolling(20, min_periods=5).mean()

    if data:
        return {"daytrading_ratio": pd.DataFrame(data).sort_index()}
    return {}


# ── IC 計算 ────────────────────────────────────────────────────────


def compute_ic_series(
    factor_panel: pd.DataFrame,
    fwd_ret: pd.DataFrame,
    sample_every: int = 5,
) -> pd.Series:
    """逐日計算 Spearman cross-sectional IC。"""
    common_dates = factor_panel.index.intersection(fwd_ret.index)
    common_syms = factor_panel.columns.intersection(fwd_ret.columns)

    if len(common_dates) < 10 or len(common_syms) < 5:
        return pd.Series(dtype=float)

    ics = []
    dates_used = []
    for i, dt in enumerate(common_dates):
        if i % sample_every != 0:
            continue
        f = factor_panel.loc[dt, common_syms].dropna()
        r = fwd_ret.loc[dt, common_syms].dropna()
        common = f.index.intersection(r.index)
        if len(common) < 5:
            continue
        corr, _ = stats.spearmanr(f[common], r[common])
        if not np.isnan(corr):
            ics.append(corr)
            dates_used.append(dt)

    return pd.Series(ics, index=dates_used)


def align_factor_to_daily(
    factor_panel: pd.DataFrame,
    daily_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """將月頻/不規則頻率的因子面板 forward-fill 到日頻。"""
    return factor_panel.reindex(daily_index, method="ffill", limit=60)


# ── 主函式 ─────────────────────────────────────────────────────────


def main() -> None:
    t0 = time.perf_counter()

    # 1. Load price panel
    close_panel = load_price_panel()
    symbols = list(close_panel.columns)

    # 2. Forward returns (20-day)
    fwd_ret = compute_forward_returns(close_panel, horizon=20)
    print(f"Forward returns: {fwd_ret.shape}")

    # 3. Build all factor panels
    print("\nBuilding factor panels...", flush=True)
    all_factor_panels: dict[str, pd.DataFrame] = {}

    # PER/PBR/dividend_yield (daily)
    per_panels = build_per_panel(symbols)
    for name, panel in per_panels.items():
        print(f"  {name}: {panel.shape}", flush=True)
        all_factor_panels[name] = panel

    # Revenue (monthly → forward-fill to daily)
    rev_panels = build_revenue_panel(symbols)
    for name, panel in rev_panels.items():
        aligned = align_factor_to_daily(panel, close_panel.index)
        print(f"  {name}: {panel.shape} → aligned {aligned.shape}", flush=True)
        all_factor_panels[name] = aligned

    # Institutional (daily)
    inst_panels = build_institutional_panel(symbols)
    for name, panel in inst_panels.items():
        print(f"  {name}: {panel.shape}", flush=True)
        all_factor_panels[name] = panel

    # Margin (daily)
    margin_panels = build_margin_panel(symbols)
    for name, panel in margin_panels.items():
        print(f"  {name}: {panel.shape}", flush=True)
        all_factor_panels[name] = panel

    # Shareholding (daily)
    share_panels = build_shareholding_panel(symbols)
    for name, panel in share_panels.items():
        print(f"  {name}: {panel.shape}", flush=True)
        all_factor_panels[name] = panel

    # Daytrading (daily)
    dt_panels = build_daytrading_panel(symbols)
    for name, panel in dt_panels.items():
        print(f"  {name}: {panel.shape}", flush=True)
        all_factor_panels[name] = panel

    # Revenue advanced: acceleration + new_high (FinLab-driven)
    rev_adv_panels = build_revenue_advanced_panel(symbols)
    for name, panel in rev_adv_panels.items():
        aligned = align_factor_to_daily(panel, close_panel.index)
        print(f"  {name}: {panel.shape} → aligned {aligned.shape}", flush=True)
        all_factor_panels[name] = aligned

    # Trust cumulative (10-day rolling)
    trust_cum_panels = build_trust_cumulative_panel(symbols)
    for name, panel in trust_cum_panels.items():
        print(f"  {name}: {panel.shape}", flush=True)
        all_factor_panels[name] = panel

    # Price-based factors for comparison
    mom6m = close_panel.pct_change(120)
    all_factor_panels["momentum_6m"] = mom6m
    print(f"  momentum_6m: {mom6m.shape}", flush=True)

    mom1m = close_panel.pct_change(20)
    all_factor_panels["momentum_1m"] = mom1m

    reversal_5d = -close_panel.pct_change(5)
    all_factor_panels["reversal_5d"] = reversal_5d

    volatility_20d = close_panel.pct_change().rolling(20).std() * np.sqrt(252)
    all_factor_panels["volatility_20d"] = volatility_20d

    # RSI 14
    delta = close_panel.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_panel = 100 - 100 / (1 + rs)
    all_factor_panels["rsi_14"] = rsi_panel

    # Volume momentum
    vol_panel = _load_volume_panel()
    if vol_panel is not None:
        vol_mom = vol_panel.rolling(5).mean() / vol_panel.rolling(20).mean()
        all_factor_panels["volume_momentum"] = vol_mom

    # Price vs MA60
    ma60 = close_panel.rolling(60).mean()
    price_vs_ma60 = close_panel / ma60 - 1
    all_factor_panels["price_vs_ma60"] = price_vs_ma60

    print("  + price factors: momentum_1m, reversal_5d, volatility_20d, rsi_14, volume_momentum, price_vs_ma60", flush=True)

    print(f"\nTotal factor panels: {len(all_factor_panels)}")

    # 4. IC analysis
    print("\nComputing IC...", flush=True)
    rows = []
    for name, panel in sorted(all_factor_panels.items()):
        ic_series = compute_ic_series(panel, fwd_ret, sample_every=5)
        if ic_series.empty:
            print(f"  {name}: no IC (insufficient data)")
            continue

        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        icir = ic_mean / ic_std if ic_std > 0 else 0
        hit = (ic_series > 0).mean() if len(ic_series) > 0 else 0

        rows.append({
            "factor": name,
            "ic_mean": ic_mean,
            "ic_std": ic_std,
            "icir": icir,
            "hit_rate": hit,
            "n_obs": len(ic_series),
            "type": _classify_factor(name),
        })

    df = pd.DataFrame(rows).sort_values("icir", ascending=False, key=abs)

    # 5. Print results
    print()
    hdr = f"{'Factor':<25} {'Type':<10} {'IC':>8} {'ICIR':>8} {'Hit%':>7} {'N':>5}"
    print(hdr)
    print("-" * len(hdr))
    for _, r in df.iterrows():
        passed = "***" if abs(r["icir"]) >= 0.3 else ("* " if abs(r["icir"]) >= 0.15 else "  ")
        print(
            f"{r['factor']:<25} {r['type']:<10} {r['ic_mean']:>+8.4f} "
            f"{r['icir']:>+8.4f} {r['hit_rate']:>6.1%} {r['n_obs']:>5} {passed}"
        )

    # 6. Summary
    strong = df[df["icir"].abs() >= 0.3]
    moderate = df[(df["icir"].abs() >= 0.15) & (df["icir"].abs() < 0.3)]
    print(f"\n*** ICIR >= 0.3: {len(strong)}")
    if not strong.empty:
        print(f"    {list(strong['factor'])}")
    print(f" *  ICIR 0.15~0.3: {len(moderate)}")
    if not moderate.empty:
        print(f"    {list(moderate['factor'])}")
    print(f"    ICIR < 0.15: {len(df) - len(strong) - len(moderate)}")

    # 7. Save
    df.to_csv(OUT_CSV, index=False)
    print(f"\nSaved: {OUT_CSV}")
    print(f"Total time: {time.perf_counter() - t0:.1f}s")


def _classify_factor(name: str) -> str:
    if name in ("pe_ratio", "pb_ratio", "dividend_yield", "revenue_yoy",
                "revenue_momentum", "revenue_acceleration", "revenue_new_high"):
        return "fundamental"
    if name in ("foreign_net", "trust_net", "margin_change",
                "foreign_holding_chg", "trust_10d_cumulative"):
        return "chip"
    if name in ("daytrading_ratio",):
        return "sentiment"
    return "price"


if __name__ == "__main__":
    main()
