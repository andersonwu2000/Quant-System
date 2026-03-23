/**
 * Typed API endpoints — maps 1:1 to backend routes.
 */

import { get, post, put } from "./client";
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
} from "../types";

export const auth = {
  login: (apiKey: string) =>
    post<{ access_token: string; token_type: string }>("/api/v1/auth/login", { api_key: apiKey }),
  logout: () => post<{ detail: string }>("/api/v1/auth/logout", {}),
};

export const system = {
  health: () => get<HealthCheck>("/api/v1/system/health"),
  status: () => get<SystemStatus>("/api/v1/system/status"),
  metrics: () => get<SystemMetrics>("/api/v1/system/metrics"),
};

export const portfolio = {
  get: () => get<Portfolio>("/api/v1/portfolio"),
  positions: () => get<Position[]>("/api/v1/portfolio/positions"),
};

export const strategies = {
  list: () =>
    get<{ strategies: StrategyInfo[] }>("/api/v1/strategies").then(
      (r) => r.strategies,
    ),
  get: (id: string) => get<StrategyInfo>(`/api/v1/strategies/${id}`),
  start: (id: string, params?: Record<string, unknown>) =>
    post<StrategyInfo>(`/api/v1/strategies/${id}/start`, params ? { params } : undefined),
  stop: (id: string) =>
    post<StrategyInfo>(`/api/v1/strategies/${id}/stop`),
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

export const risk = {
  rules: () => get<RiskRule[]>("/api/v1/risk/rules"),
  toggleRule: (name: string, enabled: boolean) =>
    put<RiskRule>(`/api/v1/risk/rules/${name}`, { enabled }),
  alerts: () => get<RiskAlert[]>("/api/v1/risk/alerts"),
  killSwitch: () => post<{ detail: string }>("/api/v1/risk/kill-switch"),
};
