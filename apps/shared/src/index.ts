// Types
export type {
  UserRole,
  Position,
  Portfolio,
  StrategyInfo,
  OrderInfo,
  ManualOrderRequest,
  BacktestRequest,
  BacktestSummary,
  BacktestResult,
  RiskRule,
  RiskAlert,
  SystemStatus,
  SystemMetrics,
  HealthCheck,
} from "./types";

// API client
export { ApiError, initClient } from "./api/client";
export type { ClientAdapter } from "./api/client";
export { get, post, put } from "./api/client";

// WebSocket
export { WSManager, initWs } from "./api/ws";
export type { Channel } from "./api/ws";

// Endpoints
export { auth, system, portfolio, strategies, orders, backtest, risk } from "./api/endpoints";

// Hooks / utilities
export { pollBacktestResult } from "./hooks/pollBacktestResult";
export type { PollOptions, PollOutcome, PollSuccess, PollFailure } from "./hooks/pollBacktestResult";

// Utils
export { fmtCurrency, fmtPct, fmtNum, fmtDate, fmtTime } from "./utils/format";
