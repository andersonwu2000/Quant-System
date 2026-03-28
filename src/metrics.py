"""Centralized Prometheus metrics for the trading system.

Import and use these counters/gauges/histograms throughout the codebase.
All metrics are automatically exposed via the /metrics endpoint
(set up by prometheus_fastapi_instrumentator in app.py).
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Kill Switch ──────────────────────────────────────

KILL_SWITCH_TRIGGERS = Counter(
    "kill_switch_triggers_total",
    "Number of times kill switch was triggered",
    labelnames=["path"],  # "poll" (path A) or "tick" (path B)
)

# ── Risk Alerts ──────────────────────────────────────

RISK_ALERTS = Counter(
    "risk_alerts_total",
    "Risk alerts emitted",
    labelnames=["severity"],  # info, warning, critical, emergency
)

INTRADAY_DRAWDOWN = Gauge(
    "intraday_drawdown_pct",
    "Current intraday drawdown percentage (negative = loss)",
)

NAV_CURRENT = Gauge(
    "nav_current",
    "Current portfolio NAV",
)

# ── Reconciliation ───────────────────────────────────

RECONCILE_RUNS = Counter(
    "reconcile_runs_total",
    "Total reconciliation runs",
    labelnames=["status"],  # clean, discrepancy, error, skipped
)

RECONCILE_MISMATCHES = Gauge(
    "reconcile_mismatches",
    "Number of mismatched positions in last reconciliation",
)

# ── Pipeline / Rebalance ─────────────────────────────

PIPELINE_RUNS = Counter(
    "pipeline_runs_total",
    "Trading pipeline executions",
    labelnames=["status"],  # ok, error, skipped, data_failed
)

PIPELINE_TRADES = Counter(
    "pipeline_trades_total",
    "Total trades executed by pipeline",
)

PIPELINE_DURATION = Histogram(
    "pipeline_duration_seconds",
    "Time spent executing trading pipeline",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

# ── Orders ───────────────────────────────────────────

ORDERS_SUBMITTED = Counter(
    "orders_submitted_total",
    "Orders submitted to broker",
    labelnames=["side"],  # BUY, SELL
)

ORDERS_REJECTED = Counter(
    "orders_rejected_total",
    "Orders rejected by risk engine",
)
