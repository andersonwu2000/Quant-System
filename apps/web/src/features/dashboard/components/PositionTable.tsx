import { useState } from "react";
import { fmtCurrency, fmtPrice, fmtPct, pnlColor } from "@core/utils";
import { useT } from "@core/i18n";
import type { Position } from "@core/api";

const DEFAULT_LIMIT = 10;

export function PositionTable({ positions }: { positions: Position[] }) {
  const { t } = useT();
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? positions : positions.slice(0, DEFAULT_LIMIT);
  const hasMore = positions.length > DEFAULT_LIMIT;

  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
      <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">{t.dashboard.topPositions}</p>
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
          {visible.map((p) => (
            <tr key={p.symbol} className="border-b border-slate-100 dark:border-surface-light/50 hover:bg-slate-50 dark:hover:bg-surface-light/30">
              <td className="py-2 font-medium">{p.symbol}</td>
              <td className="text-right py-2">{p.quantity}</td>
              <td className="text-right py-2">{p.market_price != null ? fmtPrice(p.market_price) : "—"}</td>
              <td className="text-right py-2">{fmtCurrency(p.market_value)}</td>
              <td className={`text-right py-2 ${pnlColor(p.unrealized_pnl)}`}>{fmtCurrency(p.unrealized_pnl)}</td>
              <td className="text-right py-2">{fmtPct(p.weight)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {hasMore && (
        <button
          onClick={() => setShowAll((v) => !v)}
          className="mt-2 text-xs text-blue-500 hover:text-blue-400 transition-colors"
        >
          {showAll ? t.dashboard.showLess : `${t.dashboard.showAll} (${positions.length})`}
        </button>
      )}
    </div>
  );
}
