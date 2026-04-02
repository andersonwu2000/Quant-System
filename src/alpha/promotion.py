"""Strategy promotion — explicit step between validation and deployment.

AO-5: Promotion artifact is separate from validation report.
- validation_report.json: produced by every validate() call (research artifact)
- promotion_decision.json: produced only by explicit promote() call (deployment artifact)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROMOTIONS_DIR = Path("data/promotions")
VALIDATIONS_DIR = Path("data/validations")


@dataclass
class PromotionDecision:
    strategy_id: str
    validator_version: str
    validation_report_path: str
    data_snapshot_date: str
    universe_snapshot_id: str
    code_version: str
    decision_basis_version: str
    research_score: float
    deployment_score: float
    approved_mode: str  # "research" | "paper" | "live-disabled"
    blocking_reasons: list[str]
    soft_warnings: list[str]
    reviewer: str
    timestamp: str


def save_validation_report(report: Any, strategy_name: str) -> Path:
    """Save a validation report as research artifact."""
    VALIDATIONS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    # Use validation_schema if available
    try:
        from src.backtest.validation_schema import ValidationReportJSON
        report_json = ValidationReportJSON.from_validation_report(report)
        data = report_json.to_json()
    except Exception:
        # Fallback: serialize summary
        data = {
            "strategy_name": strategy_name,
            "passed": report.passed if hasattr(report, 'passed') else False,
            "n_hard_passed": report.n_hard_passed if hasattr(report, 'n_hard_passed') else 0,
            "n_hard_total": report.n_hard_total if hasattr(report, 'n_hard_total') else 0,
            "n_passed": report.n_passed if hasattr(report, 'n_passed') else 0,
            "n_total": report.n_total if hasattr(report, 'n_total') else 0,
            "timestamp": today,
        }

    path = VALIDATIONS_DIR / f"{today}_{strategy_name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    logger.info("Validation report saved: %s", path)
    return path


def promote(
    strategy_name: str,
    validation_report_path: str | Path,
    target_mode: str = "paper",
    reviewer: str = "system",
) -> PromotionDecision:
    """Create a promotion decision based on a validation report.

    This is an explicit action, not a side effect of validation.
    """
    report_path = Path(validation_report_path)
    if not report_path.exists():
        raise FileNotFoundError(f"Validation report not found: {report_path}")

    report_data = json.loads(report_path.read_text(encoding="utf-8"))

    # Extract info from report
    passed = report_data.get("passed", False)
    blocking = []
    warnings = []

    for check in report_data.get("hard_gates", []):
        if not check.get("passed", True):
            blocking.append(check.get("name", "unknown"))
    for check in report_data.get("soft_gates", []):
        if not check.get("passed", True):
            warnings.append(check.get("name", "unknown"))

    if blocking:
        target_mode = "research"  # cannot promote with hard gate failures

    # Get code version
    code_version = ""
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        code_version = result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        pass

    _tw = timezone(timedelta(hours=8))
    decision = PromotionDecision(
        strategy_id=strategy_name,
        validator_version=report_data.get("validator_version", "unknown"),
        validation_report_path=str(report_path),
        data_snapshot_date=datetime.now().strftime("%Y-%m-%d"),
        universe_snapshot_id=f"tw_{report_data.get('universe_size', 0)}_{datetime.now().strftime('%Y%m%d')}",
        code_version=code_version,
        decision_basis_version="AO-1_scoring_v1",
        research_score=report_data.get("research_score", 0.0),
        deployment_score=report_data.get("deployment_score", 0.0),
        approved_mode=target_mode,
        blocking_reasons=blocking,
        soft_warnings=warnings,
        reviewer=reviewer,
        timestamp=datetime.now(_tw).isoformat(),
    )

    # Persist
    PROMOTIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROMOTIONS_DIR / f"{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    path.write_text(json.dumps(asdict(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Promotion decision: %s → %s (%s)", strategy_name, target_mode, path)

    return decision


def get_latest_promotion(strategy_name: str) -> PromotionDecision | None:
    """Get the most recent promotion decision for a strategy."""
    if not PROMOTIONS_DIR.exists():
        return None
    matches = sorted(PROMOTIONS_DIR.glob(f"{strategy_name}_*.json"), reverse=True)
    if not matches:
        return None
    try:
        data = json.loads(matches[0].read_text(encoding="utf-8"))
        return PromotionDecision(**data)
    except Exception:
        logger.warning("Failed to load promotion decision: %s", matches[0])
        return None
