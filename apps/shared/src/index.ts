// Types
export type {
  UserRole,
  UserInfo,
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
  NavPoint,
  TradeRecord,
  FactorName,
  AlphaFactorSpec,
  AlphaRunRequest,
  AlphaSummary,
  ICResult,
  AlphaTurnoverResult,
  QuantileReturn,
  FactorReport,
  AlphaReport,
  AssetClassName,
  TacticalRequest,
  TacticalResponse,
  TacticalWeightItem,
  MacroSignalItem,
  ExecutionStatus,
  PaperTradingStatus,
  MarketHoursStatus,
  ReconcileResult,
  ReconcileDiff,
  QueuedOrdersResponse,
  PortfolioListItem,
  SavedPortfolio,
  PortfolioCreateRequest,
  RebalancePreviewRequest,
  SuggestedTrade,
  RebalancePreviewResponse,
  AutoAlphaStatus,
  AutoAlphaPerformance,
  FactorScoreInfo,
  AutoAlphaSnapshot,
} from "./types";

// API client
export { ApiError, initClient } from "./api/client";
export type { ClientAdapter } from "./api/client";
export { get, post, put, del } from "./api/client";

// WebSocket
export { WSManager, initWs } from "./api/ws";
export type { Channel } from "./api/ws";

// Endpoints
export { auth, system, portfolio, strategies, orders, backtest, risk, alpha, allocation, execution, autoAlpha } from "./api/endpoints";

// Hooks / utilities
export { pollBacktestResult } from "./hooks/pollBacktestResult";
export type { PollOptions, PollOutcome, PollSuccess, PollFailure } from "./hooks/pollBacktestResult";

// Utils
export { fmtCurrency, fmtPrice, fmtPct, fmtNum, fmtDate, fmtTime, fmtUptime } from "./utils/format";
