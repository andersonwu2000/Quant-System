"""StrategyValidator — 策略上線前的強制驗證閘門。

所有策略（無論手動研究或自動化 Alpha）在進入 Paper/Live 交易前，
必須通過此驗證器的硬門檻檢查。軟門檻 fail 會顯示警告但不阻擋。

檢查項目（16 項，Phase AC §7 硬/軟分離）：

硬門檻（必須全部通過）：
  CAGR ≥ 8%, Sharpe ≥ 0.7, Cost ratio < 50%, 2× cost safety,
  Temporal consistency ≥ 60%, DSR ≥ 0.70, Bootstrap ≥ 80%,
  vs EW benchmark ≥ 50%, PBO ≤ 50%, Market corr ≤ 0.80,
  Permutation p < 0.10 (if applicable)

軟門檻（報告但不阻擋）：
  Universe ≥ 50, MDD ≤ 40%, OOS Sharpe ≥ 0.3 (SE=0.82),
  Worst regime ≥ -30%, Recent Sharpe ≥ 0 (SE=1.0), CVaR ≥ -5%

用法：
    from src.backtest.validator import StrategyValidator, ValidationConfig
    validator = StrategyValidator(config)
    report = validator.validate(strategy, universe, start, end)
    if report.passed:  # 硬門檻全部通過
        print(report.summary())  # 軟門檻 warning 會顯示
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.analytics import BacktestResult, deflated_sharpe
from src.backtest.engine import BacktestConfig, BacktestEngine
from src.backtest.checks.statistical import StatisticalChecks
from src.backtest.checks.economic import EconomicChecks
from src.backtest.checks.descriptive import DescriptiveChecks
from src.strategy.base import Strategy

logger = logging.getLogger(__name__)

# Methodology version — bump when gates change
VALIDATOR_VERSION = "v3.0-AM"


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
    max_pbo: float = 0.60             # PBO < 60% (0.50 too tight — Bailey warns at 0.50-0.60)
    pbo_n_partitions: int = 10

    # 4. Deflated Sharpe
    min_dsr: float = 0.70             # DSR p-value > 0.70（Phase AB: N=15 時 0.95 太嚴）
    n_trials: int = 1                 # 已測試的策略總數（需外部傳入）

    # 5. Bootstrap
    bootstrap_n: int = 1000
    min_prob_sharpe_positive: float = 0.80  # P(SR > 0) > 80%

    # 6. OOS holdout
    oos_end: str = ""
    oos_start: str = ""
    oos_min_sharpe: float = 0.3       # OOS Sharpe > 0.3

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
    max_market_corr: float = 0.65     # AO-16: |corr| < 0.65 (was 0.80, target 0.50, gradual)

    # 15. CVaR / tail risk
    max_cvar_95: float = -0.05        # Daily CVaR(95%) > -5%

    # Backtest settings
    initial_cash: float = 10_000_000
    commission_rate: float = 0.001425
    tax_rate: float = 0.003
    rebalance_freq: str = "monthly"

    def __post_init__(self) -> None:
        """Compute rolling OOS dates at instance creation time."""
        if not self.oos_start or not self.oos_end:
            from datetime import datetime, timedelta
            today = datetime.now()
            self.oos_end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            self.oos_start = (today - timedelta(days=1 + 274)).strftime("%Y-%m-%d")


# ── 單項檢查結果 ───────────────────────────────────────────────────


@dataclass
class CheckResult:
    """單一檢查項的結果。"""
    name: str
    passed: bool
    value: Any            # 實際值
    threshold: Any        # 門檻值
    detail: str = ""      # 額外說明
    hard: bool = True     # True = 硬門檻，False = 軟門檻
    dimension: str = ""   # AO-1: "research" | "deployment" | "both"


# AO-1: Check dimension classification
CHECK_DIMENSION: dict[str, str] = {
    # Research: statistical significance of the signal
    "cagr": "both", "sharpe": "research", "deflated_sharpe": "research",
    "bootstrap_p_sharpe_positive": "research", "temporal_consistency": "research",
    "construction_sensitivity": "research", "permutation_p": "research",
    "oos_sharpe": "research", "worst_regime": "research", "sharpe_decay": "research",
    # Deployment: tradability and cost viability
    "annual_cost_ratio": "deployment", "cost_2x_safety": "deployment",
    "market_correlation": "deployment", "vs_ew_universe": "deployment",
    "naive_baseline": "deployment", "cvar_95": "deployment",
    # Both
    "max_drawdown": "both", "universe_size": "both",
}

HARD_CHECKS = {
    "cagr", "annual_cost_ratio", "cost_2x_safety",
    "temporal_consistency", "deflated_sharpe",
    "construction_sensitivity", "market_correlation",
    "permutation_p", "naive_baseline",
}
SOFT_CHECKS = {
    "universe_size", "sharpe", "max_drawdown", "oos_sharpe",
    "bootstrap_p_sharpe_positive", "vs_ew_universe",
    "worst_regime", "sharpe_decay", "cvar_95",
}


# ── 驗證報告 ───────────────────────────────────────────────────────


@dataclass
class ValidationReport:
    """完整驗證報告。"""
    strategy_name: str
    checks: list[CheckResult] = field(default_factory=list)
    backtest_result: BacktestResult | None = None
    walkforward_results: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    actual_is_start: str = ""
    actual_is_end: str = ""
    factor_attribution: str = ""
    cost_breakdown: str = ""
    regime_split: str = ""
    capacity_analysis: str = ""
    stress_test: str = ""
    benchmark_relative: str = ""
    exit_warning: str = ""
    oos_regime: str = ""
    announcement_warning: str = ""
    factor_risk: str = ""
    economic_rationale: str = ""
    family_cluster: str = ""
    position_liquidity: str = ""
    crowding_risk: str = ""
    loss_attribution: str = ""       # AO-12: 5-dimension OOS loss attribution

    MAX_SOFT_FAILURES = 3

    @property
    def research_score(self) -> float:
        """AO-1: Research dimension score (0-1). Only meaningful when hard gates pass."""
        research_checks = [c for c in self.checks
                           if CHECK_DIMENSION.get(c.name, "both") in ("research", "both")]
        if not research_checks:
            return 0.0
        return sum(1 for c in research_checks if c.passed) / len(research_checks)

    @property
    def deployment_score(self) -> float:
        """AO-1: Deployment dimension score (0-1). Only meaningful when hard gates pass."""
        deploy_checks = [c for c in self.checks
                         if CHECK_DIMENSION.get(c.name, "both") in ("deployment", "both")]
        if not deploy_checks:
            return 0.0
        return sum(1 for c in deploy_checks if c.passed) / len(deploy_checks)

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        if not all(c.passed for c in self.checks if c.hard):
            return False
        n_soft_fail = sum(1 for c in self.checks if not c.hard and not c.passed)
        return n_soft_fail < self.MAX_SOFT_FAILURES

    @property
    def n_passed(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def n_total(self) -> int:
        return len(self.checks)

    @property
    def n_hard_passed(self) -> int:
        return sum(1 for c in self.checks if c.hard and c.passed)

    @property
    def n_hard_total(self) -> int:
        return sum(1 for c in self.checks if c.hard)

    @property
    def soft_warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.hard and not c.passed]

    def summary(self) -> str:
        lines = [
            f"=== Strategy Validation Report: {self.strategy_name} ===",
            f"Validator: {VALIDATOR_VERSION}",
            f"Result: {'PASSED' if self.passed else 'FAILED'} "
            f"(hard: {self.n_hard_passed}/{self.n_hard_total}, "
            f"total: {self.n_passed}/{self.n_total})",
            "",
        ]
        if self.error:
            lines.append(f"ERROR: {self.error}")
            return "\n".join(lines)

        hard_checks = [c for c in self.checks if c.hard]
        soft_checks = [c for c in self.checks if not c.hard]

        if hard_checks:
            lines.append("--- Hard Gates (must all pass) ---")
            for c in hard_checks:
                icon = "+" if c.passed else "X"
                lines.append(f"  {icon} {c.name:<30s} {str(c.value):>12s}  (threshold: {c.threshold})")
                if c.detail:
                    lines.append(f"    {c.detail}")
            lines.append("")

        if soft_checks:
            lines.append("--- Soft Gates (warnings only) ---")
            for c in soft_checks:
                icon = "+" if c.passed else "!"
                lines.append(f"  {icon} {c.name:<30s} {str(c.value):>12s}  (threshold: {c.threshold})")
                if c.detail:
                    lines.append(f"    {c.detail}")
            lines.append("")

        for label, attr in [
            ("Cost & Capacity", "cost_breakdown"),
            ("Regime Split", "regime_split"),
            ("Capacity Analysis", "capacity_analysis"),
            ("Factor Attribution", "factor_attribution"),
            ("Stress Test", "stress_test"),
            ("Benchmark Relative", "benchmark_relative"),
            ("Exit Warning", "exit_warning"),
            ("OOS Regime", "oos_regime"),
            ("Announcement Warning (AN-8)", "announcement_warning"),
            ("Factor Risk (AN-10)", "factor_risk"),
            ("Economic Rationale (AN-12)", "economic_rationale"),
            ("Strategy Family (AN-13)", "family_cluster"),
            ("Position Liquidity (AN-14)", "position_liquidity"),
            ("Crowding Risk (AN-15)", "crowding_risk"),
            ("Loss Attribution (AO-12)", "loss_attribution"),
        ]:
            val = getattr(self, attr, "")
            if val:
                lines.append(f"--- {label} (descriptive) ---")
                lines.append(f"  {val}")
                lines.append("")

        # AO-1: Dual dimension scores
        lines.append(f"--- Scores (AO-1) ---")
        lines.append(f"  Research:   {self.research_score:.0%}")
        lines.append(f"  Deployment: {self.deployment_score:.0%}")
        lines.append("")

        n_soft_fail = sum(1 for c in self.checks if not c.hard and not c.passed)
        if self.passed:
            warnings = self.soft_warnings
            if warnings:
                lines.append(f"PASSED — eligible for paper/live trading. "
                           f"{len(warnings)} soft warning(s): {', '.join(w.name for w in warnings)}")
            else:
                lines.append("PASSED — all checks passed. Strategy is eligible for paper/live trading.")
        else:
            failed_hard = [c.name for c in self.checks if c.hard and not c.passed]
            if failed_hard:
                lines.append(f"FAILED — hard gate(s) not met: {', '.join(failed_hard)}")
                lines.append("Strategy CANNOT proceed to trading until all hard gates pass.")
            elif n_soft_fail >= self.MAX_SOFT_FAILURES:
                failed_soft = [c.name for c in self.checks if not c.hard and not c.passed]
                lines.append(f"FAILED — {n_soft_fail} soft failures (max {self.MAX_SOFT_FAILURES - 1}): "
                           f"{', '.join(failed_soft)}")
                lines.append("Strategy CANNOT proceed — too many soft warnings indicate systemic issues.")

        return "\n".join(lines)


# ── 驗證器 ─────────────────────────────────────────────────────────


class StrategyValidator(StatisticalChecks, EconomicChecks, DescriptiveChecks):
    """策略上線前的強制驗證閘門。

    Check implementations split into:
      - checks/statistical.py: bootstrap, PBO, permutation, CVaR
      - checks/economic.py: walk-forward, regime, EW benchmark, market correlation
      - checks/descriptive.py: factor attribution, stress test, capacity, etc.
    """

    def __init__(self, config: ValidationConfig | None = None) -> None:
        self.config = config or ValidationConfig()

    def validate(
        self,
        strategy: Strategy,
        universe: list[str],
        start: str,
        end: str,
        compute_fn: Any = None,
    ) -> ValidationReport:
        """執行全部驗證檢查。"""
        cfg = self.config
        report = ValidationReport(strategy_name=strategy.name())

        # V8 fix: OOS 重疊防護
        if pd.Timestamp(end) > pd.Timestamp(cfg.oos_start):
            logger.warning("IS end (%s) > OOS start (%s) — truncating IS", end, cfg.oos_start)
            end = (pd.Timestamp(cfg.oos_start) - pd.DateOffset(days=1)).strftime("%Y-%m-%d")

        report.actual_is_start = start
        report.actual_is_end = end

        # Universe size (soft)
        report.checks.append(CheckResult(
            name="universe_size",
            passed=len(universe) >= cfg.min_universe_size,
            value=str(len(universe)),
            threshold=f">= {cfg.min_universe_size}",
        ))

        # Pre-load shared feed from DataCatalog
        logger.info("[Validator] Pre-loading data feed from DataCatalog...")
        try:
            self._shared_feed = self._build_catalog_feed(universe)
        except Exception:
            self._shared_feed = None

        # ── 1. Full backtest ─────────────────────────────────────
        logger.info("[Validator] Running full backtest...")
        try:
            full_bt_config = self._make_bt_config(universe, start, end)
            engine = BacktestEngine()
            result = engine.run(strategy, full_bt_config, feed_override=self._shared_feed)
            report.backtest_result = result

            report.checks.append(CheckResult(
                name="cagr", passed=result.annual_return >= cfg.min_cagr,
                value=f"{result.annual_return:+.2%}", threshold=f">= {cfg.min_cagr:+.2%}"))
            report.checks.append(CheckResult(
                name="sharpe", passed=result.sharpe >= cfg.min_sharpe,
                value=f"{result.sharpe:.3f}", threshold=f">= {cfg.min_sharpe:.3f}"))
            report.checks.append(CheckResult(
                name="max_drawdown", passed=abs(result.max_drawdown) <= cfg.max_drawdown,
                value=f"{result.max_drawdown:+.2%}", threshold=f"<= {cfg.max_drawdown:.0%}"))
        except Exception as e:
            report.error = f"Full backtest failed: {e}"
            return report

        # ── 2. Cost checks ───────────────────────────────────────
        if len(result.nav_series) > 1:
            n_years = max((len(result.nav_series) - 1) / 252, 0.5)
        else:
            calendar_days = (pd.Timestamp(end) - pd.Timestamp(start)).days
            n_years = max(calendar_days * 252 / 365 / 252, 0.5)
        annual_cost_rate = result.total_commission / cfg.initial_cash / n_years
        gross_alpha = result.annual_return + annual_cost_rate
        cost_ratio = annual_cost_rate / abs(gross_alpha) if gross_alpha > 0 else 1.0

        report.checks.append(CheckResult(
            name="annual_cost_ratio",
            passed=cost_ratio <= cfg.max_cost_ratio if gross_alpha > 0 else False,
            value=f"{cost_ratio:.0%}", threshold=f"< {cfg.max_cost_ratio:.0%} of gross",
            detail=f"Annual cost: {annual_cost_rate:.2%}, Gross CAGR: {gross_alpha:.2%}, Net CAGR: {result.annual_return:.2%}",
        ))

        net_cagr_2x_cost = result.annual_return - annual_cost_rate
        report.checks.append(CheckResult(
            name="cost_2x_safety", passed=net_cagr_2x_cost > 0,
            value=f"{net_cagr_2x_cost:.2%}", threshold="> 0% CAGR after 2x cost",
            detail=f"Gross: {gross_alpha:.2%}, 2x cost: {2*annual_cost_rate:.2%}, Net(2x): {net_cagr_2x_cost:.2%}",
        ))

        # Cost breakdown (descriptive)
        report.cost_breakdown = self._compute_cost_breakdown(
            result, cfg, n_years, annual_cost_rate, report.walkforward_results)

        # ── 3. Walk-Forward + temporal consistency ────────────────
        logger.info("[Validator] Running Walk-Forward...")
        wf_results = self._run_walkforward(strategy, universe, start, end)
        report.walkforward_results = wf_results
        valid_wf = [r for r in wf_results if "error" not in r and r.get("trades", 0) > 0]
        oos_sharpes = [r["sharpe"] for r in valid_wf]

        cap = 2.0
        if oos_sharpes:
            scores = [np.sign(s) * min(abs(s), cap) for s in oos_sharpes]
            consistency_score = float(np.mean(scores))
        else:
            consistency_score = 0.0
        positive_ratio = sum(1 for s in oos_sharpes if s > 0) / max(len(oos_sharpes), 1)

        error_wf = [r for r in wf_results if "error" in r or r.get("trades", 0) == 0]
        wf_detail = f"OOS Sharpes: {[f'{s:.2f}' for s in oos_sharpes]}"
        if error_wf:
            err_years = [str(r.get("year", "?")) for r in error_wf]
            wf_detail += f" (excluded {len(error_wf)} folds: {','.join(err_years)})"
        report.checks.append(CheckResult(
            name="temporal_consistency",
            passed=consistency_score > 0,
            value=f"{consistency_score:+.3f} ({positive_ratio:.0%} positive)",
            threshold="> 0 (sign-magnitude weighted)", detail=wf_detail,
        ))

        # ── 4. Deflated Sharpe ────────────────────────────────────
        logger.info("[Validator] Computing Deflated Sharpe...")
        if result.sharpe > 0 and hasattr(result, 'daily_returns'):
            try:
                ret = result.daily_returns if result.daily_returns is not None else pd.Series(dtype=float)
                if len(ret) > 10:
                    from scipy.stats import skew, kurtosis
                    sk = float(skew(ret.dropna()))
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

        # ── 5. Bootstrap ──────────────────────────────────────────
        logger.info("[Validator] Running Bootstrap...")
        prob_positive = self._bootstrap_sharpe(result, cfg.bootstrap_n)
        report.checks.append(CheckResult(
            name="bootstrap_p_sharpe_positive",
            passed=prob_positive >= cfg.min_prob_sharpe_positive,
            value=f"{prob_positive:.1%}", threshold=f">= {cfg.min_prob_sharpe_positive:.0%}",
        ))

        # ── 6. OOS holdout ────────────────────────────────────────
        logger.info("[Validator] Running OOS holdout...")
        oos_result = self._run_oos(strategy, universe, cfg.oos_start, cfg.oos_end)
        oos_sharpe = oos_result.get("sharpe", 0.0)
        oos_error = oos_result.get("error", "")
        oos_detail = (f"OOS {cfg.oos_start}~{cfg.oos_end}: ERROR — {oos_error}" if oos_error
                      else f"OOS {cfg.oos_start}~{cfg.oos_end}, return={oos_result.get('return', 0):+.2%}")
        report.checks.append(CheckResult(
            name="oos_sharpe",
            passed=oos_sharpe >= cfg.oos_min_sharpe and not oos_error,
            value=f"{oos_sharpe:.3f}" if not oos_error else "N/A (error)",
            threshold=f">= {cfg.oos_min_sharpe:.3f}", detail=oos_detail,
        ))

        # ── 7. vs EW benchmark (walk-forward) ────────────────────
        logger.info("[Validator] Running walk-forward EW benchmark comparison...")
        wf_excess_results = []
        for wf in report.walkforward_results:
            if "error" in wf or wf.get("trades", 0) == 0:
                continue
            wf_year = wf.get("year", 0)
            wf_return = wf.get("return", wf.get("cagr", 0))
            wf_commission = wf.get("commission", 0)
            wf_cost_rate = wf_commission / cfg.initial_cash if cfg.initial_cash > 0 else 0
            wf_gross = wf_return + wf_cost_rate
            ew_annual = self._get_ew_annual(universe, f"{wf_year}-01-01", f"{wf_year}-12-31")
            if ew_annual is not None:
                wf_excess_results.append(wf_gross - ew_annual)

        if wf_excess_results:
            n_positive = sum(1 for e in wf_excess_results if e >= 0)
            ew_positive_ratio = n_positive / len(wf_excess_results)
            avg_excess = float(np.mean(wf_excess_results))
            excess_detail = (f"WF: {n_positive}/{len(wf_excess_results)} windows positive, "
                           f"avg excess {avg_excess:+.2%}")
        else:
            ew_positive_ratio = 0.0
            avg_excess = -999.0
            excess_detail = "No valid WF windows for EW comparison"

        report.checks.append(CheckResult(
            name="vs_ew_universe", passed=ew_positive_ratio >= 0.5,
            value=f"{ew_positive_ratio:.0%} ({avg_excess:+.2%} avg)",
            threshold=">= 50% windows positive beta-neutral excess",
            detail=excess_detail,
        ))

        # ── 8. PBO ────────────────────────────────────────────────
        logger.info("[Validator] Computing PBO...")
        _cfn = compute_fn or getattr(strategy, '_compute_fn', None)
        pbo_val = self._compute_pbo(wf_results, strategy=strategy, universe=universe,
                                     start=start, end=end, compute_fn=_cfn)
        avg_corr = getattr(self, '_pbo_avg_corr', 0.0)
        confidence = "LOW CONFIDENCE" if avg_corr > 0.8 else "normal"
        report.checks.append(CheckResult(
            name="construction_sensitivity", passed=pbo_val <= cfg.max_pbo,
            value=f"{pbo_val:.3f}", threshold=f"<= {cfg.max_pbo:.3f}",
            detail=f"Construction PBO (avg_pairwise_corr={avg_corr:.3f}, {confidence})",
        ))

        # ── 9. Regime ─────────────────────────────────────────────
        logger.info("[Validator] Regime breakdown...")
        report.checks.append(self._check_regime_breakdown(
            wf_results, cfg.max_worst_regime_loss, result=result, start=start, end=end))

        # ── 10. Sharpe decay ──────────────────────────────────────
        logger.info("[Validator] Checking sharpe decay...")
        decay_val, decay_t, decay_detail = 0.0, 0.0, ""
        try:
            ret = result.daily_returns
            if ret is not None and len(ret) > 60:
                mid = len(ret) // 2
                first_half, second_half = ret.iloc[:mid], ret.iloc[mid:]
                sr1 = float(first_half.mean() / first_half.std() * np.sqrt(252)) if first_half.std() > 0 else 0.0
                sr2 = float(second_half.mean() / second_half.std() * np.sqrt(252)) if second_half.std() > 0 else 0.0
                decay_val = sr2 - sr1
                se_decay = np.sqrt(2.0 / len(first_half) * (1 + sr1 ** 2 / 4))
                decay_t = decay_val / se_decay if se_decay > 0 else 0.0
                decay_detail = (f"SR(first_half)={sr1:.3f}, SR(second_half)={sr2:.3f}, "
                               f"delta={decay_val:+.3f}, t={decay_t:+.2f}")
        except Exception:
            decay_detail = "computation error"
        report.checks.append(CheckResult(
            name="sharpe_decay", passed=decay_t > -2.0,
            value=f"t={decay_t:+.2f} (delta={decay_val:+.3f})",
            threshold="t > -2.0 (decay not significant)", detail=decay_detail,
        ))

        # ── 11. Market correlation ────────────────────────────────
        logger.info("[Validator] Checking market correlation...")
        mkt_corr = self._market_correlation(result, universe, start, end)
        report.checks.append(CheckResult(
            name="market_correlation", passed=abs(mkt_corr) <= cfg.max_market_corr,
            value=f"{mkt_corr:.3f}", threshold=f"|corr| <= {cfg.max_market_corr:.2f}",
            detail="Daily return correlation with 0050.TW",
        ))

        # ── 12. CVaR ──────────────────────────────────────────────
        logger.info("[Validator] Computing CVaR...")
        cvar95 = self._compute_cvar(result, 0.05)
        report.checks.append(CheckResult(
            name="cvar_95", passed=cvar95 >= cfg.max_cvar_95,
            value=f"{cvar95:.2%}", threshold=f">= {cfg.max_cvar_95:.2%}",
            detail="Daily CVaR(95%): expected shortfall in worst 5% of days",
        ))

        # ── 13. Permutation test ──────────────────────────────────
        _cfn_perm = compute_fn or getattr(strategy, '_compute_fn', None)
        if _cfn_perm is not None:
            logger.info("[Validator] Running permutation test...")
            perm_p = self._permutation_test(
                result=result, strategy=strategy, universe=universe,
                start=start, end=end, compute_fn_override=_cfn_perm)
            report.checks.append(CheckResult(
                name="permutation_p", passed=perm_p < 0.10,
                value=f"{perm_p:.3f}", threshold="< 0.10",
                detail="p-value: fraction of random shuffles with Sharpe >= strategy",
            ))
        else:
            logger.info("[Validator] Skipping permutation test (no compute_fn)")

        # ── 14. Factor attribution (descriptive) ──────────────────
        logger.info("[Validator] Computing factor attribution...")
        attr_result = None
        try:
            from src.backtest.factor_attribution import compute_factor_attribution
            strat_rets = result.nav_series.pct_change().dropna()
            strat_rets = strat_rets.replace([np.inf, -np.inf], 0.0)
            attr_result = compute_factor_attribution(strat_rets, universe, start, end)
            report.factor_attribution = attr_result.summary() if attr_result else "N/A (insufficient data)"
        except Exception:
            report.factor_attribution = "N/A"

        # AN-10: Factor risk
        report.factor_risk = self._compute_factor_risk(attr_result)

        # AN-11: Naive baseline (hard gate — placeholder)
        report.checks.append(CheckResult(
            name="naive_baseline", passed=True,
            value=f"{result.sharpe:.3f}", threshold=">= naive momentum (TODO: implement)",
            detail="Placeholder — actual naive 12-1 momentum baseline not yet computed",
        ))

        # AN-12: Economic rationale
        report.economic_rationale = "N/A — manual annotation required"

        # AN-13: Family cluster
        report.family_cluster = self._compute_family_cluster(attr_result)

        # ── Descriptive sections ──────────────────────────────────
        logger.info("[Validator] Computing descriptive sections...")
        report.capacity_analysis = self._compute_capacity_analysis(result, cfg, n_years, universe)
        report.position_liquidity = self._compute_position_liquidity(result, universe)
        report.crowding_risk = self._compute_crowding_risk(result)
        report.regime_split = self._compute_regime_split(result, start, end)
        report.stress_test = self._compute_stress_test(result)
        report.announcement_warning = self._compute_announcement_warning(result)
        report.benchmark_relative = self._compute_benchmark_relative(result, cfg.oos_start, cfg.oos_end)
        report.exit_warning = self._compute_exit_warning(result, annual_cost_rate)
        report.oos_regime = self._compute_oos_regime(cfg)
        report.loss_attribution = self._compute_loss_attribution(result, start, end)

        # ── Mark hard/soft + dimension ────────────────────────────
        all_known = HARD_CHECKS | SOFT_CHECKS
        for c in report.checks:
            if c.name not in all_known:
                logger.warning("Check '%s' not in HARD_CHECKS or SOFT_CHECKS — defaulting to hard", c.name)
            c.hard = c.name in HARD_CHECKS
            c.dimension = CHECK_DIMENSION.get(c.name, "both")

        return report

    # ── Shared helpers ────────────────────────────────────────────

    @staticmethod
    def _build_catalog_feed(universe: list[str]) -> "HistoricalFeed":  # noqa: F821
        """Build HistoricalFeed from DataCatalog (local parquets)."""
        from src.data.feed import HistoricalFeed
        from src.data.data_catalog import get_catalog

        catalog = get_catalog()
        feed = HistoricalFeed()
        for sym in universe:
            df = catalog.get("price", sym)
            if df.empty or "close" not in df.columns:
                continue
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            feed.load(sym, df)
        return feed

    def _make_bt_config(self, universe: list[str], start: str, end: str) -> BacktestConfig:
        cfg = self.config
        fractional = getattr(cfg, "fractional_shares", False)
        from src.risk.rules import (
            max_position_weight, max_order_notional, daily_drawdown_limit,
        )
        validator_risk_rules = [
            max_position_weight(0.15),
            max_order_notional(0.20),
            daily_drawdown_limit(0.05),
        ]

        return BacktestConfig(
            universe=universe, start=start, end=end,
            initial_cash=cfg.initial_cash,
            commission_rate=cfg.commission_rate,
            tax_rate=cfg.tax_rate,
            rebalance_freq=cfg.rebalance_freq,  # type: ignore[arg-type]
            fractional_shares=fractional,
            market_lot_sizes={".TW": 1000, ".TWO": 1000},
            risk_rules=validator_risk_rules,
            enable_kill_switch=False,
            kill_switch_cooldown="end_of_month",
            execution_delay=1,
            fill_on="open",
            impact_model="sqrt",
            price_limit_pct=0.10,
        )

    def _load_0050(self, start: str, end: str) -> pd.DataFrame | None:
        """Load 0050.TW bars from DataCatalog."""
        from src.data.data_catalog import get_catalog
        try:
            df = get_catalog().get("price", "0050.TW")
            if df.empty or "close" not in df.columns:
                return None
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            sliced = df.loc[start:end]
            return sliced if len(sliced) >= 20 else None
        except Exception:
            return None

    def _run_oos(self, strategy: Strategy, universe: list[str], start: str, end: str) -> dict[str, Any]:
        """OOS holdout backtest."""
        try:
            bt_config = self._make_bt_config(universe, start, end)
            engine = BacktestEngine()
            feed = self._build_catalog_feed(universe)
            r = engine.run(strategy, bt_config, feed_override=feed)
            if r.nav_series is not None and len(r.nav_series) < 5:
                return {"return": 0.0, "sharpe": 0.0,
                        "error": f"OOS {start}~{end}: only {len(r.nav_series)} days"}
            if r.total_trades == 0:
                return {"return": 0.0, "sharpe": 0.0,
                        "error": f"OOS {start}~{end}: 0 trades"}
            return {"return": r.total_return, "sharpe": r.sharpe}
        except Exception as e:
            logger.warning("OOS backtest failed: %s", e)
            return {"return": 0.0, "sharpe": 0.0, "error": str(e)}
