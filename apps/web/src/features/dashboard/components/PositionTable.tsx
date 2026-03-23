import { fmtCurrency, fmtPct, pnlColor } from "@core/utils";
import { useT } from "@core/i18n";
import type { Position } from "@quant/shared";

export function PositionTable({ positions }: { positions: Position[] }) {
  const { t } = useT();
  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
      <p className="text-sm font-medium text-slate-500 dark:text-slate-400 mb-3">{t.dashboard.topPositions}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-500 border-b border-slate-200 dark:border-surface-light">
            <th className="text-left py-2">{t.dashboard.symbol}</th>
            <th className="text-right py-2">{t.dashboard.qty}</th>
            <th className="text-right py-2">{t.dashboard.price}</th>
            <th className="text-right py-2">{t.dashboard.value}</th>
            <th className="text-right py-2">{t.dashboard.pnl}</th>
            <th className="text-right py-2">{t.dashboard.weight}</th>
          </tr>
        </thead>
        <tbody>
          {positions.slice(0, 10).map((p) => (
            <tr key={p.symbol} className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30">
              <td className="py-2 font-medium">{p.symbol}</td>
              <td className="text-right py-2">{p.quantity}</td>
              <td className="text-right py-2">${p.market_price?.toFixed(2) ?? "—"}</td>
              <td className="text-right py-2">{fmtCurrency(p.market_value)}</td>
              <td className={`text-right py-2 ${pnlColor(p.unrealized_pnl)}`}>{fmtCurrency(p.unrealized_pnl)}</td>
              <td className="text-right py-2">{fmtPct(p.weight)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
