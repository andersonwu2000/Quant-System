"""Descriptive validation checks — non-gate computations for ValidationReport."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _load_0050_close() -> pd.Series:
    """Load 0050.TW close price series from DataCatalog. Returns empty Series on failure."""
    try:
        from src.data.data_catalog import get_catalog
        df = get_catalog().get("price", "0050.TW")
        if df.empty or "close" not in df.columns:
            return pd.Series(dtype=float)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return df["close"]
    except Exception:
        return pd.Series(dtype=float)


class DescriptiveChecks:
    """Mixin for descriptive (non-gate) validation computations."""

    @staticmethod
    def _compute_cost_breakdown(
        result: Any, config: Any, n_years: float,
        annual_cost_rate: float, wf_results: list[dict] | None = None,
    ) -> str:
        try:
            commission_annual = result.total_commission / config.initial_cash / n_years
            total_cost_annual = annual_cost_rate
            vol_annual = float(result.nav_series.pct_change().std() * np.sqrt(252)) if len(result.nav_series) > 1 else 0.15
            cost_adj_sharpe = result.sharpe - total_cost_annual / max(vol_annual, 0.01) if result.sharpe > 0 else 0.0

            wf_turnovers = []
            for wf in (wf_results or []):
                if "error" not in wf and wf.get("trades", 0) > 0:
                    wf_turnovers.append(wf.get("trades", 0))

            turnover_detail = ""
            if wf_turnovers:
                t_arr = np.array(wf_turnovers)
                turnover_detail = f"Trades/yr: p50={np.median(t_arr):.0f}, p95={np.percentile(t_arr, 95):.0f}, max={t_arr.max():.0f}"

            ic_halflife = "N/A"
            try:
                ret = result.daily_returns
                if ret is not None and len(ret) > 60:
                    monthly_ret = ret.resample("MS").sum()
                    if len(monthly_ret) > 6:
                        autocorr_1 = float(monthly_ret.autocorr(lag=1))
                        if 0 < autocorr_1 < 1:
                            halflife = -np.log(2) / np.log(autocorr_1)
                            ic_halflife = f"{halflife:.0f}m"
                        elif autocorr_1 <= 0:
                            ic_halflife = "<1m (no persistence)"
                        else:
                            ic_halflife = "stable"
            except Exception:
                pass

            text = (
                f"Commission: {commission_annual:.3%}/yr | "
                f"Total cost: {total_cost_annual:.3%}/yr | "
                f"Cost-adj SR: {cost_adj_sharpe:.3f} | "
                f"IC half-life: {ic_halflife}"
            )
            if turnover_detail:
                text += f" | {turnover_detail}"
            return text
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_regime_split(result: Any, start: str, end: str) -> str:
        try:
            strat_rets = result.daily_returns
            if strat_rets is None or len(strat_rets) <= 60:
                return "N/A (insufficient returns)"

            mkt_close = _load_0050_close()
            if mkt_close.empty:
                return "N/A (no 0050 data)"

            mkt_ret = mkt_close.pct_change().dropna()
            common_idx = strat_rets.index.intersection(mkt_ret.index)
            s = strat_rets.loc[common_idx]
            m = mkt_ret.loc[common_idx]
            mkt_rolling = m.rolling(252).sum()

            regimes = {
                "bull": mkt_rolling > 0.15,
                "bear": mkt_rolling < -0.10,
                "sideways": (mkt_rolling >= -0.05) & (mkt_rolling <= 0.15),
                "high_vol": m.rolling(60).std() * np.sqrt(252) > 0.25,
                "earnings_month": pd.Series(
                    [d.month in (3, 5, 8, 11) for d in common_idx],
                    index=common_idx,
                ),
            }

            regime_parts = []
            for name, mask in regimes.items():
                valid_mask = mask.reindex(common_idx).fillna(False)
                regime_rets = s[valid_mask]
                if len(regime_rets) > 20:
                    sr = float(regime_rets.mean() / regime_rets.std() * np.sqrt(252)) if regime_rets.std() > 0 else 0.0
                    regime_parts.append(f"{name}: SR={sr:+.2f} ({len(regime_rets)}d)")
                else:
                    regime_parts.append(f"{name}: N/A (<20d)")

            return " | ".join(regime_parts)
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_capacity_analysis(
        result: Any, config: Any, n_years: float, universe: list[str],
    ) -> str:
        try:
            base_sharpe = result.sharpe
            impact_k = 0.1

            capacity_parts = []
            for multiplier in [1, 3, 5, 10]:
                avg_adv = 0.0
                try:
                    from src.data.registry import parquet_path as _cp
                    adv_samples = []
                    for sym in universe[:50]:
                        _p = _cp(sym, "price")
                        if _p.exists():
                            _df = pd.read_parquet(_p)
                            if "volume" in _df.columns:
                                adv_samples.append(float(_df["volume"].iloc[-20:].mean()))
                    if adv_samples:
                        avg_adv = np.median(adv_samples)
                except Exception:
                    avg_adv = 1e6

                if avg_adv > 0:
                    vol_annual = float(result.nav_series.pct_change().std() * np.sqrt(252)) if len(result.nav_series) > 1 else 0.15
                    if multiplier == 1:
                        adj_sharpe = base_sharpe
                    else:
                        turnover_annual = result.total_trades / max(n_years, 0.5) / len(universe)
                        extra_impact = impact_k * (np.sqrt(multiplier) - 1) * turnover_annual
                        adj_sharpe = max(0, base_sharpe - extra_impact / max(vol_annual, 0.01))
                else:
                    adj_sharpe = base_sharpe

                capacity_parts.append(f"{multiplier}x: SR={adj_sharpe:.2f}")

            return " | ".join(capacity_parts)
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_stress_test(result: Any) -> str:
        try:
            strat_rets = result.daily_returns
            if strat_rets is None or len(strat_rets) <= 20:
                return "N/A (insufficient returns)"

            stress_parts = []

            fixed_periods = {
                "COVID": ("2020-03-01", "2020-03-31"),
                "Shipping": ("2022-01-01", "2022-01-31"),
                "RateHike": ("2022-06-01", "2022-06-30"),
                "Election": ("2024-01-01", "2024-01-31"),
            }
            for label, (ps, pe) in fixed_periods.items():
                mask = (strat_rets.index >= ps) & (strat_rets.index <= pe)
                period_rets = strat_rets[mask]
                if len(period_rets) > 0:
                    cum_ret = float((1 + period_rets).prod() - 1)
                    stress_parts.append(f"{label}: {cum_ret:+.1%}")
                else:
                    stress_parts.append(f"{label}: N/A")

            exdiv_mask = pd.Series(
                [d.month in (7, 8, 9) for d in strat_rets.index],
                index=strat_rets.index,
            )
            exdiv_rets = strat_rets[exdiv_mask]
            if len(exdiv_rets) > 0:
                cum_ret = float((1 + exdiv_rets).prod() - 1)
                stress_parts.append(f"ExDiv(7-9): {cum_ret:+.1%}")
            else:
                stress_parts.append("ExDiv(7-9): N/A")

            big_drops = strat_rets[strat_rets < -0.05]
            if len(big_drops) > 0:
                worst_drop = float(big_drops.min())
                stress_parts.append(f">5%drops: {len(big_drops)}d, worst={worst_drop:+.1%}")
            else:
                stress_parts.append(">5%drops: none")

            # AN-9: Max consecutive loss months
            monthly_rets = strat_rets.resample("ME").apply(lambda x: (1 + x).prod() - 1)
            max_consec_loss = 0
            cur_streak = 0
            for mr in monthly_rets:
                if mr < 0:
                    cur_streak += 1
                    max_consec_loss = max(max_consec_loss, cur_streak)
                else:
                    cur_streak = 0
            stress_parts.append(f"MaxConsecLoss: {max_consec_loss}m")

            # AN-9: Sharpe without top-20 positive days
            sorted_rets = strat_rets.sort_values(ascending=False)
            top20_idx = sorted_rets.head(20).index
            rets_no_top20 = strat_rets.drop(top20_idx)
            if len(rets_no_top20) > 1 and rets_no_top20.std() > 0:
                sr_no_top20 = float(rets_no_top20.mean() / rets_no_top20.std() * (252 ** 0.5))
                stress_parts.append(f"SR_no_top20: {sr_no_top20:.2f}")
            else:
                stress_parts.append("SR_no_top20: N/A")

            return " | ".join(stress_parts)
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_benchmark_relative(result: Any, oos_start: str, oos_end: str) -> str:
        try:
            strat_rets = result.daily_returns
            if strat_rets is None or len(strat_rets) <= 60:
                return "N/A (insufficient returns)"

            bm_close = _load_0050_close()
            if bm_close.empty:
                return "N/A (no 0050 data)"
            bm_ret = bm_close.pct_change().dropna()

            common_idx = strat_rets.index.intersection(bm_ret.index)
            s = strat_rets.loc[common_idx]
            b = bm_ret.loc[common_idx]

            if len(common_idx) <= 60:
                return "N/A (insufficient overlap with 0050)"

            n_days = len(common_idx)
            strat_annual = float((1 + s).prod() ** (252 / n_days) - 1)
            bm_annual = float((1 + b).prod() ** (252 / n_days) - 1)
            excess = strat_annual - bm_annual

            bm_cum = (1 + b).cumprod()
            bm_peak = bm_cum.cummax()
            bm_dd = (bm_cum - bm_peak) / bm_peak

            bear_mask = bm_dd < -0.15
            if bear_mask.any():
                s_cum = (1 + s).cumprod()
                s_peak = s_cum.cummax()
                s_dd = (s_cum - s_peak) / s_peak
                strat_bear_mdd = float(s_dd[bear_mask].min())
                bm_bear_mdd = float(bm_dd[bear_mask].min())
                bear_str = f"Bear DD: strategy {strat_bear_mdd:+.1%} vs market {bm_bear_mdd:+.1%}"
            else:
                bear_str = "Bear DD: no bear periods (0050 DD>15%) found"

            return f"Excess vs 0050: {excess:+.1%}/yr | {bear_str}"
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_exit_warning(result: Any, annual_cost_rate: float) -> str:
        try:
            strat_rets = result.daily_returns
            if strat_rets is None or len(strat_rets) <= 63:
                return "N/A (insufficient returns)"

            warnings_list = []
            recent_126 = strat_rets.iloc[-126:] if len(strat_rets) >= 126 else strat_rets.iloc[-63:]
            if len(recent_126) > 20 and recent_126.std() > 0:
                rolling_6m_sr = float(recent_126.mean() / recent_126.std() * np.sqrt(252))
                if rolling_6m_sr < 0:
                    warnings_list.append(f"rolling 6m SR={rolling_6m_sr:.2f}")

            recent_63 = strat_rets.iloc[-63:]
            if len(recent_63) > 10 and recent_63.std() > 0:
                sr_63 = float(recent_63.mean() / recent_63.std() * np.sqrt(252))
                cost_drag = annual_cost_rate / max(float(recent_63.std() * np.sqrt(252)), 0.01)
                cost_adj_ir = sr_63 - cost_drag
                if cost_adj_ir < 0:
                    warnings_list.append(f"63d cost-adj IR={cost_adj_ir:.2f}")

            if warnings_list:
                return f"WARNING: {', '.join(warnings_list)}, consider exit"
            return "No exit triggers"
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_oos_regime(config: Any) -> str:
        try:
            oos_bm = _load_0050_close()
            if oos_bm.empty:
                return "N/A (no 0050 data)"
            oos_mask = (oos_bm.index >= config.oos_start) & (oos_bm.index <= config.oos_end)
            oos_bm_period = oos_bm[oos_mask]
            if len(oos_bm_period) <= 20:
                return "N/A (insufficient OOS 0050 data)"
            oos_bm_ret = oos_bm_period.pct_change().dropna()
            n_oos_days = len(oos_bm_ret)
            oos_bm_annual = float((1 + oos_bm_ret).prod() ** (252 / n_oos_days) - 1)
            if oos_bm_annual > 0.15:
                regime = "bull"
            elif oos_bm_annual < -0.10:
                regime = "bear"
            else:
                regime = "sideways"
            return f"OOS regime: {regime} (0050 annual: {oos_bm_annual:+.1%})"
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_announcement_warning(result: Any) -> str:
        try:
            strat_rets = result.daily_returns
            if strat_rets is None or len(strat_rets) == 0:
                return ""
            trade_days = strat_rets.index
            ann_days = sum(1 for d in trade_days if d.day <= 10)
            ratio = ann_days / len(trade_days) if len(trade_days) > 0 else 0
            if ratio > 0.30:
                return (
                    f"WARNING: {ratio:.0%} of trading days fall on days 1-10 "
                    f"(revenue announcement window) — {ann_days}/{len(trade_days)}"
                )
            return ""
        except Exception:
            return ""

    @staticmethod
    def _compute_factor_risk(attr_result: Any) -> str:
        try:
            risk_parts = []
            if attr_result:
                if abs(attr_result.beta_smb) > 0.3:
                    risk_parts.append(f"HIGH size exposure (SMB={attr_result.beta_smb:+.3f})")
                if abs(attr_result.beta_hml) > 0.3:
                    risk_parts.append(f"HIGH value exposure (HML={attr_result.beta_hml:+.3f})")
                if abs(attr_result.beta_mom) > 0.3:
                    risk_parts.append(f"HIGH momentum exposure (MOM={attr_result.beta_mom:+.3f})")
                if attr_result.r_squared > 0.8:
                    risk_parts.append(f"Low alpha — R²={attr_result.r_squared:.3f}")
            return " | ".join(risk_parts) or "No concentrated factor risk detected"
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_family_cluster(attr_result: Any) -> str:
        try:
            if attr_result:
                family, label, val = "other", "", 0.0
                if abs(attr_result.beta_hml) > 0.2:
                    family, label, val = "value", "HML", attr_result.beta_hml
                elif abs(attr_result.beta_mom) > 0.2:
                    family, label, val = "momentum", "MOM", attr_result.beta_mom
                elif abs(attr_result.beta_smb) > 0.2:
                    family, label, val = "size", "SMB", attr_result.beta_smb
                return f"Family: {family} ({label}={val:+.3f})" if label else f"Family: {family}"
            return "N/A (no attribution)"
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_position_liquidity(result: Any, universe: list[str]) -> str:
        try:
            from src.data.registry import parquet_path as _lp
            pos: dict[str, float] = {}
            for t in result.trades:
                qty = float(t.quantity) if t.side.value == "BUY" else -float(t.quantity)
                pos[t.symbol] = pos.get(t.symbol, 0.0) + qty
            held = {s: q for s, q in pos.items() if q > 0}
            if not held:
                return "N/A (no final holdings)"
            adv_pcts = []
            small_cap_count = 0
            for sym, qty in held.items():
                p = _lp(sym, "price")
                if p.exists():
                    df = pd.read_parquet(p)
                    if "volume" in df.columns and "close" in df.columns:
                        adv = float(df["volume"].iloc[-20:].mean())
                        adv_twd = adv * float(df["close"].iloc[-1])
                        adv_pct = (qty / adv * 100) if adv > 0 else 100.0
                        adv_pcts.append(adv_pct)
                        if adv_twd < 1e7:
                            small_cap_count += 1
            if not adv_pcts:
                return "N/A (no volume data)"
            arr = np.array(adv_pcts)
            p50, p95, mx = np.percentile(arr, 50), np.percentile(arr, 95), arr.max()
            sc_pct = small_cap_count / len(held) * 100
            return (
                f"Position ADV%: p50={p50:.1f}%, p95={p95:.1f}%, max={mx:.1f}% "
                f"| Small-cap exposure: {sc_pct:.0f}% (ADV < 10M TWD)"
            )
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_loss_attribution(result: Any, start: str, end: str) -> str:
        """Analyze why an OOS period performed poorly across 5 dimensions."""
        try:
            strat_rets = result.daily_returns
            if strat_rets is None or len(strat_rets) <= 60:
                return "N/A (insufficient returns)"

            mid = len(strat_rets) // 2
            first_half = strat_rets.iloc[:mid]
            second_half = strat_rets.iloc[mid:]

            if first_half.std() == 0 or second_half.std() == 0:
                return "N/A (zero volatility in half period)"

            sr_first = float(first_half.mean() / first_half.std() * np.sqrt(252))
            sr_second = float(second_half.mean() / second_half.std() * np.sqrt(252))
            sr_overall = float(strat_rets.mean() / strat_rets.std() * np.sqrt(252)) if strat_rets.std() > 0 else 0.0

            # Standard error of Sharpe ~ sqrt((1 + 0.5 * SR^2) / N)
            n_days = len(strat_rets)
            se_sr = np.sqrt((1 + 0.5 * sr_overall**2) / n_days) * np.sqrt(252)

            if sr_overall >= 0 and (sr_first - sr_second) <= se_sr:
                return "No significant deterioration detected"

            parts = []

            # 1. Factor decay — rolling 126-day Sharpe as IC proxy
            window = 126
            if len(strat_rets) >= window + 20:
                rolling_sr = strat_rets.rolling(window).apply(
                    lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0.0,
                    raw=False,
                )
                rolling_sr = rolling_sr.dropna()
                if len(rolling_sr) > 20:
                    rs_mid = len(rolling_sr) // 2
                    sr_h1 = float(rolling_sr.iloc[:rs_mid].mean())
                    sr_h2 = float(rolling_sr.iloc[rs_mid:].mean())
                    decayed = sr_h2 < sr_h1 - 0.3
                    parts.append(f"factor_decay({'YES' if decayed else 'NO'}: SR {sr_h1:.1f}\u2192{sr_h2:.1f})")
                else:
                    parts.append("factor_decay(N/A)")
            else:
                parts.append("factor_decay(N/A)")

            # 2. Execution cost — cost ratio in each half
            try:
                gross_alpha = float((1 + strat_rets).prod() - 1)
                total_cost = float(result.total_commission) if hasattr(result, 'total_commission') else 0.0
                cost_ratio = total_cost / abs(gross_alpha) if abs(gross_alpha) > 1e-9 else 0.0
                high_cost = cost_ratio > 0.5
                parts.append(f"cost({'YES' if high_cost else 'NO'}: {cost_ratio:.0%})")
            except Exception:
                parts.append("cost(N/A)")

            # 3. Regime shift — check 0050 bull/bear transition
            try:
                mkt_close = _load_0050_close()
                if not mkt_close.empty:
                    mkt_ret = mkt_close.pct_change().dropna()
                    common_idx = strat_rets.index.intersection(mkt_ret.index)
                    if len(common_idx) > 60:
                        m = mkt_ret.loc[common_idx]
                        m_mid = len(m) // 2
                        m_h1 = m.iloc[:m_mid]
                        m_h2 = m.iloc[m_mid:]
                        ann_h1 = float(m_h1.mean() * 252)
                        ann_h2 = float(m_h2.mean() * 252)
                        regime_h1 = "bull" if ann_h1 > 0.10 else ("bear" if ann_h1 < -0.10 else "sideways")
                        regime_h2 = "bull" if ann_h2 > 0.10 else ("bear" if ann_h2 < -0.10 else "sideways")
                        shifted = regime_h1 != regime_h2
                        parts.append(f"regime({'YES' if shifted else 'NO'}: {regime_h1}\u2192{regime_h2})")
                    else:
                        parts.append("regime(N/A)")
                else:
                    parts.append("regime(N/A)")
            except Exception:
                parts.append("regime(N/A)")

            # 4. Concentration risk — kurtosis of returns
            try:
                kurt = float(strat_rets.kurtosis())
                high_kurt = kurt > 5.0
                parts.append(f"concentration({'YES' if high_kurt else 'NO'}: kurt={kurt:.1f})")
            except Exception:
                parts.append("concentration(N/A)")

            # 5. Correlation increase — strategy vs market correlation in each half
            try:
                mkt_close = _load_0050_close()
                if not mkt_close.empty:
                    mkt_ret = mkt_close.pct_change().dropna()
                    common_idx = strat_rets.index.intersection(mkt_ret.index)
                    if len(common_idx) > 60:
                        s = strat_rets.loc[common_idx]
                        m = mkt_ret.loc[common_idx]
                        c_mid = len(common_idx) // 2
                        corr_h1 = float(s.iloc[:c_mid].corr(m.iloc[:c_mid]))
                        corr_h2 = float(s.iloc[c_mid:].corr(m.iloc[c_mid:]))
                        increased = corr_h2 > corr_h1 + 0.15
                        parts.append(f"correlation({'YES' if increased else 'NO'}: {corr_h1:.2f}\u2192{corr_h2:.2f})")
                    else:
                        parts.append("correlation(N/A)")
                else:
                    parts.append("correlation(N/A)")
            except Exception:
                parts.append("correlation(N/A)")

            return "Loss attribution: " + " | ".join(parts)
        except Exception:
            return "N/A"

    @staticmethod
    def _compute_crowding_risk(result: Any) -> str:
        try:
            if not result.trades:
                return "N/A (no trades)"
            ann_day_trades = 0
            other_day_trades = 0
            for t in result.trades:
                if t.timestamp.day in (11, 12):
                    ann_day_trades += 1
                else:
                    other_day_trades += 1
            n_months = max(len(result.nav_series) / 21, 1)
            ann_per_day = ann_day_trades / max(n_months * 2, 1)
            other_per_day = other_day_trades / max(n_months * 20, 1)
            crowding = ann_per_day > 3 * other_per_day if other_per_day > 0 else False
            flag = "WARNING CROWDING RISK" if crowding else "OK"
            return (
                f"Day 11-12 trades: {ann_day_trades} ({ann_per_day:.1f}/day) vs "
                f"other: {other_day_trades} ({other_per_day:.1f}/day) — {flag}"
            )
        except Exception:
            return "N/A"
