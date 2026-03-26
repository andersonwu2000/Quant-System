import { useEffect, useRef } from "react";
import { useApi } from "@core/hooks";
import { useT } from "@core/i18n";
import { fmtUptime } from "@core/utils";
import { systemApi } from "../api";

const REFRESH_INTERVAL_MS = 30_000;

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-4 py-1.5 border-b border-slate-100 dark:border-surface-light last:border-0">
      <span className="text-sm text-slate-500 dark:text-slate-400 w-32 shrink-0">{label}</span>
      <span className="text-sm font-medium text-slate-800 dark:text-slate-200">{value}</span>
    </div>
  );
}

export function SystemMetrics() {
  const { t } = useT();
  const { data: status } = useApi(systemApi.status);
  const { data: metrics, loading, refresh } = useApi(systemApi.metrics);
  const intervalRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    const start = () => { intervalRef.current = setInterval(refresh, REFRESH_INTERVAL_MS); };
    const stop = () => clearInterval(intervalRef.current);
    const onVisibility = () => { document.hidden ? stop() : start(); };

    start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => { stop(); document.removeEventListener("visibilitychange", onVisibility); };
  }, [refresh]);

  if (loading && !metrics) {
    return <p className="text-sm text-slate-400 py-2">{t.dashboard.loading}</p>;
  }

  return (
    <div>
      {status && (
        <>
          <Row label={t.settings.mode} value={status.mode} />
          <Row label={t.settings.dataSource} value={status.data_source} />
          <Row label={t.settings.uptime} value={fmtUptime(status.uptime_seconds)} />
          <Row label={t.settings.strategiesRunning} value={String(status.strategies_running)} />
        </>
      )}
      {metrics && (
        <>
          <Row label={t.settings.requestCount} value={String(metrics.total_requests)} />
          <Row label={t.settings.wsConnections} value={String(metrics.active_ws_connections)} />
          <Row label={t.settings.activeBacktests} value={String(metrics.active_backtests)} />
        </>
      )}
    </div>
  );
}
