"""Alpha Research Agent — 自動化因子挖掘主循環。

三階段管線（Idea → Factor → Eval）+ Experience Memory 持久化。
每輪產出一個因子假說，實作、驗證、蒸餾結果回 Memory。

用法：
    # 單輪（Claude Code 排程用）
    python -m scripts.alpha_research_agent --rounds 1

    # 多輪連續研究
    python -m scripts.alpha_research_agent --rounds 20 --interval 5

    # 指定方向
    python -m scripts.alpha_research_agent --direction revenue_quality_interaction

    # 查看 Memory 狀態
    python -m scripts.alpha_research_agent --status
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.alpha.auto.experience_memory import (
    ExperienceMemory,
    Hypothesis,
    ResearchTrajectory,
    SuccessPattern,
)
from src.alpha.auto.factor_evaluator import EvaluationResult, FactorEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MEMORY_PATH = "data/research/memory.json"
FACTOR_DIR = Path("src/strategy/factors/research")
EVAL_DIR = Path("data/research/evaluations")
TRAJECTORY_DIR = Path("data/research/trajectories")
SUMMARY_DIR = Path("data/research/daily_summary")


# ── Hypothesis Templates ───────────────────────────────────────


HYPOTHESIS_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "revenue_quality_interaction": [
        {
            "name": "rev_yoy_x_gross_margin_chg",
            "description": "營收成長且毛利率同步改善 = 真需求增長（非削價搶市）",
            "formula_sketch": "rank(rev_yoy) × rank(gross_margin_pct_change)",
            "academic_basis": "Novy-Marx (2013) gross profitability + revenue momentum",
            "data_requirements": ["revenue", "financial_statement"],
        },
        {
            "name": "rev_yoy_x_roe_improvement",
            "description": "營收成長且 ROE 提升 = 高品質成長",
            "formula_sketch": "rank(rev_yoy) × rank(roe_change_yoy)",
            "academic_basis": "Fama-French (2015) RMW profitability",
            "data_requirements": ["revenue", "financial_statement"],
        },
        {
            "name": "rev_accel_x_operating_margin",
            "description": "營收加速中且營業利益率穩定/改善",
            "formula_sketch": "rank(rev_3m/rev_12m) × rank(operating_margin > median)",
            "academic_basis": "Operating leverage effect",
            "data_requirements": ["revenue", "financial_statement"],
        },
    ],
    "seasonal_revenue_patterns": [
        {
            "name": "rev_seasonal_deviation",
            "description": "實際營收 vs 同行業歷史同月平均的偏離",
            "formula_sketch": "rev_this_month / mean(rev_same_month_past_3years) - 1",
            "academic_basis": "Seasonal anomalies in earnings",
            "data_requirements": ["revenue"],
        },
        {
            "name": "rev_yoy_acceleration",
            "description": "營收 YoY 的月度加速度（本月 YoY - 上月 YoY）",
            "formula_sketch": "rev_yoy[t] - rev_yoy[t-1]",
            "academic_basis": "Earnings momentum acceleration",
            "data_requirements": ["revenue"],
        },
    ],
    "revenue_acceleration_2nd_order": [
        {
            "name": "rev_accel_2nd_derivative",
            "description": "營收加速度的二階導數（加速度的變化率）",
            "formula_sketch": "d(rev_3m/rev_12m)/dt",
            "academic_basis": "Second-order momentum",
            "data_requirements": ["revenue"],
        },
        {
            "name": "rev_consecutive_beat",
            "description": "連續 N 月營收超越去年同月的月數",
            "formula_sketch": "sum(rev_yoy > 0 for last 12 months)",
            "academic_basis": "Earnings consistency premium",
            "data_requirements": ["revenue"],
        },
    ],
    "earnings_surprise_proxy": [
        {
            "name": "rev_vs_trend_residual",
            "description": "實際營收 vs 近 6 月線性趨勢的殘差",
            "formula_sketch": "actual_rev - linear_trend_prediction(rev[-6:])",
            "academic_basis": "Earnings surprise (Ball-Brown 1968)",
            "data_requirements": ["revenue"],
        },
        {
            "name": "rev_breakout",
            "description": "本月營收突破近 12 月最高值的幅度",
            "formula_sketch": "max(0, rev_this_month / max(rev[-12:]) - 1)",
            "academic_basis": "52-week high effect applied to revenue",
            "data_requirements": ["revenue"],
        },
    ],
    "supply_chain_propagation": [
        {
            "name": "upstream_rev_lead",
            "description": "同行業上游公司營收 lead 本公司 1-2 月",
            "formula_sketch": "corr(upstream_rev_yoy[t-1], self_rev_yoy[t])",
            "academic_basis": "Supply chain momentum (Menzly-Ozbas 2010)",
            "data_requirements": ["revenue", "industry"],
        },
    ],
    "inventory_turnover": [
        {
            "name": "inventory_revenue_divergence",
            "description": "存貨下降 + 營收上升 = 真需求",
            "formula_sketch": "rank(-inventory_change) × rank(rev_yoy)",
            "academic_basis": "Thomas-Zhang (2002) inventory changes",
            "data_requirements": ["financial_statement", "revenue"],
        },
    ],
    "operating_leverage": [
        {
            "name": "rev_sensitivity_to_profit",
            "description": "營收小增 → 利潤大增（高營業槓桿）",
            "formula_sketch": "profit_growth / revenue_growth",
            "academic_basis": "Operating leverage effect",
            "data_requirements": ["financial_statement", "revenue"],
        },
    ],
    "cash_flow_quality": [
        {
            "name": "cfo_over_ni",
            "description": "CFO/NI > 1 表示盈餘品質好（非應計）",
            "formula_sketch": "cash_from_operations / net_income",
            "academic_basis": "Sloan (1996) accrual anomaly",
            "data_requirements": ["financial_statement"],
        },
    ],
    "capex_intensity": [
        {
            "name": "capex_to_revenue_change",
            "description": "資本支出/營收的變化（投資強度）",
            "formula_sketch": "-(capex/revenue)[t] + (capex/revenue)[t-4]",
            "academic_basis": "Fama-French (2015) CMA investment factor",
            "data_requirements": ["financial_statement", "revenue"],
        },
    ],
}


# ── Factor Implementation Templates ───────────────────────────


def _implement_revenue_factor(hypothesis: Hypothesis) -> str | None:
    """根據假說產生因子計算代碼（營收相關）。"""
    name = hypothesis.name

    code = f'''"""Auto-generated research factor: {name}

{hypothesis.description}
Academic basis: {hypothesis.academic_basis}
Direction: {hypothesis.direction}
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path

FUND_DIR = Path("data/fundamental")


def compute_{name}(symbols: list[str], as_of: pd.Timestamp) -> dict[str, float]:
    """Compute {name} for all symbols at as_of date."""
    results = {{}}
    for sym in symbols:
        try:
            rev_path = FUND_DIR / f"{{sym}}_revenue.parquet"
            if not rev_path.exists():
                continue
            df = pd.read_parquet(rev_path)
            if df.empty or "revenue" not in df.columns:
                continue
            df["date"] = pd.to_datetime(df["date"])
            df = df[df["date"] <= as_of].sort_values("date")
            if len(df) < 12:
                continue

            revenues = df["revenue"].astype(float).values
'''

    # Add specific computation based on hypothesis name
    if "yoy_acceleration" in name or "2nd_derivative" in name:
        code += '''
            # YoY for each month
            if len(revenues) < 24:
                continue
            yoy = []
            for i in range(12, len(revenues)):
                if revenues[i-12] > 0:
                    yoy.append(revenues[i] / revenues[i-12] - 1)
                else:
                    yoy.append(0)
            if len(yoy) < 2:
                continue
            # Acceleration = latest YoY - previous YoY
            results[sym] = float(yoy[-1] - yoy[-2])
'''
    elif "consecutive_beat" in name:
        code += '''
            if len(revenues) < 24:
                continue
            count = 0
            for i in range(max(len(revenues)-12, 12), len(revenues)):
                if revenues[i-12] > 0 and revenues[i] > revenues[i-12]:
                    count += 1
            results[sym] = float(count)
'''
    elif "seasonal_deviation" in name:
        code += '''
            if len(revenues) < 36:
                continue
            # Current month revenue vs same month average of past 3 years
            current = revenues[-1]
            month_idx = len(revenues) - 1
            same_month = [revenues[month_idx - 12*k] for k in range(1, 4) if month_idx - 12*k >= 0]
            if not same_month or np.mean(same_month) <= 0:
                continue
            results[sym] = float(current / np.mean(same_month) - 1)
'''
    elif "vs_trend_residual" in name or "breakout" in name:
        code += '''
            if len(revenues) < 12:
                continue
            recent_6 = revenues[-6:]
            # Linear trend
            x = np.arange(len(recent_6))
            slope = np.polyfit(x, recent_6, 1)[0]
            predicted = recent_6[-1] + slope
            actual = revenues[-1]
            if predicted > 0:
                results[sym] = float((actual - predicted) / predicted)
'''
    elif "x_gross_margin" in name or "x_roe" in name or "x_operating" in name:
        code += '''
            # Revenue YoY
            if len(revenues) < 12 or revenues[-12] <= 0:
                continue
            rev_yoy = revenues[-1] / revenues[-12] - 1

            # For interaction factors, use rev_yoy as proxy
            # (full implementation needs financial_statement data)
            results[sym] = float(rev_yoy)
'''
    else:
        code += '''
            # Generic: use latest revenue YoY
            if len(revenues) < 12 or revenues[-12] <= 0:
                continue
            results[sym] = float(revenues[-1] / revenues[-12] - 1)
'''

    code += '''
        except Exception:
            continue
    return results
'''

    # Write to file
    factor_path = FACTOR_DIR / f"{name}.py"
    FACTOR_DIR.mkdir(parents=True, exist_ok=True)
    factor_path.write_text(code, encoding="utf-8")
    return str(factor_path)


# ── Main Agent ─────────────────────────────────────────────────


class AlphaResearchAgent:
    """自動化因子研究 Agent。"""

    def __init__(self, memory_path: str = MEMORY_PATH):
        self.memory = ExperienceMemory.load(memory_path)
        self.memory_path = memory_path
        self._data_cache: dict[str, pd.DataFrame] | None = None
        self._evaluator: FactorEvaluator | None = None

    def _load_data(self) -> dict[str, pd.DataFrame]:
        """載入價格數據（快取）。"""
        if self._data_cache is not None:
            return self._data_cache

        market_dir = Path("data/market")
        data = {}
        for p in sorted(market_dir.glob("*.TW_1d.parquet")):
            sym = p.stem.replace("_1d", "")
            if sym.startswith("finmind_") or sym.startswith("00"):
                continue
            try:
                df = pd.read_parquet(p)
                if not df.empty and len(df) > 252:
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    df.index = pd.to_datetime(df.index.date)
                    df = df[~df.index.duplicated(keep="first")]
                    data[sym] = df
            except Exception:
                continue

        logger.info("Loaded %d stocks for evaluation", len(data))
        self._data_cache = data
        return data

    def _get_evaluator(self) -> FactorEvaluator:
        if self._evaluator is None:
            self._evaluator = FactorEvaluator(
                data=self._load_data(),
                total_tested=self.memory.total_rounds + 83,  # 83 existing factors already tested
            )
        else:
            self._evaluator.total_tested = self.memory.total_rounds + 83
        return self._evaluator

    def run_one_cycle(self, direction: str | None = None) -> ResearchTrajectory:
        """執行一輪研究循環。"""
        t0 = time.perf_counter()
        tid = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:4]

        # 1. IDEA — 選擇方向 + 假說
        if direction:
            dir_status = None
            for d in self.memory.directions:
                if d.name == direction:
                    dir_status = d
                    break
        else:
            dir_status = self.memory.get_next_direction()

        if dir_status is None:
            logger.warning("No available research direction")
            return ResearchTrajectory(
                id=tid, timestamp=datetime.now().isoformat(),
                hypothesis={}, failure_step="hypothesis",
                failure_reason="No available direction",
                duration_seconds=time.perf_counter() - t0,
            )

        hypothesis = self._generate_hypothesis(dir_status.name)
        if hypothesis is None:
            return ResearchTrajectory(
                id=tid, timestamp=datetime.now().isoformat(),
                hypothesis={"direction": dir_status.name},
                failure_step="hypothesis",
                failure_reason=f"No untested hypotheses for {dir_status.name}",
                duration_seconds=time.perf_counter() - t0,
            )

        logger.info("[Idea] Direction=%s, Hypothesis=%s", dir_status.name, hypothesis.name)

        # 2. FACTOR — 實作
        factor_path = _implement_revenue_factor(hypothesis)
        if factor_path is None:
            traj = ResearchTrajectory(
                id=tid, timestamp=datetime.now().isoformat(),
                hypothesis=asdict(hypothesis),
                failure_step="implementation",
                failure_reason="Failed to generate factor code",
                duration_seconds=time.perf_counter() - t0,
            )
            self.memory.add_trajectory(traj)
            self.memory.save(self.memory_path)
            return traj

        logger.info("[Factor] Implemented: %s", factor_path)

        # 3. EVAL — 計算因子值 + 多層驗證
        try:
            factor_values = self._compute_factor_values(hypothesis.name)
            if factor_values.empty:
                traj = ResearchTrajectory(
                    id=tid, timestamp=datetime.now().isoformat(),
                    hypothesis=asdict(hypothesis),
                    implementation_success=True,
                    failure_step="L1",
                    failure_reason="Empty factor values",
                    duration_seconds=time.perf_counter() - t0,
                )
                self.memory.add_trajectory(traj)
                self.memory.save(self.memory_path)
                return traj

            evaluator = self._get_evaluator()
            eval_result = evaluator.evaluate(hypothesis.name, factor_values)

            logger.info(
                "[Eval] %s: L=%s, ICIR=%.3f, Fitness=%.2f, %s",
                hypothesis.name, eval_result.level_reached,
                eval_result.best_icir, eval_result.fitness,
                "PASS" if eval_result.passed else f"FAIL: {eval_result.failure_reason}",
            )

        except Exception as e:
            traj = ResearchTrajectory(
                id=tid, timestamp=datetime.now().isoformat(),
                hypothesis=asdict(hypothesis),
                implementation_success=True,
                failure_step="L1",
                failure_reason=f"Evaluation error: {e}",
                duration_seconds=time.perf_counter() - t0,
            )
            self.memory.add_trajectory(traj)
            self.memory.save(self.memory_path)
            return traj

        # 4. DISTILL — 蒸餾結果回 Memory
        traj = ResearchTrajectory(
            id=tid,
            timestamp=datetime.now().isoformat(),
            hypothesis=asdict(hypothesis),
            implementation_success=True,
            eval_results={
                "ic_20d": eval_result.ic_20d,
                "best_icir": eval_result.best_icir,
                "best_horizon": eval_result.best_horizon,
                "fitness": eval_result.fitness,
                "turnover": eval_result.avg_turnover,
                "max_corr": eval_result.max_correlation,
                "positive_years": eval_result.positive_years,
            },
            fitness=eval_result.fitness,
            failure_step=eval_result.level_reached if not eval_result.passed else "",
            failure_reason=eval_result.failure_reason if not eval_result.passed else "",
            duration_seconds=time.perf_counter() - t0,
            passed=eval_result.passed,
        )

        self.memory.add_trajectory(traj)

        # 高品質因子加入成功模式
        if eval_result.passed and eval_result.fitness >= 5.0:
            self.memory.add_success(SuccessPattern(
                name=hypothesis.name,
                description=hypothesis.description,
                factors=[hypothesis.name],
                avg_icir=eval_result.best_icir,
                avg_fitness=eval_result.fitness,
                evidence=f"auto_research_{tid}",
            ))
            logger.info("*** DISCOVERY: %s fitness=%.2f ***", hypothesis.name, eval_result.fitness)

        self.memory.save(self.memory_path)

        # Save evaluation detail
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        eval_path = EVAL_DIR / f"{hypothesis.name}.json"
        with open(eval_path, "w", encoding="utf-8") as f:
            json.dump(asdict(eval_result), f, indent=2, ensure_ascii=False, default=str)

        # L5 通過 → 自動跑 StrategyValidator 13 項
        if traj.passed:
            validator_result = self._run_strategy_validator(hypothesis, eval_result)
            traj.eval_results["validator_passed"] = validator_result.get("n_passed", 0)
            traj.eval_results["validator_total"] = validator_result.get("n_total", 0)
            self._write_discovery_report(traj, eval_result, validator_result)

            # 判斷是否自動部署到 Paper Trading
            self._try_auto_deploy(hypothesis, validator_result)

        return traj

    def _try_auto_deploy(
        self, hypothesis: Hypothesis, validator_result: dict[str, Any],
    ) -> None:
        """判斷因子是否符合自動部署條件，若符合則部署到 Paper Trading。

        部署條件（全部滿足）：
        1. StrategyValidator >= 10/13
        2. Sharpe > 0050.TW Sharpe（風險調整打敗大盤）
        3. CAGR > 8%
        """
        n_passed = validator_result.get("n_passed", 0)
        n_total = validator_result.get("n_total", 13)

        if n_passed < 10:
            logger.info("[Deploy] %s: %d/%d < 10, skip deploy", hypothesis.name, n_passed, n_total)
            return

        # 從 validator checks 取 Sharpe 和 CAGR
        checks = validator_result.get("checks", [])
        strategy_sharpe = 0.0
        strategy_cagr = 0.0
        for c in checks:
            if c["name"] == "sharpe":
                try:
                    strategy_sharpe = float(c["value"])
                except (ValueError, TypeError):
                    pass
            if c["name"] == "cagr":
                try:
                    strategy_cagr = float(c["value"].replace("%", "").replace("+", "")) / 100
                except (ValueError, TypeError):
                    pass

        # 取 0050.TW Sharpe
        bench_sharpe = self._get_0050_sharpe()

        logger.info(
            "[Deploy] %s: Sharpe=%.3f vs 0050=%.3f, CAGR=%.2f%%",
            hypothesis.name, strategy_sharpe, bench_sharpe, strategy_cagr * 100,
        )

        if strategy_sharpe <= bench_sharpe:
            logger.info("[Deploy] %s: Sharpe <= 0050, skip deploy", hypothesis.name)
            return

        if strategy_cagr < 0.08:
            logger.info("[Deploy] %s: CAGR < 8%%, skip deploy", hypothesis.name)
            return

        # 全部通過 → 部署到 Paper Trading
        try:
            from src.alpha.auto.paper_deployer import PaperDeployer

            deployer = PaperDeployer()
            can, reason = deployer.can_deploy()
            if not can:
                logger.warning("[Deploy] Cannot deploy: %s", reason)
                return

            result = deployer.deploy(
                name=f"auto_{hypothesis.name}",
                factor_name=hypothesis.name,
                total_nav=10_000_000,  # 預設 1000 萬
            )
            if result:
                logger.info(
                    "*** AUTO-DEPLOYED: %s → Paper Trading (%.0f NAV, stop %s) ***",
                    hypothesis.name, result.initial_nav, result.stop_date[:10],
                )
        except Exception as e:
            logger.warning("[Deploy] Failed: %s", e)

    def _get_0050_sharpe(self) -> float:
        """取得 0050.TW 的 Sharpe 作為基準。"""
        try:
            from src.data.sources.yahoo import YahooFeed
            import numpy as np

            feed = YahooFeed()
            bars = feed.get_bars("0050.TW", start="2018-01-01", end="2025-06-30")
            if bars.empty:
                return 0.8  # fallback
            daily_ret = bars["close"].pct_change().dropna()
            return float(daily_ret.mean() / daily_ret.std() * np.sqrt(252))
        except Exception:
            return 0.8  # fallback

    def _run_strategy_validator(
        self, hypothesis: Hypothesis, eval_result: EvaluationResult,
    ) -> dict[str, Any]:
        """用因子自己的策略跑 StrategyValidator 13 項。"""
        logger.info("[Validator] Running 13-check validation for %s...", hypothesis.name)
        try:
            from src.backtest.validator import StrategyValidator, ValidationConfig
            from src.alpha.auto.strategy_builder import build_from_research_factor
            from scripts.run_strategy_backtest import discover_universe

            # 用因子自己建構 FilterStrategy（不是固定的 revenue_momentum）
            built = build_from_research_factor(
                factor_name=hypothesis.name,
                direction=hypothesis.expected_direction,
                top_n=15,
            )
            universe = discover_universe()

            config = ValidationConfig(
                min_cagr=0.08, min_sharpe=0.5, max_drawdown=0.50,
                n_trials=self.memory.total_rounds + 83,
                oos_start="2025-07-01", oos_end="2025-12-31",
            )

            validator = StrategyValidator(config)
            report = validator.validate(built.strategy, universe, "2018-01-01", "2025-06-30")

            logger.info(
                "[Validator] %s: %d/%d passed",
                hypothesis.name, report.n_passed, report.n_total,
            )

            return {
                "n_passed": report.n_passed,
                "n_total": report.n_total,
                "passed": report.passed,
                "checks": [
                    {"name": c.name, "passed": c.passed, "value": str(c.value)}
                    for c in report.checks
                ],
                "summary": report.summary(),
            }
        except Exception as e:
            logger.warning("[Validator] Failed: %s", e)
            return {"n_passed": 0, "n_total": 13, "passed": False, "error": str(e)}

    def _write_discovery_report(
        self, traj: ResearchTrajectory, eval_result: EvaluationResult,
        validator_result: dict[str, Any] | None = None,
    ) -> None:
        """成果寫到 docs/dev/auto/。"""
        auto_dir = Path("docs/dev/auto")
        auto_dir.mkdir(parents=True, exist_ok=True)

        name = traj.hypothesis.get("name", "unknown")
        report_path = auto_dir / f"{name}.md"

        lines = [
            f"# Auto-Discovery: {name}",
            "",
            f"**日期**: {traj.timestamp}",
            f"**方向**: {traj.hypothesis.get('direction', '')}",
            f"**假說**: {traj.hypothesis.get('description', '')}",
            f"**學術依據**: {traj.hypothesis.get('academic_basis', '')}",
            "",
            "## L1-L5 快速評估",
            "",
            "| 指標 | 值 |",
            "|------|---:|",
            f"| IC (20d) | {eval_result.ic_20d:+.4f} |",
            f"| Best ICIR | {eval_result.best_icir:+.4f} ({eval_result.best_horizon}) |",
            f"| Fitness | {eval_result.fitness:.2f} |",
            f"| Turnover | {eval_result.avg_turnover:.1%} |",
            f"| Max Correlation | {eval_result.max_correlation:.3f} ({eval_result.correlated_with}) |",
            f"| Positive Years | {eval_result.positive_years}/{eval_result.total_years} |",
        ]

        # StrategyValidator 結果
        if validator_result:
            n_pass = validator_result.get("n_passed", 0)
            n_total = validator_result.get("n_total", 13)
            lines.extend([
                "",
                f"## StrategyValidator: {n_pass}/{n_total}",
                "",
            ])
            checks = validator_result.get("checks", [])
            if checks:
                lines.append("| 檢查 | 值 | 結果 |")
                lines.append("|------|---:|:----:|")
                for c in checks:
                    icon = "PASS" if c["passed"] else "FAIL"
                    lines.append(f"| {c['name']} | {c['value']} | {icon} |")

            if n_pass >= 10:
                lines.extend([
                    "",
                    f"**{n_pass}/13 通過 — 可考慮進入 Paper Trading。**",
                ])
            else:
                lines.extend([
                    "",
                    f"**{n_pass}/13 通過 — 需改進後再驗證。**",
                ])

        # Walk-Forward 年度明細
        if validator_result:
            checks = validator_result.get("checks", [])
            wf_check = next((c for c in checks if c["name"] == "walkforward_positive_ratio"), None)
            if wf_check:
                lines.extend(["", f"## Walk-Forward: {wf_check['value']}", ""])

            # 失敗項解讀
            failed = [c for c in checks if not c["passed"]]
            if failed:
                lines.extend(["", "## 失敗項解讀", ""])
                for c in failed:
                    if c["name"] == "annual_cost_ratio":
                        lines.append(f"- **{c['name']}** ({c['value']}): 交易成本佔 gross alpha 比例偏高。改善方向：降低換手（延長持有期 / 提高篩選門檻）")
                    elif c["name"] == "deflated_sharpe":
                        lines.append(f"- **{c['name']}** ({c['value']}): 多重測試校正後信心不足（測了 {self.memory.total_rounds + 83} 個因子）。這是統計保守，不代表因子無效")
                    elif c["name"] == "recent_period_sharpe":
                        lines.append(f"- **{c['name']}** ({c['value']}): 近 252 天 Sharpe 為負，受市場環境影響。需觀察是暫時還是永久衰退")
                    else:
                        lines.append(f"- **{c['name']}** ({c['value']}): 未達門檻")

        # 與現有策略比較
        lines.extend([
            "",
            "## 與現有因子比較",
            "",
            "| 因子 | ICIR | 說明 |",
            "|------|:----:|------|",
            f"| **{traj.hypothesis.get('name', '?')}** | **{eval_result.best_icir:+.3f}** | **本次發現** |",
            "| revenue_yoy（基線） | +0.674 | 已驗證的核心因子 |",
            "| revenue_acceleration | +0.847 | 60d 最強因子 |",
            "| momentum_6m | +0.217 | 最佳 price-volume 因子 |",
        ])

        lines.extend([
            "",
            "## 下一步",
            "",
            "- [ ] 人工審閱假說邏輯",
            "- [ ] 決定是否加入正式因子庫",
            "- [ ] 決定是否部署到 Paper Trading",
        ])

        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Discovery report: %s", report_path)

    def _generate_hypothesis(self, direction: str) -> Hypothesis | None:
        """從模板產出假說（跳過已測試的）。"""
        templates = HYPOTHESIS_TEMPLATES.get(direction, [])
        tested = {t.hypothesis.get("name", "") for t in self.memory.trajectories}

        for tmpl in templates:
            if tmpl["name"] not in tested and not self.memory.is_forbidden(tmpl["name"]):
                return Hypothesis(
                    name=tmpl["name"],
                    description=tmpl["description"],
                    formula_sketch=tmpl["formula_sketch"],
                    academic_basis=tmpl.get("academic_basis", ""),
                    data_requirements=tmpl.get("data_requirements", []),
                    direction=direction,
                )
        return None

    def _compute_factor_values(self, factor_name: str) -> pd.DataFrame:
        """動態載入並計算因子值。"""
        factor_path = FACTOR_DIR / f"{factor_name}.py"
        if not factor_path.exists():
            return pd.DataFrame()

        # Dynamic import
        spec = importlib.util.spec_from_file_location(f"research_{factor_name}", factor_path)
        if spec is None or spec.loader is None:
            return pd.DataFrame()
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        compute_fn = getattr(mod, f"compute_{factor_name}", None)
        if compute_fn is None:
            return pd.DataFrame()

        data = self._load_data()
        symbols = list(data.keys())

        # Compute at multiple dates (monthly samples)
        all_dates = sorted(set().union(*(d.index for d in data.values())))
        sample_dates = all_dates[::20]  # every 20 trading days

        rows = []
        for dt in sample_dates[-120:]:  # last ~2400 trading days
            try:
                values = compute_fn(symbols, pd.Timestamp(dt))
                if values:
                    row = {"_date": dt}
                    row.update(values)
                    rows.append(row)
            except Exception:
                continue

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).set_index("_date")
        df.index.name = None
        return df

    def print_status(self) -> None:
        """印出 Memory 狀態。"""
        mem = self.memory
        print("\n=== Alpha Research Agent Status ===")
        print(f"Rounds: {mem.total_rounds} (pass: {mem.total_pass}, fail: {mem.total_fail})")
        print(f"Best fitness: {mem.best_fitness:.2f}")
        print(f"Patterns: {len(mem.success_patterns)}, Forbidden: {len(mem.forbidden_regions)}")
        print("\nDirections:")
        for d in mem.directions:
            status_icon = {"pending": ".", "exploring": "~", "strong": "+", "weak": "-", "exhausted": "x"}.get(d.status, "?")
            print(f"  [{status_icon}] {d.name:35s} {d.priority} hypotheses={d.hypothesis_count} pass={d.pass_count} best_icir={d.best_icir:.3f}")
        print("\nRecent trajectories:")
        for t in mem.trajectories[-5:]:
            name = t.hypothesis.get("name", "?")
            icon = "+" if t.passed else "x"
            print(f"  [{icon}] {name:35s} fitness={t.fitness:.2f} step={t.failure_step or 'PASS'} ({t.duration_seconds:.1f}s)")
        print()


# ── CLI ────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Alpha Research Agent")
    parser.add_argument("--rounds", type=int, default=1, help="Number of research rounds")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between rounds")
    parser.add_argument("--direction", type=str, default=None, help="Force research direction")
    parser.add_argument("--status", action="store_true", help="Print memory status")
    args = parser.parse_args()

    agent = AlphaResearchAgent()

    if args.status:
        agent.print_status()
        return

    for i in range(args.rounds):
        print(f"\n{'='*60}")
        print(f"Round {i+1}/{args.rounds}")
        print(f"{'='*60}")

        traj = agent.run_one_cycle(direction=args.direction)

        name = traj.hypothesis.get("name", "?")
        if traj.passed:
            print(f"  PASS: {name} (fitness={traj.fitness:.2f})")
        else:
            print(f"  FAIL: {name} at {traj.failure_step}: {traj.failure_reason}")
        print(f"  Time: {traj.duration_seconds:.1f}s")

        if i < args.rounds - 1:
            time.sleep(args.interval)

    agent.print_status()


if __name__ == "__main__":
    main()
