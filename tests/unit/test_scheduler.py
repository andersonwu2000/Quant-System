"""Scheduler service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from src.core.config import TradingConfig
from src.scheduler import SchedulerService


def _make_config(**overrides: object) -> TradingConfig:
    defaults = {"env": "dev", "api_key": "test-key"}
    defaults.update(overrides)
    return TradingConfig(**defaults)  # type: ignore[arg-type]


class TestSchedulerService:
    """SchedulerService 行為測試。"""

    def test_disabled_by_default(self) -> None:
        config = _make_config(scheduler_enabled=False)
        assert config.scheduler_enabled is False

        scheduler = SchedulerService()
        scheduler.start(config)
        assert scheduler.is_running is False

    def test_start_stop(self) -> None:
        config = _make_config(scheduler_enabled=True, rebalance_cron="0 9 1 * *")

        mock_trigger = MagicMock()
        mock_async_scheduler_instance = MagicMock()

        # Build fake apscheduler module tree so the local import works
        mock_apscheduler = MagicMock()
        mock_apscheduler.schedulers.asyncio.AsyncIOScheduler = MagicMock(
            return_value=mock_async_scheduler_instance
        )
        mock_apscheduler.triggers.cron.CronTrigger.from_crontab = MagicMock(
            return_value=mock_trigger
        )

        modules = {
            "apscheduler": mock_apscheduler,
            "apscheduler.schedulers": mock_apscheduler.schedulers,
            "apscheduler.schedulers.asyncio": mock_apscheduler.schedulers.asyncio,
            "apscheduler.triggers": mock_apscheduler.triggers,
            "apscheduler.triggers.cron": mock_apscheduler.triggers.cron,
        }

        with patch.dict("sys.modules", modules):
            scheduler = SchedulerService()
            scheduler.start(config)

            assert scheduler.is_running is True
            # 3 jobs: rebalance + revenue_update + revenue_rebalance
            assert mock_async_scheduler_instance.add_job.call_count >= 1
            mock_async_scheduler_instance.start.assert_called_once()

            scheduler.stop()
            assert scheduler.is_running is False
            mock_async_scheduler_instance.shutdown.assert_called_once()

    def test_missing_apscheduler_graceful(self) -> None:
        config = _make_config(scheduler_enabled=True)

        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if "apscheduler" in name:
                raise ImportError("No module named 'apscheduler'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            scheduler = SchedulerService()
            scheduler.start(config)
            assert scheduler.is_running is False

    def test_stop_when_not_started(self) -> None:
        """Calling stop on a non-started scheduler should not raise."""
        scheduler = SchedulerService()
        scheduler.stop()  # Should not raise
        assert scheduler.is_running is False
