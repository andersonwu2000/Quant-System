"""Reconciliation functions — extracted from jobs.py.

Covers:
- _reconcile: compare strategy targets vs actual positions
- update_portfolio_market_prices: refresh market prices from DataCatalog
- execute_backtest_reconcile: EOD backtest vs paper comparison
- execute_daily_reconcile: EOD broker reconciliation
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.config import TradingConfig
    from src.core.models import Portfolio

from src.scheduler.pipeline.records import _today_run_id

logger = logging.getLogger(__name__)


def _reconcile(
    target_weights: dict[str, float],
    portfolio: "Portfolio",
    threshold: float = 0.02,
) -> list[dict[str, Any]]:
    """T3: 比對策略目標 vs 實際持倉，回傳偏差 > threshold 的股票。"""
    deviations: list[dict[str, Any]] = []
    all_symbols = set(target_weights.keys()) | set(portfolio.positions.keys())
    for sym in all_symbols:
        target_w = target_weights.get(sym, 0.0)
        actual_w = float(portfolio.get_position_weight(sym))
        diff = abs(target_w - actual_w)
        if diff > threshold:
            deviations.append({
                "symbol": sym,
                "target": round(target_w, 4),
                "actual": round(actual_w, 4),
                "deviation": round(diff, 4),
            })
    deviations.sort(key=lambda d: d["deviation"], reverse=True)

    # 存檔（含 run_id）
    recon_dir = Path("data/paper_trading/reconciliation")
    recon_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    recon_record = {
        "date": today,
        "run_id": _today_run_id(),  # P3: 關聯
        "n_deviations": len(deviations),
        "deviations": deviations,
    }
    path = recon_dir / f"{today}.json"
    path.write_text(json.dumps(recon_record, indent=2, ensure_ascii=False), encoding="utf-8")

    return deviations


async def update_portfolio_market_prices() -> None:
    """Update portfolio positions' market_price from latest data.

    Paper trading NAV is frozen between rebalances because market_price = fill_price.
    This function reads latest close from parquet and updates market_price,
    enabling correct daily_drawdown / kill_switch calculation.
    """
    from src.api.state import get_app_state, save_portfolio
    from src.data.data_catalog import get_catalog

    state = get_app_state()
    if not state.portfolio.positions:
        return

    catalog = get_catalog()
    updated = 0

    for sym, pos in state.portfolio.positions.items():
        try:
            df = catalog.get("price", sym)
            if not df.empty and "close" in df.columns:
                latest_close = Decimal(str(float(df["close"].iloc[-1])))
                if latest_close > 0:
                    pos.market_price = latest_close
                    updated += 1
        except Exception:
            # data-quality: individual symbol price lookup failure
            logger.debug("Price update failed for %s", sym, exc_info=True)
            continue

    if updated > 0:
        state.portfolio.nav_sod = state.portfolio.nav
        save_portfolio(state.portfolio)
        logger.info("Portfolio prices updated: %d/%d positions, NAV=%s",
                    updated, len(state.portfolio.positions), state.portfolio.nav)


async def execute_backtest_reconcile() -> dict[str, Any]:
    """EOD: compare paper trading vs backtest expectation.

    Runs after market close. Compares today's actual NAV change
    against what the portfolio's holdings should have returned.
    Alerts on drift > 50bps.
    """
    from src.reconciliation.daily import reconcile_date, save_reconciliation

    today = datetime.now().strftime("%Y-%m-%d")

    try:
        result = reconcile_date(today)
        save_reconciliation(result)
        logger.info("Backtest reconcile: %s", result.summary())

        if result.status == "drift":
            from src.core.config import get_config
            from src.notifications.factory import create_notifier
            config = get_config()
            notifier = create_notifier(config)
            if notifier.is_configured():
                await notifier.send(
                    "Backtest Reconcile DRIFT",
                    result.summary() + "\n" + "\n".join(result.warnings),
                )

        return {
            "status": result.status,
            "return_diff_bps": round(result.return_diff_bps, 2),
            "weight_drift_bps": round(result.weight_drift_bps, 2),
        }
    except Exception as exc:
        logger.exception("Backtest reconcile failed")
        return {"status": "error", "error": str(exc)}


async def execute_daily_reconcile(config: "TradingConfig") -> dict[str, Any]:
    """收盤後自動對帳：比對系統持倉與券商端持倉。

    只在 paper/live mode 且 broker 已初始化時執行。
    如有差異，透過通知系統（Discord/LINE/Telegram）告警。
    """
    from src.api.state import get_app_state
    from src.execution.reconcile import reconcile
    from src.notifications.factory import create_notifier

    state = get_app_state()
    notifier = create_notifier(config)

    # Broker reconciliation 只在 live mode 有意義：
    # - paper mode：系統有模擬持倉，券商帳戶空的（或有手動部位），比對必定不一致
    # - live mode：系統下真單，券商持倉應與系統一致，差異才是真正的告警
    if not config.enable_reconciliation:
        logger.debug("Daily reconcile skipped: mode=%s (only runs in live)", config.mode)
        return {"status": "skipped", "reason": "not live mode"}

    # Update market prices before reconcile (fixes frozen NAV / kill switch)
    await update_portfolio_market_prices()

    exec_svc = state.execution_service
    if not exec_svc.is_initialized or exec_svc.broker is None:
        logger.warning("Daily reconcile skipped: broker not initialized")
        return {"status": "skipped", "reason": "broker not initialized"}

    try:
        broker_positions = exec_svc.broker.query_positions()
        result = reconcile(state.portfolio, broker_positions)

        summary = result.summary()
        logger.info("Daily reconcile completed:\n%s", summary)

        status = "clean" if result.is_clean else "discrepancy"
        try:
            from src.metrics import RECONCILE_RUNS, RECONCILE_MISMATCHES
            RECONCILE_RUNS.labels(status=status).inc()
            RECONCILE_MISMATCHES.set(len(result.mismatched))
        except Exception:
            # expected: prometheus metrics not available
            logger.debug("Suppressed exception", exc_info=True)

        if not result.is_clean and notifier.is_configured():
            await notifier.send(
                "Reconciliation Discrepancy",
                f"{len(result.mismatched)} mismatched, "
                f"{len(result.system_only)} system-only, "
                f"{len(result.broker_only)} broker-only positions.\n\n"
                + summary,
            )

        return {
            "status": status,
            "matched": len(result.matched),
            "mismatched": len(result.mismatched),
            "system_only": len(result.system_only),
            "broker_only": len(result.broker_only),
        }
    except Exception as exc:
        logger.exception("Daily reconcile failed")
        try:
            from src.metrics import RECONCILE_RUNS
            RECONCILE_RUNS.labels(status="error").inc()
        except Exception:
            # expected: prometheus metrics not available
            logger.debug("Suppressed exception", exc_info=True)
        if notifier.is_configured():
            try:
                await notifier.send(
                    "Reconcile Error",
                    f"Daily reconciliation failed.\n"
                    f"Error: {type(exc).__name__}: {exc}\n"
                    f"Mode: {config.mode}\n"
                    f"Positions: {len(state.portfolio.positions)}",
                )
            except Exception:
                # expected: external API failure (notification service)
                logger.debug("Suppressed exception", exc_info=True)
        return {"status": "error"}
