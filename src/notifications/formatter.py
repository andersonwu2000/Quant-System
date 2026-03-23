"""Format trade suggestions into human-readable notification messages."""

from __future__ import annotations


def format_rebalance_notification(
    strategy_name: str,
    suggested_trades: list[dict[str, object]],
    estimated_commission: float,
    estimated_tax: float,
) -> tuple[str, str]:
    """Format a rebalance suggestion into (title, body) for notifications.

    Returns:
        (title, message) tuple
    """
    title = f"\U0001f4ca {strategy_name} \u518d\u5e73\u8861\u5efa\u8b70"

    lines = ["\u2501" * 21]
    for trade in suggested_trades:
        side = trade.get("side", "")
        emoji = "\U0001f7e2" if side == "BUY" else "\U0001f534"
        action = "\u8cb7\u9032" if side == "BUY" else "\u8ce3\u51fa"
        cost = abs(float(str(trade.get("estimated_cost", 0))))
        lines.append(
            f"{emoji} {action} {trade['symbol']} {trade['quantity']}\u80a1 \u2248${cost:,.0f}"
        )

    lines.append("\u2501" * 21)
    lines.append(
        f"\u9810\u4f30\u624b\u7e8c\u8cbb: ${estimated_commission:,.0f} "
        f"| \u4ea4\u6613\u7a05: ${estimated_tax:,.0f}"
    )

    message = "\n".join(lines)
    return title, message
