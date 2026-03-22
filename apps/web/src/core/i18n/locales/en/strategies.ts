export const strategies = {
  title: "Strategies",
  start: "Start",
  stop: "Stop",
  noStrategies: "No strategies configured",
  strategyDescriptions: {
    momentum: "Classic 12-1 momentum strategy. Buys the top performers of the past 12 months (skipping the most recent month to avoid short-term reversal). Weights are allocated proportionally to signal strength, capped at 10% per position and 95% gross exposure. Rebalances weekly or monthly.",
    mean_reversion: "Mean-reversion strategy. Buys stocks whose price has fallen significantly below their moving average (Z-score above threshold, default 1.5). Signal-weighted allocation with a max 8% per position and 90% gross exposure. Suited for range-bound, low-momentum markets.",
  },
};
