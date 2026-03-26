"""Auto Monitor — 每日監控自動部署的策略。

功能：
- 每日 NAV snapshot
- Factor IC 追蹤（近 60 天 rolling IC）
- DD 告警
- 週報 / 月報生成
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class AutoMonitor:
    """監控自動部署策略的績效。"""

    def __init__(self, monitor_dir: str = "data/paper_trading/auto/monitor"):
        self._dir = Path(monitor_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def daily_snapshot(
        self,
        strategy_name: str,
        nav: float,
        positions: dict[str, float],
        factor_ic_60d: float | None = None,
    ) -> None:
        """記錄每日快照。"""
        today = datetime.now().strftime("%Y-%m-%d")
        snapshot = {
            "date": today,
            "strategy": strategy_name,
            "nav": nav,
            "n_positions": len(positions),
            "top_positions": dict(sorted(positions.items(), key=lambda x: -x[1])[:5]),
            "factor_ic_60d": factor_ic_60d,
            "timestamp": datetime.now().isoformat(),
        }

        # Append to daily log
        log_path = self._dir / f"{strategy_name}_daily.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")

        logger.info(
            "Snapshot %s: NAV=%.0f, positions=%d, IC_60d=%s",
            strategy_name, nav, len(positions),
            f"{factor_ic_60d:.3f}" if factor_ic_60d is not None else "N/A",
        )

    def check_alerts(
        self,
        strategy_name: str,
        current_nav: float,
        peak_nav: float,
        dd_threshold: float = 0.03,
    ) -> list[str]:
        """檢查告警條件。"""
        alerts = []
        if peak_nav > 0:
            dd = (peak_nav - current_nav) / peak_nav
            if dd > dd_threshold:
                alerts.append(
                    f"DD ALERT: {strategy_name} drawdown {dd:.1%} > {dd_threshold:.0%}"
                )
        return alerts

    def generate_weekly_report(
        self,
        strategy_name: str,
    ) -> str:
        """產出週報。"""
        log_path = self._dir / f"{strategy_name}_daily.jsonl"
        if not log_path.exists():
            return f"No data for {strategy_name}"

        snapshots = []
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    snapshots.append(json.loads(line))

        if not snapshots:
            return f"No snapshots for {strategy_name}"

        recent = snapshots[-5:]  # last 5 trading days
        first_nav = recent[0]["nav"]
        last_nav = recent[-1]["nav"]
        week_return = (last_nav / first_nav - 1) * 100 if first_nav > 0 else 0

        lines = [
            f"# Weekly Report: {strategy_name}",
            f"**Period**: {recent[0]['date']} ~ {recent[-1]['date']}",
            f"**Return**: {week_return:+.2f}%",
            f"**NAV**: {last_nav:,.0f}",
            f"**Positions**: {recent[-1]['n_positions']}",
        ]

        if recent[-1].get("factor_ic_60d") is not None:
            lines.append(f"**Factor IC (60d)**: {recent[-1]['factor_ic_60d']:.3f}")

        return "\n".join(lines)

    def generate_monthly_review(
        self,
        strategy_name: str,
        backtest_sharpe: float | None = None,
    ) -> str:
        """產出月度審閱報告（供人工確認）。"""
        log_path = self._dir / f"{strategy_name}_daily.jsonl"
        if not log_path.exists():
            return f"No data for {strategy_name}"

        snapshots = []
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    snapshots.append(json.loads(line))

        if len(snapshots) < 5:
            return f"Insufficient data for {strategy_name} ({len(snapshots)} days)"

        navs = [s["nav"] for s in snapshots]
        first = navs[0]
        last = navs[-1]
        total_return = (last / first - 1) * 100 if first > 0 else 0
        peak = max(navs)
        mdd = min((n - peak) / peak * 100 for n in navs) if peak > 0 else 0

        report_dir = Path("docs/dev/auto")
        report_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        report_path = report_dir / f"review_{strategy_name}_{today}.md"

        lines = [
            f"# Monthly Review: {strategy_name}",
            "",
            f"**Period**: {snapshots[0]['date']} ~ {snapshots[-1]['date']} ({len(snapshots)} days)",
            f"**Total Return**: {total_return:+.2f}%",
            f"**Max Drawdown**: {mdd:+.2f}%",
            f"**Final NAV**: {last:,.0f}",
            "",
            "## vs Backtest",
            "",
        ]

        if backtest_sharpe is not None:
            lines.append(f"- Backtest Sharpe: {backtest_sharpe:.3f}")
            lines.append(f"- Paper return: {total_return:+.2f}%")
            lines.append("")

        lines.extend([
            "## Decision",
            "",
            "- [ ] Promote to Live Trading",
            "- [ ] Extend Paper Trading 30 days",
            "- [ ] Reduce position and observe",
            "- [ ] Stop and add to forbidden regions",
        ])

        report_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("Monthly review: %s", report_path)
        return str(report_path)
