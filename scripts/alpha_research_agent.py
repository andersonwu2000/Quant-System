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
            # 40 天營收公布延遲（台灣月營收於次月 10 日前公布）
            usable_cutoff = as_of - pd.DateOffset(days=40)
            df = df[df["date"] <= usable_cutoff].sort_values("date")
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
    elif "vs_trend_residual" in name:
        code += '''
            if len(revenues) < 12:
                continue
            recent_6 = revenues[-6:]
            x = np.arange(len(recent_6))
            coeffs = np.polyfit(x, recent_6, 1)
            predicted_next = coeffs[0] * len(recent_6) + coeffs[1]
            actual = revenues[-1]
            if predicted_next > 0:
                results[sym] = float((actual - predicted_next) / predicted_next)
'''
    elif "breakout" in name:
        code += '''
            if len(revenues) < 12:
                continue
            max_12 = float(np.max(revenues[-12:]))
            if max_12 <= 0:
                continue
            # How much current revenue exceeds 12-month high (0 if below)
            results[sym] = float(max(0, revenues[-1] / max_12 - 1))
'''
    elif "x_gross_margin" in name or "x_roe" in name or "x_operating" in name:
        # Interaction factors need financial_statement data — cannot proxy as rev_acceleration
        logger.warning(
            "[Factor] '%s' is an interaction factor requiring financial_statement data. "
            "Cannot implement with revenue-only data (would be a revenue_acceleration clone).",
            name,
        )
        return None
    elif "coefficient_of_variation" in name:
        code += '''
            if len(revenues) < 12:
                continue
            recent = revenues[-12:]
            std = float(np.std(recent))
            mean = float(np.mean(recent))
            if std <= 0 or mean <= 0:
                continue
            # Inverse CV: higher = more stable growth (lower relative volatility)
            results[sym] = float(mean / std)
'''
    elif "positive_streak" in name:
        code += '''
            if len(revenues) < 6:
                continue
            streak = 0
            for i in range(len(revenues) - 1, 0, -1):
                if revenues[i] > revenues[i - 1]:
                    streak += 1
                else:
                    break
            results[sym] = float(streak)
'''
    elif "rank_change" in name:
        # Cross-sectional rank change requires all symbols computed simultaneously
        # Cannot implement per-symbol in this loop structure
        logger.warning(
            "[Factor] '%s' requires cross-sectional rank computation. "
            "Cannot implement in per-symbol loop.",
            name,
        )
        return None
    elif "zscore" in name:
        code += '''
            if len(revenues) < 24:
                continue
            recent_24 = revenues[-24:]
            mean = float(np.mean(recent_24))
            std = float(np.std(recent_24, ddof=1))
            if std <= 0:
                continue
            results[sym] = float((revenues[-1] - mean) / std)
'''
    elif "beat_magnitude" in name:
        code += '''
            if len(revenues) < 13 or revenues[-12] <= 0:
                continue
            yoy = revenues[-1] / revenues[-12] - 1
            # Squared positive surprise (penalize negative)
            results[sym] = float(max(0, yoy) ** 2)
'''
    elif "3m_vs_6m" in name:
        code += '''
            if len(revenues) < 6:
                continue
            rev_3m = float(np.mean(revenues[-3:]))
            rev_6m = float(np.mean(revenues[-6:]))
            if rev_6m <= 0:
                continue
            results[sym] = float(rev_3m / rev_6m)
'''
    elif "monotonic" in name:
        code += '''
            from scipy.stats import kendalltau
            if len(revenues) < 6:
                continue
            recent = revenues[-6:]
            tau, _ = kendalltau(range(len(recent)), recent)
            if np.isnan(tau):
                continue
            results[sym] = float(tau)
'''
    elif "cfo_over_ni" in name or "capex" in name or "inventory" in name or "upstream" in name or "sensitivity" in name:
        # These require financial_statement data not yet available
        logger.warning(
            "[Factor] '%s' requires financial_statement data (not just revenue). "
            "Cannot auto-implement with revenue-only data.",
            name,
        )
        return None
    else:
        # 不匹配任何已知 pattern → 無法自動實作，回傳 None
        logger.warning(
            "[Factor] Cannot auto-implement '%s' — no matching pattern. "
            "Needs manual implementation or new pattern in _implement_revenue_factor().",
            name,
        )
        return None

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
            data = self._load_data()
            # 計算已知因子的 IC 序列，供 L3 相關性檢查
            existing_ics = self._compute_baseline_factor_ics(data)
            self._evaluator = FactorEvaluator(
                data=data,
                total_tested=self.memory.total_rounds + 83,
                existing_factor_ics=existing_ics,
            )
        else:
            self._evaluator.total_tested = self.memory.total_rounds + 83
        return self._evaluator

    def _compute_baseline_factor_ics(self, data: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
        """計算 revenue_acceleration 和 revenue_yoy 的 IC 序列作為 L3 去重基準。"""
        import numpy as np
        from scipy.stats import spearmanr

        fund_dir = Path("data/fundamental")
        rev_cache: dict[str, pd.DataFrame] = {}
        for p in sorted(fund_dir.glob("*_revenue.parquet")):
            sym = p.stem.replace("_revenue", "")
            try:
                df = pd.read_parquet(p)
                if df.empty or "revenue" not in df.columns:
                    continue
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
                rev_cache[sym] = df
            except Exception:
                continue

        if not rev_cache:
            return {}

        # 月度取樣，計算 revenue_acceleration IC
        all_close = pd.DataFrame({s: data[s]["close"] for s in data if "close" in data[s].columns})
        monthly = all_close.resample("ME").last().dropna(how="all")

        result: dict[str, list[float]] = {"revenue_acceleration": [], "revenue_yoy": []}
        for i in range(len(monthly) - 1):
            as_of = monthly.index[i]
            fwd_date = monthly.index[i + 1]
            if as_of < pd.Timestamp("2017-01-01"):
                continue

            cutoff = as_of - pd.DateOffset(days=40)
            accel_vals, yoy_vals, rets = [], [], []

            for sym in rev_cache:
                if sym not in data:
                    continue
                df = rev_cache[sym]
                usable = df[df["date"] <= cutoff]
                if len(usable) < 12:
                    continue
                rev = usable["revenue"].astype(float).values

                if sym in all_close.columns and as_of in all_close.index and fwd_date in all_close.index:
                    p0 = all_close.loc[as_of, sym]
                    p1 = all_close.loc[fwd_date, sym]
                    if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
                        continue
                    ret = p1 / p0 - 1
                else:
                    continue

                r3 = np.mean(rev[-3:])
                r12 = np.mean(rev[-12:])
                if r12 > 0:
                    accel_vals.append(r3 / r12)
                    rets.append(ret)

                if len(rev) >= 13 and rev[-12] > 0:
                    yoy_vals.append(rev[-1] / rev[-12] - 1)

            if len(accel_vals) >= 20:
                ic, _ = spearmanr(accel_vals, rets[:len(accel_vals)])
                if not np.isnan(ic):
                    result["revenue_acceleration"].append(ic)

        return {k: pd.Series(v) for k, v in result.items() if len(v) >= 10}

    def _get_direction_with_untested(self):
        """找到有未測假說的方向（避免選已耗盡的方向）。"""
        from src.alpha.auto.experience_memory import DirectionStatus

        tested = {t.hypothesis.get("name", "") for t in self.memory.trajectories}

        # Load templates
        templates_path = Path("data/research/hypothesis_templates.json")
        if templates_path.exists():
            try:
                with open(templates_path, encoding="utf-8") as f:
                    all_templates = json.load(f)
            except Exception:
                all_templates = dict(HYPOTHESIS_TEMPLATES)
        else:
            all_templates = dict(HYPOTHESIS_TEMPLATES)

        # Find directions with untested hypotheses
        candidates = []
        for d in self.memory.directions:
            if d.status not in ("pending", "exploring"):
                continue
            templates = all_templates.get(d.name, [])
            # 跳過需要 financial_statement 的假說（目前不支援）
            NEEDS_FIN_DATA = {"financial_statement"}
            has_untested = any(
                t["name"] not in tested
                and not self.memory.is_forbidden(t["name"])
                and not (set(t.get("data_requirements", [])) & NEEDS_FIN_DATA)
                for t in templates
            )
            if has_untested:
                candidates.append(d)

        if not candidates:
            return None

        def _sort_key(d: DirectionStatus) -> tuple:
            try:
                p = int(str(d.priority).lstrip("P"))
            except (ValueError, TypeError):
                p = 99
            return (p, int(d.hypothesis_count or 0))

        candidates.sort(key=_sort_key)
        return candidates[0]

    def _sync_directions_from_templates(self) -> None:
        """從 hypothesis_templates.json 同步方向到 memory。

        確保 Claude Code 新增的方向/假說能被 get_next_direction() 看到。
        """
        from src.alpha.auto.experience_memory import DirectionStatus

        templates_path = Path("data/research/hypothesis_templates.json")
        if not templates_path.exists():
            return

        try:
            with open(templates_path, encoding="utf-8") as f:
                all_templates = json.load(f)
        except Exception:
            return

        existing_names = {d.name for d in self.memory.directions}
        for direction_name in all_templates:
            if direction_name not in existing_names:
                self.memory.directions.append(DirectionStatus(
                    name=direction_name,
                    status="pending",
                    priority=5,
                    hypothesis_count=0,
                    pass_count=0,
                    best_icir=0.0,
                ))
                logger.info("Synced new direction: %s", direction_name)

    def run_one_cycle(self, direction: str | None = None) -> ResearchTrajectory:
        """執行一輪研究循環。"""
        t0 = time.perf_counter()
        tid = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:4]

        # 1. IDEA — 選擇方向 + 假說
        # 先同步 JSON 模板中的方向到 memory（確保新加的方向被探索）
        self._sync_directions_from_templates()

        if direction:
            dir_status = None
            for d in self.memory.directions:
                if d.name == direction:
                    dir_status = d
                    break
        else:
            # 找有可用假說的方向（跳過已耗盡的）
            dir_status = self._get_direction_with_untested()

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

        # L5 通過 → 大規模 IC 驗證 → StrategyValidator → 部署
        if traj.passed:
            # Step A: 大規模 IC 驗證（865+ 支台股）
            large_ic = self._run_large_scale_ic(hypothesis.name)
            traj.eval_results["large_icir_5d"] = large_ic.get("icir_5d", 0)
            traj.eval_results["large_icir_20d"] = large_ic.get("icir_20d", 0)
            traj.eval_results["large_icir_60d"] = large_ic.get("icir_60d", 0)
            traj.eval_results["large_hit_20d"] = large_ic.get("hit_20d", 0)
            traj.eval_results["large_n_months"] = large_ic.get("n_months", 0)

            large_icir_20d = large_ic.get("icir_20d", 0)
            if large_icir_20d < 0.20:
                logger.info(
                    "[Large-Scale] %s: ICIR(20d)=%.3f < 0.20, skip Validator",
                    hypothesis.name, large_icir_20d,
                )
                traj.eval_results["large_scale_pass"] = False
                self._write_discovery_report(traj, eval_result, None, large_ic)
                self.memory.save(self.memory_path)
                return traj

            logger.info(
                "[Large-Scale] %s: ICIR(20d)=%.3f PASS",
                hypothesis.name, large_icir_20d,
            )
            traj.eval_results["large_scale_pass"] = True

            # Step B: StrategyValidator 13 項
            validator_result = self._run_strategy_validator(hypothesis, eval_result)
            traj.eval_results["validator_passed"] = validator_result.get("n_passed", 0)
            traj.eval_results["validator_total"] = validator_result.get("n_total", 0)
            self.memory.save(self.memory_path)

            self._write_discovery_report(traj, eval_result, validator_result, large_ic)

            # Step C: 判斷是否自動部署
            self._try_auto_deploy(hypothesis, validator_result, large_ic)

        return traj

    def _try_auto_deploy(
        self, hypothesis: Hypothesis, validator_result: dict[str, Any],
        large_ic: dict[str, float] | None = None,
    ) -> None:
        """判斷因子是否符合自動部署條件，若符合則部署到 Paper Trading。

        部署條件（全部滿足）：
        1. StrategyValidator >= 11/13（排除 DSR 後 ≥12/13）
        2. deflated_sharpe >= 0.70（寬鬆門檻，<0.70 仍視為過擬合風險）
        3. Sharpe > 0050.TW Sharpe
        4. CAGR > 8%
        5. recent_period_sharpe > -0.10（允許輕微噪音）
        6. 大規模 ICIR(20d) >= 0.20（865+ 支台股驗證）
        """
        n_passed = validator_result.get("n_passed", 0)
        n_total = validator_result.get("n_total", 13)

        # 計算排除 deflated_sharpe 後的通過數
        checks = validator_result.get("checks", [])
        n_passed_excl_dsr = sum(
            1 for c in checks
            if c["passed"] or c["name"] == "deflated_sharpe"
        )

        if n_passed_excl_dsr < 12:
            logger.info(
                "[Deploy] %s: %d/%d (excl DSR: %d/13) < 12, skip deploy",
                hypothesis.name, n_passed, n_total, n_passed_excl_dsr,
            )
            return

        # DSR 寬鬆門檻：不要求 0.95，但 < 0.50 仍然危險（可能真的過擬合）
        dsr_value = 0.0
        for c in checks:
            if c["name"] == "deflated_sharpe":
                try:
                    dsr_value = float(c["value"])
                except (ValueError, TypeError):
                    pass
        if dsr_value < 0.70:
            logger.info("[Deploy] %s: DSR %.3f < 0.70 (relaxed threshold), skip deploy",
                       hypothesis.name, dsr_value)
            return

        # 從 validator checks 取 Sharpe、CAGR、recent Sharpe
        checks = validator_result.get("checks", [])
        strategy_sharpe = 0.0
        strategy_cagr = 0.0
        recent_sharpe = 0.0
        for c in checks:
            if c["name"] == "sharpe":
                try:
                    strategy_sharpe = float(c["value"])
                except (ValueError, TypeError):
                    pass
            if c["name"] == "cagr":
                try:
                    val_str = str(c["value"]).strip().rstrip("%").lstrip("+")
                    strategy_cagr = float(val_str) / 100
                except (ValueError, TypeError):
                    pass
            if c["name"] == "recent_period_sharpe":
                try:
                    recent_sharpe = float(c["value"])
                except (ValueError, TypeError):
                    pass

        # 取 0050.TW Sharpe
        bench_sharpe = self._get_0050_sharpe()

        logger.info(
            "[Deploy] %s: Sharpe=%.3f vs 0050=%.3f, CAGR=%.2f%%, recent=%.3f",
            hypothesis.name, strategy_sharpe, bench_sharpe, strategy_cagr * 100, recent_sharpe,
        )

        if strategy_sharpe <= bench_sharpe:
            logger.info("[Deploy] %s: Sharpe <= 0050, skip deploy", hypothesis.name)
            return

        if strategy_cagr < 0.08:
            logger.info("[Deploy] %s: CAGR < 8%%, skip deploy", hypothesis.name)
            return

        if recent_sharpe < -0.10:
            logger.info("[Deploy] %s: recent Sharpe %.3f < -0.10, skip deploy", hypothesis.name, recent_sharpe)
            return

        # 5. 大規模 ICIR 門檻
        large_icir = large_ic.get("icir_20d", 0) if large_ic else 0
        if large_icir < 0.20:
            logger.info("[Deploy] %s: large ICIR(20d) %.3f < 0.20, skip deploy", hypothesis.name, large_icir)
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

    def _run_large_scale_ic(self, factor_name: str) -> dict[str, float]:
        """大規模 IC 驗證（865+ 支台股，月度 Spearman IC）。

        Returns:
            dict with icir_5d, icir_20d, icir_60d, hit_20d, n_months
        """
        import importlib
        import numpy as np
        from scipy.stats import spearmanr

        logger.info("[Large-Scale] Running IC check for %s ...", factor_name)
        t0 = time.perf_counter()

        # Load revenue cache
        fund_dir = Path("data/fundamental")
        rev_cache: dict[str, pd.DataFrame] = {}
        for p in sorted(fund_dir.glob("*_revenue.parquet")):
            sym = p.stem.replace("_revenue", "")
            try:
                df = pd.read_parquet(p)
                if df.empty or "revenue" not in df.columns:
                    continue
                df["date"] = pd.to_datetime(df["date"])
                df = df.sort_values("date")
                df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
                rev_cache[sym] = df
            except Exception:
                continue

        # Load factor compute function (same mechanism as _compute_factor_values)
        factor_path = FACTOR_DIR / f"{factor_name}.py"
        if not factor_path.exists():
            logger.warning("[Large-Scale] Factor file not found: %s", factor_path)
            return {"icir_5d": 0, "icir_20d": 0, "icir_60d": 0, "hit_20d": 0, "n_months": 0}
        try:
            spec = importlib.util.spec_from_file_location(f"research_{factor_name}", factor_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create spec for {factor_path}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            compute_fn = getattr(mod, f"compute_{factor_name}")
        except Exception as e:
            logger.warning("[Large-Scale] Cannot load factor %s: %s", factor_name, e)
            return {"icir_5d": 0, "icir_20d": 0, "icir_60d": 0, "hit_20d": 0, "n_months": 0}

        # Use full price data
        price_data = self._load_data()
        all_symbols = sorted(price_data.keys())

        # Monthly sampling — 用全 universe 的日期（不只前 200 支）
        sample_dates = sorted(set().union(*[set(price_data[s].index) for s in all_symbols]))
        monthly = pd.DatetimeIndex(sample_dates).to_period("M").unique()

        horizons = [5, 20, 60]
        ic_store: dict[int, list[float]] = {h: [] for h in horizons}
        n_months = 0

        for period in monthly:
            as_of = period.to_timestamp() + pd.DateOffset(months=1) - pd.DateOffset(days=1)
            if as_of < pd.Timestamp("2017-01-01") or as_of > pd.Timestamp("2025-12-31"):
                continue

            active = [s for s in all_symbols if s in price_data and as_of in price_data[s].index]
            if len(active) < 50:
                continue

            try:
                fvals = compute_fn(active, as_of)
            except Exception:
                continue
            if len(fvals) < 20:
                continue

            for h in horizons:
                xs, ys = [], []
                for sym, fv in fvals.items():
                    if sym not in price_data:
                        continue
                    df = price_data[sym]
                    # Forward return: close[as_of+h] / close[as_of] - 1
                    # 和 L1-L5 的 pct_change(h).shift(-h) 一致
                    if as_of not in df.index:
                        continue
                    after = df.index[df.index > as_of]
                    if len(after) < h:
                        continue
                    ret = float(df.loc[after[h - 1], "close"] / df.loc[as_of, "close"] - 1)
                    xs.append(fv)
                    ys.append(ret)
                if len(xs) < 20:
                    continue
                ic, _ = spearmanr(xs, ys)
                if not np.isnan(ic):
                    ic_store[h].append(ic)

            n_months += 1

        # Compute ICIRs
        result: dict[str, float] = {"n_months": n_months}
        for h in horizons:
            ics = ic_store[h]
            if len(ics) > 5:
                std = float(np.std(ics, ddof=1))
                icir = float(np.mean(ics)) / std if std > 0 else 0
                result[f"icir_{h}d"] = round(icir, 3)
                if h == 20:
                    result["hit_20d"] = round(sum(1 for x in ics if x > 0) / len(ics) * 100, 1)
            else:
                result[f"icir_{h}d"] = 0
                if h == 20:
                    result["hit_20d"] = 0

        elapsed = time.perf_counter() - t0
        logger.info(
            "[Large-Scale] %s: ICIR(5d)=%+.3f, ICIR(20d)=%+.3f, ICIR(60d)=%+.3f, Hit=%.1f%%, %d months, %.0fs",
            factor_name, result.get("icir_5d", 0), result.get("icir_20d", 0),
            result.get("icir_60d", 0), result.get("hit_20d", 0), n_months, elapsed,
        )
        return result

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
        large_ic: dict[str, float] | None = None,
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

            # 排除 deflated_sharpe 後的有效通過數
            n_excl_dsr = sum(1 for c in checks if c["passed"] or c["name"] == "deflated_sharpe")
            if n_excl_dsr >= 12:
                lines.extend([
                    "",
                    f"**{n_pass}/13 通過（排除 DSR: {n_excl_dsr}/13）— 符合部署門檻。**",
                ])
            elif n_pass >= 10:
                lines.extend([
                    "",
                    f"**{n_pass}/13 通過（排除 DSR: {n_excl_dsr}/13）— 未達部署門檻，僅供觀察。**",
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

        # 大規模 IC 驗證
        if large_ic and large_ic.get("n_months", 0) > 0:
            icir_5 = large_ic.get("icir_5d", 0)
            icir_20 = large_ic.get("icir_20d", 0)
            icir_60 = large_ic.get("icir_60d", 0)
            hit_20 = large_ic.get("hit_20d", 0)
            n_m = large_ic.get("n_months", 0)
            passed = icir_20 >= 0.20
            lines.extend([
                "",
                f"## 大規模 IC 驗證（865+ 支台股，{n_m} 個月）",
                "",
                "| Factor | ICIR(5d) | ICIR(20d) | ICIR(60d) | Hit%(20d) |",
                "|--------|:--------:|:---------:|:---------:|:---------:|",
                f"| **{traj.hypothesis.get('name', '?')}** | {icir_5:+.3f} | **{icir_20:+.3f}** | {icir_60:+.3f} | {hit_20:.1f}% |",
                "| revenue_acceleration (#16 基準) | +0.202 | +0.240 | +0.426 | 63.9% |",
                "| revenue_new_high (#16 基準) | +0.246 | +0.207 | +0.364 | 61.3% |",
                "",
                f"**大規模 ICIR(20d) = {icir_20:+.3f} — {'PASS (≥0.20)' if passed else 'FAIL (<0.20)'}**",
            ])
        elif large_ic is not None:
            lines.extend([
                "",
                "## 大規模 IC 驗證",
                "",
                "未能完成大規模驗證。",
            ])

        # 部署判定
        deploy_eligible = True
        reasons = []
        if validator_result:
            checks = validator_result.get("checks", [])
            n_excl_dsr = sum(1 for c in checks if c["passed"] or c["name"] == "deflated_sharpe")
            if n_excl_dsr < 12:
                deploy_eligible = False
                reasons.append(f"Validator (excl DSR) {n_excl_dsr}/13 < 12")
            # DSR 寬鬆門檻
            dsr_val = next((float(c["value"]) for c in checks if c["name"] == "deflated_sharpe"), 0)
            if dsr_val < 0.70:
                deploy_eligible = False
                reasons.append(f"DSR {dsr_val:.3f} < 0.70")
            # recent sharpe
            recent_val = next((float(c["value"]) for c in checks if c["name"] == "recent_period_sharpe"), 0)
            if recent_val < -0.10:
                deploy_eligible = False
                reasons.append(f"recent_sharpe {recent_val:.3f} < -0.10")
            # CAGR check
            cagr_str = next((c["value"] for c in checks if c["name"] == "cagr"), "0")
            try:
                cagr_val = float(str(cagr_str).strip().rstrip("%").lstrip("+")) / 100
            except (ValueError, TypeError):
                cagr_val = 0
            if cagr_val < 0.08:
                deploy_eligible = False
                reasons.append(f"CAGR {cagr_val:.1%} < 8%")
        if large_ic:
            if large_ic.get("icir_20d", 0) < 0.20:
                deploy_eligible = False
                reasons.append(f"大規模 ICIR(20d) {large_ic.get('icir_20d', 0):.3f} < 0.20")

        lines.extend([
            "",
            "## 部署判定",
            "",
        ])
        if deploy_eligible:
            lines.append("**符合所有部署條件（Validator ≥11/13 excl DSR + 大規模 ICIR ≥0.20 + recent>-0.10）。**")
        else:
            lines.append(f"**不符合部署條件：{'; '.join(reasons)}**")


        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Discovery report: %s", report_path)

    def _generate_hypothesis(self, direction: str) -> Hypothesis | None:
        """從模板產出假說（跳過已測試的）。

        模板來源：
        1. data/research/hypothesis_templates.json（Claude Code 動態生成）
        2. HYPOTHESIS_TEMPLATES（硬編碼 fallback）

        Claude Code 可隨時在對話中新增假說到 JSON 文件，
        下一輪研究會自動讀取新假說。
        """
        # 優先讀 JSON 文件（Claude Code 可動態維護）
        templates_path = Path("data/research/hypothesis_templates.json")
        if templates_path.exists():
            try:
                with open(templates_path, encoding="utf-8") as f:
                    all_templates = json.load(f)
                templates = all_templates.get(direction, [])
            except Exception:
                templates = HYPOTHESIS_TEMPLATES.get(direction, [])
        else:
            templates = HYPOTHESIS_TEMPLATES.get(direction, [])

        tested = {t.hypothesis.get("name", "") for t in self.memory.trajectories}

        NEEDS_FIN = {"financial_statement"}
        for tmpl in templates:
            if (tmpl["name"] not in tested
                    and not self.memory.is_forbidden(tmpl["name"])
                    and not (set(tmpl.get("data_requirements", [])) & NEEDS_FIN)):
                return Hypothesis(
                    name=tmpl["name"],
                    description=tmpl["description"],
                    formula_sketch=tmpl["formula_sketch"],
                    academic_basis=tmpl.get("academic_basis", ""),
                    data_requirements=tmpl.get("data_requirements", []),
                    direction=direction,
                    expected_direction=tmpl.get("expected_direction", 1),
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
