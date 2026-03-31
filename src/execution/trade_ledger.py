"""Trade ledger — append-only record of all trade intents and fills.

Two log types:
  1. Intent log: written BEFORE order submission (what we plan to do)
  2. Fill log: written AFTER trade execution (what actually happened)

On crash recovery, the ledger is replayed to reconstruct the correct
portfolio state. The append-only design ensures no data loss.

Storage: data/paper_trading/ledger/ (one JSON-lines file per day)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)

LEDGER_DIR = Path("data/paper_trading/ledger")


class DecimalEncoder(json.JSONEncoder):
    def default(self, o: object) -> object:
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def log_intent(
    symbol: str,
    side: str,
    quantity: int | float,
    expected_price: float,
    strategy: str = "",
    run_id: str = "",
) -> None:
    """Write intent BEFORE order submission.

    If crash occurs after intent but before fill, recovery knows
    an order was attempted and can query broker for status.
    """
    entry = {
        "type": "intent",
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "side": side,
        "quantity": float(quantity),
        "expected_price": expected_price,
        "strategy": strategy,
        "run_id": run_id,
    }
    _append(entry)


def log_fill(
    symbol: str,
    side: str,
    quantity: int | float,
    fill_price: float,
    commission: float = 0.0,
    run_id: str = "",
) -> None:
    """Write fill AFTER trade execution.

    This is the authoritative record. Portfolio state must reflect
    all fills in the ledger.
    """
    entry = {
        "type": "fill",
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "side": side,
        "quantity": float(quantity),
        "fill_price": fill_price,
        "commission": commission,
        "run_id": run_id,
    }
    _append(entry)


def get_today_entries() -> list[dict]:
    """Read today's ledger entries."""
    path = _today_path()
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def get_unmatched_intents() -> list[dict]:
    """Find intents without corresponding fills (potential incomplete trades).

    Used during crash recovery to detect orders that may have been
    submitted to broker but not confirmed in our system.
    """
    entries = get_today_entries()
    intents: dict[str, dict] = {}  # key: symbol+side+run_id
    fills: set[str] = set()

    for e in entries:
        key = f"{e.get('symbol')}:{e.get('side')}:{e.get('run_id', '')}"
        if e["type"] == "intent":
            intents[key] = e
        elif e["type"] == "fill":
            fills.add(key)

    return [v for k, v in intents.items() if k not in fills]


def get_fills_since(portfolio_as_of: str) -> list[dict]:
    """Get all fills after a given timestamp.

    Used to replay fills that occurred after the last portfolio save.
    """
    entries = get_today_entries()
    result = []
    for e in entries:
        if e["type"] == "fill" and e.get("timestamp", "") > portfolio_as_of:
            result.append(e)
    return result


def _today_path() -> Path:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    return LEDGER_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"


def _append(entry: dict) -> None:
    """Append one JSON line to today's ledger. Atomic (single write)."""
    path = _today_path()
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, cls=DecimalEncoder, ensure_ascii=False) + "\n")
    except Exception:
        logger.error("Failed to write ledger entry: %s", entry)
