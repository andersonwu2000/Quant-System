package com.quant.trading.data.api

import retrofit2.http.*

/**
 * Retrofit interface — maps 1:1 to backend routes.
 * Mirrors apps/shared/src/api/endpoints.ts
 */
interface QuantApiService {

    // ── Auth ────────────────────────────────────────────────────────────────
    @POST("api/v1/auth/login")
    suspend fun login(@Body body: LoginRequest): LoginResponse

    @POST("api/v1/auth/logout")
    suspend fun logout(): MessageResponse

    @POST("api/v1/auth/change-password")
    suspend fun changePassword(@Body body: ChangePasswordRequest): MessageResponse

    // ── System ──────────────────────────────────────────────────────────────
    @GET("api/v1/system/health")
    suspend fun health(): HealthCheck

    @GET("api/v1/system/status")
    suspend fun systemStatus(): SystemStatus

    @GET("api/v1/system/metrics")
    suspend fun systemMetrics(): SystemMetrics

    // ── Portfolio ───────────────────────────────────────────────────────────
    @GET("api/v1/portfolio")
    suspend fun getPortfolio(): Portfolio

    @GET("api/v1/portfolio/positions")
    suspend fun getPositions(): List<Position>

    @GET("api/v1/portfolio/saved")
    suspend fun listSavedPortfolios(): PortfolioListResponse

    @POST("api/v1/portfolio/saved")
    suspend fun createSavedPortfolio(@Body body: PortfolioCreateRequest): SavedPortfolio

    @GET("api/v1/portfolio/saved/{id}")
    suspend fun getSavedPortfolio(@Path("id") id: String): SavedPortfolio

    @DELETE("api/v1/portfolio/saved/{id}")
    suspend fun deleteSavedPortfolio(@Path("id") id: String): MessageResponse

    @GET("api/v1/portfolio/saved/{id}/trades")
    suspend fun getPortfolioTrades(@Path("id") id: String): List<TradeRecord>

    @POST("api/v1/portfolio/saved/{id}/rebalance-preview")
    suspend fun rebalancePreview(
        @Path("id") id: String,
        @Body body: RebalancePreviewRequest,
    ): RebalancePreviewResponse

    // ── Strategies ──────────────────────────────────────────────────────────
    @GET("api/v1/strategies")
    suspend fun listStrategies(): StrategyListResponse

    @GET("api/v1/strategies/{id}")
    suspend fun getStrategy(@Path("id") id: String): StrategyInfo

    @POST("api/v1/strategies/{id}/start")
    suspend fun startStrategy(@Path("id") id: String): MessageResponse

    @POST("api/v1/strategies/{id}/stop")
    suspend fun stopStrategy(@Path("id") id: String): MessageResponse

    // ── Orders ──────────────────────────────────────────────────────────────
    @GET("api/v1/orders")
    suspend fun listOrders(@Query("status") status: String? = null): List<OrderInfo>

    @POST("api/v1/orders")
    suspend fun createOrder(@Body body: ManualOrderRequest): OrderInfo

    // ── Backtest ────────────────────────────────────────────────────────────
    @POST("api/v1/backtest")
    suspend fun submitBacktest(@Body body: BacktestRequest): BacktestSummary

    @GET("api/v1/backtest/{taskId}")
    suspend fun backtestStatus(@Path("taskId") taskId: String): BacktestSummary

    @GET("api/v1/backtest/{taskId}/result")
    suspend fun backtestResult(@Path("taskId") taskId: String): BacktestResult

    @DELETE("api/v1/backtest/{taskId}")
    suspend fun cancelBacktest(@Path("taskId") taskId: String): MessageResponse

    // ── Alpha ───────────────────────────────────────────────────────────────
    @POST("api/v1/alpha")
    suspend fun runAlpha(@Body body: AlphaRunRequest): AlphaSummary

    @GET("api/v1/alpha/{taskId}")
    suspend fun alphaStatus(@Path("taskId") taskId: String): AlphaSummary

    @GET("api/v1/alpha/{taskId}/result")
    suspend fun alphaResult(@Path("taskId") taskId: String): AlphaReport

    // ── Allocation ──────────────────────────────────────────────────────────
    @POST("api/v1/allocation")
    suspend fun computeAllocation(@Body body: TacticalRequest): TacticalResponse

    // ── Execution ───────────────────────────────────────────────────────────
    @GET("api/v1/execution/status")
    suspend fun executionStatus(): ExecutionStatus

    @GET("api/v1/execution/paper-trading/status")
    suspend fun paperTradingStatus(): PaperTradingStatus

    @GET("api/v1/execution/market-hours")
    suspend fun marketHours(): MarketHoursStatus

    @POST("api/v1/execution/reconcile")
    suspend fun reconcile(): ReconcileResult

    @POST("api/v1/execution/reconcile/auto-correct")
    suspend fun autoCorrect(): AutoCorrectResponse

    @GET("api/v1/execution/queued-orders")
    suspend fun queuedOrders(): QueuedOrdersResponse

    // ── Risk ────────────────────────────────────────────────────────────────
    @GET("api/v1/risk/rules")
    suspend fun riskRules(): List<RiskRule>

    @PUT("api/v1/risk/rules/{name}")
    suspend fun toggleRiskRule(
        @Path("name") name: String,
        @Body body: RiskRuleToggle,
    ): MessageResponse

    @GET("api/v1/risk/alerts")
    suspend fun riskAlerts(): List<RiskAlert>

    @POST("api/v1/risk/kill-switch")
    suspend fun killSwitch(): KillSwitchResponse

    // ── Admin ───────────────────────────────────────────────────────────────
    @GET("api/v1/admin/users")
    suspend fun listUsers(): List<UserInfo>

    @POST("api/v1/admin/users")
    suspend fun createUser(@Body body: Map<String, String>): UserInfo

    @GET("api/v1/admin/users/{id}")
    suspend fun getUser(@Path("id") id: Int): UserInfo

    @PUT("api/v1/admin/users/{id}")
    suspend fun updateUser(@Path("id") id: Int, @Body body: Map<String, String>): UserInfo

    @DELETE("api/v1/admin/users/{id}")
    suspend fun deleteUser(@Path("id") id: Int): MessageResponse

    @POST("api/v1/admin/users/{id}/reset-password")
    suspend fun resetPassword(@Path("id") id: Int, @Body body: Map<String, String>): MessageResponse
}
