import { useCallback, useEffect, useRef, useState } from "react";
import { useApi, useWs } from "@core/hooks";
import { useT } from "@core/i18n";
import { fmtPct, fmtNum, fmtDate, fmtTime, pnlColor } from "@core/utils";
import { Card, MetricCard, StatusBadge, ErrorAlert, Skeleton, useToast } from "@shared/ui";
import { autoAlphaEndpoints } from "@core/api";
import type { AutoAlphaStatus, AutoAlphaPerformance, AutoAlphaSnapshot } from "@core/api";
import { Play, Square, Zap } from "lucide-react";

const REGIME_COLORS: Record<string, string> = {
  bull: "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400",
  bear: "bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400",
  sideways: "bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400",
};

interface AlertItem {
  timestamp: string;
  level: string;
  message: string;
}

export function AutoAlphaPage() {
  const { t } = useT();
  const { toast } = useToast();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const mountedRef = useRef(true);
  useEffect(() => { return () => { mountedRef.current = false; }; }, []);

  const {
    data: status,
    error: statusError,
    refresh: refreshStatus,
    setData: setStatus,
  } = useApi<AutoAlphaStatus>(autoAlphaEndpoints.status);

  const {
    data: perf,
    error: perfError,
    refresh: refreshPerf,
  } = useApi<AutoAlphaPerformance>(autoAlphaEndpoints.performance);

  const {
    data: history,
    error: historyError,
    refresh: refreshHistory,
  } = useApi<AutoAlphaSnapshot[]>(() => autoAlphaEndpoints.history(10));

  const {
    data: alerts,
    error: alertsError,
    refresh: refreshAlerts,
    setData: setAlerts,
  } = useApi<AlertItem[]>(() => autoAlphaEndpoints.alerts(10));

  // Listen for live updates on auto-alpha channel
  useWs(
    "auto-alpha",
    useCallback(
      (msg: unknown) => {
        const data = msg as Record<string, unknown>;
        if (!data || typeof data !== "object") return;
        if (data.type === "status" && data.payload) {
          setStatus(data.payload as AutoAlphaStatus);
        } else if (data.type === "alert" && data.payload) {
          setAlerts((prev) =>
            prev ? [data.payload as AlertItem, ...prev].slice(0, 50) : [data.payload as AlertItem],
          );
        }
      },
      [setStatus, setAlerts],
    ),
  );

  const handleStart = async () => {
    setActionLoading("start");
    try {
      const resp = await autoAlphaEndpoints.start();
      if (!mountedRef.current) return;
      toast("success", resp.message);
      refreshStatus();
    } catch {
      if (!mountedRef.current) return;
      toast("error", t.common.requestFailed);
    } finally {
      if (mountedRef.current) setActionLoading(null);
    }
  };

  const handleStop = async () => {
    setActionLoading("stop");
    try {
      const resp = await autoAlphaEndpoints.stop();
      if (!mountedRef.current) return;
      toast("success", resp.message);
      refreshStatus();
    } catch {
      if (!mountedRef.current) return;
      toast("error", t.common.requestFailed);
    } finally {
      if (mountedRef.current) setActionLoading(null);
    }
  };

  const handleRunNow = async () => {
    setActionLoading("runNow");
    try {
      await autoAlphaEndpoints.runNow();
      if (!mountedRef.current) return;
      toast("success", t.autoAlpha.runNow);
      refreshStatus();
      refreshHistory();
      refreshPerf();
    } catch {
      if (!mountedRef.current) return;
      toast("error", t.common.requestFailed);
    } finally {
      if (mountedRef.current) setActionLoading(null);
    }
  };

  const regimeLabel = (regime: string | null | undefined): string => {
    if (!regime) return "-";
    const key = regime.toLowerCase() as "bull" | "bear" | "sideways";
    return t.autoAlpha[key] ?? regime;
  };

  const regimeColor = (regime: string | null | undefined): string => {
    if (!regime) return "bg-slate-100 dark:bg-slate-500/20 text-slate-600 dark:text-slate-400";
    return REGIME_COLORS[regime.toLowerCase()] ?? "bg-slate-100 dark:bg-slate-500/20 text-slate-600 dark:text-slate-400";
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold">{t.autoAlpha.title}</h2>
          {status && (
            <StatusBadge status={status.running ? "running" : "stopped"} />
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRunNow}
            disabled={actionLoading !== null}
            className="flex items-center gap-1.5 px-3 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
          >
            <Zap size={14} />
            {actionLoading === "runNow" ? "..." : t.autoAlpha.runNow}
          </button>
          {status?.running ? (
            <button
              onClick={handleStop}
              disabled={actionLoading !== null}
              className="flex items-center gap-1.5 px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
            >
              <Square size={14} />
              {actionLoading === "stop" ? "..." : t.autoAlpha.stop}
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={actionLoading !== null}
              className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg text-sm font-medium text-white transition-colors"
            >
              <Play size={14} />
              {actionLoading === "start" ? "..." : t.autoAlpha.start}
            </button>
          )}
        </div>
      </div>

      {/* Errors */}
      {statusError && <ErrorAlert message={statusError} onRetry={refreshStatus} />}
      {perfError && <ErrorAlert message={perfError} onRetry={refreshPerf} />}

      {/* Performance MetricCards */}
      {!perfError && !perf && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-5">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-7 w-16" />
            </Card>
          ))}
        </div>
      )}
      {perf && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            label={t.autoAlpha.cumulativeReturn}
            value={fmtPct(perf.cumulative_return)}
            className={pnlColor(perf.cumulative_return)}
          />
          <MetricCard
            label={t.autoAlpha.winRate}
            value={fmtPct(perf.win_rate)}
          />
          <MetricCard
            label={t.autoAlpha.maxDrawdown}
            value={fmtPct(perf.max_drawdown)}
            className="text-red-500"
          />
          <MetricCard
            label={t.autoAlpha.avgDailyPnl}
            value={fmtNum(perf.avg_daily_pnl, 2)}
            className={pnlColor(perf.avg_daily_pnl)}
          />
        </div>
      )}

      {/* Current Regime */}
      {status && (
        <Card className="p-5">
          <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">
            {t.autoAlpha.regime}
          </p>
          <span
            className={`inline-flex items-center px-3 py-1.5 rounded-lg text-sm font-semibold ${regimeColor(status.regime)}`}
          >
            {regimeLabel(status.regime)}
          </span>
          {status.last_run && (
            <p className="text-xs text-slate-400 mt-2">
              Last run: {fmtDate(status.last_run)} {fmtTime(status.last_run)}
            </p>
          )}
        </Card>
      )}

      {/* Factor Allocation Table */}
      {status && status.selected_factors.length > 0 && (
        <Card className="p-5">
          <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">
            {t.autoAlpha.factors}
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-surface-light">
                  <th className="text-left py-2">{t.autoAlpha.factorName}</th>
                  <th className="text-right py-2">{t.autoAlpha.weight}</th>
                  <th className="text-right py-2 w-48">
                    {/* visual bar header */}
                  </th>
                </tr>
              </thead>
              <tbody>
                {status.selected_factors.map((factor) => {
                  const w = status.factor_weights[factor] ?? 0;
                  return (
                    <tr
                      key={factor}
                      className="border-b border-slate-100 dark:border-surface-light/50"
                    >
                      <td className="py-2 font-medium">{factor}</td>
                      <td className="py-2 text-right font-mono">{fmtPct(w)}</td>
                      <td className="py-2">
                        <div className="h-4 bg-slate-100 dark:bg-surface-light rounded overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded transition-all"
                            style={{ width: `${Math.min(Math.abs(w) * 100, 100)}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent History */}
        <Card className="p-5">
          <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">
            {t.autoAlpha.history}
          </p>
          {historyError && <ErrorAlert message={historyError} onRetry={refreshHistory} />}
          {!historyError && !history && (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          )}
          {!historyError && history && history.length === 0 && (
            <p className="text-center text-slate-500 py-8">{t.autoAlpha.noData}</p>
          )}
          {!historyError && history && history.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-slate-500 dark:text-slate-400 border-b border-slate-200 dark:border-surface-light">
                    <th className="text-left py-2">{t.autoAlpha.date}</th>
                    <th className="text-left py-2">{t.autoAlpha.regime}</th>
                    <th className="text-left py-2">{t.autoAlpha.factors}</th>
                    <th className="text-right py-2">{t.autoAlpha.trades}</th>
                    <th className="text-right py-2">{t.autoAlpha.turnover}</th>
                    <th className="text-right py-2">{t.autoAlpha.dailyPnl}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((snap) => (
                    <tr
                      key={snap.date}
                      className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30"
                    >
                      <td className="py-2 whitespace-nowrap">{fmtDate(snap.date)}</td>
                      <td className="py-2">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold ${regimeColor(snap.regime)}`}
                        >
                          {regimeLabel(snap.regime)}
                        </span>
                      </td>
                      <td className="py-2 text-xs max-w-[160px] truncate" title={snap.selected_factors.join(", ")}>
                        {snap.selected_factors.join(", ")}
                      </td>
                      <td className="py-2 text-right">{snap.trades_count}</td>
                      <td className="py-2 text-right">{fmtPct(snap.turnover)}</td>
                      <td className={`py-2 text-right font-mono ${snap.daily_pnl !== null ? pnlColor(snap.daily_pnl) : ""}`}>
                        {snap.daily_pnl !== null ? fmtNum(snap.daily_pnl, 2) : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Recent Alerts */}
        <Card className="p-5">
          <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">
            {t.autoAlpha.alerts}
          </p>
          {alertsError && <ErrorAlert message={alertsError} onRetry={refreshAlerts} />}
          {!alertsError && !alerts && (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          )}
          {!alertsError && alerts && alerts.length === 0 && (
            <p className="text-center text-slate-500 py-8">{t.autoAlpha.noData}</p>
          )}
          {!alertsError && alerts && alerts.length > 0 && (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {alerts.map((a: AlertItem, i: number) => (
                <div
                  key={`${a.timestamp}-${i}`}
                  className="flex items-start gap-2 py-2 border-b border-slate-100 dark:border-surface-light/50"
                >
                  <StatusBadge status={a.level} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm">{a.message}</p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {fmtDate(a.timestamp)} {fmtTime(a.timestamp)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
