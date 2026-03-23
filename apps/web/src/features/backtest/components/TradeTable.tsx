import { useT } from "@core/i18n";
import { ExportButton } from "@shared/ui";
import { fmtCurrency, fmtNum } from "@core/utils";
import type { TradeRecord } from "@quant/shared";

interface Props {
  trades: TradeRecord[];
}

export function TradeTable({ trades }: Props) {
  const { t } = useT();

  if (trades.length === 0) return null;

  const headers = [
    t.orders.time,
    t.orders.symbol,
    t.orders.side,
    t.orders.qty,
    t.orders.price,
    t.orders.commission,
  ];

  const rows = trades.map((tr) => [
    tr.date,
    tr.symbol,
    tr.side,
    fmtNum(tr.quantity),
    fmtCurrency(tr.price),
    fmtCurrency(tr.commission),
  ]);

  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{t.backtest.tradeDetail}</p>
        <ExportButton filename="trades.csv" headers={headers} rows={rows} />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-200 dark:border-surface-light">
              <th className="px-3 py-2 text-left text-slate-400 font-medium">{t.orders.time}</th>
              <th className="px-3 py-2 text-left text-slate-400 font-medium">{t.orders.symbol}</th>
              <th className="px-3 py-2 text-left text-slate-400 font-medium">{t.orders.side}</th>
              <th className="px-3 py-2 text-right text-slate-400 font-medium">{t.orders.qty}</th>
              <th className="px-3 py-2 text-right text-slate-400 font-medium">{t.orders.price}</th>
              <th className="px-3 py-2 text-right text-slate-400 font-medium">{t.orders.commission}</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((tr, i) => (
              <tr key={i} className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30 transition-colors">
                <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{tr.date}</td>
                <td className="px-3 py-2 text-slate-800 dark:text-slate-200 font-medium">{tr.symbol}</td>
                <td className={`px-3 py-2 font-medium ${tr.side === "BUY" ? "text-emerald-400" : "text-red-400"}`}>
                  {tr.side}
                </td>
                <td className="px-3 py-2 text-right text-slate-600 dark:text-slate-300 font-mono">{fmtNum(tr.quantity)}</td>
                <td className="px-3 py-2 text-right text-slate-600 dark:text-slate-300 font-mono">{fmtCurrency(tr.price)}</td>
                <td className="px-3 py-2 text-right text-slate-600 dark:text-slate-300 font-mono">{fmtCurrency(tr.commission)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
