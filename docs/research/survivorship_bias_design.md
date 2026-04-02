# AN-31: Survivorship Bias — Design & Alternative Assessment

## Problem

Yahoo Finance only provides data for currently listed stocks. Delisted stocks silently disappear from the dataset, so backtests only use survivors. Academic literature estimates this overstates CAGR by 3-8% for broad TW equity universes.

## Current Mitigation

- FinLab panel data includes some delisted stocks (2005-2018 coverage).
- `BacktestEngine` emits `SURVIVORSHIP_BIAS` warnings when the universe shrinks unexpectedly.

## Alternatives Assessed

| Source | Cost | Coverage | Pros | Cons |
|--------|------|----------|------|------|
| **FinLab panel** | Free (already have) | 2005-2018, partial delisted | Ready to use | Stocks delisted after 2018 not covered |
| **TWSE API** | Free | Listing to delisting date | Official daily prices | Must manually track delisting events from TWSE announcements; no packaged delisted history |
| **TEJ** | ~50K TWD/year | Complete delisted history | Gold standard for TW academic research | Expensive for personal use |
| **Manual tracking** | Free | Going forward only | Simple, no dependency | No historical backfill; requires monthly discipline |

## Recommendation

**Phase 1 (now):** Manual tracking (going forward) + FinLab panel (historical 2005-2018).
- Monitor TWSE delisting announcements monthly, download final-day prices before delisting.
- Use FinLab panel for historical backtests that need delisted stock data.

**Phase 2 (if live capital):** Budget TEJ subscription for complete delisted history.

## Impact Assessment for Current Top Factor

For `revenue_acceleration`, survivorship bias impact is likely **LOW**:

- Universe is top 200 by ADV (large/mid cap) — very few delistings per year.
- Monthly rebalance naturally exits declining stocks well before delisting.
- Factor logic (acceleration of revenue growth) does not systematically favor distressed stocks.

Estimated CAGR overstatement for this universe: <1%, vs 3-8% for broad all-cap strategies.
