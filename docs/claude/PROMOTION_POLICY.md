# Promotion Policy

Defines when a strategy moves between lifecycle stages and when it gets frozen or de-listed.

## Lifecycle Stages

| Stage | Description |
|-------|-------------|
| research | Factor under development, backtest only |
| paper | Live signal generation, no real orders |
| live | Real orders executed via broker |

## Promotion Rules

### research -> paper
- All hard gates pass (11/11)
- Soft gate failures <= 2
- ValidationReportJSON.decision is "pass" or "pass-with-warning"

### paper -> live
- All hard gates pass (re-validated on paper-period data)
- 30 days minimum paper trading (Phase AL G1-G6 graduation)
- 0 invariant violations during paper period
- Paper Sharpe consistent with backtest (no > 50% degradation)

## Demotion Rules

### Freeze (pause signal generation)
- Any hard gate failure on rolling re-validation -> immediate freeze
- 3+ soft gate warnings on rolling re-validation -> freeze promotion (cannot advance)
- Any invariant violation in live trading -> immediate freeze pending review

### De-listing (remove from deployment)
- Rolling 6-month Sharpe < 0 sustained (two consecutive monthly checks)
- Hard gate failure not resolved within 14 days of freeze
- Manual override by operator

## Re-instatement
- Fix root cause and re-run full validation (research-level gates)
- Must pass all hard gates + <= 2 soft warnings
- Restart from paper stage (no direct return to live)

## Audit Trail
- Every promotion/demotion produces a ValidationReportJSON record
- Reports stored in `data/validation_reports/` with timestamp
- VALIDATOR_VERSION tracked for reproducibility
