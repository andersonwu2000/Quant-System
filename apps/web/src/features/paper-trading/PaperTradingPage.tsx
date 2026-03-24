import { useState, useCallback, useRef, useEffect } from "react";
import { useApi, useWs } from "@core/hooks";
import { useT } from "@core/i18n";
import { useAuth } from "@core/auth";
import { Card, MetricCard, ErrorAlert, HelpTip, StatusBadge } from "@shared/ui";
import { fmtCurrency, fmtPrice, fmtDate, fmtTime, pnlColor, translateApiError } from "@core/utils";
import { paperTradingApi } from "./api";
import { portfolioApi } from "@feat/portfolio/api";
import { ordersApi } from "@feat/orders/api";
import { strategiesApi } from "@feat/strategies/api";
import { Play, Square } from "lucide-react";
import type {
  PaperTradingStatus,
  MarketHoursStatus,
  ExecutionStatus,
  ReconcileResult,
  StrategyInfo,
  Portfolio,
  OrderInfo,
} from "@core/api";

export function PaperTradingPage() {
  const { t } = useT();
  const { hasRole } = useAuth();
  const canTrade = hasRole("trader");
  const canManageRisk = hasRole("risk_manager");

  // --- Data fetching ---
  const { data: execStatus, loading: execLoading, error: execError } = useApi<ExecutionStatus>(paperTradingApi.status);
  const { data: ptStatus, loading: ptLoading } = useApi<PaperTradingStatus>(paperTradingApi.paperTradingStatus);
  const { data: hours } = useApi<MarketHoursStatus>(paperTradingApi.marketHours);
  const { data: strats, refresh: refreshStrats } = useApi<StrategyInfo[]>(strategiesApi.list);
  const { data: portfolio, refresh: refreshPortfolio } = useApi<Portfolio>(portfolioApi.get);
  const { data: recentOrders, refresh: refreshOrders } = useApi<OrderInfo[]>(() => ordersApi.list());

  // --- WebSocket real-time updates ---
  const ordersTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const portfolioTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (ordersTimerRef.current) clearTimeout(ordersTimerRef.current);
      if (portfolioTimerRef.current) clearTimeout(portfolioTimerRef.current);
    };
  }, []);

  useWs(
    "orders",
    useCallback(
      (msg: unknown) => {
        if (msg && typeof msg === "object") {
          if (!ordersTimerRef.current) {
            ordersTimerRef.current = setTimeout(() => {
              ordersTimerRef.current = null;
              if (mountedRef.current) refreshOrders();
            }, 1000);
          }
        }
      },
      [refreshOrders],
    ),
  );

  useWs(
    "portfolio",
    useCallback(
      (msg: unknown) => {
        if (msg && typeof msg === "object") {
          if (!portfolioTimerRef.current) {
            portfolioTimerRef.current = setTimeout(() => {
              portfolioTimerRef.current = null;
              if (mountedRef.current) refreshPortfolio();
            }, 1000);
          }
        }
      },
      [refreshPortfolio],
    ),
  );

  // --- Strategy control ---
  const [selectedStrategy, setSelectedStrategy] = useState("");
  const [toggling, setToggling] = useState(false);
  const [stratError, setStratError] = useState<string | null>(null);

  const handleStartStrategy = useCallback(async () => {
    if (!selectedStrategy) return;
    setToggling(true);
    setStratError(null);
    try {
      await strategiesApi.start(selectedStrategy);
      refreshStrats();
    } catch (e) {
      setStratError(translateApiError(e instanceof Error ? e.message : String(e), t));
    } finally {
      setToggling(false);
    }
  }, [selectedStrategy, refreshStrats, t]);

  const handleStopStrategy = useCallback(async (name: string) => {
    setToggling(true);
    setStratError(null);
    try {
      await strategiesApi.stop(name);
      refreshStrats();
    } catch (e) {
      setStratError(translateApiError(e instanceof Error ? e.message : String(e), t));
    } finally {
      setToggling(false);
    }
  }, [refreshStrats, t]);

  // --- Reconciliation ---
  const [reconcileResult, setReconcileResult] = useState<ReconcileResult | null>(null);
  const [reconcileLoading, setReconcileLoading] = useState(false);
  const [reconcileError, setReconcileError] = useState<string | null>(null);

  const handleReconcile = useCallback(async () => {
    setReconcileLoading(true);
    setReconcileError(null);
    try {
      const result = await paperTradingApi.reconcile();
      setReconcileResult(result);
    } catch (e) {
      setReconcileError(e instanceof Error ? e.message : String(e));
    } finally {
      setReconcileLoading(false);
    }
  }, []);

  const handleAutoCorrect = useCallback(async () => {
    try {
      await paperTradingApi.autoCorrect();
      handleReconcile();
    } catch (e) {
      setReconcileError(e instanceof Error ? e.message : String(e));
    }
  }, [handleReconcile]);

  const loading = execLoading || ptLoading;
  const isBacktestMode = execStatus?.mode === "backtest";
  const isConnected = execStatus?.connected ?? false;
  const runningStrats = strats?.filter((s) => s.status === "running") ?? [];
  const last20Orders = recentOrders?.slice(0, 20) ?? [];

  const sessionLabel = hours
    ? (t.paperTrading.sessionLabels as Record<string, string>)[hours.session] ?? hours.session
    : "\u2014";

  return (
    <div className="space-y-6">
      {execError && <ErrorAlert message={execError} />}

      {/* Connection status + Backtest warning */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className={`inline-block w-2.5 h-2.5 rounded-full ${isConnected ? "bg-emerald-500" : "bg-red-500"}`} />
          <span className="text-sm text-slate-600 dark:text-slate-400">
            {isConnected ? t.paperTrading.connected : t.paperTrading.disconnected}
          </span>
        </div>
        <span className="text-sm text-slate-400">
          {execStatus?.mode === "paper" ? t.paperTrading.paperMode
            : execStatus?.mode === "live" ? t.paperTrading.liveMode
            : t.paperTrading.backtestMode}
        </span>
      </div>

      {!loading && isBacktestMode && (
        <Card className="p-5 border-amber-300 dark:border-amber-500/40 bg-amber-50 dark:bg-amber-500/10">
          <p className="text-sm text-amber-700 dark:text-amber-400">{t.paperTrading.notInitialized}</p>
        </Card>
      )}

      {/* Performance Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label={t.paperTrading.portfolioNav}
          value={ptStatus ? fmtCurrency(ptStatus.portfolio_nav) : "\u2014"}
          help={<HelpTip term="nav" />}
        />
        <MetricCard
          label={t.portfolio.dailyPnl}
          value={portfolio ? fmtCurrency(portfolio.daily_pnl) : "\u2014"}
        />
        <MetricCard
          label={t.paperTrading.openOrders}
          value={String(ptStatus?.open_orders ?? 0)}
        />
        <MetricCard
          label={t.paperTrading.queuedOrders}
          value={String(ptStatus?.queued_orders ?? 0)}
        />
      </div>

      {/* Strategy Control Panel */}
      {canTrade && (
        <Card className="p-5 space-y-4">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100">{t.strategies.title}</h3>

          {stratError && <ErrorAlert message={stratError} />}

          <div className="flex items-center gap-3">
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              className="flex-1 max-w-xs px-3 py-2 rounded-lg border border-slate-300 dark:border-surface-light bg-white dark:bg-surface-dark text-sm text-slate-800 dark:text-slate-200"
            >
              <option value="">{t.paperTrading.selectStrategy}</option>
              {strats?.map((s) => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
            <button
              onClick={handleStartStrategy}
              disabled={!selectedStrategy || toggling}
              className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
            >
              <Play size={14} /> {t.strategies.start}
            </button>
          </div>

          {/* Running strategies */}
          {runningStrats.length > 0 && (
            <div className="space-y-2">
              {runningStrats.map((s) => (
                <div key={s.name} className="flex items-center justify-between px-3 py-2 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-200 dark:border-emerald-500/20">
                  <div className="flex items-center gap-3">
                    <StatusBadge status={s.status} />
                    <span className="text-sm font-medium">{s.name}</span>
                    <span className={`text-sm ${pnlColor(s.pnl)}`}>{fmtCurrency(s.pnl)}</span>
                  </div>
                  <button
                    onClick={() => handleStopStrategy(s.name)}
                    disabled={toggling}
                    className="flex items-center gap-2 px-3 py-1.5 bg-red-100 dark:bg-red-500/15 text-red-700 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-500/25 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
                  >
                    <Square size={14} /> {t.strategies.stop}
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Current Positions Table */}
      {portfolio && portfolio.positions.length > 0 && (
        <Card className="p-5 overflow-x-auto">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-3">{t.portfolio.title}</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 border-b border-slate-200 dark:border-surface-light">
                <th className="text-left py-2">{t.portfolio.symbol}</th>
                <th className="text-right py-2">{t.portfolio.quantity}</th>
                <th className="text-right py-2">{t.portfolio.avgCost}</th>
                <th className="text-right py-2">{t.portfolio.price}</th>
                <th className="text-right py-2">{t.portfolio.marketValue}</th>
                <th className="text-right py-2">{t.portfolio.unrealizedPnl}</th>
              </tr>
            </thead>
            <tbody>
              {portfolio.positions.map((p) => (
                <tr key={p.symbol} className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30">
                  <td className="py-2 font-medium">{p.symbol}</td>
                  <td className="text-right py-2 tabular-nums">{p.quantity}</td>
                  <td className="text-right py-2 tabular-nums">{p.avg_cost != null ? fmtPrice(p.avg_cost) : "\u2014"}</td>
                  <td className="text-right py-2 tabular-nums">{p.market_price != null ? fmtPrice(p.market_price) : "\u2014"}</td>
                  <td className="text-right py-2 tabular-nums">{fmtCurrency(p.market_value)}</td>
                  <td className={`text-right py-2 tabular-nums ${pnlColor(p.unrealized_pnl)}`}>
                    {fmtCurrency(p.unrealized_pnl)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Recent Orders */}
      {last20Orders.length > 0 && (
        <Card className="p-5 overflow-x-auto">
          <h3 className="font-semibold text-slate-800 dark:text-slate-100 mb-3">{t.orders.title}</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-slate-500 border-b border-slate-200 dark:border-surface-light">
                <th className="text-left py-2">{t.orders.time}</th>
                <th className="text-left py-2">{t.orders.symbol}</th>
                <th className="text-left py-2">{t.orders.side}</th>
                <th className="text-right py-2">{t.orders.qty}</th>
                <th className="text-right py-2">{t.orders.price}</th>
                <th className="text-left py-2">{t.orders.status}</th>
              </tr>
            </thead>
            <tbody>
              {last20Orders.map((o) => (
                <tr key={o.id} className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30">
                  <td className="py-2 whitespace-nowrap">
                    <span className="text-slate-400">{fmtDate(o.created_at)}</span>{" "}
                    {fmtTime(o.created_at)}
                  </td>
                  <td className="py-2 font-medium">{o.symbol}</td>
                  <td className={`py-2 font-medium ${o.side === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                    {o.side}
                  </td>
                  <td className="text-right py-2 tabular-nums">{o.quantity}</td>
                  <td className="text-right py-2 tabular-nums">{o.price != null ? fmtPrice(o.price) : "MKT"}</td>
                  <td className="py-2"><StatusBadge status={o.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Market Hours */}
      {hours && (
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">{t.paperTrading.marketHours}</h3>
            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold ${
              hours.is_tradable ? "bg-emerald-500/20 text-emerald-400" : "bg-slate-500/20 text-slate-400"
            }`}>
              {hours.is_tradable ? t.paperTrading.tradable : t.paperTrading.notTradable}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
            <div>
              <span className="text-slate-500 dark:text-slate-400">{t.paperTrading.session}</span>
              <p className="font-medium mt-0.5">{sessionLabel}</p>
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400">{t.paperTrading.oddLot}</span>
              <p className="font-medium mt-0.5">{hours.is_odd_lot ? "Yes" : "No"}</p>
            </div>
            <div>
              <span className="text-slate-500 dark:text-slate-400">{t.paperTrading.nextOpen}</span>
              <p className="font-medium mt-0.5">{fmtDate(hours.next_open)} {fmtTime(hours.next_open)}</p>
            </div>
          </div>
        </Card>
      )}

      {/* Reconciliation */}
      {canTrade && !isBacktestMode && (
        <Card className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-slate-800 dark:text-slate-100">{t.paperTrading.reconciliation}</h3>
            <div className="flex gap-2">
              <button
                onClick={handleReconcile}
                disabled={reconcileLoading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
              >
                {reconcileLoading ? "..." : t.paperTrading.reconcile}
              </button>
              {canManageRisk && reconcileResult && !reconcileResult.is_clean && (
                <button
                  onClick={handleAutoCorrect}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-500 rounded-lg text-sm font-medium text-white transition-colors"
                >
                  {t.paperTrading.autoCorrect}
                </button>
              )}
            </div>
          </div>

          {reconcileError && <ErrorAlert message={reconcileError} />}

          {reconcileResult && (
            <>
              <div className="flex gap-3 text-sm">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold ${
                  reconcileResult.is_clean ? "bg-emerald-500/20 text-emerald-400" : "bg-amber-500/20 text-amber-400"
                }`}>
                  {reconcileResult.is_clean ? t.paperTrading.clean : t.paperTrading.discrepancy}
                </span>
                <span className="text-slate-500 dark:text-slate-400">
                  {t.paperTrading.matched}: {reconcileResult.matched}
                  {" / "}
                  {t.paperTrading.mismatched}: {reconcileResult.mismatched}
                </span>
              </div>

              {reconcileResult.details.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-surface-light text-slate-500">
                        <th className="text-left py-2 pr-4">{t.paperTrading.symbol}</th>
                        <th className="text-right py-2 pr-4">{t.paperTrading.systemQty}</th>
                        <th className="text-right py-2 pr-4">{t.paperTrading.brokerQty}</th>
                        <th className="text-right py-2">{t.paperTrading.diffQty}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reconcileResult.details.map((d) => (
                        <tr key={d.symbol} className="border-b border-slate-100 dark:border-surface-light/50">
                          <td className="py-2 pr-4 font-medium">{d.symbol}</td>
                          <td className="py-2 pr-4 text-right tabular-nums">{d.system_qty}</td>
                          <td className="py-2 pr-4 text-right tabular-nums">{d.broker_qty}</td>
                          <td className={`py-2 text-right tabular-nums font-medium ${d.diff_qty !== 0 ? "text-amber-500" : ""}`}>
                            {d.diff_qty > 0 ? "+" : ""}{d.diff_qty}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-slate-500 dark:text-slate-400">{t.paperTrading.noDiscrepancies}</p>
              )}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
