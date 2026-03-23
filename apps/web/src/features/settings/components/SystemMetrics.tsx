import { useEffect, useRef } from "react";
import { useApi } from "@core/hooks";
import { useT } from "@core/i18n";
import { MetricCard, MetricCardSkeleton } from "@shared/ui";
import { systemApi } from "../api";

const REFRESH_INTERVAL_MS = 30_000;

export function SystemMetrics() {
  const { t } = useT();
  const { data: metrics, loading, refresh } = useApi(systemApi.metrics);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    intervalRef.current = setInterval(refresh, REFRESH_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, [refresh]);

  if (loading && !metrics) {
    return (
      <div>
        <p className="text-sm font-medium text-slate-400 mb-3">{t.settings.metrics}</p>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton />
        </div>
      </div>
    );
  }

  if (!metrics) return null;

  const fmtUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h > 0 ? `${h}h ${m}m` : `${m}m`;
  };

  return (
    <div>
      <p className="text-sm font-medium text-slate-400 mb-3">{t.settings.metrics}</p>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label={t.settings.uptime} value={fmtUptime(metrics.uptime_seconds)} />
        <MetricCard label={t.settings.requestCount} value={String(metrics.total_requests)} />
        <MetricCard label={t.settings.wsConnections} value={String(metrics.active_ws_connections)} />
        <MetricCard label={t.settings.strategiesRunning} value={String(metrics.strategies_running)} />
        <MetricCard label={t.settings.activeBacktests} value={String(metrics.active_backtests)} />
      </div>
    </div>
  );
}
