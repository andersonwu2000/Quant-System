package com.quant.trading.data.api

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// ── Auth ────────────────────────────────────────────────────────────────────

@Serializable
data class LoginRequest(
    @SerialName("api_key") val apiKey: String? = null,
    val username: String? = null,
    val password: String? = null,
)

@Serializable
data class LoginResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String,
)

@Serializable
data class ChangePasswordRequest(
    @SerialName("current_password") val currentPassword: String,
    @SerialName("new_password") val newPassword: String,
)

@Serializable
data class MessageResponse(val detail: String? = null, val message: String? = null)

// ── Portfolio ───────────────────────────────────────────────────────────────

@Serializable
data class Position(
    val symbol: String,
    val quantity: Double,
    @SerialName("avg_cost") val avgCost: Double,
    @SerialName("market_price") val marketPrice: Double,
    @SerialName("market_value") val marketValue: Double,
    @SerialName("unrealized_pnl") val unrealizedPnl: Double,
    val weight: Double,
)

@Serializable
data class NavPoint(val date: String, val nav: Double)

@Serializable
data class Portfolio(
    val nav: Double,
    val cash: Double,
    @SerialName("gross_exposure") val grossExposure: Double,
    @SerialName("net_exposure") val netExposure: Double,
    @SerialName("positions_count") val positionsCount: Int,
    @SerialName("daily_pnl") val dailyPnl: Double,
    @SerialName("daily_pnl_pct") val dailyPnlPct: Double,
    val positions: List<Position>,
    @SerialName("as_of") val asOf: String,
    @SerialName("nav_history") val navHistory: List<NavPoint>? = null,
)

@Serializable
data class PortfolioListItem(
    val id: String,
    val name: String,
    val cash: Double,
    @SerialName("initial_cash") val initialCash: Double,
    @SerialName("strategy_name") val strategyName: String,
    @SerialName("position_count") val positionCount: Int,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class SavedPortfolioPosition(
    val symbol: String,
    val quantity: Double,
    @SerialName("avg_cost") val avgCost: Double,
    @SerialName("market_price") val marketPrice: Double,
    @SerialName("market_value") val marketValue: Double,
    @SerialName("unrealized_pnl") val unrealizedPnl: Double,
)

@Serializable
data class SavedPortfolio(
    val id: String,
    val name: String,
    val cash: Double,
    @SerialName("initial_cash") val initialCash: Double,
    @SerialName("strategy_name") val strategyName: String,
    val positions: List<SavedPortfolioPosition>,
    val nav: Double,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class PortfolioCreateRequest(
    val name: String,
    @SerialName("initial_cash") val initialCash: Double? = null,
    @SerialName("strategy_name") val strategyName: String? = null,
)

@Serializable
data class PortfolioListResponse(val portfolios: List<PortfolioListItem>)

@Serializable
data class RebalancePreviewRequest(
    val strategy: String,
    val universes: List<String>,
    val params: Map<String, kotlinx.serialization.json.JsonElement>? = null,
    @SerialName("slippage_bps") val slippageBps: Double? = null,
    @SerialName("commission_rate") val commissionRate: Double? = null,
    @SerialName("tax_rate") val taxRate: Double? = null,
)

@Serializable
data class SuggestedTrade(
    val symbol: String,
    val side: String,
    val quantity: Int,
    @SerialName("estimated_price") val estimatedPrice: Double,
    @SerialName("estimated_cost") val estimatedCost: Double,
)

@Serializable
data class RebalancePreviewResponse(
    val strategy: String,
    @SerialName("target_weights") val targetWeights: Map<String, Double>,
    @SerialName("current_weights") val currentWeights: Map<String, Double>,
    @SerialName("suggested_trades") val suggestedTrades: List<SuggestedTrade>,
    @SerialName("estimated_total_commission") val estimatedTotalCommission: Double,
    @SerialName("estimated_total_tax") val estimatedTotalTax: Double,
)

@Serializable
data class TradeRecord(
    val date: String,
    val symbol: String,
    val side: String,
    val quantity: Int,
    val price: Double,
    val commission: Double,
)

// ── Strategies ──────────────────────────────────────────────────────────────

@Serializable
data class StrategyInfo(
    val name: String,
    val status: String,
    val pnl: Double,
)

@Serializable
data class StrategyListResponse(val strategies: List<StrategyInfo>)

// ── Orders ──────────────────────────────────────────────────────────────────

@Serializable
data class OrderInfo(
    val id: String,
    val symbol: String,
    val side: String,
    val quantity: Int,
    val price: Double? = null,
    val status: String,
    @SerialName("filled_qty") val filledQty: Int,
    @SerialName("filled_avg_price") val filledAvgPrice: Double,
    val commission: Double,
    @SerialName("created_at") val createdAt: String,
    @SerialName("strategy_id") val strategyId: String,
)

@Serializable
data class ManualOrderRequest(
    val symbol: String,
    val side: String,
    val quantity: Int,
    val price: Double? = null,
)

// ── Backtest ────────────────────────────────────────────────────────────────

@Serializable
data class BacktestRequest(
    val strategy: String,
    val universe: List<String>,
    val start: String,
    val end: String,
    @SerialName("initial_cash") val initialCash: Double = 1_000_000.0,
    val params: Map<String, kotlinx.serialization.json.JsonElement> = emptyMap(),
    @SerialName("slippage_bps") val slippageBps: Double = 5.0,
    @SerialName("commission_rate") val commissionRate: Double = 0.001425,
    @SerialName("rebalance_freq") val rebalanceFreq: String = "daily",
)

@Serializable
data class BacktestSummary(
    @SerialName("task_id") val taskId: String,
    val status: String,
    @SerialName("strategy_name") val strategyName: String,
    @SerialName("total_return") val totalReturn: Double? = null,
    @SerialName("annual_return") val annualReturn: Double? = null,
    val sharpe: Double? = null,
    @SerialName("max_drawdown") val maxDrawdown: Double? = null,
    @SerialName("total_trades") val totalTrades: Int? = null,
    @SerialName("progress_current") val progressCurrent: Int? = null,
    @SerialName("progress_total") val progressTotal: Int? = null,
    val error: String? = null,
)

@Serializable
data class BacktestResult(
    @SerialName("strategy_name") val strategyName: String,
    @SerialName("start_date") val startDate: String,
    @SerialName("end_date") val endDate: String,
    @SerialName("initial_cash") val initialCash: Double,
    @SerialName("total_return") val totalReturn: Double,
    @SerialName("annual_return") val annualReturn: Double,
    val sharpe: Double,
    val sortino: Double,
    val calmar: Double,
    @SerialName("max_drawdown") val maxDrawdown: Double,
    @SerialName("max_drawdown_duration") val maxDrawdownDuration: Int,
    val volatility: Double,
    @SerialName("total_trades") val totalTrades: Int,
    @SerialName("win_rate") val winRate: Double,
    @SerialName("total_commission") val totalCommission: Double,
    @SerialName("nav_series") val navSeries: List<NavPoint>? = null,
    val trades: List<TradeRecord>? = null,
)

// ── Alpha Research ──────────────────────────────────────────────────────────

@Serializable
data class AlphaFactorSpec(
    val name: String,
    val direction: Int,
)

@Serializable
data class AlphaRunRequest(
    val factors: List<AlphaFactorSpec>,
    val universe: List<String>,
    val start: String,
    val end: String,
    @SerialName("neutralize_method") val neutralizeMethod: String? = null,
    @SerialName("n_quantiles") val nQuantiles: Int? = null,
    @SerialName("holding_period") val holdingPeriod: Int? = null,
)

@Serializable
data class AlphaSummary(
    @SerialName("task_id") val taskId: String,
    val status: String,
    @SerialName("progress_current") val progressCurrent: Int? = null,
    @SerialName("progress_total") val progressTotal: Int? = null,
    val error: String? = null,
)

@Serializable
data class ICResult(
    @SerialName("ic_mean") val icMean: Double,
    @SerialName("ic_std") val icStd: Double,
    val icir: Double,
    @SerialName("hit_rate") val hitRate: Double,
    @SerialName("ic_series") val icSeries: List<ICPoint>? = null,
)

@Serializable
data class ICPoint(val date: String, val ic: Double)

@Serializable
data class AlphaTurnoverResult(
    @SerialName("avg_turnover") val avgTurnover: Double,
    @SerialName("cost_drag_annual_bps") val costDragAnnualBps: Double,
    @SerialName("breakeven_cost_bps") val breakevenCostBps: Double,
)

@Serializable
data class QuantileReturn(
    val quantile: Int,
    @SerialName("mean_return") val meanReturn: Double,
    @SerialName("annual_return") val annualReturn: Double,
)

@Serializable
data class FactorReport(
    val name: String,
    val direction: Int,
    val ic: ICResult,
    val turnover: AlphaTurnoverResult,
    @SerialName("quantile_returns") val quantileReturns: List<QuantileReturn>,
    @SerialName("long_short_sharpe") val longShortSharpe: Double,
    @SerialName("monotonicity_score") val monotonicityScore: Double,
)

@Serializable
data class AlphaReport(
    @SerialName("task_id") val taskId: String,
    val factors: List<FactorReport>,
    @SerialName("composite_ic") val compositeIc: ICResult? = null,
    @SerialName("composite_long_short_sharpe") val compositeLongShortSharpe: Double? = null,
    @SerialName("composite_quantile_returns") val compositeQuantileReturns: List<QuantileReturn>? = null,
    @SerialName("universe_size") val universeSize: Int,
    @SerialName("start_date") val startDate: String,
    @SerialName("end_date") val endDate: String,
)

// ── Allocation ──────────────────────────────────────────────────────────────

@Serializable
data class TacticalRequest(
    @SerialName("strategic_weights") val strategicWeights: Map<String, Double>? = null,
    val start: String? = null,
    val end: String? = null,
    @SerialName("macro_weight") val macroWeight: Double? = null,
    @SerialName("cross_asset_weight") val crossAssetWeight: Double? = null,
    @SerialName("regime_weight") val regimeWeight: Double? = null,
    @SerialName("max_deviation") val maxDeviation: Double? = null,
)

@Serializable
data class TacticalWeightItem(
    @SerialName("asset_class") val assetClass: String,
    @SerialName("strategic_weight") val strategicWeight: Double,
    @SerialName("tactical_weight") val tacticalWeight: Double,
    val deviation: Double,
)

@Serializable
data class MacroSignalItem(val name: String, val value: Double)

@Serializable
data class TacticalResponse(
    val weights: List<TacticalWeightItem>,
    @SerialName("macro_signals") val macroSignals: List<MacroSignalItem>,
    val regime: String,
    @SerialName("cross_asset_signals") val crossAssetSignals: Map<String, Double>,
)

// ── Execution / Paper Trading ───────────────────────────────────────────────

@Serializable
data class ExecutionStatus(
    val mode: String,
    val connected: Boolean,
    @SerialName("broker_type") val brokerType: String,
    val simulation: Boolean,
    @SerialName("queued_orders") val queuedOrders: Int,
)

@Serializable
data class PaperTradingStatus(
    val active: Boolean,
    val mode: String,
    @SerialName("broker_connected") val brokerConnected: Boolean,
    @SerialName("portfolio_nav") val portfolioNav: Double,
    @SerialName("open_orders") val openOrders: Int,
    @SerialName("queued_orders") val queuedOrders: Int,
)

@Serializable
data class MarketHoursStatus(
    val session: String,
    @SerialName("is_tradable") val isTradable: Boolean,
    @SerialName("is_odd_lot") val isOddLot: Boolean,
    @SerialName("next_open") val nextOpen: String,
)

@Serializable
data class ReconcileDiff(
    val symbol: String,
    @SerialName("system_qty") val systemQty: Double,
    @SerialName("broker_qty") val brokerQty: Double,
    @SerialName("diff_qty") val diffQty: Double,
    @SerialName("diff_pct") val diffPct: Double,
)

@Serializable
data class ReconcileResult(
    @SerialName("is_clean") val isClean: Boolean,
    val matched: Int,
    val mismatched: Int,
    @SerialName("system_only") val systemOnly: Int,
    @SerialName("broker_only") val brokerOnly: Int,
    val details: List<ReconcileDiff>,
    val summary: String,
)

@Serializable
data class QueuedOrder(val symbol: String, val timestamp: String)

@Serializable
data class QueuedOrdersResponse(val orders: List<QueuedOrder>, val count: Int)

@Serializable
data class AutoCorrectResponse(val corrections: List<String>, val count: Int)

// ── Risk ────────────────────────────────────────────────────────────────────

@Serializable
data class RiskRule(val name: String, val enabled: Boolean)

@Serializable
data class RiskRuleToggle(val enabled: Boolean)

@Serializable
data class RiskAlert(
    val timestamp: String,
    @SerialName("rule_name") val ruleName: String,
    val severity: String,
    @SerialName("metric_value") val metricValue: Double,
    val threshold: Double,
    @SerialName("action_taken") val actionTaken: String,
    val message: String,
)

@Serializable
data class KillSwitchResponse(
    val message: String,
    @SerialName("strategies_stopped") val strategiesStopped: Int,
    @SerialName("orders_cancelled") val ordersCancelled: Int,
)

// ── System ──────────────────────────────────────────────────────────────────

@Serializable
data class HealthCheck(val status: String, val version: String)

@Serializable
data class SystemStatus(
    val mode: String,
    @SerialName("uptime_seconds") val uptimeSeconds: Double,
    @SerialName("strategies_running") val strategiesRunning: Int,
    @SerialName("data_source") val dataSource: String,
    val database: String,
)

@Serializable
data class SystemMetrics(
    @SerialName("uptime_seconds") val uptimeSeconds: Double,
    @SerialName("total_requests") val totalRequests: Int,
    @SerialName("active_ws_connections") val activeWsConnections: Int,
    @SerialName("strategies_running") val strategiesRunning: Int,
    @SerialName("active_backtests") val activeBacktests: Int,
)

// ── Admin ───────────────────────────────────────────────────────────────────

@Serializable
data class UserInfo(
    val id: Int,
    val username: String,
    @SerialName("display_name") val displayName: String,
    val role: String,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("failed_login_count") val failedLoginCount: Int,
    @SerialName("locked_until") val lockedUntil: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)
