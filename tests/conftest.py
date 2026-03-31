"""Global test fixtures — prevent tests from affecting production state."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _block_real_notifications(tmp_path):
    """Prevent any test from sending real Discord/LINE/Telegram notifications."""
    from unittest.mock import AsyncMock

    fake_notifier = AsyncMock()
    fake_notifier.is_configured.return_value = False
    fake_notifier.send = AsyncMock()

    with patch("src.notifications.factory.create_notifier", return_value=fake_notifier):
        yield


@pytest.fixture(autouse=True)
def _block_portfolio_persistence(tmp_path):
    """Prevent tests from writing to the real portfolio_state.json."""
    fake_path = tmp_path / "portfolio_state.json"
    fake_dir = tmp_path

    with patch("src.api.state._PERSIST_PATH", fake_path), \
         patch("src.api.state._PERSIST_DIR", fake_dir):
        yield


@pytest.fixture(autouse=True)
def _block_trade_ledger(tmp_path):
    """Prevent tests from writing to the real trade ledger."""
    fake_ledger_dir = tmp_path / "ledger"
    with patch("src.execution.trade_ledger.LEDGER_DIR", fake_ledger_dir):
        yield
