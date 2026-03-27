"""Tests for src/scheduler/jobs.py — Pipeline execution, records, crash detection.

Covers:
- Pipeline record writing/reading
- Idempotency checks (_has_completed_run_today, _has_completed_run_this_month)
- Crash detection (check_crashed_runs)
- Trade/selection log saving
- PipelineResult dataclass
- Reconciliation helper
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.scheduler.jobs import (
    PipelineResult,
    _has_completed_run_this_month,
    _has_completed_run_today,
    _reconcile,
    _save_trade_log,
    _today_run_id,
    _write_pipeline_record,
    check_crashed_runs,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture()
def tmp_pipeline_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect PIPELINE_RUNS_DIR to a temp directory."""
    runs_dir = tmp_path / "pipeline_runs"
    runs_dir.mkdir()
    monkeypatch.setattr("src.scheduler.jobs.PIPELINE_RUNS_DIR", runs_dir)
    return runs_dir


@pytest.fixture()
def tmp_trades_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect trade log output to temp directory."""
    trades_dir = tmp_path / "trades"
    # Don't create it yet — _save_trade_log should create it
    monkeypatch.setattr(
        "src.scheduler.jobs._save_trade_log",
        lambda trades, strategy_name: _save_trade_log_patched(
            trades, strategy_name, trades_dir,
        ),
    )
    return trades_dir


def _save_trade_log_patched(
    trades: list, strategy_name: str, out_dir: Path,
) -> None:
    """Helper that writes trade logs to a custom directory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d_%H%M")
    log = {
        "date": today,
        "strategy": strategy_name,
        "n_trades": len(trades),
        "trades": [],
    }
    path = out_dir / f"{today}.json"
    path.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")


# ── _write_pipeline_record ───────────────────────────────────


class TestWritePipelineRecord:
    def test_write_started_record(self, tmp_pipeline_dir: Path) -> None:
        path = _write_pipeline_record("2026-03-27_0900", status="started", strategy="momentum")
        assert path.exists()
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["run_id"] == "2026-03-27_0900"
        assert record["status"] == "started"
        assert record["strategy"] == "momentum"
        assert record["started_at"] is not None
        assert record["finished_at"] is None

    def test_write_completed_preserves_started_at(self, tmp_pipeline_dir: Path) -> None:
        # First write started
        _write_pipeline_record("2026-03-27_0900", status="started", strategy="test")
        # Then complete
        path = _write_pipeline_record(
            "2026-03-27_0900", status="completed", strategy="test", n_trades=5,
        )
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["status"] == "completed"
        assert record["started_at"] is not None  # preserved from first write
        assert record["finished_at"] is not None
        assert record["n_trades"] == 5

    def test_write_failed_with_error(self, tmp_pipeline_dir: Path) -> None:
        path = _write_pipeline_record(
            "2026-03-27_0900", status="failed", strategy="test", error="timeout",
        )
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["status"] == "failed"
        assert record["error"] == "timeout"

    def test_creates_directory(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should create the runs directory if it does not exist."""
        runs_dir = tmp_path / "new_runs_dir"
        monkeypatch.setattr("src.scheduler.jobs.PIPELINE_RUNS_DIR", runs_dir)
        assert not runs_dir.exists()
        _write_pipeline_record("test_run", status="started")
        assert runs_dir.exists()


# ── _today_run_id ────────────────────────────────────────────


class TestTodayRunId:
    def test_format(self) -> None:
        run_id = _today_run_id()
        # Should match YYYY-MM-DD_HHMM format
        assert len(run_id) >= 15  # e.g. "2026-03-27_0900"
        parts = run_id.split("_")
        assert len(parts) == 2
        assert len(parts[0].split("-")) == 3  # date part


# ── Idempotency checks ──────────────────────────────────────


class TestIdempotency:
    def test_no_completed_run_today(self, tmp_pipeline_dir: Path) -> None:
        assert _has_completed_run_today() is False

    def test_has_completed_run_today(self, tmp_pipeline_dir: Path) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        record = {"status": "completed"}
        path = tmp_pipeline_dir / f"{today}_0900.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        assert _has_completed_run_today() is True

    def test_has_ok_run_today(self, tmp_pipeline_dir: Path) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        record = {"status": "ok"}
        path = tmp_pipeline_dir / f"{today}_1000.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        assert _has_completed_run_today() is True

    def test_failed_run_not_counted(self, tmp_pipeline_dir: Path) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        record = {"status": "failed"}
        path = tmp_pipeline_dir / f"{today}_0900.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        assert _has_completed_run_today() is False

    def test_no_completed_run_this_month(self, tmp_pipeline_dir: Path) -> None:
        assert _has_completed_run_this_month() is False

    def test_has_completed_run_this_month(self, tmp_pipeline_dir: Path) -> None:
        month = datetime.now().strftime("%Y-%m")
        record = {"status": "completed"}
        path = tmp_pipeline_dir / f"{month}-01_0900.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        assert _has_completed_run_this_month() is True

    def test_nonexistent_dir_returns_false(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "src.scheduler.jobs.PIPELINE_RUNS_DIR", tmp_path / "nonexistent",
        )
        assert _has_completed_run_today() is False
        assert _has_completed_run_this_month() is False


# ── Crash detection ──────────────────────────────────────────


class TestCrashDetection:
    def test_no_crashes_empty_dir(self, tmp_pipeline_dir: Path) -> None:
        assert check_crashed_runs() == []

    def test_detects_started_as_crashed(self, tmp_pipeline_dir: Path) -> None:
        record = {
            "run_id": "2026-03-27_0900",
            "status": "started",
            "strategy": "momentum",
            "started_at": "2026-03-27T09:00:00",
        }
        path = tmp_pipeline_dir / "2026-03-27_0900.json"
        path.write_text(json.dumps(record), encoding="utf-8")

        crashed = check_crashed_runs()
        assert len(crashed) == 1
        assert crashed[0]["run_id"] == "2026-03-27_0900"

        # Verify the file was updated to "crashed" status
        updated = json.loads(path.read_text(encoding="utf-8"))
        assert updated["status"] == "crashed"
        assert updated["finished_at"] is not None
        assert "terminated unexpectedly" in updated["error"]

    def test_completed_not_flagged_as_crash(self, tmp_pipeline_dir: Path) -> None:
        record = {"run_id": "test", "status": "completed"}
        path = tmp_pipeline_dir / "test.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        assert check_crashed_runs() == []

    def test_multiple_crashes(self, tmp_pipeline_dir: Path) -> None:
        for i in range(3):
            record = {"run_id": f"run_{i}", "status": "started"}
            path = tmp_pipeline_dir / f"run_{i}.json"
            path.write_text(json.dumps(record), encoding="utf-8")

        crashed = check_crashed_runs()
        assert len(crashed) == 3

    def test_nonexistent_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "src.scheduler.jobs.PIPELINE_RUNS_DIR", tmp_path / "nonexistent",
        )
        assert check_crashed_runs() == []

    def test_corrupt_json_skipped(self, tmp_pipeline_dir: Path) -> None:
        path = tmp_pipeline_dir / "corrupt.json"
        path.write_text("not valid json{{{", encoding="utf-8")
        # Should not raise, just skip
        crashed = check_crashed_runs()
        assert crashed == []


# ── Trade logging ────────────────────────────────────────────


class TestTradeLogging:
    def test_save_trade_log(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

        # Create mock trades
        mock_trade = MagicMock()
        mock_trade.symbol = "2330.TW"
        mock_trade.side = "BUY"
        mock_trade.quantity = "1000"
        mock_trade.price = "600"

        # Call the actual function (it uses relative paths internally)
        # We need to ensure data/paper_trading/trades exists relative to cwd
        trades_dir = tmp_path / "data" / "paper_trading" / "trades"
        trades_dir.mkdir(parents=True, exist_ok=True)
        _save_trade_log([mock_trade], "test_strategy")

        files = list(trades_dir.glob("*.json"))
        assert len(files) == 1
        record = json.loads(files[0].read_text(encoding="utf-8"))
        assert record["strategy"] == "test_strategy"
        assert record["n_trades"] == 1


# ── PipelineResult dataclass ─────────────────────────────────


class TestPipelineResult:
    def test_ok_result(self) -> None:
        r = PipelineResult(status="ok", n_trades=5, strategy_name="momentum")
        assert r.status == "ok"
        assert r.n_trades == 5
        assert r.strategy_name == "momentum"
        assert r.error == ""

    def test_error_result(self) -> None:
        r = PipelineResult(status="error", error="something broke")
        assert r.status == "error"
        assert r.error == "something broke"
        assert r.n_trades == 0

    def test_defaults(self) -> None:
        r = PipelineResult(status="ok")
        assert r.n_trades == 0
        assert r.strategy_name == ""
        assert r.error == ""


# ── Reconciliation ───────────────────────────────────────────


class TestReconcile:
    def _make_portfolio_with_weights(
        self, weights: dict[str, float],
    ) -> MagicMock:
        portfolio = MagicMock()
        portfolio.positions = {s: MagicMock() for s in weights}
        portfolio.get_position_weight.side_effect = lambda s: weights.get(s, 0.0)
        return portfolio

    def test_no_deviations(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        target = {"AAPL": 0.5, "MSFT": 0.5}
        portfolio = self._make_portfolio_with_weights({"AAPL": 0.5, "MSFT": 0.5})
        deviations = _reconcile(target, portfolio)
        assert deviations == []

    def test_with_deviations(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        target = {"AAPL": 0.5, "MSFT": 0.3}
        portfolio = self._make_portfolio_with_weights({"AAPL": 0.3, "MSFT": 0.3})
        deviations = _reconcile(target, portfolio)
        assert len(deviations) == 1
        assert deviations[0]["symbol"] == "AAPL"

    def test_missing_from_portfolio(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        target = {"AAPL": 0.5}
        portfolio = self._make_portfolio_with_weights({})
        portfolio.positions = {}
        deviations = _reconcile(target, portfolio)
        assert len(deviations) == 1
        assert deviations[0]["symbol"] == "AAPL"

    def test_custom_threshold(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        target = {"AAPL": 0.50}
        portfolio = self._make_portfolio_with_weights({"AAPL": 0.49})
        # Default threshold 2% -> 0.01 diff should not flag
        deviations = _reconcile(target, portfolio, threshold=0.02)
        assert deviations == []
        # But with 0.005 threshold it should
        deviations = _reconcile(target, portfolio, threshold=0.005)
        assert len(deviations) == 1

    def test_deviations_sorted_descending(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        target = {"A": 0.5, "B": 0.3, "C": 0.1}
        portfolio = self._make_portfolio_with_weights({"A": 0.1, "B": 0.1, "C": 0.0})
        deviations = _reconcile(target, portfolio)
        # Should be sorted by deviation descending
        devs = [d["deviation"] for d in deviations]
        assert devs == sorted(devs, reverse=True)
