// Types matching backend Pydantic schemas (src/api/schemas.py)

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

export interface BacktestSummary {
  task_id: string;
  status: "running" | "completed" | "failed";
  strategy_name: string;
  total_return: number | null;
  annual_return: number | null;
  sharpe: number | null;
  max_drawdown: number | null;
  total_trades: number | null;
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
  nav_series: { date: string; nav: number }[] | null;
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
