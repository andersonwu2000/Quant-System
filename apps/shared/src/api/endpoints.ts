/**
 * Typed API endpoints — maps 1:1 to backend routes.
 */

import { get, post, put, del } from "./client";
import type {
  Portfolio,
  Position,
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
  AlphaRunRequest,
  AlphaSummary,
  AlphaReport,
  TacticalRequest,
  TacticalResponse,
  ExecutionStatus,
  PaperTradingStatus,
  MarketHoursStatus,
  ReconcileResult,
  QueuedOrdersResponse,
  PortfolioListItem,
  SavedPortfolio,
  PortfolioCreateRequest,
  RebalancePreviewRequest,
  RebalancePreviewResponse,
  TradeRecord,
  AutoAlphaStatus,
  AutoAlphaPerformance,
  AutoAlphaSnapshot,
  AutoAlphaAlert,
  AutoAlphaConfig,
} from "../types";

export const auth = {
  login: (apiKey: string) =>
    post<{ access_token: string; token_type: string }>("/api/v1/auth/login", { api_key: apiKey }),
  logout: () => post<{ detail: string }>("/api/v1/auth/logout", {}),
  changePassword: (currentPassword: string, newPassword: string) =>
    post<{ message: string }>("/api/v1/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    }),
};

export const system = {
  health: () => get<HealthCheck>("/api/v1/system/health"),
  status: () => get<SystemStatus>("/api/v1/system/status"),
  metrics: () => get<SystemMetrics>("/api/v1/system/metrics"),
};

export const portfolio = {
  get: () => get<Portfolio>("/api/v1/portfolio"),
  positions: () => get<Position[]>("/api/v1/portfolio/positions"),
  listSaved: () =>
    get<{ portfolios: PortfolioListItem[] }>("/api/v1/portfolio/saved").then(
      (r) => r.portfolios,
    ),
  createSaved: (req: PortfolioCreateRequest) =>
    post<SavedPortfolio>("/api/v1/portfolio/saved", req),
  getSaved: (id: string) =>
    get<SavedPortfolio>(`/api/v1/portfolio/saved/${id}`),
  deleteSaved: (id: string) =>
    del<{ message: string }>(`/api/v1/portfolio/saved/${id}`),
  trades: (id: string) =>
    get<TradeRecord[]>(`/api/v1/portfolio/saved/${id}/trades`),
  rebalancePreview: (id: string, req: RebalancePreviewRequest) =>
    post<RebalancePreviewResponse>(
      `/api/v1/portfolio/saved/${id}/rebalance-preview`,
      req,
    ),
};

export const strategies = {
  list: () =>
    get<{ strategies: StrategyInfo[] }>("/api/v1/strategies").then(
      (r) => r.strategies,
    ),
  get: (id: string) => get<StrategyInfo>(`/api/v1/strategies/${id}`),
  start: (id: string, params?: Record<string, unknown>) =>
    post<{ message: string }>(`/api/v1/strategies/${id}/start`, params ? { params } : undefined),
  stop: (id: string) =>
    post<{ message: string }>(`/api/v1/strategies/${id}/stop`),
};

export const orders = {
  list: (status?: "open" | "filled") => {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    return get<OrderInfo[]>(`/api/v1/orders${query}`);
  },
  create: (req: ManualOrderRequest) =>
    post<OrderInfo>("/api/v1/orders", req),
};

export const backtest = {
  submit: (req: BacktestRequest) =>
    post<BacktestSummary>("/api/v1/backtest", req),
  status: (taskId: string) =>
    get<BacktestSummary>(`/api/v1/backtest/${taskId}`),
  result: (taskId: string) =>
    get<BacktestResult>(`/api/v1/backtest/${taskId}/result`),
};

export const alpha = {
  run: (req: AlphaRunRequest) =>
    post<AlphaSummary>("/api/v1/alpha", req),
  status: (taskId: string) =>
    get<AlphaSummary>(`/api/v1/alpha/${taskId}`),
  result: (taskId: string) =>
    get<AlphaReport>(`/api/v1/alpha/${taskId}/result`),
};

export const allocation = {
  compute: (req: TacticalRequest) =>
    post<TacticalResponse>("/api/v1/allocation", req),
};

export const execution = {
  status: () => get<ExecutionStatus>("/api/v1/execution/status"),
  paperTradingStatus: () => get<PaperTradingStatus>("/api/v1/execution/paper-trading/status"),
  marketHours: () => get<MarketHoursStatus>("/api/v1/execution/market-hours"),
  reconcile: () => post<ReconcileResult>("/api/v1/execution/reconcile"),
  autoCorrect: () => post<{ corrections: string[]; count: number }>("/api/v1/execution/reconcile/auto-correct"),
  queuedOrders: () => get<QueuedOrdersResponse>("/api/v1/execution/queued-orders"),
};

export const autoAlpha = {
  status: () => get<AutoAlphaStatus>("/api/v1/auto-alpha/status"),
  performance: () => get<AutoAlphaPerformance>("/api/v1/auto-alpha/performance"),
  history: (limit = 30) => get<AutoAlphaSnapshot[]>(`/api/v1/auto-alpha/history?limit=${limit}`),
  alerts: (limit = 50) => get<AutoAlphaAlert[]>(`/api/v1/auto-alpha/alerts?limit=${limit}`),
  config: () => get<AutoAlphaConfig>("/api/v1/auto-alpha/config"),
  updateConfig: (data: Partial<AutoAlphaConfig>) => put<AutoAlphaConfig>("/api/v1/auto-alpha/config", data),
  start: () => post<{ message: string }>("/api/v1/auto-alpha/start"),
  stop: () => post<{ message: string }>("/api/v1/auto-alpha/stop"),
  runNow: () => post<{ task_id: string }>("/api/v1/auto-alpha/run-now"),
  taskStatus: (taskId: string) => get<{
    task_id: string;
    status: string;
    stage?: string;
    symbols_loaded?: number;
    factors_computed?: number;
    selected_factors?: string[];
    regime?: string;
    error?: string;
    started?: string;
    completed?: string;
  }>(`/api/v1/auto-alpha/run-now/${taskId}`),
};

export const risk = {
  rules: () => get<RiskRule[]>("/api/v1/risk/rules"),
  toggleRule: (name: string, enabled: boolean) =>
    put<{ message: string }>(`/api/v1/risk/rules/${name}`, { enabled }),
  alerts: () => get<RiskAlert[]>("/api/v1/risk/alerts"),
  killSwitch: () => post<{ message: string; strategies_stopped: number; orders_cancelled: number }>("/api/v1/risk/kill-switch"),
};
