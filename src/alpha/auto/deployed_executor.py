"""Deployed Strategy Executor — Phase AG Step 3.

Reads deploy_queue/ markers (written by watchdog), builds strategies,
generates weights daily, records paper trades with independent NAV tracking.
Does NOT submit real orders — avoids conflict with main trading pipeline.

Daily execution:
- process_deploy_queue(): pick up new factors from watchdog
- execute_deployed_strategies(): generate weights, track NAV, enforce kill switch
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

            # Use actual portfolio NAV (not hardcoded 10M) for realistic allocation
            from src.api.state import get_app_state
            _state = get_app_state()
            _total_nav = float(_state.portfolio.nav) if _state.portfolio.nav > 0 else 10_000_000
            result = deployer.deploy(
                name=f"auto_{factor_name}",
                factor_name=factor_name,
                total_nav=_total_nav,
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
    """Generate weights and track NAV for all active deployed strategies.

    Called daily. Each strategy:
    - Rebalances monthly (first execution of month)
    - NAV tracked daily using last weights + daily returns
    - Kill switch: MDD > 3% → auto stop
    - Expiry: 30 days → auto stop

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
            logger.info("Deployed %s: NAV=%.0f, %d positions",
                        strategy_info.name, nav, len(weights))
        except Exception as e:
            logger.warning("Execution failed for %s: %s", strategy_info.name, e)
            results[strategy_info.name] = {"status": "error", "error": str(e)}

    return results


def _load_last_trade(name: str) -> dict | None:
    """Load the most recent paper trade record for a strategy."""
    trade_dir = PAPER_TRADE_DIR / name
    if not trade_dir.exists():
        return None
    records = sorted(trade_dir.glob("*.json"))
    if not records:
        return None
    try:
        return json.loads(records[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def _should_rebalance(name: str) -> bool:
    """Check if strategy should rebalance (first trading day of month)."""
    last = _load_last_trade(name)
    if last is None:
        return True  # first execution
    last_date = last.get("date", "")
    today = datetime.now().strftime("%Y-%m")
    last_month = last_date[:7] if len(last_date) >= 7 else ""
    return today != last_month


def _load_data_for_universe(universe: list[str]) -> dict:
    """Load full data dict via DataCatalog (consistent with evaluate.py)."""
    from src.data.data_catalog import get_catalog
    catalog = get_catalog()

    bars: dict[str, pd.DataFrame] = {}
    revenue: dict[str, pd.DataFrame] = {}
    institutional: dict[str, pd.DataFrame] = {}
    per_history: dict[str, pd.DataFrame] = {}
    margin_data: dict[str, pd.DataFrame] = {}

    for sym in universe:
        # Price bars
        df = catalog.get("price", sym)
        if not df.empty and "close" in df.columns:
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)
            df.index = pd.to_datetime(df.index.date)
            df = df[~df.index.duplicated(keep="first")]
            bars[sym] = df

        # Revenue
        df = catalog.get("revenue", sym)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            revenue[sym] = df.sort_values("date")

        # Institutional
        try:
            df = catalog.get("institutional", sym)
            if not df.empty and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                institutional[sym] = df.sort_values("date")
        except Exception:
            pass

        # PER history
        try:
            df = catalog.get("per", sym)
            if not df.empty and "PER" in df.columns and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                per_history[sym] = df.sort_values("date")
        except Exception:
            pass

        # Margin
        try:
            df = catalog.get("margin", sym)
            if not df.empty and "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                margin_data[sym] = df.sort_values("date")
        except Exception:
            pass

    return {
        "bars": bars,
        "revenue": revenue,
        "institutional": institutional,
        "per_history": per_history,
        "margin": margin_data,
        "pe": {}, "pb": {}, "roe": {},
    }


def _execute_single(strategy_info) -> tuple[dict[str, float], float]:
    """Generate weights and compute NAV for a single deployed strategy.

    Monthly rebalance: recalculate weights on first execution of each month.
    Daily NAV: use last weights + daily returns between executions.
    """
    import importlib.util

    today = datetime.now().strftime("%Y-%m-%d")
    rebalance = _should_rebalance(strategy_info.name)
    last_trade = _load_last_trade(strategy_info.name)

    # Load universe from DataCatalog
    from src.data.data_catalog import get_catalog
    catalog = get_catalog()
    all_syms = catalog.available_symbols("price")
    # Filter: .TW only, no ETFs (00xx), limit 200
    universe = sorted(
        s for s in all_syms
        if ".TW" in s and not s.replace(".TW", "").startswith("00")
    )[:200]

    if len(universe) < 50:
        raise ValueError(f"Insufficient universe: {len(universe)} < 50")

    # Load data
    data = _load_data_for_universe(universe)
    bars = data["bars"]

    if rebalance:
        # ── Rebalance: compute new weights ──
        factor_path = Path("src/strategy/factors/research") / f"{strategy_info.factor_name}.py"
        spec = importlib.util.spec_from_file_location(strategy_info.factor_name, factor_path)
        if spec is None or spec.loader is None:
            raise ValueError(f"Cannot load factor: {factor_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        compute_fn = getattr(mod, "compute_factor", None)
        if compute_fn is None:
            raise ValueError(f"No compute_factor in {factor_path}")

        as_of = pd.Timestamp(today)

        # Liquidity filter (match strategy_builder: 300 lots = 300,000 shares)
        eligible = []
        for sym in universe:
            if sym not in bars:
                continue
            b = bars[sym]
            if len(b) >= 20 and "volume" in b.columns:
                avg_vol = float(b["volume"].iloc[-20:].mean())
                if avg_vol >= 300_000:
                    eligible.append(sym)

        if len(eligible) < 20:
            raise ValueError(f"Too few eligible symbols: {len(eligible)} < 20")

        # Mask data to as_of (prevent look-ahead)
        masked = {
            "bars": {s: bars[s].loc[:as_of] for s in eligible if s in bars},
            "revenue": {
                s: df[df["date"] <= as_of - pd.DateOffset(days=40)]
                for s, df in data["revenue"].items() if s in eligible
            },
            "institutional": {
                s: df[df["date"] <= as_of]
                for s, df in data["institutional"].items() if s in eligible
            },
            "per_history": {
                s: df[df["date"] <= as_of]
                for s, df in data["per_history"].items() if s in eligible
            },
            "margin": {
                s: df[df["date"] <= as_of]
                for s, df in data["margin"].items() if s in eligible
            },
            "pe": {}, "pb": {}, "roe": {},
        }

        factor_values = compute_fn(eligible, as_of, masked)

        if not factor_values or len(factor_values) < 10:
            raise ValueError(f"Factor returned {len(factor_values or {})} values (need 10+)")

        # Top 15 equal weight, 95% invested, max 10% per stock
        sorted_factors = sorted(factor_values.items(), key=lambda x: -x[1])[:15]
        n = len(sorted_factors)
        w = min(0.95 / n, 0.10)
        weights = {sym: w for sym, _ in sorted_factors}
    else:
        # ── No rebalance: use last weights ──
        weights = last_trade.get("weights", {}) if last_trade else {}

    # ── Calculate NAV ──
    if strategy_info.current_nav > 0 and last_trade:
        last_date_str = last_trade.get("date", "")
        last_weights = last_trade.get("weights", {})

        if last_date_str and last_weights:
            # Compute cumulative return since last trade date
            portfolio_return = 0.0
            for sym, w in last_weights.items():
                if sym in bars and len(bars[sym]) >= 2:
                    b = bars[sym]
                    # Get close on last_date and today
                    try:
                        after = b.loc[pd.Timestamp(last_date_str):]
                        if len(after) >= 2:
                            ret = after["close"].iloc[-1] / after["close"].iloc[0] - 1
                            portfolio_return += w * float(ret)
                    except (KeyError, IndexError):
                        pass
            new_nav = strategy_info.current_nav * (1 + portfolio_return)
        else:
            new_nav = strategy_info.current_nav
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
    all_strategies = deployer._deployed
    if not all_strategies:
        return None

    report_dir = Path("docs/research/autoresearch/comparison")
    report_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    lines = [
        "# Auto-Alpha Comparison Report",
        "",
        f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> Benchmark: {benchmark_name}",
        "",
        "## Deployed Strategies",
        "",
        "| Name | Status | Days | P&L | NAV | Peak |",
        "|------|--------|------|-----|-----|------|",
    ]

    for d in all_strategies:
        days = len(d.daily_navs)
        pnl = (d.current_nav / d.initial_nav - 1) * 100 if d.initial_nav > 0 else 0
        lines.append(
            f"| {d.name} | {d.status} | {days} | {pnl:+.1f}% | {d.current_nav:,.0f} | {d.peak_nav:,.0f} |"
        )

    lines.extend([
        "",
        "## Decision",
        "",
        "| Condition | Check |",
        "|-----------|-------|",
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
