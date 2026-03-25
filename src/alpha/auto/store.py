"""AlphaStore — JSON file persistence for research snapshots and alerts."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.alpha.auto.config import AlphaAlert, FactorScore, ResearchSnapshot
from src.alpha.regime import MarketRegime

logger = logging.getLogger(__name__)

_MAX_SNAPSHOTS = 365


def _serialize_snapshot(snap: ResearchSnapshot) -> dict[str, Any]:
    """Convert ResearchSnapshot to JSON-safe dict."""
    d = asdict(snap)
    # date → ISO string, MarketRegime → value
    if isinstance(d.get("date"), date):
        d["date"] = d["date"].isoformat()
    if isinstance(d.get("regime"), MarketRegime):
        d["regime"] = d["regime"].value
    elif hasattr(d.get("regime"), "value"):
        d["regime"] = d["regime"].value
    return d


def _deserialize_snapshot(d: dict[str, Any]) -> ResearchSnapshot:
    """Convert dict back to ResearchSnapshot."""
    # Reconstruct FactorScore objects
    factor_scores: dict[str, FactorScore] = {}
    for k, v in d.get("factor_scores", {}).items():
        if isinstance(v, dict):
            factor_scores[k] = FactorScore(**v)
        else:
            factor_scores[k] = v
    d["factor_scores"] = factor_scores

    # Convert date string back to date object
    if isinstance(d.get("date"), str):
        d["date"] = date.fromisoformat(d["date"])

    # Convert regime string back to MarketRegime enum
    regime_val = d.get("regime")
    if isinstance(regime_val, str):
        try:
            d["regime"] = MarketRegime(regime_val)
        except ValueError:
            d["regime"] = MarketRegime.SIDEWAYS

    return ResearchSnapshot(**d)


def _serialize_alert(alert: AlphaAlert) -> dict[str, Any]:
    """Convert AlphaAlert to JSON-safe dict."""
    d = asdict(alert)
    if isinstance(d.get("timestamp"), datetime):
        d["timestamp"] = d["timestamp"].isoformat()
    return d


def _deserialize_alert(d: dict[str, Any]) -> AlphaAlert:
    """Convert dict back to AlphaAlert."""
    ts = d.get("timestamp")
    if isinstance(ts, str):
        d["timestamp"] = datetime.fromisoformat(ts)
    return AlphaAlert(**d)


class AlphaStore:
    """Simple JSON file store for auto-alpha snapshots and alerts.

    Data is stored as a single JSON object with two arrays:
    ``{"snapshots": [...], "alerts": [...]}``.

    Uses atomic writes (write to temp then rename) for safety.
    """

    def __init__(self, db_path: str = "data/auto_alpha.json") -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal I/O
    # ------------------------------------------------------------------

    def _read_db(self) -> dict[str, list[Any]]:
        """Read the entire JSON file. Returns empty structure if missing."""
        if not self._path.exists():
            return {"snapshots": [], "alerts": []}
        try:
            text = self._path.read_text(encoding="utf-8")
            if not text.strip():
                return {"snapshots": [], "alerts": []}
            return dict(json.loads(text))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read alpha store at %s: %s", self._path, exc)
            return {"snapshots": [], "alerts": []}

    def _write_db(self, data: dict[str, list[Any]]) -> None:
        """Atomic write: write to temp file then rename."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._path.parent),
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # On Windows, target must not exist for rename
            if self._path.exists():
                self._path.unlink()
            os.rename(tmp_path, str(self._path))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    def save_snapshot(self, snapshot: ResearchSnapshot) -> None:
        """Append snapshot to store, keeping at most 365 entries."""
        db = self._read_db()
        db["snapshots"].append(_serialize_snapshot(snapshot))
        # Trim to max entries (keep most recent)
        if len(db["snapshots"]) > _MAX_SNAPSHOTS:
            db["snapshots"] = db["snapshots"][-_MAX_SNAPSHOTS:]
        self._write_db(db)

    def get_snapshot(self, target_date: str) -> ResearchSnapshot | None:
        """Lookup snapshot by date string (ISO format, e.g. '2026-03-26')."""
        db = self._read_db()
        for raw in db["snapshots"]:
            snap_date = raw.get("date", "")
            if isinstance(snap_date, str) and snap_date == target_date:
                return _deserialize_snapshot(dict(raw))
            # Also handle date objects that were serialized
            if hasattr(snap_date, "isoformat") and snap_date.isoformat() == target_date:
                return _deserialize_snapshot(dict(raw))
        return None

    def list_snapshots(self, limit: int = 30) -> list[ResearchSnapshot]:
        """Return most-recent-first snapshots, up to *limit*."""
        db = self._read_db()
        raw_list = db["snapshots"]
        # Most recent last in storage → reverse for output
        recent = list(reversed(raw_list))[:limit]
        return [_deserialize_snapshot(dict(r)) for r in recent]

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def save_alert(self, alert: AlphaAlert) -> None:
        """Append alert to store."""
        db = self._read_db()
        db["alerts"].append(_serialize_alert(alert))
        self._write_db(db)

    def list_alerts(self, limit: int = 50) -> list[AlphaAlert]:
        """Return most-recent-first alerts, up to *limit*."""
        db = self._read_db()
        raw_list = db["alerts"]
        recent = list(reversed(raw_list))[:limit]
        return [_deserialize_alert(dict(r)) for r in recent]

    # ------------------------------------------------------------------
    # Performance summary
    # ------------------------------------------------------------------

    def get_performance_summary(self) -> dict[str, Any]:
        """Compute aggregate performance metrics from stored snapshots.

        Returns dict with keys: total_days, win_rate, cumulative_return,
        max_drawdown, avg_daily_pnl, best_day, worst_day.
        """
        snapshots = self.list_snapshots(limit=_MAX_SNAPSHOTS)
        pnl_values: list[float] = []
        for snap in snapshots:
            if snap.daily_pnl is not None:
                pnl_values.append(snap.daily_pnl)

        if not pnl_values:
            return {
                "total_days": 0,
                "win_rate": 0.0,
                "cumulative_return": 0.0,
                "max_drawdown": 0.0,
                "avg_daily_pnl": 0.0,
                "best_day": 0.0,
                "worst_day": 0.0,
            }

        total_days = len(pnl_values)
        wins = sum(1 for p in pnl_values if p > 0)
        win_rate = wins / total_days if total_days > 0 else 0.0

        cumulative_return = sum(pnl_values)

        # Max drawdown from cumulative PnL curve
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for pnl in pnl_values:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        return {
            "total_days": total_days,
            "win_rate": win_rate,
            "cumulative_return": cumulative_return,
            "max_drawdown": max_dd,
            "avg_daily_pnl": cumulative_return / total_days,
            "best_day": max(pnl_values),
            "worst_day": min(pnl_values),
        }
