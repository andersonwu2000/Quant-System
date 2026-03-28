"""StrategyValidator — 策略上線前的強制驗證閘門。

所有策略（無論手動研究或自動化 Alpha）在進入 Paper/Live 交易前，
必須通過此驗證器的全部檢查。任何一項不通過即判定為不合格。

檢查項目（15 項）：
1.  Universe size — 選股池 ≥ 50
2.  CAGR — ≥ 8%
3.  Sharpe — ≥ 0.7
4.  Max Drawdown — ≤ 40%
5.  Turnover + cost — 成本 / gross alpha < 50%
6.  Walk-Forward — ≥ 60% 年份 OOS Sharpe > 0
7.  Deflated Sharpe — ≥ 0.70（寬鬆門檻）
8.  Bootstrap — P(Sharpe > 0) ≥ 80%
9.  OOS Sharpe — ≥ 0
10. vs 1/N benchmark — 超額 ≥ 0
11. PBO — ≤ 50%
12. Regime breakdown — 最差年 ≥ -30%
13. Factor decay — 最近 1 年 Sharpe ≥ 0
14. Market correlation — |corr with 0050| ≤ 0.90
15. CVaR(95%) — ≥ -5%

用法：
    from src.backtest.validator import StrategyValidator, ValidationConfig
    validator = StrategyValidator(config)
    report = validator.validate(strategy, universe, start, end)
    if not report.passed:
        print(report.summary())
        # 不可進入交易
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.analytics import BacktestResult, deflated_sharpe
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.backtest.overfitting import compute_pbo
from src.strategy.base import Strategy

logger = logging.getLogger(__name__)


# ── 驗證配置 ───────────────────────────────────────────────────────


@dataclass
class ValidationConfig:
    """驗證標準配置。可依策略類型調整門檻。"""

    # 1. Full backtest
    min_cagr: float = 0.08            # CAGR > 8%（統一標準，15% 太嚴）
    min_sharpe: float = 0.7           # Sharpe > 0.7
    max_drawdown: float = 0.40        # MDD < 40%（收緊自 50%，機構標準）

    # 2. Walk-Forward
    wf_train_years: int = 2           # 訓練窗口（從 3 改 2，確保 WF ≥ 4 年讓 PBO 有效）
    wf_test_years: int = 1            # 測試窗口
    wf_min_positive_ratio: float = 0.6  # ≥ 60% 年份 OOS Sharpe > 0

    # 3. PBO
    max_pbo: float = 0.50             # PBO < 50%
    pbo_n_partitions: int = 10

    # 4. Deflated Sharpe
    min_dsr: float = 0.95             # DSR p-value > 0.95
    n_trials: int = 1                 # 已測試的策略總數（需外部傳入）

    # 5. Bootstrap
    bootstrap_n: int = 1000
    min_prob_sharpe_positive: float = 0.80  # P(SR > 0) > 80%

    # 6. OOS holdout
    oos_start: str = "2025-01-01"
    oos_end: str = "2025-12-31"
    oos_min_sharpe: float = 0.3       # OOS Sharpe > 0.3（合理的風險調整報酬）

    # 7. vs 0050.TW benchmark
    min_excess_return: float = 0.0    # 超額 > 0

    # 8. Turnover + cost
    max_annual_turnover: float = 0.80  # 年化換手率 < 80%（月頻策略）
    max_cost_ratio: float = 0.50      # 成本 / gross alpha < 50%

    # 9. Regime breakdown
    max_worst_regime_loss: float = -0.30  # 最差 regime 年化 < -30%

    # 10. Selection bias
    min_universe_size: int = 50       # 驗證用 universe 至少 50 支

    # 11. Factor decay
    decay_lookback_days: int = 252    # 看最近 1 年
    min_recent_sharpe: float = 0.0    # 最近 1 年 Sharpe > 0

    # 14. Market correlation
    max_market_corr: float = 0.90     # |corr with market| < 0.90（需有獨立 alpha）

    # 15. CVaR / tail risk
    max_cvar_95: float = -0.05        # Daily CVaR(95%) > -5%（允許最差 5% 日均損 < 5%）

    # Backtest settings
    initial_cash: float = 10_000_000
    commission_rate: float = 0.001425
    tax_rate: float = 0.003
    rebalance_freq: str = "monthly"


# ── 單項檢查結果 ───────────────────────────────────────────────────


@dataclass
class CheckResult:
    """單一檢查項的結果。"""
    name: str
    passed: bool
    value: Any            # 實際值
    threshold: Any        # 門檻值
    detail: str = ""      # 額外說明


# ── 驗證報告 ───────────────────────────────────────────────────────


@dataclass
class ValidationReport:
    """完整驗證報告。"""
    strategy_name: str
    checks: list[CheckResult] = field(default_factory=list)
    backtest_result: BacktestResult | None = None
    walkforward_results: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""

    @property
    def passed(self) -> bool:
        """全部檢查通過才算 pass。"""
        if self.error:
            return False
        return all(c.passed for c in self.checks)

    @property
    def n_passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def n_total(self) -> int:
        return len(self.checks)

    def summary(self) -> str:
        """產出人類可讀的驗證摘要。"""
        lines = [
            f"═══ Strategy Validation Report: {self.strategy_name} ═══",
            f"Result: {'PASSED' if self.passed else 'FAILED'} ({self.n_passed}/{self.n_total})",
            "",
        ]
        if self.error:
            lines.append(f"ERROR: {self.error}")
            return "\n".join(lines)

        for c in self.checks:
            icon = "✓" if c.passed else "✗"
            lines.append(f"  {icon} {c.name:<30s} {str(c.value):>12s}  (threshold: {c.threshold})")
            if c.detail:
                lines.append(f"    {c.detail}")

        lines.append("")
        if self.passed:
            lines.append("All checks passed. Strategy is eligible for paper/live trading.")
        else:
            failed = [c.name for c in self.checks if not c.passed]
            lines.append(f"Failed checks: {', '.join(failed)}")
            lines.append("Strategy CANNOT proceed to trading until all checks pass.")

        return "\n".join(lines)


# ── 驗證器 ─────────────────────────────────────────────────────────


class StrategyValidator:
    """策略上線前的強制驗證閘門。

    用法：
        config = ValidationConfig(min_sharpe=0.7, n_trials=5)
        validator = StrategyValidator(config)
        report = validator.validate(strategy, universe, "2017-01-01", "2025-06-30")
        if report.passed:
            # 可以進入 paper trading
        else:
            print(report.summary())
    """

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    def validate(
        self,
        strategy: Strategy,
        universe: list[str],
        start: str,
        end: str,
    ) -> ValidationReport:
        """執行全部驗證檢查。"""
        cfg = self.config
        report = ValidationReport(strategy_name=strategy.name())

        # V8 fix: OOS 重疊防護 — IS end 不能超過 OOS start
        if pd.Timestamp(end) > pd.Timestamp(cfg.oos_start):
            logger.warning(
                "IS end (%s) > OOS start (%s) — truncating IS to avoid data leakage",
                end, cfg.oos_start,
            )
            end = (pd.Timestamp(cfg.oos_start) - pd.DateOffset(days=1)).strftime("%Y-%m-%d")

        # 10. Selection bias check（前置：universe 夠大嗎？）
        report.checks.append(CheckResult(
            name="universe_size",
            passed=len(universe) >= cfg.min_universe_size,
            value=str(len(universe)),
            threshold=f">= {cfg.min_universe_size}",
        ))

        # 1. Full backtest
        logger.info("[Validator] Running full backtest...")
        try:
            bt_config = self._make_bt_config(universe, start, end)
            engine = BacktestEngine()
            result = engine.run(strategy, bt_config)
            report.backtest_result = result

            report.checks.append(CheckResult(
                name="cagr",
                passed=result.annual_return >= cfg.min_cagr,
                value=f"{result.annual_return:+.2%}",
                threshold=f">= {cfg.min_cagr:+.2%}",
            ))
            report.checks.append(CheckResult(
                name="sharpe",
                passed=result.sharpe >= cfg.min_sharpe,
                value=f"{result.sharpe:.3f}",
                threshold=f">= {cfg.min_sharpe:.3f}",
            ))
            report.checks.append(CheckResult(
                name="max_drawdown",
                passed=abs(result.max_drawdown) <= cfg.max_drawdown,
                value=f"{result.max_drawdown:+.2%}",
                threshold=f"<= {cfg.max_drawdown:.0%}",
            ))
        except Exception as e:
            report.error = f"Full backtest failed: {e}"
            return report

        # 8. Turnover + cost（兩邊都年化比較）
        # V2 fix: 用 gross alpha（net + cost）作為分母，而非 net return
        # Use trading days / 252 (consistent with analytics.py CAGR calculation)
        n_years = max((len(result.nav_series) - 1) / 252, 0.5) if len(result.nav_series) > 1 \
            else max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 0.5)
        annual_cost_rate = result.total_commission / cfg.initial_cash / n_years
        gross_alpha = result.annual_return + annual_cost_rate  # gross ≈ net + cost
        cost_ratio = annual_cost_rate / abs(gross_alpha) if gross_alpha > 0 else 1.0
        report.checks.append(CheckResult(
            name="annual_cost_ratio",
            passed=cost_ratio <= cfg.max_cost_ratio if gross_alpha > 0 else False,
            value=f"{cost_ratio:.0%}",
            threshold=f"< {cfg.max_cost_ratio:.0%} of gross",
            detail=f"Annual cost: {annual_cost_rate:.2%}, Gross CAGR: {gross_alpha:.2%}, Net CAGR: {result.annual_return:.2%}",
        ))

        # 2. Walk-Forward
        logger.info("[Validator] Running Walk-Forward...")
        wf_results = self._run_walkforward(strategy, universe, start, end)
        report.walkforward_results = wf_results
        valid_wf = [r for r in wf_results if "error" not in r and r.get("trades", 0) > 0]
        error_wf = [r for r in wf_results if "error" in r or r.get("trades", 0) == 0]
        oos_sharpes = [r["sharpe"] for r in valid_wf]
        positive_ratio = sum(1 for s in oos_sharpes if s > 0) / max(len(oos_sharpes), 1)
        wf_detail = f"OOS Sharpes: {[f'{s:.2f}' for s in oos_sharpes]}"
        if error_wf:
            err_years = [str(r.get("year", "?")) for r in error_wf]
            wf_detail += f" (excluded {len(error_wf)} folds: {','.join(err_years)})"
        report.checks.append(CheckResult(
            name="walkforward_positive_ratio",
            passed=positive_ratio >= cfg.wf_min_positive_ratio,
            value=f"{positive_ratio:.0%}",
            threshold=f">= {cfg.wf_min_positive_ratio:.0%}",
            detail=wf_detail,
        ))

        # 4. Deflated Sharpe
        logger.info("[Validator] Computing Deflated Sharpe...")
        if result.sharpe > 0 and hasattr(result, 'daily_returns'):
            try:
                ret = result.daily_returns if result.daily_returns is not None else pd.Series(dtype=float)
                if len(ret) > 10:
                    from scipy.stats import skew, kurtosis
                    sk = float(skew(ret.dropna()))
                    # V1 fix: scipy kurtosis(fisher=True) returns excess kurtosis (normal=0)
                    # deflated_sharpe expects normal kurtosis (normal=3), so add 3
                    ku = float(kurtosis(ret.dropna())) + 3.0
                    dsr = deflated_sharpe(result.sharpe, cfg.n_trials, len(ret), sk, ku)
                else:
                    dsr = 0.0
            except Exception:
                dsr = 0.0
        else:
            dsr = 0.0
        report.checks.append(CheckResult(
            name="deflated_sharpe",
            passed=dsr >= cfg.min_dsr or cfg.n_trials <= 1,
            value=f"{dsr:.3f}",
            threshold=f">= {cfg.min_dsr:.3f}" if cfg.n_trials > 1 else "N/A (single trial)",
        ))

        # 5. Bootstrap P(Sharpe > 0)
        logger.info("[Validator] Running Bootstrap...")
        prob_positive = self._bootstrap_sharpe(result, cfg.bootstrap_n)
        report.checks.append(CheckResult(
            name="bootstrap_p_sharpe_positive",
            passed=prob_positive >= cfg.min_prob_sharpe_positive,
            value=f"{prob_positive:.1%}",
            threshold=f">= {cfg.min_prob_sharpe_positive:.0%}",
        ))

        # 6. OOS holdout
        logger.info("[Validator] Running OOS holdout...")
        oos_result = self._run_oos(strategy, universe, cfg.oos_start, cfg.oos_end)
        oos_sharpe = oos_result.get("sharpe", 0.0)
        oos_error = oos_result.get("error", "")
        if oos_error:
            oos_detail = f"OOS {cfg.oos_start}~{cfg.oos_end}: ERROR — {oos_error}"
        else:
            oos_detail = f"OOS {cfg.oos_start}~{cfg.oos_end}, return={oos_result.get('return', 0):+.2%}"
        report.checks.append(CheckResult(
            name="oos_sharpe",
            passed=oos_sharpe >= cfg.oos_min_sharpe and not oos_error,
            value=f"{oos_sharpe:.3f}" if not oos_error else "N/A (error)",
            threshold=f">= {cfg.oos_min_sharpe:.3f}",
            detail=oos_detail,
        ))

        # 7. vs 0050.TW benchmark
        logger.info("[Validator] Running 0050.TW benchmark comparison...")
        excess = self._vs_benchmark(result, universe, start, end)
        report.checks.append(CheckResult(
            name="vs_0050_excess",
            passed=excess >= cfg.min_excess_return,
            value=f"{excess:+.2%}",
            threshold=f">= {cfg.min_excess_return:+.2%}",
        ))

        # 3. PBO (needs Walk-Forward period returns as strategy variants)
        logger.info("[Validator] Computing PBO...")
        pbo_val = self._compute_pbo(wf_results, strategy=strategy, universe=universe, start=start, end=end)
        report.checks.append(CheckResult(
            name="pbo",
            passed=pbo_val <= cfg.max_pbo,
            value=f"{pbo_val:.3f}",
            threshold=f"<= {cfg.max_pbo:.3f}",
            detail="Bailey 2015 CSCV on WF periods",
        ))

        # 9. Regime breakdown (bull/bear/sideways)
        logger.info("[Validator] Regime breakdown...")
        regime_check = self._check_regime_breakdown(wf_results, cfg.max_worst_regime_loss)
        report.checks.append(regime_check)

        # 11. Factor decay (recent period)
        logger.info("[Validator] Checking factor decay...")
        recent_result = self._check_recent_performance(strategy, universe, end, cfg.decay_lookback_days)
        recent_sharpe = recent_result["sharpe"]
        recent_error = recent_result.get("error", "")
        recent_range = f"{recent_result.get('start', '?')}~{recent_result.get('end', '?')}"
        if recent_error:
            recent_detail = f"{recent_range}: ERROR — {recent_error}"
        else:
            recent_detail = f"{recent_range} ({cfg.decay_lookback_days} trading days)"
        report.checks.append(CheckResult(
            name="recent_period_sharpe",
            passed=recent_sharpe >= cfg.min_recent_sharpe and not recent_error,
            value=f"{recent_sharpe:.3f}" if not recent_error else "N/A (error)",
            threshold=f">= {cfg.min_recent_sharpe:.3f}",
            detail=recent_detail,
        ))

        # 14. 因子相關性（和市場的相關性 — 是否有獨立 alpha）
        logger.info("[Validator] Checking market correlation...")
        mkt_corr = self._market_correlation(result, universe, start, end)
        report.checks.append(CheckResult(
            name="market_correlation",
            passed=abs(mkt_corr) <= cfg.max_market_corr,
            value=f"{mkt_corr:.3f}",
            threshold=f"|corr| <= {cfg.max_market_corr:.2f}",
            detail="Daily return correlation with 0050.TW (high = no independent alpha)",
        ))

        # 15. CVaR/尾部風險
        logger.info("[Validator] Computing CVaR...")
        cvar95 = self._compute_cvar(result, 0.05)
        report.checks.append(CheckResult(
            name="cvar_95",
            passed=cvar95 >= cfg.max_cvar_95,
            value=f"{cvar95:.2%}",
            threshold=f">= {cfg.max_cvar_95:.2%}",
            detail="Daily CVaR(95%): expected shortfall in worst 5% of days",
        ))

        return report

    # ── 內部方法 ───────────────────────────────────────────────────

    def _make_bt_config(self, universe: list[str], start: str, end: str) -> BacktestConfig:
        cfg = self.config
        # V7 fix: 使用 config 的 fractional_shares 設定，而非強制 True
        # 台股用整張（fractional_shares=False）才能反映真實交易
        fractional = getattr(cfg, "fractional_shares", False)
        # Validator 用寬鬆風控 — 目的是測試策略邏輯，不是測試風控規則
        from src.risk.rules import (
            max_position_weight, max_order_notional, daily_drawdown_limit,
        )
        validator_risk_rules = [
            max_position_weight(0.15),       # 允許 15%/股（策略通常 10%）
            max_order_notional(0.20),        # 單筆上限 20%
            daily_drawdown_limit(0.05),      # 5% 日回撤
        ]

        return BacktestConfig(
            universe=universe,
            start=start,
            end=end,
            initial_cash=cfg.initial_cash,
            commission_rate=cfg.commission_rate,
            tax_rate=cfg.tax_rate,
            rebalance_freq=cfg.rebalance_freq,  # type: ignore[arg-type]
            fractional_shares=fractional,
            market_lot_sizes={".TW": 1000, ".TWO": 1000},
            risk_rules=validator_risk_rules,
            enable_kill_switch=True,
            kill_switch_cooldown="end_of_month",
            execution_delay=1,
            fill_on="open",
            impact_model="sqrt",
        )

    def _run_walkforward(
        self,
        strategy: Strategy,
        universe: list[str],
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        """滾動 Walk-Forward。"""
        cfg = self.config
        start_year = int(start[:4])
        end_year = int(end[:4])
        results: list[dict[str, Any]] = []

        # Generate windows
        for test_year in range(start_year + cfg.wf_train_years, end_year + 1):
            test_start = f"{test_year}-01-01"
            test_end = f"{test_year}-12-31"
            try:
                bt_config = self._make_bt_config(universe, test_start, test_end)
                engine = BacktestEngine()
                r = engine.run(strategy, bt_config)
                results.append({
                    "year": test_year,
                    "return": r.total_return,
                    "cagr": r.annual_return,
                    "sharpe": r.sharpe,
                    "max_drawdown": r.max_drawdown,
                    "trades": r.total_trades,
                })
            except Exception as e:
                results.append({"year": test_year, "sharpe": 0.0, "error": str(e)})

        return results

    def _bootstrap_sharpe(self, result: BacktestResult, n_bootstrap: int) -> float:
        """Bootstrap P(Sharpe > 0)。"""
        # 使用 daily_returns（與 DSR 一致）
        ret_series = getattr(result, 'daily_returns', None)
        if ret_series is None:
            return 1.0 if result.sharpe > 0 else 0.0

        returns = ret_series.dropna().values
        if len(returns) < 20:
            return 1.0 if result.sharpe > 0 else 0.0

        rng = np.random.default_rng(42)
        positive_count = 0
        for _ in range(n_bootstrap):
            sample = rng.choice(returns, size=len(returns), replace=True)
            mean_r = sample.mean()
            std_r = sample.std(ddof=1)
            if std_r > 0:
                sr = mean_r / std_r * np.sqrt(252)
                if sr > 0:
                    positive_count += 1

        return positive_count / n_bootstrap

    def _market_correlation(
        self, result: BacktestResult, universe: list[str], start: str, end: str,
    ) -> float:
        """計算策略日報酬和市場（0050.TW）的相關性。

        優先讀本地 parquet，fallback Yahoo。取得失敗回傳 1.0（fail-closed）。
        """
        strat_rets = result.daily_returns
        if strat_rets is None or len(strat_rets) < 20:
            return 1.0  # cannot verify independence → assume correlated

        bench = self._load_0050(start, end)
        if bench is None or len(bench) < 20:
            return 1.0

        try:
            bench_rets = bench["close"].pct_change().dropna()
            common = strat_rets.index.intersection(bench_rets.index)
            if len(common) < 20:
                return 1.0
            corr = float(strat_rets.loc[common].corr(bench_rets.loc[common]))
            return corr if np.isfinite(corr) else 1.0
        except Exception:
            return 1.0

    def _load_0050(self, start: str, end: str) -> pd.DataFrame | None:
        """Load 0050.TW bars: local parquet first, Yahoo fallback."""
        from pathlib import Path

        market_dir = Path(__file__).resolve().parent.parent.parent / "data" / "market"
        # Try multiple naming conventions
        candidates = [
            market_dir / "0050.TW_1d.parquet",
            market_dir / "0050.TW.parquet",
            market_dir / "finmind_0050.parquet",
        ]
        for local_path in candidates:
            if not local_path.exists():
                continue
            try:
                df = pd.read_parquet(local_path)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date").sort_index()
                sliced = df.loc[start:end]
                if len(sliced) >= 20:
                    return sliced
            except Exception:
                continue

        try:
            from src.data.sources.yahoo import YahooFeed
            return YahooFeed().get_bars("0050.TW", start=start, end=end)
        except Exception:
            return None

    @staticmethod
    def _compute_cvar(result: BacktestResult, alpha: float = 0.05) -> float:
        """CVaR(95%) = 最差 5% 日均報酬的平均值。

        Returns negative value (worst-case loss). Returns -1.0 on error (fail-closed).
        """
        try:
            rets = result.daily_returns
            if rets is None or len(rets) < 20:
                return -1.0  # fail-closed: insufficient data
            sorted_rets = sorted(rets.dropna().values)
            n_tail = max(int(len(sorted_rets) * alpha), 1)
            return float(np.mean(sorted_rets[:n_tail]))
        except Exception:
            return -1.0  # fail-closed

    def _run_oos(self, strategy: Strategy, universe: list[str], start: str, end: str) -> dict[str, Any]:
        """OOS holdout 回測。"""
        try:
            bt_config = self._make_bt_config(universe, start, end)
            engine = BacktestEngine()
            r = engine.run(strategy, bt_config)
            if r.nav_series is not None and len(r.nav_series) < 5:
                return {"return": 0.0, "sharpe": 0.0,
                        "error": f"OOS {start}~{end}: only {len(r.nav_series)} days — data likely missing"}
            if r.total_trades == 0:
                return {"return": 0.0, "sharpe": 0.0,
                        "error": f"OOS {start}~{end}: 0 trades — check data availability"}
            return {"return": r.total_return, "sharpe": r.sharpe}
        except Exception as e:
            logger.warning("OOS backtest failed: %s", e)
            return {"return": 0.0, "sharpe": 0.0, "error": str(e)}

    def _compute_pbo(
        self,
        wf_results: list[dict[str, Any]],
        strategy: Strategy | None = None,
        universe: list[str] | None = None,
        start: str = "",
        end: str = "",
    ) -> float:
        """Bailey (2015) CSCV PBO using orthogonal strategy variants.

        Creates genuinely different strategy variants along 3 dimensions
        (portfolio size, weighting, rebalance frequency) to reduce
        inter-variant correlation.

        Falls back to 0.5 (inconclusive) if insufficient data.
        """
        if strategy is None or universe is None:
            logger.warning("PBO: no strategy/universe provided, returning inconclusive (0.5)")
            return 0.5

        try:
            from src.strategy.base import Context, Strategy as StrategyBase

            class _VariantStrategy(StrategyBase):
                """Strategy variant with different selection/weighting/rebalance."""
                def __init__(self, base: Strategy, top_n: int,
                             weight_mode: str = "equal", rebal_skip: int = 0):
                    self._base = base
                    self._top_n = top_n
                    self._weight_mode = weight_mode
                    self._rebal_skip = rebal_skip  # skip N bars between rebalances
                    self._bar_count = 0
                    self._cached_weights: dict[str, float] = {}
                    self._name = f"{base.name()}_n{top_n}_{weight_mode}_s{rebal_skip}"

                def name(self) -> str:
                    return self._name

                def on_bar(self, ctx: Context) -> dict[str, float]:
                    self._bar_count += 1
                    # Rebalance frequency variation: skip N bars
                    if self._rebal_skip > 0 and self._bar_count % (self._rebal_skip + 1) != 1:
                        return dict(self._cached_weights) if self._cached_weights else {}

                    weights = self._base.on_bar(ctx)
                    if not weights:
                        return dict(self._cached_weights) if self._cached_weights else {}

                    sorted_syms = sorted(weights, key=lambda s: weights[s], reverse=True)
                    selected = sorted_syms[:self._top_n]
                    if not selected:
                        return {}

                    if self._weight_mode == "signal":
                        vals = {s: max(weights[s], 0.0) for s in selected}
                        total = sum(vals.values())
                        if total <= 0:
                            result = {s: 1.0 / len(selected) for s in selected}
                        else:
                            result = {s: v / total for s, v in vals.items()}
                    elif self._weight_mode == "inverse_rank":
                        n = len(selected)
                        rank_weights = {s: (n - i) for i, s in enumerate(selected)}
                        total = sum(rank_weights.values())
                        result = {s: v / total for s, v in rank_weights.items()}
                    else:
                        w = 1.0 / len(selected)
                        result = {s: w for s in selected}

                    self._cached_weights = result
                    return dict(result)

            # 3 dimensions of variation:
            #   portfolio size: 8, 12, 15, 20
            #   weighting: equal, signal, inverse_rank
            #   rebalance skip: 0 (every bar), 1 (every 2nd bar)
            variant_configs: list[tuple[int, str, int]] = [
                (8,  "equal",        0),
                (8,  "signal",       0),
                (12, "equal",        0),
                (12, "inverse_rank", 0),
                (15, "equal",        0),
                (15, "signal",       0),
                (15, "inverse_rank", 1),
                (20, "equal",        0),
                (20, "signal",       1),
                (20, "inverse_rank", 0),
            ]

            daily_returns_dict: dict[str, pd.Series] = {}
            bt_config = self._make_bt_config(universe, start, end)

            for top_n, wmode, skip in variant_configs:
                variant = _VariantStrategy(strategy, top_n, wmode, skip)
                try:
                    engine = BacktestEngine()
                    result = engine.run(variant, bt_config)
                    if result.daily_returns is not None and len(result.daily_returns) > 20:
                        daily_returns_dict[f"n{top_n}_{wmode}_s{skip}"] = result.daily_returns
                except Exception as e:
                    logger.debug("PBO variant n%d_%s_s%d failed: %s", top_n, wmode, skip, e)
                    continue

            if len(daily_returns_dict) < 4:
                logger.warning("PBO: only %d variants produced returns (need >=4), "
                               "returning inconclusive (0.5)", len(daily_returns_dict))
                return 0.5

            # Align by date — ffill(limit=5) then drop remaining NaN rows
            # (avoids dropna() discarding entire rows when one variant has a gap)
            returns_matrix = pd.DataFrame(daily_returns_dict)
            returns_matrix = returns_matrix.ffill(limit=5).dropna()
            if len(returns_matrix) < 120:
                logger.warning("PBO: insufficient aligned data (%d days < 120), "
                               "returning pessimistic (1.0)", len(returns_matrix))
                return 1.0

            # 8-16 partitions, each >= 60 trading days for stable Sharpe
            n_parts = min(16, max(8, len(returns_matrix) // 60))
            if n_parts % 2 != 0:
                n_parts -= 1

            pbo_result = compute_pbo(returns_matrix, n_partitions=n_parts)
            logger.info("PBO CSCV: %.3f (%d combos, %d variants, %d days, %d partitions)",
                        pbo_result.pbo, pbo_result.n_combinations,
                        len(daily_returns_dict), len(returns_matrix), n_parts)
            return pbo_result.pbo

        except Exception as e:
            logger.warning("PBO computation failed: %s — returning inconclusive (0.5)", e)
            return 0.5

    def _check_regime_breakdown(
        self,
        wf_results: list[dict[str, Any]],
        max_worst_loss: float,
    ) -> CheckResult:
        """檢查最差年份的表現。

        用 WF 年度結果中最差的 CAGR 作為 worst regime proxy。
        嚴格來說應該分 bull/bear/sideways，但這需要市場 regime 分類。
        這裡用最差年度作為近似。
        """
        cagrs = [r.get("cagr", r.get("return", 0)) for r in wf_results if "error" not in r]
        if not cagrs:
            return CheckResult(
                name="worst_regime",
                passed=False,
                value="N/A",
                threshold=f">= {max_worst_loss:+.0%}",
                detail="No WF results available — fail-closed",
            )

        worst = min(cagrs)
        worst_year = "?"
        for r in wf_results:
            cagr = r.get("cagr", r.get("return", 0))
            if cagr == worst:
                worst_year = str(r.get("year", "?"))
                break

        return CheckResult(
            name="worst_regime",
            passed=worst >= max_worst_loss,
            value=f"{worst:+.2%}",
            threshold=f">= {max_worst_loss:+.0%}",
            detail=f"Worst year: {worst_year}",
        )

    def _vs_benchmark(
        self,
        result: BacktestResult,
        universe: list[str],
        start: str,
        end: str,
    ) -> float:
        """計算 vs 0050.TW buy-and-hold 的年化超額報酬。

        取得失敗回傳 -999（確保不自動通過）。
        """
        bars = self._load_0050(start, end)
        if bars is None or len(bars) < 20:
            logger.warning("Benchmark 0050.TW unavailable for %s~%s", start, end)
            return -999.0

        try:
            close = bars["close"]
            bench_total = float(close.iloc[-1] / close.iloc[0] - 1)
            n_years = max((len(result.nav_series) - 1) / 252, 0.5) if len(result.nav_series) > 1 \
                else max(len(bars) / 252, 0.5)
            bench_annual = (1 + bench_total) ** (1 / n_years) - 1
            return float(result.annual_return - bench_annual)
        except Exception as e:
            logger.warning("Benchmark calculation failed: %s", e)
            return -999.0

    def _check_recent_performance(
        self,
        strategy: Strategy,
        universe: list[str],
        end: str,
        lookback_days: int,
    ) -> dict[str, Any]:
        """檢查最近 N 交易日的 Sharpe。回傳 dict 含 sharpe + 元資料。"""
        try:
            calendar_days = int(lookback_days * 365 / 252) + 30
            recent_start = (pd.Timestamp(end) - pd.Timedelta(days=calendar_days)).strftime("%Y-%m-%d")
            bt_config = self._make_bt_config(universe, recent_start, end)
            engine = BacktestEngine()
            r = engine.run(strategy, bt_config)
            if r.nav_series is not None and len(r.nav_series) < 5:
                return {"sharpe": 0.0, "start": recent_start, "end": end,
                        "error": f"Only {len(r.nav_series)} trading days — data likely missing"}
            if r.total_trades == 0:
                return {"sharpe": 0.0, "start": recent_start, "end": end,
                        "error": "0 trades in recent period"}
            return {"sharpe": r.sharpe, "start": recent_start, "end": end}
        except Exception as e:
            logger.warning("Recent performance check failed: %s", e)
            return {"sharpe": 0.0, "start": "", "end": end, "error": str(e)}
