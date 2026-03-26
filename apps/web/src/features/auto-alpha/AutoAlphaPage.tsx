import { useCallback, useEffect, useRef, useState } from "react";
import { useApi, useWs } from "@core/hooks";
import { useT } from "@core/i18n";
import { fmtPct, fmtNum, fmtDate, fmtTime, pnlColor } from "@core/utils";
import { Card, MetricCard, StatusBadge, ErrorAlert, Skeleton, useToast } from "@shared/ui";
import { autoAlphaEndpoints } from "@core/api";
import type { AutoAlphaStatus, AutoAlphaPerformance, AutoAlphaSnapshot, AutoAlphaAlert } from "@core/api";
import { Play, Square, Zap, Loader2 } from "lucide-react";

const REGIME_COLORS: Record<string, string> = {
  bull: "bg-emerald-100 dark:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400",
  bear: "bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-400",
  sideways: "bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-400",
};

type AlertItem = AutoAlphaAlert;

type RunProgress = {
  taskId: string;
  status: "downloading" | "researching" | "completed" | "failed";
  symbolsLoaded?: number;
  factorsComputed?: number;
  selectedFactors?: string[];
  regime?: string;
  error?: string;
};

const STAGE_LABELS: Record<string, Record<string, string>> = {
  en: { downloading: "Downloading market data...", researching: "Running factor analysis...", completed: "Completed", failed: "Failed" },
  zh: { downloading: "下載市場數據中...", researching: "執行因子分析中...", completed: "完成", failed: "失敗" },
};

export function AutoAlphaPage() {
  const { t } = useT();
  const { toast } = useToast();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [runProgress, setRunProgress] = useState<RunProgress | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
      toast("success", resp.message);
      refreshStatus();
    } catch {
      toast("error", t.common.requestFailed);
    } finally {
      setActionLoading(null);
    }
  };

  const handleStop = async () => {
    setActionLoading("stop");
    try {
      const resp = await autoAlphaEndpoints.stop();
      toast("success", resp.message);
      refreshStatus();
    } catch {
      toast("error", t.common.requestFailed);
    } finally {
      setActionLoading(null);
    }
  };

  // Cleanup poll on unmount
  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleRunNow = async () => {
    setActionLoading("runNow");
    try {
      const resp = await autoAlphaEndpoints.runNow();
      const taskId = resp.task_id;
      setRunProgress({ taskId, status: "downloading" });

      // Poll every 5 seconds, with error counter
      if (pollRef.current) clearInterval(pollRef.current);
      let pollErrors = 0;
      pollRef.current = setInterval(async () => {
        try {
          const task = await autoAlphaEndpoints.taskStatus(taskId);
          pollErrors = 0; // Reset on success
          if (task.status === "completed") {
            setRunProgress({
              taskId,
              status: "completed",
              factorsComputed: task.factors_computed,
              selectedFactors: task.selected_factors,
              regime: task.regime,
            });
            if (pollRef.current) clearInterval(pollRef.current);
            setActionLoading(null);
            refreshStatus();
            refreshHistory();
            refreshPerf();
            setTimeout(() => setRunProgress(null), 5000);
          } else if (task.status === "failed") {
            setRunProgress({ taskId, status: "failed", error: task.error });
            if (pollRef.current) clearInterval(pollRef.current);
            setActionLoading(null);
            setTimeout(() => setRunProgress(null), 8000);
          } else {
            // Still running — update stage
            const stage = task.stage === "researching" ? "researching" : "downloading";
            setRunProgress((prev) => prev ? {
              ...prev,
              status: stage,
              symbolsLoaded: task.symbols_loaded ?? prev.symbolsLoaded,
            } : prev);
          }
        } catch {
          pollErrors++;
          // After 3 consecutive errors or 7 minutes, check status endpoint as fallback
          if (pollErrors >= 3) {
            if (pollRef.current) clearInterval(pollRef.current);
            // Fallback: check if status shows new data
            try {
              const st = await autoAlphaEndpoints.status();
              if (st.last_run) {
                setRunProgress({
                  taskId,
                  status: "completed",
                  regime: st.regime ?? undefined,
                  selectedFactors: st.selected_factors,
                });
                setActionLoading(null);
                refreshStatus();
                refreshHistory();
                refreshPerf();
                setTimeout(() => setRunProgress(null), 5000);
                return;
              }
            } catch { /* ignore */ }
            setRunProgress({ taskId, status: "failed", error: "Lost connection to task" });
            setActionLoading(null);
            setTimeout(() => setRunProgress(null), 5000);
          }
        }
      }, 5000);
    } catch {
      toast("error", t.common.requestFailed);
      setActionLoading(null);
      setRunProgress(null);
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
            {actionLoading === "runNow" ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Zap size={14} />
            )}
            {actionLoading === "runNow" ? t.autoAlpha.runNow + "..." : t.autoAlpha.runNow}
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

      {/* Run Progress Banner */}
      {runProgress && (
        <Card className={`p-4 border-l-4 ${
          runProgress.status === "completed" ? "border-l-emerald-500 bg-emerald-500/5" :
          runProgress.status === "failed" ? "border-l-red-500 bg-red-500/5" :
          "border-l-amber-500 bg-amber-500/5"
        }`}>
          <div className="flex items-center gap-3">
            {runProgress.status !== "completed" && runProgress.status !== "failed" && (
              <Loader2 size={18} className="animate-spin text-amber-500" />
            )}
            <div className="flex-1">
              <p className="font-medium text-sm">
                {STAGE_LABELS[/[\u4e00-\u9fff]/.test(t.autoAlpha.title) ? "zh" : "en"]?.[runProgress.status] ?? runProgress.status}
              </p>
              {runProgress.status !== "completed" && runProgress.status !== "failed" && (
                <p className="text-xs text-slate-400 mt-0.5">
                  {runProgress.symbolsLoaded != null ? `${runProgress.symbolsLoaded} symbols loaded · ` : ""}
                  This may take 2-5 minutes
                </p>
              )}
              {runProgress.status === "completed" && (
                <p className="text-xs text-emerald-600 dark:text-emerald-400 mt-0.5">
                  {runProgress.factorsComputed ?? 0} factors analyzed
                  {runProgress.regime && ` · Regime: ${runProgress.regime}`}
                  {runProgress.selectedFactors && runProgress.selectedFactors.length > 0
                    ? ` · Selected: ${runProgress.selectedFactors.join(", ")}`
                    : " · No factors passed threshold"}
                </p>
              )}
              {runProgress.status === "failed" && runProgress.error && (
                <p className="text-xs text-red-500 mt-0.5">{runProgress.error}</p>
              )}
            </div>
            {(runProgress.status === "completed" || runProgress.status === "failed") && (
              <button onClick={() => setRunProgress(null)} className="text-slate-400 hover:text-slate-300 text-xs">
                ✕
              </button>
            )}
          </div>
          {/* Progress bar — indeterminate animation */}
          {runProgress.status !== "completed" && runProgress.status !== "failed" && (
            <div className="mt-3 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden relative">
              <div className="absolute inset-0 bg-amber-500/30 rounded-full animate-pulse" />
              <div
                className="h-full bg-amber-500 rounded-full transition-all duration-[3000ms] ease-linear"
                style={{ width: runProgress.status === "researching" ? "75%" : "30%" }}
              />
            </div>
          )}
        </Card>
      )}

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
                  const w = 1 / status.selected_factors.length; // Equal weight display when detailed weights unavailable
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
