"""Deployed Strategy Executor — Phase AG Step 3.

Reads deploy_queue/ markers (written by watchdog), builds strategies,
generates weights, records paper trades with independent NAV tracking.
Does NOT submit real orders — avoids conflict with main trading pipeline.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.alpha.auto.paper_deployer import PaperDeployer

logger = logging.getLogger(__name__)

DEPLOY_QUEUE_DIR = Path("docker/autoresearch/watchdog_data/deploy_queue")
PAPER_TRADE_DIR = Path("data/paper_trading/auto")


def process_deploy_queue(deployer: PaperDeployer) -> list[str]:
    """Process pending deploy markers from watchdog. Returns list of deployed names."""
    if not DEPLOY_QUEUE_DIR.exists():
        return []

    deployed_names = []
    for marker_path in sorted(DEPLOY_QUEUE_DIR.glob("*.json")):
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            factor_code = marker["factor_code"]
            code_hash = marker.get("code_hash", "unknown")
            ts = marker.get("timestamp", "unknown")

            # Save factor code to research factors dir
            factor_name = f"auto_{ts}"
            factor_dir = Path("src/strategy/factors/research")
            factor_dir.mkdir(parents=True, exist_ok=True)
            factor_path = factor_dir / f"{factor_name}.py"
            factor_path.write_text(factor_code, encoding="utf-8")

            # Deploy via PaperDeployer
            can, reason = deployer.can_deploy()
            if not can:
                logger.warning("Cannot deploy %s: %s", factor_name, reason)
                marker_path.unlink()
                continue

            result = deployer.deploy(
                name=f"auto_{factor_name}",
                factor_name=factor_name,
                total_nav=10_000_000,
            )
            if result:
                deployed_names.append(result.name)
                logger.info("Deployed from queue: %s (hash=%s)", result.name, code_hash)

            # Remove processed marker
            marker_path.unlink()

        except Exception as e:
            logger.warning("Deploy queue processing failed for %s: %s", marker_path.name, e)
            # Move to failed/
            failed_dir = DEPLOY_QUEUE_DIR / "failed"
            failed_dir.mkdir(exist_ok=True)
            marker_path.rename(failed_dir / marker_path.name)

    return deployed_names


def execute_deployed_strategies(deployer: PaperDeployer) -> dict[str, dict]:
    """Generate weights and record paper trades for all active deployed strategies.

    Returns {strategy_name: {weights: dict, nav: float, status: str}}.
    """
    active = deployer.get_active()
    if not active:
        return {}

    results = {}
    for strategy_info in active:
        try:
            weights, nav = _execute_single(strategy_info)
            deployer.update_nav(strategy_info.name, nav)
            _record_paper_trade(strategy_info.name, weights, nav)
            results[strategy_info.name] = {
                "weights": weights,
                "nav": nav,
                "status": "ok",
                "n_positions": len(weights),
            }
        except Exception as e:
            logger.warning("Execution failed for %s: %s", strategy_info.name, e)
            results[strategy_info.name] = {"status": "error", "error": str(e)}

    return results


def _execute_single(strategy_info) -> tuple[dict[str, float], float]:
    """Generate weights for a single deployed strategy. Returns (weights, new_nav)."""
    from src.alpha.auto.strategy_builder import build_from_research_factor

    built = build_from_research_factor(
        factor_name=strategy_info.factor_name,
        top_n=15,
    )

    # Load market data
    market_dir = Path("data/market")
    universe = []
    bars_dict = {}
    for p in sorted(market_dir.glob("*_1d.parquet"))[:200]:
        sym = p.stem.replace("_1d", "")
        if sym.startswith("00"):
            continue
        try:
            df = pd.read_parquet(p)
            if len(df) >= 500:
                universe.append(sym)
                bars_dict[sym] = df
        except Exception:
            pass

    if len(universe) < 50:
        raise ValueError(f"Insufficient universe: {len(universe)} < 50")

    # Generate factor values
    import importlib.util
    factor_path = Path("src/strategy/factors/research") / f"{strategy_info.factor_name}.py"
    spec = importlib.util.spec_from_file_location(strategy_info.factor_name, factor_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load factor: {factor_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    compute_fn = getattr(mod, "compute_factor", None)
    if compute_fn is None:
        raise ValueError(f"No compute_factor in {factor_path}")

    as_of = pd.Timestamp(datetime.now().strftime("%Y-%m-%d"))
    data = {"bars": bars_dict}
    factor_values = compute_fn(universe, as_of, data)

    if not factor_values or len(factor_values) < 10:
        raise ValueError(f"Factor returned {len(factor_values or {})} values (need 10+)")

    # Top 15 equal weight
    sorted_factors = sorted(factor_values.items(), key=lambda x: -x[1])[:15]
    weights = {sym: 1 / 15 * 0.95 for sym, _ in sorted_factors}

    # Calculate NAV change (simple: use latest daily returns of held positions)
    if strategy_info.current_nav > 0:
        portfolio_return = 0.0
        for sym, w in weights.items():
            if sym in bars_dict and len(bars_dict[sym]) >= 2:
                last_two = bars_dict[sym]["close"].iloc[-2:]
                daily_ret = last_two.iloc[-1] / last_two.iloc[-2] - 1
                portfolio_return += w * daily_ret
        new_nav = strategy_info.current_nav * (1 + portfolio_return)
    else:
        new_nav = strategy_info.initial_nav

    return weights, new_nav


def _record_paper_trade(name: str, weights: dict[str, float], nav: float) -> None:
    """Save paper trade record to data/paper_trading/auto/{name}/."""
    trade_dir = PAPER_TRADE_DIR / name
    trade_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    record = {
        "date": today,
        "weights": weights,
        "nav": nav,
        "n_positions": len(weights),
    }
    record_path = trade_dir / f"{today}.json"
    record_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")


def generate_comparison_report(
    deployer: PaperDeployer,
    benchmark_name: str = "revenue_momentum_hedged",
) -> str | None:
    """Generate comparison report: deployed strategies vs benchmark (Phase AG Step 5).

    Returns report path or None if nothing to compare.
    """
    active = deployer.get_active()
    all_strategies = deployer._deployed
    if not all_strategies:
        return None

    report_dir = Path("docs/research/autoresearch/comparison")
    report_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    lines = [
        f"# Auto-Alpha Comparison Report",
        f"",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> Benchmark: {benchmark_name}",
        f"",
        f"## Deployed Strategies",
        f"",
        f"| Name | Status | Days | P&L | NAV | Peak |",
        f"|------|--------|------|-----|-----|------|",
    ]

    for d in all_strategies:
        days = len(d.daily_navs)
        pnl = (d.current_nav / d.initial_nav - 1) * 100 if d.initial_nav > 0 else 0
        lines.append(
            f"| {d.name} | {d.status} | {days} | {pnl:+.1f}% | {d.current_nav:,.0f} | {d.peak_nav:,.0f} |"
        )

    lines.extend([
        f"",
        f"## Decision",
        f"",
        f"| Condition | Check |",
        f"|-----------|-------|",
    ])

    for d in all_strategies:
        if d.status != "active":
            continue
        days = len(d.daily_navs)
        pnl = (d.current_nav / d.initial_nav - 1) * 100 if d.initial_nav > 0 else 0
        mdd = (d.peak_nav - d.current_nav) / d.peak_nav * 100 if d.peak_nav > 0 else 0

        if pnl < -10 or mdd > 15:
            lines.append(f"| {d.name}: crash (P&L={pnl:+.1f}%, MDD={mdd:.1f}%) | STOP |")
        elif days < 30:
            lines.append(f"| {d.name}: {days} days (< 30 sanity check) | CONTINUE |")
        elif days < 90:
            lines.append(f"| {d.name}: {days} days (< 90 for decision) | CONTINUE |")
        else:
            lines.append(f"| {d.name}: {days} days, P&L={pnl:+.1f}% | REVIEW for promotion |")

    report_path = report_dir / f"{today}_comparison.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return str(report_path)
