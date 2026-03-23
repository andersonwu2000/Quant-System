export { isAuthenticated, login, logout, ApiError, get, post, put, del } from "./client";
export {
  WSManager,
  auth as authEndpoints,
  backtest as backtestEndpoints,
  strategies as strategiesEndpoints,
  system as systemEndpoints,
  risk as riskEndpoints,
  portfolio as portfolioEndpoints,
  pollBacktestResult,
} from "@quant/shared";
export type { Channel } from "@quant/shared";
export type {
  BacktestRequest,
  BacktestSummary,
  BacktestResult,
  ManualOrderRequest,
  NavPoint,
  OrderInfo,
  Portfolio,
  Position,
  RiskAlert,
  RiskRule,
  StrategyInfo,
  TradeRecord,
  UserInfo,
  UserRole,
} from "@quant/shared";
