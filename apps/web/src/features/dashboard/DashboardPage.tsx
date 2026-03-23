import { MetricCard, ErrorAlert, MetricCardSkeleton, TableSkeleton, Skeleton, ConnectionBanner } from "@shared/ui";
import { fmtCurrency, fmtPct, pnlColor } from "@core/utils";
import { useT } from "@core/i18n";
import { useDashboard } from "./hooks/useDashboard";
import { MarketTicker } from "./components/MarketTicker";
import { NavChart } from "./components/NavChart";
import { PositionTable } from "./components/PositionTable";

export function DashboardPage() {
  const { t } = useT();
  const { pf, error, refresh, navHistory, running, connected } = useDashboard();

  if (error) return <ErrorAlert message={error} onRetry={refresh} />;
  if (!pf) return (
    <div className="space-y-6">
      <Skeleton className="h-7 w-40" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton />
      </div>
      <TableSkeleton rows={5} cols={6} />
    </div>
  );

  return (
    <div className="space-y-6">
      <ConnectionBanner connected={connected} label={t.common.connectionLost} />
      <MarketTicker />
      <h2 className="text-2xl font-bold">{t.dashboard.title}</h2>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" aria-live="polite">
        <MetricCard label={t.dashboard.nav} value={fmtCurrency(pf.nav)} />
        <MetricCard label={t.dashboard.cash} value={fmtCurrency(pf.cash)} />
        <MetricCard
          label={t.dashboard.dailyPnl}
          value={fmtCurrency(pf.daily_pnl)}
          sub={fmtPct(pf.daily_pnl_pct)}
          className={pnlColor(pf.daily_pnl)}
        />
        <MetricCard
          label={t.dashboard.positions}
          value={String(pf.positions_count)}
          sub={t.dashboard.strategiesRunning.replace("{n}", String(running))}
        />
      </div>

      {navHistory.length > 1 && <NavChart data={navHistory} />}
      {pf.positions.length > 0 && <PositionTable positions={pf.positions} />}
    </div>
  );
}
