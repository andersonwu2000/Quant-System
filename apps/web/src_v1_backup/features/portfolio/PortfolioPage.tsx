import { useApi } from "@core/hooks";
import { fmtCurrency, fmtPrice, fmtPct, pnlColor } from "@core/utils";
import { Card, ErrorAlert, MetricCardSkeleton, TableSkeleton, Skeleton, HelpTip, EmptyState } from "@shared/ui";
import { useT } from "@core/i18n";
import type { Portfolio } from "@core/api";
import { portfolioApi } from "./api";
import { SavedPortfoliosPanel } from "./components/SavedPortfoliosPanel";

export function PortfolioPage() {
  const { t } = useT();
  const { data: pf, loading, error, refresh } = useApi<Portfolio>(portfolioApi.get);

  if (error) return <ErrorAlert message={error} onRetry={refresh} />;
  if (loading || !pf) return (
    <div className="space-y-6">
      <Skeleton className="h-7 w-40" />
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton /><MetricCardSkeleton />
      </div>
      <TableSkeleton rows={8} cols={7} />
    </div>
  );

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h2 className="text-2xl font-bold">{t.portfolio.title}</h2>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 text-sm">
        <Card className="p-4">
          <p className="text-slate-500 dark:text-slate-400">{t.portfolio.nav}<HelpTip term="nav" /></p>
          <p className="text-xl font-bold">{fmtCurrency(pf.nav)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-slate-500 dark:text-slate-400">{t.portfolio.cash}</p>
          <p className="text-xl font-bold">{fmtCurrency(pf.cash)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-slate-500 dark:text-slate-400">{t.portfolio.grossExposure}<HelpTip term="gross_exposure" /></p>
          <p className="text-xl font-bold">{fmtPct(pf.gross_exposure)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-slate-500 dark:text-slate-400">{t.portfolio.netExposure}<HelpTip term="net_exposure" /></p>
          <p className="text-xl font-bold">{fmtPct(pf.net_exposure)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-slate-500 dark:text-slate-400">{t.portfolio.dailyPnl}</p>
          <p className={`text-xl font-bold ${pnlColor(pf.daily_pnl)}`}>
            {fmtCurrency(pf.daily_pnl)} ({fmtPct(pf.daily_pnl_pct)})
          </p>
        </Card>
      </div>

      <Card className="p-5 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-500 border-b border-slate-200 dark:border-surface-light">
              <th className="text-left py-2">{t.portfolio.symbol}</th>
              <th className="text-right py-2">{t.portfolio.quantity}</th>
              <th className="text-right py-2">{t.portfolio.avgCost}</th>
              <th className="text-right py-2">{t.portfolio.price}</th>
              <th className="text-right py-2">{t.portfolio.marketValue}</th>
              <th className="text-right py-2">{t.portfolio.unrealizedPnl}</th>
              <th className="text-right py-2">{t.portfolio.weight}</th>
            </tr>
          </thead>
          <tbody>
            {pf.positions.map((p) => (
              <tr key={p.symbol} className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30">
                <td className="py-2 font-medium">{p.symbol}</td>
                <td className="text-right py-2">{p.quantity}</td>
                <td className="text-right py-2">{p.avg_cost != null ? fmtPrice(p.avg_cost) : "—"}</td>
                <td className="text-right py-2">{p.market_price != null ? fmtPrice(p.market_price) : "—"}</td>
                <td className="text-right py-2">{fmtCurrency(p.market_value)}</td>
                <td className={`text-right py-2 ${pnlColor(p.unrealized_pnl)}`}>
                  {fmtCurrency(p.unrealized_pnl)}
                </td>
                <td className="text-right py-2">{fmtPct(p.weight)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {pf.positions.length === 0 && (
          <EmptyState message={t.portfolio.noPositions} actionLabel={t.nav.strategies} actionHref="/strategies" />
        )}
      </Card>

      <hr className="border-slate-200 dark:border-surface-light" />
      <SavedPortfoliosPanel />
    </div>
  );
}
