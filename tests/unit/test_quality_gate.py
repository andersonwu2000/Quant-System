"""Tests for src.data.quality_gate — pre-trade data quality checks."""

from __future__ import annotations

import pandas as pd
import pytest
from dataclasses import replace
from datetime import date
from pathlib import Path

from src.data.quality_gate import (
    pre_trade_quality_gate,
    GateResult,
    CheckResult,
    _is_recent_trading_day,
)
from src.data.registry import REGISTRY


# ── Helpers ──────────────────────────────────────────────────────────

def _make_ohlcv(days: int = 5, start: str = "2026-03-24") -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=days)
    return pd.DataFrame(
        {
            "open": [100.0] * days,
            "high": [105.0] * days,
            "low": [95.0] * days,
            "close": [102.0] * days,
            "volume": [1000.0] * days,
        },
        index=dates,
    )


def _setup_universe(tmp_path: Path, symbols: list[str], days: int = 5, start: str = "2026-03-24") -> None:
    """Create parquet files for test symbols."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    for sym in symbols:
        df = _make_ohlcv(days, start)
        path = tmp_path / f"{sym}_1d.parquet"
        df.to_parquet(path)


def _patch_registry(monkeypatch, tmp_path):
    """Patch registry so price source_dirs points to tmp_path."""
    patched_price = replace(REGISTRY["price"], source_dirs=(tmp_path,))
    patched = {**REGISTRY, "price": patched_price}
    monkeypatch.setattr("src.data.registry.REGISTRY", patched)


# ── Unit tests ───────────────────────────────────────────────────────

class TestIsRecentTradingDay:
    def test_same_day(self):
        assert _is_recent_trading_day(date(2026, 3, 28), date(2026, 3, 28))

    def test_one_day_ago(self):
        assert _is_recent_trading_day(date(2026, 3, 27), date(2026, 3, 28))

    def test_weekend_gap(self):
        # Friday to Monday = 3 calendar days
        assert _is_recent_trading_day(date(2026, 3, 27), date(2026, 3, 30))

    def test_too_old(self):
        assert not _is_recent_trading_day(date(2026, 3, 20), date(2026, 3, 28))


class TestPreTradeQualityGate:
    def test_empty_universe_blocks(self):
        result = pre_trade_quality_gate([])
        assert not result.passed
        assert "Empty universe" in result.blocking

    def test_all_missing_blocks(self, tmp_path, monkeypatch):
        _patch_registry(monkeypatch, tmp_path)
        result = pre_trade_quality_gate(["FAKE1.TW", "FAKE2.TW"])
        assert not result.passed
        assert any("L1" in b for b in result.blocking)

    def test_all_fresh_passes(self, tmp_path, monkeypatch):
        _patch_registry(monkeypatch, tmp_path)
        symbols = ["A.TW", "B.TW", "C.TW"]
        _setup_universe(tmp_path, symbols)
        result = pre_trade_quality_gate(symbols, reference_date=date(2026, 3, 28))
        assert result.passed
        assert len(result.blocking) == 0
        assert result.universe_size == 3

    def test_stale_data_blocks(self, tmp_path, monkeypatch):
        _patch_registry(monkeypatch, tmp_path)
        symbols = ["A.TW", "B.TW"]
        # Data from January — very stale relative to March reference
        _setup_universe(tmp_path, symbols, days=5, start="2026-01-05")
        result = pre_trade_quality_gate(symbols, reference_date=date(2026, 3, 28))
        assert not result.passed
        assert any("L2" in b for b in result.blocking)

    def test_partial_missing_passes_under_threshold(self, tmp_path, monkeypatch):
        _patch_registry(monkeypatch, tmp_path)
        # 20 symbols, 1 missing = 5% = at threshold
        symbols = [f"S{i}.TW" for i in range(20)]
        _setup_universe(tmp_path, symbols[:19])  # 19 exist, 1 missing
        result = pre_trade_quality_gate(symbols, reference_date=date(2026, 3, 28))
        # L1 should pass (5% = threshold)
        l1 = [c for c in result.checks if c.name == "L1_completeness"][0]
        assert l1.passed

    def test_sanity_detects_limit_up(self, tmp_path, monkeypatch):
        _patch_registry(monkeypatch, tmp_path)
        symbols = ["A.TW"]
        df = _make_ohlcv(5, "2026-03-24")
        # Make last bar have a 15% jump (exceeds 11% limit)
        df.iloc[-1, df.columns.get_loc("close")] = 120.0
        path = tmp_path / "A.TW_1d.parquet"
        df.to_parquet(path)
        result = pre_trade_quality_gate(symbols, reference_date=date(2026, 3, 28))
        l3 = [c for c in result.checks if c.name == "L3_sanity"][0]
        assert "A.TW" in l3.affected_symbols

    def test_consistency_warning_only(self, tmp_path, monkeypatch):
        _patch_registry(monkeypatch, tmp_path)
        symbols = ["A.TW"]
        df = _make_ohlcv(5, "2026-03-24")
        # Make last bar open wildly different from prev close
        df.iloc[-1, df.columns.get_loc("open")] = 200.0
        path = tmp_path / "A.TW_1d.parquet"
        df.to_parquet(path)
        result = pre_trade_quality_gate(symbols, reference_date=date(2026, 3, 28))
        # L4 is warning-only, should not block
        l4 = [c for c in result.checks if c.name == "L4_consistency"][0]
        assert l4.passed  # L4 never blocks
        assert any("L4" in w for w in result.warnings)

    def test_gate_result_summary(self):
        g = GateResult(passed=True, universe_size=10)
        assert "PASS" in g.summary()

        g2 = GateResult(passed=False, universe_size=10, blocking=["L1: 5 missing"])
        assert "BLOCKED" in g2.summary()
