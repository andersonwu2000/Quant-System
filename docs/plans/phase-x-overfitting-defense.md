# Phase X: Anti-Overfitting Defense for Autoresearch

## Problem

Running 100+ automated experiments creates multiple testing risk. Current L1-L4 gates
have fixed thresholds regardless of how many trials have been run. A factor that passes
L4 after 1000 trials is far less trustworthy than one that passes after 10.

## Academic & Industry Consensus

- **Harvey et al. (2016)**: global Bonferroni (t > sqrt(2*ln(N))) becomes impossible after ~1000 trials
- **Bailey & Lopez de Prado**: global DSR has the same problem — E[max(SR)] grows with ln(N)
- **WorldQuant/AQR/Two Sigma**: nobody uses global FWER correction; instead use:
  1. Time-based OOS holdout (strongest defense)
  2. FDR (BH procedure) within factor families
  3. Incremental contribution vs existing factor pool
  4. Economic intuition as Bayesian prior

## Design

### 1. Time Holdout (L5 gate in evaluate.py)

Split evaluation period:
- **IS (In-Sample)**: 2017-01-01 to 2023-06-30 — used for L1-L4
- **OOS (Out-of-Sample)**: 2023-07-01 to 2024-12-31 — used for L5 only
- Agent's factor code never sees OOS forward returns during development
- OOS period is 1.5 years (sufficient for yearly stability check)

L5 gate criteria:
- OOS IC direction must match IS IC direction (same sign)
- OOS |ICIR| >= IS |ICIR| * 0.40 (allow up to 60% decay, industry standard 50-70%)
- OOS positive_months >= 50% (not just lucky in one month)

### 2. Family Labeling (results.tsv)

Add `family` column to results.tsv. Families:
- `momentum` — price momentum, Sharpe, trend
- `value` — PE, PB, earnings yield
- `quality` — ROE, margins, stability
- `revenue` — revenue growth, acceleration, beat
- `liquidity` — volume, Amihud, turnover
- `institutional` — trust/foreign/dealer flows
- `technical` — RSI, MACD, Bollinger, patterns
- `composite` — multi-family combinations

Agent self-labels in results.tsv. evaluate.py validates family is provided.

### 3. Family-Aware Trial Count (evaluate.py)

- Read results.tsv to count trials per family
- Apply BH-FDR (q=0.10) within family for ICIR significance
- Cross-family: no global correction (rely on OOS holdout)
- Implementation: after L4, check if ICIR p-value survives BH correction within family

### 4. What We Do NOT Add

- Global Bonferroni / global DSR penalty — becomes impossible after ~500 trials
- Trial count decay on fitness — arbitrary and hard to calibrate
- Automatic threshold escalation — creates perverse incentives

## Implementation

### Files Modified
- `scripts/autoresearch/evaluate.py` — add L5 OOS gate, family FDR
- `scripts/autoresearch/program.md` — update protocol with family labeling
- `scripts/autoresearch/results.tsv` — add family column

### Evaluation Flow (after changes)

```
L1: |IC_20d| >= 0.02          (IS period, first 30 dates, early exit)
L2: |ICIR| >= 0.15            (IS period, full evaluation)
L3: dedup corr <= 0.50        (IS period)
    positive_years >= 5/7     (IS period, 7 IS years)
L4: fitness >= 3.0            (IS period)
L5: OOS validation            (OOS period, NEW)
    - OOS IC sign == IS IC sign
    - OOS |ICIR| >= IS |ICIR| * 0.40
    - OOS positive_months >= 50%
Stage 2: large_icir >= 0.20   (full period, 865+ symbols)
```

### Risk

- OOS period is burned after first use — but in autoresearch, agent never sees OOS
  returns (evaluate.py computes forward returns internally, agent only sees the pass/fail)
- Family labeling is self-reported by agent — acceptable because FDR is within-family
  (mislabeling only hurts the agent by pooling with stronger factors)
- 1.5 year OOS may be too short for regime testing — acceptable given IS is 6.5 years

## Success Criteria

- Factors passing L5 should have genuine OOS alpha (not just IS optimization)
- System can still discover factors after 1000+ trials (no impossible thresholds)
- Family FDR prevents within-family p-hacking without blocking cross-family exploration
