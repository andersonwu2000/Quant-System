// Types matching backend Pydantic schemas (src/api/schemas.py)

export type UserRole = "viewer" | "researcher" | "trader" | "risk_manager" | "admin";

export interface UserInfo {
  id: number;
  username: string;
  display_name: string;
  role: UserRole;
  is_active: boolean;
  failed_login_count: number;
  locked_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface Position {
  symbol: string;
  quantity: number;
  avg_cost: number;
  market_price: number;
  market_value: number;
  unrealized_pnl: number;
  weight: number;
}

export interface Portfolio {
  nav: number;
  cash: number;
  gross_exposure: number;
  net_exposure: number;
  positions_count: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  positions: Position[];
  as_of: string;
  nav_history?: { date: string; nav: number }[];
}

export interface StrategyInfo {
  name: string;
  status: "running" | "stopped" | "error";
  pnl: number;
}

export interface OrderInfo {
  id: string;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number | null;
  status: string;
  filled_qty: number;
  filled_avg_price: number;
  commission: number;
  created_at: string;
  strategy_id: string;
}

export interface BacktestRequest {
  strategy: string;
  universe: string[];
  start: string;
  end: string;
  initial_cash: number;
  params: Record<string, unknown>;
  slippage_bps: number;
  commission_rate: number;
  rebalance_freq: "daily" | "weekly" | "monthly";
}

export interface ManualOrderRequest {
  symbol: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number | null; // null = market order
}

export interface BacktestSummary {
  task_id: string;
  status: "running" | "completed" | "failed";
  strategy_name: string;
  total_return: number | null;
  annual_return: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  total_trades: number | null;
  progress_current: number | null;
  progress_total: number | null;
  error: string | null;
}

export interface NavPoint {
  date: string;
  nav: number;
}

export interface TradeRecord {
  date: string;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  commission: number;
}

export interface BacktestResult {
  strategy_name: string;
  start_date: string;
  end_date: string;
  initial_cash: number;
  total_return: number;
  annual_return: number;
  sharpe: number;
  sortino: number;
  calmar: number;
  max_drawdown: number;
  max_drawdown_duration: number;
  volatility: number;
  total_trades: number;
  win_rate: number;
  total_commission: number;
  nav_series: NavPoint[] | null;
  trades?: TradeRecord[];
}

export interface RiskRule {
  name: string;
  enabled: boolean;
}

export interface RiskAlert {
  timestamp: string;
  rule_name: string;
  severity: string;
  metric_value: number;
  threshold: number;
  action_taken: string;
  message: string;
}

export interface SystemStatus {
  mode: string;
  uptime_seconds: number;
  strategies_running: number;
  data_source: string;
  database: string;
}

export interface HealthCheck {
  status: string;
  version: string;
}

// ── Alpha Research types ──────────────────────────────────────────────────────
// Provisional: alpha layer is under code review and may change.
// These types reflect the expected API contract, not the Python dataclasses.

/** Known factor names from FACTOR_REGISTRY. String allows future additions. */
export type FactorName =
  | "momentum"
  | "mean_reversion"
  | "volatility"
  | "rsi"
  | "pe_ratio"
  | "pb_ratio"
  | "roe"
  | "revenue_growth"
  | (string & {});

export interface AlphaFactorSpec {
  name: FactorName;
  /** 1 = higher is better, -1 = lower is better */
  direction: 1 | -1;
}

export interface AlphaRunRequest {
  factors: AlphaFactorSpec[];
  universe: string[];
  start: string;
  end: string;
  neutralize_method?: "market" | "industry" | "size" | "industry_size";
  n_quantiles?: number;
  holding_period?: number;
}

export interface AlphaSummary {
  task_id: string;
  status: "running" | "completed" | "failed";
  progress_current: number | null;
  progress_total: number | null;
  error: string | null;
}

export interface ICResult {
  ic_mean: number;
  ic_std: number;
  icir: number;
  hit_rate: number;
  ic_series?: { date: string; ic: number }[];
}

export interface AlphaTurnoverResult {
  avg_turnover: number;
  cost_drag_annual_bps: number;
  breakeven_cost_bps: number;
}

export interface QuantileReturn {
  quantile: number;
  mean_return: number;
  annual_return: number;
}

export interface FactorReport {
  name: string;
  direction: number;
  ic: ICResult;
  turnover: AlphaTurnoverResult;
  quantile_returns: QuantileReturn[];
  long_short_sharpe: number;
  monotonicity_score: number;
}

export interface AlphaReport {
  task_id: string;
  factors: FactorReport[];
  composite_ic?: ICResult;
  composite_long_short_sharpe?: number;
  composite_quantile_returns?: QuantileReturn[];
  universe_size: number;
  start_date: string;
  end_date: string;
}

export interface SystemMetrics {
  uptime_seconds: number;
  total_requests: number;
  active_ws_connections: number;
  strategies_running: number;
  active_backtests: number;
}
