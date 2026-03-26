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
  | "ma_cross"
  | "vpt"
  | "reversal"
  | "illiquidity"
  | "ivol"
  | "skewness"
  | "max_ret"
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
  min_listing_days?: number;
  min_avg_volume?: number;
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
  /** Original universe symbols (echoed back from request for UI display) */
  universe?: string[];
  /** Market regime detected during analysis period */
  regime?: string;
}

export interface SystemMetrics {
  uptime_seconds: number;
  total_requests: number;
  active_ws_connections: number;
  strategies_running: number;
  active_backtests: number;
}

// ── Tactical Allocation types ───────────────────────────────────────────────

export type AssetClassName = "EQUITY" | "ETF" | "FUTURE";

export interface TacticalRequest {
  strategic_weights?: Record<AssetClassName, number>;
  start?: string;
  end?: string;
  macro_weight?: number;
  cross_asset_weight?: number;
  regime_weight?: number;
  max_deviation?: number;
}

export interface TacticalWeightItem {
  asset_class: string;
  strategic_weight: number;
  tactical_weight: number;
  deviation: number;
}

export interface MacroSignalItem {
  name: string;
  value: number;
}

export interface TacticalResponse {
  weights: TacticalWeightItem[];
  macro_signals: MacroSignalItem[];
  regime: string;
  cross_asset_signals: Record<string, number>;
}

// ── Execution / Paper Trading types ─────────────────────────────────────────

export interface ExecutionStatus {
  mode: string;
  connected: boolean;
  broker_type: string;
  simulation: boolean;
  queued_orders: number;
}

export interface PaperTradingStatus {
  active: boolean;
  mode: string;
  broker_connected: boolean;
  portfolio_nav: number;
  open_orders: number;
  queued_orders: number;
}

export interface MarketHoursStatus {
  session: string;
  is_tradable: boolean;
  is_odd_lot: boolean;
  next_open: string;
}

export interface ReconcileResult {
  is_clean: boolean;
  matched: number;
  mismatched: number;
  system_only: number;
  broker_only: number;
  details: ReconcileDiff[];
  summary: string;
}

export interface ReconcileDiff {
  symbol: string;
  system_qty: number;
  broker_qty: number;
  diff_qty: number;
  diff_pct: number;
}

export interface QueuedOrdersResponse {
  orders: { symbol: string; timestamp: string }[];
  count: number;
}

// ── Auto-Alpha types ────────────────────────────────────────────────────────

export interface AutoAlphaStatus {
  running: boolean;
  status: string;
  last_run: string | null;
  next_run: string | null;
  regime: string | null;
  selected_factors: string[];
}

export interface AutoAlphaPerformance {
  total_days: number;
  win_rate: number;
  cumulative_return: number;
  max_drawdown: number;
  avg_daily_pnl: number;
  best_day: number;
  worst_day: number;
}

export interface FactorScoreInfo {
  name: string;
  ic: number;
  icir: number;
  hit_rate: number;
  eligible: boolean;
}

export interface AutoAlphaSnapshot {
  id: string;
  date: string;
  regime: string;
  universe_size: number;
  selected_factors: string[];
  trades_count: number;
  turnover: number;
  daily_pnl: number | null;
  cumulative_return: number | null;
}

export interface AutoAlphaSnapshotDetail extends AutoAlphaSnapshot {
  universe: string[];
  factor_scores: Record<string, FactorScoreInfo>;
  factor_weights: Record<string, number>;
  target_weights: Record<string, number>;
}

export interface AutoAlphaAlert {
  timestamp: string;
  level: string;
  category: string;
  message: string;
  details: Record<string, unknown>;
}

export interface AutoAlphaConfig {
  schedule: string;
  eod_schedule: string;
  universe_count: number;
  min_adv: number;
  min_listing_days: number;
  exclude_disposition: boolean;
  exclude_attention: boolean;
  lookback: number;
  max_turnover: number;
  min_trade_value: number;
  max_consecutive_losses: number;
  emergency_stop_drawdown: number;
  kill_switch_cooldown_days: number;
  kill_switch_recovery_position_pct: number;
  backtest_gate_enabled: boolean;
  backtest_gate_lookback: number;
  backtest_gate_min_sharpe: number;
  decision: {
    min_icir: number;
    min_hit_rate: number;
    max_cost_drag: number;
    oos_decay_factor: number;
    regime_aware: boolean;
  };
}

// ── Saved Portfolio types ───────────────────────────────────────────────────

export interface PortfolioListItem {
  id: string;
  name: string;
  cash: number;
  initial_cash: number;
  strategy_name: string;
  position_count: number;
  created_at: string;
}

export interface SavedPortfolio {
  id: string;
  name: string;
  cash: number;
  initial_cash: number;
  strategy_name: string;
  positions: {
    symbol: string;
    quantity: number;
    avg_cost: number;
    market_price: number;
    market_value: number;
    unrealized_pnl: number;
  }[];
  nav: number;
  created_at: string;
}

export interface PortfolioCreateRequest {
  name: string;
  initial_cash?: number;
  strategy_name?: string;
}

export interface RebalancePreviewRequest {
  strategy: string;
  universes: string[];
  params?: Record<string, unknown>;
  slippage_bps?: number;
  commission_rate?: number;
  tax_rate?: number;
}

export interface SuggestedTrade {
  symbol: string;
  side: string;
  quantity: number;
  estimated_price: number;
  estimated_cost: number;
}

export interface RebalancePreviewResponse {
  strategy: string;
  target_weights: Record<string, number>;
  current_weights: Record<string, number>;
  suggested_trades: SuggestedTrade[];
  estimated_total_commission: number;
  estimated_total_tax: number;
}
