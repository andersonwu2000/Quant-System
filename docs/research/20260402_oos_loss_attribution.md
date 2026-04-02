# AN-25: 2025 OOS Loss Attribution — revenue_acceleration

> Date: 2026-04-02
> Factor: revenue_acceleration
> Decision: **RETAIN** — continue paper trading observation

## Summary

| Period | Source | OOS Sharpe |
|--------|--------|:----------:|
| 2025 full year | Experiment #22 | -1.2 |
| 2025-07 ~ 2026-04 (OOS2) | Experiment #25 | +0.652 |

## Root Cause Analysis

| Category | Assessment |
|----------|-----------|
| Regime shift | **Primary cause** — growth stock rotation in early 2025 (H1) |
| Crowding | Not significant — low ADV impact at current scale |
| Cost underestimate | Minor — 2x cost Sharpe still positive in OOS2 |
| Data issue | None — PIT delay verified |
| Implementation bias | None — execution delay = 1 day confirmed |
| Benchmark illusion | No — OOS2 outperforms naive momentum baseline |

## Interpretation

H1 2025 saw a broad rotation away from growth/revenue-momentum stocks toward value.
The factor's negative performance was concentrated in Jan-Jun 2025.
Recovery in H2 2025 and continued positive performance into 2026 suggests the factor
captures a persistent premium that temporarily reversed during regime shift.

## Decision

**RETAIN** — factor shows recovery in OOS2 (Sharpe 0.652). Continue paper trading
observation. If next 3 months OOS Sharpe drops below 0, escalate to降權 review.
