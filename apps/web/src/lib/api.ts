const BASE = '/api/v1';

function getApiKey(): string | null {
  return localStorage.getItem('quant-api-key');
}

/* ── API Response Interfaces ─────────────────────────────── */

export interface Portfolio {
  total_value: number;
  cash: number;
  daily_pnl: number;
  positions: Position[];
}

export interface Position {
  symbol: string;
  quantity: number;
  market_value: number;
  last_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface RegimeResponse {
  regime: 'bull' | 'bear' | 'sideways' | 'unknown';
  reason: string;
  indicators: Record<string, number>;
  last_date?: string;
}

export interface SelectionResponse {
  date: string | null;
  weights: Record<string, number>;
  n_targets: number;
  strategy: string;
}

export interface DriftResponse {
  drift: DriftItem[];
  max_drift: number;
  selection_date: string | null;
  n_targets: number;
  n_actual: number;
}

export interface DriftItem {
  symbol: string;
  target_weight: number;
  actual_weight: number;
  drift: number;
  status: 'new' | 'exit' | 'held';
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface DataStatusResponse {
  market_symbols: number;
  revenue_symbols: number;
  institutional_symbols: number;
  latest_revenue_date: string | null;
}

export interface StrategyInfo {
  name: string;
  description: string;
  factor: string;
  rebalance: string;
  bear_scale: number;
  sideways_scale: number;
  max_holdings: number;
  validation: string;
}

export interface RebalanceResponse {
  status: string;
  n_targets: number;
  n_orders: number;
  n_approved: number;
  n_rejected: number;
  trades: any[];
  rejected: any[];
}

export interface BacktestSubmitResponse {
  task_id: string;
}

export interface BacktestResult {
  annual_return: number;
  cagr?: number;
  sharpe: number;
  sortino?: number;
  calmar?: number;
  max_drawdown: number;
  total_return: number;
  total_trades: number;
  win_rate?: number;
  volatility?: number;
}

/* ── Request Helper ──────────────────────────────────────── */

// In-flight request deduplication
const inflight = new Map<string, Promise<any>>();

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const key = getApiKey();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(key ? { 'X-API-Key': key } : {}),
  };

  const method = options.method ?? 'GET';
  const dedupeKey = method === 'GET' ? `${method}:${path}` : '';

  // Deduplicate concurrent GET requests to same endpoint
  if (dedupeKey && inflight.has(dedupeKey)) {
    return inflight.get(dedupeKey)!;
  }

  const promise = (async () => {
    const res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: { ...headers, ...(options.headers as Record<string, string>) },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  })();

  if (dedupeKey) {
    inflight.set(dedupeKey, promise);
    promise.finally(() => inflight.delete(dedupeKey));
  }

  return promise;
}

export const api = {
  // Portfolio
  portfolio: () => request<Portfolio>('/portfolio'),

  // Strategy center
  strategyInfo: () => request<StrategyInfo>('/strategy/info'),
  regime: () => request<RegimeResponse>('/strategy/regime'),
  selectionLatest: () => request<SelectionResponse>('/strategy/selection/latest'),
  selectionHistory: (limit = 12) => request<SelectionResponse[]>(`/strategy/selection/history?limit=${limit}`),
  drift: () => request<DriftResponse>('/strategy/drift'),
  rebalance: () => request<RebalanceResponse>('/strategy/rebalance', { method: 'POST' }),
  dataStatus: () => request<DataStatusResponse>('/strategy/data-status'),

  // Risk
  riskRules: () => request<any[]>('/risk/rules'),
  riskAlerts: () => request<any>('/risk/alerts'),
  riskRealtime: () => request<any>('/risk/realtime'),
  killSwitch: (activate: boolean) => request<any>('/risk/kill-switch', { method: 'POST', body: JSON.stringify({ activate }) }),

  // Backtest
  backtest: (body: Record<string, unknown>) => request<BacktestSubmitResponse>('/backtest', { method: 'POST', body: JSON.stringify(body) }),
  backtestResult: (taskId: string) => request<BacktestResult>(`/backtest/${taskId}/result`),

  // System
  health: () => request<HealthResponse>('/system/health'),

  // Auth
  login: (apiKey: string) => request<{ token: string }>('/auth/login', { method: 'POST', body: JSON.stringify({ api_key: apiKey }) }),
};
