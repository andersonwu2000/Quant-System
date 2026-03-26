"""Tests for strategy center API endpoints."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _make_app():
    """Create test app with strategy_center router."""
    from fastapi import FastAPI
    from src.api.routes.strategy_center import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # Override auth
    from src.api.auth import verify_api_key, require_role

    app.dependency_overrides[verify_api_key] = lambda: "test-key"
    app.dependency_overrides[require_role("trader")] = lambda: "test-key"

    return app


class TestStrategyInfo:
    def test_returns_strategy_name(self):
        client = TestClient(_make_app())
        resp = client.get("/api/v1/strategy/info")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "revenue_momentum_hedged"
        assert "revenue_yoy" in data["factor"]


class TestRegime:
    def test_returns_regime_structure(self):
        client = TestClient(_make_app())
        resp = client.get("/api/v1/strategy/regime")
        assert resp.status_code == 200
        data = resp.json()
        assert "regime" in data
        assert data["regime"] in ("bull", "bear", "sideways", "unknown")
        assert "indicators" in data
        assert "reason" in data


class TestSelectionLatest:
    def test_empty_when_no_data(self):
        client = TestClient(_make_app())
        with patch("src.api.routes.strategy_center.SELECTIONS_DIR", Path("/nonexistent")):
            resp = client.get("/api/v1/strategy/selection/latest")
            assert resp.status_code == 200
            data = resp.json()
            assert data["date"] is None

    def test_reads_selection_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sel_dir = Path(tmpdir)
            sel_file = sel_dir / "2026-03-11.json"
            sel_file.write_text(json.dumps({
                "date": "2026-03-11",
                "strategy": "revenue_momentum_hedged",
                "n_targets": 15,
                "weights": {"2330.TW": 0.067, "2454.TW": 0.067},
            }))

            client = TestClient(_make_app())
            with patch("src.api.routes.strategy_center.SELECTIONS_DIR", sel_dir):
                resp = client.get("/api/v1/strategy/selection/latest")
                assert resp.status_code == 200
                data = resp.json()
                assert data["date"] == "2026-03-11"
                assert data["n_targets"] == 15


class TestSelectionHistory:
    def test_empty_when_no_data(self):
        client = TestClient(_make_app())
        with patch("src.api.routes.strategy_center.SELECTIONS_DIR", Path("/nonexistent")):
            resp = client.get("/api/v1/strategy/selection/history")
            assert resp.status_code == 200
            assert resp.json() == []

    def test_returns_sorted_history(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sel_dir = Path(tmpdir)
            for date in ["2026-01-11", "2026-02-11", "2026-03-11"]:
                (sel_dir / f"{date}.json").write_text(json.dumps({
                    "date": date, "n_targets": 15, "strategy": "test",
                }))

            client = TestClient(_make_app())
            with patch("src.api.routes.strategy_center.SELECTIONS_DIR", sel_dir):
                resp = client.get("/api/v1/strategy/selection/history?limit=2")
                data = resp.json()
                assert len(data) == 2
                assert data[0]["date"] == "2026-03-11"  # most recent first


class TestDataStatus:
    def test_returns_counts(self):
        client = TestClient(_make_app())
        resp = client.get("/api/v1/strategy/data-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "market_symbols" in data
        assert "revenue_symbols" in data
        assert isinstance(data["market_symbols"], int)
