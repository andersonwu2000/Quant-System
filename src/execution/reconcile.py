"""
EOD 持倉對帳 — 比對券商端持倉與系統 Portfolio。

用於 Paper/Live Trading，確保系統持倉與券商端一致。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from src.core.models import Portfolio

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PositionDiff:
    """單一標的的持倉差異。"""
    symbol: str
    system_qty: Decimal
    broker_qty: Decimal
    diff_qty: Decimal         # broker - system
    system_cost: Decimal
    broker_cost: Decimal

    @property
    def is_matched(self) -> bool:
        return self.diff_qty == 0

    @property
    def diff_pct(self) -> float:
        """差異佔系統持倉的百分比。"""
        if self.system_qty == 0:
            return float("inf") if self.broker_qty != 0 else 0.0
        return float(abs(self.diff_qty) / abs(self.system_qty))


@dataclass
class ReconcileResult:
    """對帳結果。"""
    timestamp: datetime
    matched: list[PositionDiff] = field(default_factory=list)
    mismatched: list[PositionDiff] = field(default_factory=list)
    system_only: list[PositionDiff] = field(default_factory=list)    # 系統有但券商無
    broker_only: list[PositionDiff] = field(default_factory=list)    # 券商有但系統無

    @property
    def is_clean(self) -> bool:
        """完全一致。"""
        return (
            len(self.mismatched) == 0
            and len(self.system_only) == 0
            and len(self.broker_only) == 0
        )

    @property
    def total_positions(self) -> int:
        return (
            len(self.matched)
            + len(self.mismatched)
            + len(self.system_only)
            + len(self.broker_only)
        )

    def summary(self) -> str:
        """產生對帳摘要。"""
        lines = [
            f"=== Reconciliation Report ({self.timestamp.strftime('%Y-%m-%d %H:%M')}) ===",
            f"Status: {'CLEAN' if self.is_clean else 'DISCREPANCY FOUND'}",
            f"Matched: {len(self.matched)} | Mismatched: {len(self.mismatched)} | "
            f"System-only: {len(self.system_only)} | Broker-only: {len(self.broker_only)}",
        ]

        if self.mismatched:
            lines.append("\n--- Mismatched Positions ---")
            for d in self.mismatched:
                lines.append(
                    f"  {d.symbol}: system={d.system_qty} vs broker={d.broker_qty} "
                    f"(diff={d.diff_qty}, {d.diff_pct:.1%})"
                )

        if self.system_only:
            lines.append("\n--- System Only (not in broker) ---")
            for d in self.system_only:
                lines.append(f"  {d.symbol}: qty={d.system_qty}")

        if self.broker_only:
            lines.append("\n--- Broker Only (not in system) ---")
            for d in self.broker_only:
                lines.append(f"  {d.symbol}: qty={d.broker_qty}")

        return "\n".join(lines)


def reconcile(
    portfolio: Portfolio,
    broker_positions: dict[str, dict[str, Any]],
    tolerance: Decimal = Decimal("0"),
) -> ReconcileResult:
    """比對系統持倉與券商端持倉。

    Args:
        portfolio: 系統端的投資組合。
        broker_positions: 券商端持倉，格式 {symbol: {quantity, avg_cost, ...}}。
        tolerance: 數量容差（考慮零股誤差）。

    Returns:
        ReconcileResult 對帳結果。
    """
    result = ReconcileResult(timestamp=datetime.now(timezone.utc))

    # Normalize broker symbols to match system format.
    # If system uses ".TW" suffix but broker uses bare ids, add suffix.
    # If both use the same format, no change needed.
    system_has_suffix = any(s.endswith((".TW", ".TWO")) for s in portfolio.positions)
    broker_has_suffix = any(s.endswith((".TW", ".TWO")) for s in broker_positions)

    normalized_broker: dict[str, dict[str, Any]]
    if system_has_suffix and not broker_has_suffix:
        normalized_broker = {f"{s}.TW": p for s, p in broker_positions.items()}
    elif not system_has_suffix and broker_has_suffix:
        normalized_broker = {s.replace(".TW", "").replace(".TWO", ""): p for s, p in broker_positions.items()}
    else:
        normalized_broker = broker_positions

    system_symbols = set(portfolio.positions.keys())
    broker_symbols = set(normalized_broker.keys())
    all_symbols = system_symbols | broker_symbols

    for symbol in sorted(all_symbols):
        sys_pos = portfolio.positions.get(symbol)
        brk_pos = normalized_broker.get(symbol)

        sys_qty = sys_pos.quantity if sys_pos else Decimal("0")
        sys_cost = sys_pos.avg_cost if sys_pos else Decimal("0")
        brk_qty = Decimal(str(brk_pos.get("quantity", 0))) if brk_pos else Decimal("0")
        brk_cost = Decimal(str(brk_pos.get("avg_cost", 0))) if brk_pos else Decimal("0")

        diff = brk_qty - sys_qty
        pos_diff = PositionDiff(
            symbol=symbol,
            system_qty=sys_qty,
            broker_qty=brk_qty,
            diff_qty=diff,
            system_cost=sys_cost,
            broker_cost=brk_cost,
        )

        if symbol not in system_symbols:
            result.broker_only.append(pos_diff)
        elif symbol not in broker_symbols:
            result.system_only.append(pos_diff)
        elif abs(diff) <= tolerance:
            result.matched.append(pos_diff)
        else:
            result.mismatched.append(pos_diff)

    if result.is_clean:
        logger.info(
            "Reconciliation clean: %d positions matched", len(result.matched)
        )
    else:
        logger.warning(
            "Reconciliation discrepancy: %d mismatched, %d system-only, %d broker-only",
            len(result.mismatched), len(result.system_only), len(result.broker_only),
        )

    return result


def auto_correct(
    portfolio: Portfolio,
    result: ReconcileResult,
    trust_broker: bool = True,
) -> list[str]:
    """根據對帳結果自動修正系統持倉。

    Args:
        portfolio: 系統端投資組合（會被就地修改）。
        result: 對帳結果。
        trust_broker: True = 以券商端為準修正系統。

    Returns:
        修正記錄列表。
    """
    from src.core.models import Instrument, Position

    corrections: list[str] = []

    if not trust_broker:
        logger.info("auto_correct: trust_broker=False, no corrections applied")
        return corrections

    # 修正數量不一致
    for diff in result.mismatched:
        pos = portfolio.positions.get(diff.symbol)
        if pos is not None:
            old_qty = pos.quantity
            pos.quantity = diff.broker_qty
            if diff.broker_cost > 0:
                pos.avg_cost = diff.broker_cost
            corrections.append(
                f"CORRECTED {diff.symbol}: {old_qty} → {diff.broker_qty}"
            )

    # 新增券商有但系統無的持倉
    for diff in result.broker_only:
        portfolio.positions[diff.symbol] = Position(
            instrument=Instrument(symbol=diff.symbol),
            quantity=diff.broker_qty,
            avg_cost=diff.broker_cost,
        )
        corrections.append(
            f"ADDED {diff.symbol}: qty={diff.broker_qty}"
        )

    # 移除系統有但券商無的持倉
    for diff in result.system_only:
        if diff.symbol in portfolio.positions:
            del portfolio.positions[diff.symbol]
            corrections.append(f"REMOVED {diff.symbol}")

    if corrections:
        logger.warning("Auto-corrected %d positions: %s", len(corrections), corrections)

    return corrections
