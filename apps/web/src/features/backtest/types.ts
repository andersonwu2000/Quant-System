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
