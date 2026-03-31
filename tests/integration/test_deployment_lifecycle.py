"""AK-2 Layer 3: Deployed strategy lifecycle tests.

Verifies deploy → execute → NAV track → kill/expire cycle.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from src.alpha.auto.paper_deployer import (
    AUTO_STOP_DAYS,
    KILL_SWITCH_DD,
    MAX_AUTO_STRATEGIES,
    PaperDeployer,
)


@pytest.fixture
def deployer(tmp_path):
    """Fresh PaperDeployer with temp directory."""
    return PaperDeployer(deploy_dir=str(tmp_path))


class TestDeployExecuteNAV:
    """Test 3.1: Deploy → Execute → NAV Track."""

    def test_deploy_creates_state(self, deployer, tmp_path):
        """deploy() writes deployed.json with correct fields."""
        result = deployer.deploy("test_auto", "test_factor", total_nav=10_000_000)
        assert result is not None
        assert result.name == "test_auto"
        assert result.status == "active"
        assert result.initial_nav == 500_000  # 5% of 10M

        state_file = tmp_path / "deployed.json"
        assert state_file.exists()
        data = json.loads(state_file.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["name"] == "test_auto"

    def test_nav_update(self, deployer):
        """update_nav() tracks NAV and daily_navs list."""
        deployer.deploy("test", "factor", total_nav=10_000_000)
        deployer.update_nav("test", 510_000)

        active = deployer.get_active()
        assert len(active) == 1
        assert active[0].current_nav == 510_000
        assert active[0].peak_nav == 510_000
        assert len(active[0].daily_navs) == 1

    def test_nav_decrease_tracks_peak(self, deployer):
        """Peak NAV stays at highest point."""
        deployer.deploy("test", "factor", total_nav=10_000_000)
        deployer.update_nav("test", 520_000)
        deployer.update_nav("test", 510_000)

        active = deployer.get_active()
        assert active[0].current_nav == 510_000
        assert active[0].peak_nav == 520_000


class TestMonthlyRebalance:
    """Test 3.2: Monthly rebalance logic."""

    def test_first_run_rebalances(self, tmp_path):
        from src.alpha.auto.deployed_executor import _should_rebalance
        with patch("src.alpha.auto.deployed_executor.PAPER_TRADE_DIR", tmp_path):
            assert _should_rebalance("new_strategy") is True

    def test_same_month_skips(self, tmp_path):
        from src.alpha.auto.deployed_executor import _should_rebalance
        trade_dir = tmp_path / "strategy_x"
        trade_dir.mkdir()
        today = datetime.now().strftime("%Y-%m-%d")
        (trade_dir / f"{today}.json").write_text(json.dumps({
            "date": today, "weights": {}, "nav": 100,
        }))
        with patch("src.alpha.auto.deployed_executor.PAPER_TRADE_DIR", tmp_path):
            assert _should_rebalance("strategy_x") is False


class TestKillSwitch:
    """Test 3.3: Kill switch at MDD > 3%."""

    def test_kill_on_mdd_breach(self, deployer):
        """MDD > 3% → status becomes 'killed'."""
        deployer.deploy("victim", "factor", total_nav=10_000_000)
        initial = deployer.get_active()[0].initial_nav  # 500,000

        # Drop 4% from peak
        deployer.update_nav("victim", initial * 0.96)

        # Should be killed
        active = deployer.get_active()
        assert len(active) == 0
        killed = [d for d in deployer._deployed if d.status == "killed"]
        assert len(killed) == 1

    def test_no_kill_within_threshold(self, deployer):
        """MDD < 3% → stays active."""
        deployer.deploy("survivor", "factor", total_nav=10_000_000)
        initial = deployer.get_active()[0].initial_nav

        # Drop 2% (within threshold)
        deployer.update_nav("survivor", initial * 0.98)
        assert len(deployer.get_active()) == 1


class TestExpiry:
    """Test 3.4: 30-day auto expiry."""

    def test_expire_after_30_days(self, deployer):
        """Strategy expires after AUTO_STOP_DAYS."""
        deployer.deploy("old", "factor", total_nav=10_000_000)

        # Manipulate stop_date to be in the past
        for d in deployer._deployed:
            if d.name == "old":
                d.stop_date = (datetime.now() - timedelta(days=1)).isoformat()

        deployer.update_nav("old", 500_000)
        assert deployer.get_active() == []
        expired = [d for d in deployer._deployed if d.status == "expired"]
        assert len(expired) == 1


class TestMaxStrategies:
    """Test 3.5: Max 3 concurrent strategies."""

    def test_max_limit_enforced(self, deployer):
        """Cannot deploy more than MAX_AUTO_STRATEGIES."""
        for i in range(MAX_AUTO_STRATEGIES):
            result = deployer.deploy(f"s{i}", f"f{i}", total_nav=10_000_000)
            assert result is not None

        # One more should fail
        result = deployer.deploy("overflow", "factor", total_nav=10_000_000)
        assert result is None
        assert deployer.active_count == MAX_AUTO_STRATEGIES
