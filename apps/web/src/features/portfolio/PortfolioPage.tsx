import { useApi } from "@core/hooks";
import { fmtCurrency, fmtPct, pnlColor } from "@core/utils";
import { ErrorAlert } from "@shared/ui";
import { useT } from "@core/i18n";
import type { Portfolio } from "@core/types";
import { portfolioApi } from "./api";

export function PortfolioPage() {
  const { t } = useT();
  const { data: pf, loading, error, refresh } = useApi<Portfolio>(portfolioApi.get);

  if (error) return <ErrorAlert message={error} onRetry={refresh} />;
  if (loading || !pf) return <div className="text-slate-400">{t.dashboard.loading}</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold">{t.portfolio.title}</h2>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 text-sm">
        <div className="bg-surface rounded-xl p-4">
          <p className="text-slate-400">{t.dashboard.nav}</p>
          <p className="text-lg font-bold">{fmtCurrency(pf.nav)}</p>
        </div>
        <div className="bg-surface rounded-xl p-4">
          <p className="text-slate-400">{t.dashboard.cash}</p>
          <p className="text-lg font-bold">{fmtCurrency(pf.cash)}</p>
        </div>
        <div className="bg-surface rounded-xl p-4">
          <p className="text-slate-400">{t.portfolio.grossExposure}</p>
          <p className="text-lg font-bold">{fmtPct(pf.gross_exposure)}</p>
        </div>
        <div className="bg-surface rounded-xl p-4">
          <p className="text-slate-400">{t.portfolio.netExposure}</p>
          <p className="text-lg font-bold">{fmtPct(pf.net_exposure)}</p>
        </div>
        <div className="bg-surface rounded-xl p-4">
          <p className="text-slate-400">{t.dashboard.dailyPnl}</p>
          <p className={`text-lg font-bold ${pnlColor(pf.daily_pnl)}`}>
            {fmtCurrency(pf.daily_pnl)} ({fmtPct(pf.daily_pnl_pct)})
          </p>
        </div>
      </div>

      <div className="bg-surface rounded-xl p-5 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-500 border-b border-surface-light">
              <th className="text-left py-2">{t.dashboard.symbol}</th>
              <th className="text-right py-2">{t.portfolio.quantity}</th>
              <th className="text-right py-2">{t.portfolio.avgCost}</th>
              <th className="text-right py-2">{t.dashboard.price}</th>
              <th className="text-right py-2">{t.portfolio.marketValue}</th>
              <th className="text-right py-2">{t.portfolio.unrealizedPnl}</th>
              <th className="text-right py-2">{t.dashboard.weight}</th>
            </tr>
          </thead>
          <tbody>
            {pf.positions.map((p) => (
              <tr key={p.symbol} className="border-b border-surface-light/50 hover:bg-surface-light/30">
                <td className="py-2 font-medium">{p.symbol}</td>
                <td className="text-right py-2">{p.quantity}</td>
                <td className="text-right py-2">${p.avg_cost?.toFixed(2) ?? "—"}</td>
                <td className="text-right py-2">${p.market_price?.toFixed(2) ?? "—"}</td>
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
          <p className="text-center text-slate-500 py-8">{t.portfolio.noPositions}</p>
        )}
      </div>
    </div>
  );
}
