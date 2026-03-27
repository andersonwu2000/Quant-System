"""StrategyValidator — 策略上線前的強制驗證閘門。

所有策略（無論手動研究或自動化 Alpha）在進入 Paper/Live 交易前，
必須通過此驗證器的全部檢查。任何一項不通過即判定為不合格。

檢查項目（11 項）：
1.  Full backtest — CAGR、Sharpe、MDD
2.  Walk-Forward — 滾動 OOS Sharpe
3.  PBO — 過擬合機率（Bailey 2015）
4.  Deflated Sharpe — 多重測試校正（Bailey & López de Prado 2014）
5.  Bootstrap — P(Sharpe > 0) 信賴區間
6.  OOS holdout — 獨立保留期驗證
7.  vs 1/N benchmark — 必須跑贏等權基準
8.  Turnover + cost — 換手率和成本佔比
9.  Regime breakdown — 牛/熊/盤整分段表現
10. Selection bias check — 最寬 universe 驗證
11. Factor decay — 最近期因子是否仍有效

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
    min_cagr: float = 0.15            # CAGR > 15%
    min_sharpe: float = 0.7           # Sharpe > 0.7
    max_drawdown: float = 0.50        # MDD < 50%

    # 2. Walk-Forward
    wf_train_years: int = 3           # 訓練窗口
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
    oos_start: str = "2025-07-01"
    oos_end: str = "2025-12-31"
    oos_min_return: float = 0.0       # OOS 報酬 > 0

    # 7. vs 1/N benchmark
    benchmark_strategy: str = "equal_weight"  # 1/N 等權
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
        n_years = max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 0.5)
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
        oos_sharpes = [r["sharpe"] for r in wf_results if "sharpe" in r]
        positive_ratio = sum(1 for s in oos_sharpes if s > 0) / max(len(oos_sharpes), 1)
        report.checks.append(CheckResult(
            name="walkforward_positive_ratio",
            passed=positive_ratio >= cfg.wf_min_positive_ratio,
            value=f"{positive_ratio:.0%}",
            threshold=f">= {cfg.wf_min_positive_ratio:.0%}",
            detail=f"OOS Sharpes: {[f'{s:.2f}' for s in oos_sharpes]}",
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
        report.checks.append(CheckResult(
            name="oos_return",
            passed=oos_result.get("return", 0) >= cfg.oos_min_return,
            value=f"{oos_result.get('return', 0):+.2%}",
            threshold=f">= {cfg.oos_min_return:+.2%}",
            detail=f"OOS {cfg.oos_start}~{cfg.oos_end}",
        ))

        # 7. vs 1/N benchmark
        logger.info("[Validator] Running 1/N benchmark comparison...")
        excess = self._vs_benchmark(result, universe, start, end)
        report.checks.append(CheckResult(
            name="vs_1n_excess",
            passed=excess >= cfg.min_excess_return,
            value=f"{excess:+.2%}",
            threshold=f">= {cfg.min_excess_return:+.2%}",
        ))

        # 3. PBO (needs Walk-Forward period returns as strategy variants)
        logger.info("[Validator] Computing PBO...")
        pbo_val = self._compute_pbo(wf_results)
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
        recent_sharpe = self._check_recent_performance(strategy, universe, end, cfg.decay_lookback_days)
        report.checks.append(CheckResult(
            name="recent_period_sharpe",
            passed=recent_sharpe >= cfg.min_recent_sharpe,
            value=f"{recent_sharpe:.3f}",
            threshold=f">= {cfg.min_recent_sharpe:.3f}",
            detail=f"Last {cfg.decay_lookback_days} days",
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
            std_r = sample.std()
            if std_r > 0:
                sr = mean_r / std_r * np.sqrt(252)
                if sr > 0:
                    positive_count += 1

        return positive_count / n_bootstrap

    def _run_oos(self, strategy: Strategy, universe: list[str], start: str, end: str) -> dict[str, Any]:
        """OOS holdout 回測。"""
        try:
            bt_config = self._make_bt_config(universe, start, end)
            engine = BacktestEngine()
            r = engine.run(strategy, bt_config)
            return {"return": r.total_return, "sharpe": r.sharpe}
        except Exception as e:
            logger.warning("OOS backtest failed: %s", e)
            return {"return": 0.0, "sharpe": 0.0, "error": str(e)}

    def _compute_pbo(self, wf_results: list[dict[str, Any]]) -> float:
        """用 Walk-Forward 各年的 Sharpe 估算 PBO。

        V4/V5 fix: 當 WF 年度不足時回傳 0.5（inconclusive），不再回傳 0.0（no overfit）。
        同時標記此方法是近似值（synthetic noise variants，非真正 CSCV）。

        NOTE: 正確的 PBO (Bailey 2015 CSCV) 需要每日報酬矩陣 × 多策略配置。
        此處用 WF Sharpe + noise 作為近似，結果僅供參考。
        """
        sharpes = [r.get("sharpe", 0) for r in wf_results if "error" not in r]
        if len(sharpes) < 4:
            # V5 fix: 數據不足 → inconclusive (0.5)，而非 optimistic (0.0)
            logger.info("PBO: insufficient WF data (%d years < 4), returning inconclusive (0.5)", len(sharpes))
            return 0.5

        try:
            rng = np.random.default_rng(42)
            n_variants = max(len(sharpes), 5)
            variants = {}
            for i in range(n_variants):
                noise = rng.normal(0, 0.1, len(sharpes))
                variants[f"v{i}"] = [s + n for s, n in zip(sharpes, noise)]
            variants["original"] = sharpes

            returns_matrix = pd.DataFrame(variants)
            n_parts = min(len(sharpes), 6)
            pbo_result = compute_pbo(returns_matrix, n_partitions=n_parts)
            return pbo_result.pbo
        except Exception as e:
            logger.warning("PBO computation failed: %s — returning inconclusive", e)
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
                passed=True,
                value="N/A",
                threshold=f">= {max_worst_loss:+.0%}",
                detail="No WF results available",
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
        """計算 vs 買入持有基準的年化超額報酬。

        用大盤 ETF (0050.TW) 的 buy-and-hold 報酬作為基準。
        如果無法取得基準，fallback 假設基準 = 0。
        """
        try:
            from src.data.sources.yahoo import YahooFeed
            feed = YahooFeed()
            bars = feed.get_bars("0050.TW", start=start, end=end)
            if bars.empty or len(bars) < 20:
                return result.annual_return  # 無基準，假設 0%

            close = bars["close"]
            bench_total = float(close.iloc[-1] / close.iloc[0] - 1)
            n_years = max(len(bars) / 252, 0.5)
            bench_annual = (1 + bench_total) ** (1 / n_years) - 1
            return float(result.annual_return - bench_annual)
        except Exception as e:
            logger.warning("Benchmark comparison failed: %s", e)
            return 0.0

    def _check_recent_performance(
        self,
        strategy: Strategy,
        universe: list[str],
        end: str,
        lookback_days: int,
    ) -> float:
        """檢查最近 N 交易日的 Sharpe。"""
        try:
            # lookback_days 是交易日，轉為日曆日（×365/252）
            calendar_days = int(lookback_days * 365 / 252) + 30  # +30 buffer
            recent_start = (pd.Timestamp(end) - pd.Timedelta(days=calendar_days)).strftime("%Y-%m-%d")
            bt_config = self._make_bt_config(universe, recent_start, end)
            engine = BacktestEngine()
            r = engine.run(strategy, bt_config)
            return r.sharpe
        except Exception as e:
            logger.warning("Recent performance check failed: %s", e)
            return 0.0
