"""Daily reconciliation — compare paper trading outcome vs backtest expectation.

Answers: "Did the portfolio do what the backtest predicted?"

Compares:
  1. Target weights (strategy output) vs actual weights (post-trade)
  2. Expected daily return (from price data) vs actual NAV change
  3. Execution cost (expected slippage vs actual shortfall)

Data sources:
  - data/paper_trading/selections/{date}.json — target weights
  - data/paper_trading/snapshots/{date}.json — actual portfolio
  - data/paper_trading/trades/{run_id}.json — execution details
  - data/paper_trading/pipeline_runs/{run_id}.json — run metadata
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

PAPER_DIR = Path("data/paper_trading")


@dataclass
class DailyReconciliation:
    """Result of one day's reconciliation."""
    date: str
    # Weight comparison
    target_weights: dict[str, float] = field(default_factory=dict)
    actual_weights: dict[str, float] = field(default_factory=dict)
    weight_drift_bps: float = 0.0  # mean absolute weight difference in bps
    missing_symbols: list[str] = field(default_factory=list)  # in target but not in portfolio
    extra_symbols: list[str] = field(default_factory=list)    # in portfolio but not in target

    # Return comparison
    nav_start: float = 0.0
    nav_end: float = 0.0
    actual_return_bps: float = 0.0
    expected_return_bps: float = 0.0  # from price change of held symbols
    return_diff_bps: float = 0.0

    # Execution quality
    n_trades: int = 0
    avg_shortfall_bps: float = 0.0
    total_commission: float = 0.0

    # Status
    status: str = "ok"  # "ok", "drift", "error"
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"[{self.date}] {self.status.upper()}"]
        parts.append(f"return: actual={self.actual_return_bps:+.1f}bps expected={self.expected_return_bps:+.1f}bps diff={self.return_diff_bps:+.1f}bps")
        parts.append(f"drift={self.weight_drift_bps:.1f}bps")
        if self.n_trades > 0:
            parts.append(f"trades={self.n_trades} shortfall={self.avg_shortfall_bps:.1f}bps")
        if self.warnings:
            parts.append(f"warnings={len(self.warnings)}")
        return " | ".join(parts)


def reconcile_date(
    trade_date: str,
    prev_date: str | None = None,
) -> DailyReconciliation:
    """Run reconciliation for a single trading day.

    Args:
        trade_date: Date string "YYYY-MM-DD"
        prev_date: Previous trading day (for NAV comparison). Auto-detected if None.
    """
    result = DailyReconciliation(date=trade_date)

    # ── Load snapshot (actual portfolio) ─────────────────────────────
    snapshot_path = PAPER_DIR / "snapshots" / f"{trade_date}.json"
    if not snapshot_path.exists():
        result.status = "error"
        result.warnings.append(f"No snapshot for {trade_date}")
        return result

    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception as e:
        result.status = "error"
        result.warnings.append(f"Bad snapshot: {e}")
        return result

    result.nav_end = float(snapshot.get("nav", 0))
    positions = snapshot.get("positions", {})

    # Calculate actual weights from snapshot
    if result.nav_end > 0 and positions:
        for sym, pos in positions.items():
            qty = float(pos.get("qty", 0))
            price = float(pos.get("price", 0))
            if qty > 0 and price > 0:
                result.actual_weights[sym] = (qty * price) / result.nav_end

    # ── Load target weights (selection) ──────────────────────────────
    selection_path = PAPER_DIR / "selections" / f"{trade_date}.json"
    if selection_path.exists():
        try:
            sel = json.loads(selection_path.read_text(encoding="utf-8"))
            result.target_weights = sel.get("weights", {})
        except Exception:
            pass

    # ── Weight drift ─────────────────────────────────────────────────
    if result.target_weights and result.actual_weights:
        all_syms = set(result.target_weights) | set(result.actual_weights)
        diffs = []
        for sym in all_syms:
            target = result.target_weights.get(sym, 0.0)
            actual = result.actual_weights.get(sym, 0.0)
            diffs.append(abs(target - actual))

        result.weight_drift_bps = sum(diffs) / len(diffs) * 10000 if diffs else 0.0
        result.missing_symbols = [s for s in result.target_weights if s not in result.actual_weights]
        result.extra_symbols = [s for s in result.actual_weights if s not in result.target_weights]

    # ── Previous day NAV for return calc ─────────────────────────────
    if prev_date is None:
        prev_date = _find_prev_snapshot(trade_date)

    if prev_date:
        prev_path = PAPER_DIR / "snapshots" / f"{prev_date}.json"
        if prev_path.exists():
            try:
                prev_snap = json.loads(prev_path.read_text(encoding="utf-8"))
                result.nav_start = float(prev_snap.get("nav", 0))
            except Exception:
                pass

    if result.nav_start > 0 and result.nav_end > 0:
        result.actual_return_bps = (result.nav_end / result.nav_start - 1) * 10000

    # ── Expected return from price changes ───────────────────────────
    if result.nav_start > 0 and prev_date and positions:
        result.expected_return_bps = _calc_expected_return(prev_date, trade_date, positions)
        result.return_diff_bps = result.actual_return_bps - result.expected_return_bps

    # ── Execution quality ────────────────────────────────────────────
    _load_trade_stats(result, trade_date)

    # ── Status ───────────────────────────────────────────────────────
    if abs(result.return_diff_bps) > 50:
        result.status = "drift"
        result.warnings.append(f"Return diff {result.return_diff_bps:+.1f}bps exceeds 50bps threshold")
    if result.weight_drift_bps > 200:
        result.warnings.append(f"Weight drift {result.weight_drift_bps:.0f}bps is high")

    return result


def _find_prev_snapshot(trade_date: str) -> str | None:
    """Find the most recent snapshot before trade_date."""
    snapshots_dir = PAPER_DIR / "snapshots"
    if not snapshots_dir.exists():
        return None

    dates = sorted(
        p.stem for p in snapshots_dir.glob("*.json")
        if p.stem < trade_date
    )
    return dates[-1] if dates else None


def _calc_expected_return(prev_date: str, trade_date: str, positions: dict) -> float:
    """Calculate expected return from price changes of held positions.

    Uses actual market prices from DataCatalog. This is what the backtest
    would have predicted given the same positions.
    """
    try:
        from src.data.data_catalog import get_catalog

        catalog = get_catalog()
        total_start_value = 0.0
        total_pnl = 0.0

        for sym, pos in positions.items():
            qty = float(pos.get("qty", 0))
            if qty <= 0:
                continue

            df = catalog.get("price", sym,
                           start=date.fromisoformat(prev_date),
                           end=date.fromisoformat(trade_date))
            if df.empty or "close" not in df.columns or len(df) < 2:
                continue

            prev_close = df["close"].iloc[-2] if len(df) >= 2 else df["close"].iloc[0]
            curr_close = df["close"].iloc[-1]

            position_value = qty * prev_close
            total_start_value += position_value
            total_pnl += qty * (curr_close - prev_close)

        if total_start_value > 0:
            return (total_pnl / total_start_value) * 10000
    except Exception as e:
        logger.debug("Expected return calc failed: %s", e)

    return 0.0


def _load_trade_stats(result: DailyReconciliation, trade_date: str) -> None:
    """Load execution stats from trade logs."""
    trades_dir = PAPER_DIR / "trades"
    if not trades_dir.exists():
        return

    for p in trades_dir.glob(f"{trade_date}*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            result.n_trades = data.get("n_trades", 0)
            result.avg_shortfall_bps = float(data.get("avg_shortfall_bps", 0))
            result.total_commission = float(data.get("total_commission", 0))
            break  # use first matching trade file
        except Exception:
            continue


def reconcile_all() -> list[DailyReconciliation]:
    """Run reconciliation for all available trading days."""
    snapshots_dir = PAPER_DIR / "snapshots"
    if not snapshots_dir.exists():
        return []

    dates = sorted(p.stem for p in snapshots_dir.glob("*.json"))
    results = []
    for i, d in enumerate(dates):
        prev = dates[i - 1] if i > 0 else None
        r = reconcile_date(d, prev)
        results.append(r)

    return results


def save_reconciliation(result: DailyReconciliation) -> Path:
    """Save reconciliation result to JSON."""
    out_dir = PAPER_DIR / "reconciliation"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.date}.json"

    data = {
        "date": result.date,
        "status": result.status,
        "nav_start": result.nav_start,
        "nav_end": result.nav_end,
        "actual_return_bps": round(result.actual_return_bps, 2),
        "expected_return_bps": round(result.expected_return_bps, 2),
        "return_diff_bps": round(result.return_diff_bps, 2),
        "weight_drift_bps": round(result.weight_drift_bps, 2),
        "n_trades": result.n_trades,
        "avg_shortfall_bps": round(result.avg_shortfall_bps, 2),
        "total_commission": round(result.total_commission, 2),
        "target_weights": {k: round(v, 4) for k, v in result.target_weights.items()},
        "actual_weights": {k: round(v, 4) for k, v in result.actual_weights.items()},
        "missing_symbols": result.missing_symbols,
        "extra_symbols": result.extra_symbols,
        "warnings": result.warnings,
    }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
