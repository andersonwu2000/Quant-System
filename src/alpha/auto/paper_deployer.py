"""Auto Paper Deployer — 限額自動部署策略到 Paper Trading。

安全限制：
- 單策略最大 5% NAV
- 同時最多 3 個 auto 策略
- 3% DD Kill Switch（比手動更嚴格）
- 30 天自動停止
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEPLOY_DIR = Path("data/paper_trading/auto")
MAX_AUTO_STRATEGIES = 3
MAX_NAV_FRACTION = 0.05  # 5%
AUTO_STOP_DAYS = 30
KILL_SWITCH_DD = 0.03  # 3%


@dataclass
class DeployedStrategy:
    """已部署的自動策略。"""
    name: str
    factor_name: str
    deploy_date: str
    stop_date: str  # auto-stop date
    nav_fraction: float
    status: str = "active"  # active | stopped | expired | killed
    initial_nav: float = 0.0
    current_nav: float = 0.0
    peak_nav: float = 0.0
    daily_navs: list[dict[str, Any]] = field(default_factory=list)


class PaperDeployer:
    """管理自動策略的 Paper Trading 部署。"""

    def __init__(self, deploy_dir: str = str(DEPLOY_DIR)):
        self._dir = Path(deploy_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._deployed: list[DeployedStrategy] = self._load_deployed()

    def _load_deployed(self) -> list[DeployedStrategy]:
        """從 JSON 載入已部署策略。"""
        state_file = self._dir / "deployed.json"
        if not state_file.exists():
            return []
        try:
            with open(state_file, encoding="utf-8") as f:
                data = json.load(f)
            return [DeployedStrategy(**d) for d in data]
        except Exception as e:
            logger.warning("Failed to load deployed state: %s", e)
            return []

    def _save_deployed(self) -> None:
        state_file = self._dir / "deployed.json"
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "name": d.name,
                        "factor_name": d.factor_name,
                        "deploy_date": d.deploy_date,
                        "stop_date": d.stop_date,
                        "nav_fraction": d.nav_fraction,
                        "status": d.status,
                        "initial_nav": d.initial_nav,
                        "current_nav": d.current_nav,
                        "peak_nav": d.peak_nav,
                        "daily_navs": d.daily_navs[-90:],  # keep last 90 days
                    }
                    for d in self._deployed
                ],
                f, indent=2, ensure_ascii=False,
            )

    @property
    def active_count(self) -> int:
        return sum(1 for d in self._deployed if d.status == "active")

    def can_deploy(self) -> tuple[bool, str]:
        """檢查是否可以部署新策略。"""
        if self.active_count >= MAX_AUTO_STRATEGIES:
            return False, f"Max {MAX_AUTO_STRATEGIES} auto strategies reached ({self.active_count} active)"
        return True, ""

    def deploy(
        self,
        name: str,
        factor_name: str,
        total_nav: float,
        nav_fraction: float = MAX_NAV_FRACTION,
    ) -> DeployedStrategy | None:
        """部署新策略。"""
        can, reason = self.can_deploy()
        if not can:
            logger.warning("Cannot deploy %s: %s", name, reason)
            return None

        # 檢查是否已部署
        for d in self._deployed:
            if d.name == name and d.status == "active":
                logger.warning("Strategy %s already active", name)
                return None

        now = datetime.now()
        allocated_nav = total_nav * nav_fraction
        deployed = DeployedStrategy(
            name=name,
            factor_name=factor_name,
            deploy_date=now.isoformat(),
            stop_date=(now + timedelta(days=AUTO_STOP_DAYS)).isoformat(),
            nav_fraction=nav_fraction,
            status="active",
            initial_nav=allocated_nav,
            current_nav=allocated_nav,
            peak_nav=allocated_nav,
        )
        self._deployed.append(deployed)
        self._save_deployed()

        logger.info(
            "Deployed %s: %.0f NAV (%.0f%%), auto-stop %s",
            name, allocated_nav, nav_fraction * 100, deployed.stop_date[:10],
        )
        return deployed

    def update_nav(self, name: str, new_nav: float) -> None:
        """更新策略 NAV（每日呼叫）。"""
        for d in self._deployed:
            if d.name == name and d.status == "active":
                d.current_nav = new_nav
                d.peak_nav = max(d.peak_nav, new_nav)
                d.daily_navs.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "nav": new_nav,
                })

                # Kill Switch: DD > 3%
                dd = (d.peak_nav - new_nav) / d.peak_nav if d.peak_nav > 0 else 0
                if dd > KILL_SWITCH_DD:
                    d.status = "killed"
                    logger.warning(
                        "KILL: %s DD %.1f%% > %.0f%% threshold",
                        name, dd * 100, KILL_SWITCH_DD * 100,
                    )

                # Auto-stop: 30 days
                if datetime.now().isoformat() > d.stop_date:
                    d.status = "expired"
                    logger.info("EXPIRED: %s reached 30-day limit", name)

                self._save_deployed()
                return

    def get_active(self) -> list[DeployedStrategy]:
        """取得所有 active 策略。"""
        return [d for d in self._deployed if d.status == "active"]

    def stop(self, name: str, reason: str = "manual") -> None:
        """手動停止策略。"""
        for d in self._deployed:
            if d.name == name and d.status == "active":
                d.status = "stopped"
                logger.info("Stopped %s: %s", name, reason)
                self._save_deployed()
                return

    def summary(self) -> str:
        """產出狀態摘要。"""
        lines = [f"Auto Paper Trading: {self.active_count}/{MAX_AUTO_STRATEGIES} active"]
        for d in self._deployed:
            pnl = (d.current_nav / d.initial_nav - 1) * 100 if d.initial_nav > 0 else 0
            lines.append(
                f"  [{d.status:8s}] {d.name:30s} P&L={pnl:+.1f}% NAV={d.current_nav:,.0f}"
            )
        return "\n".join(lines)
