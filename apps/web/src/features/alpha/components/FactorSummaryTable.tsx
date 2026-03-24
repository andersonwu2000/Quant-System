import { useT } from "@core/i18n";
import { fmtPct, fmtNum } from "@quant/shared";
import type { FactorReport } from "@core/api";

interface Props {
  factors: FactorReport[];
  selected: string | null;
  onSelect: (name: string) => void;
}

export function FactorSummaryTable({ factors, selected, onSelect }: Props) {
  const { t } = useT();

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 dark:border-surface-light text-slate-500 dark:text-slate-400 text-left">
            <th className="pb-2 pr-4 font-medium">Factor</th>
            <th className="pb-2 pr-4 font-medium text-right">{t.alpha.icMean}</th>
            <th className="pb-2 pr-4 font-medium text-right">{t.alpha.icir}</th>
            <th className="pb-2 pr-4 font-medium text-right">{t.alpha.hitRate}</th>
            <th className="pb-2 pr-4 font-medium text-right">{t.alpha.lsRatio}</th>
            <th className="pb-2 pr-4 font-medium text-right">{t.alpha.monotonicity}</th>
            <th className="pb-2 pr-4 font-medium text-right">{t.alpha.avgTurnover}</th>
            <th className="pb-2 font-medium text-right">{t.alpha.costDrag}</th>
          </tr>
        </thead>
        <tbody>
          {factors.map((f) => {
            const isSelected = f.name === selected;
            return (
              <tr
                key={f.name}
                onClick={() => onSelect(f.name)}
                className={`border-b border-slate-50 dark:border-surface-light cursor-pointer transition-colors ${
                  isSelected
                    ? "bg-blue-50 dark:bg-blue-500/10"
                    : "hover:bg-slate-50 dark:hover:bg-surface-light/50"
                }`}
              >
                <td className="py-2.5 pr-4 font-medium text-slate-800 dark:text-slate-100">
                  {(t.alpha.factorNames as Record<string, string>)[f.name] ?? f.name}
                  <span className="ml-1 text-xs text-slate-400">{f.direction === 1 ? "↑" : "↓"}</span>
                </td>
                <td className={`py-2.5 pr-4 text-right tabular-nums ${f.ic.ic_mean > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                  {f.ic.ic_mean > 0 ? "+" : ""}{fmtNum(f.ic.ic_mean, 4)}
                </td>
                <td className={`py-2.5 pr-4 text-right tabular-nums ${f.ic.icir > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                  {f.ic.icir > 0 ? "+" : ""}{fmtNum(f.ic.icir, 2)}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-slate-700 dark:text-slate-200">
                  {fmtPct(f.ic.hit_rate)}
                </td>
                <td className={`py-2.5 pr-4 text-right tabular-nums ${f.long_short_sharpe > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                  {fmtNum(f.long_short_sharpe, 2)}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-slate-700 dark:text-slate-200">
                  {fmtNum(f.monotonicity_score, 2)}
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-slate-700 dark:text-slate-200">
                  {fmtPct(f.turnover.avg_turnover)}
                </td>
                <td className="py-2.5 text-right tabular-nums text-slate-700 dark:text-slate-200">
                  {fmtNum(f.turnover.cost_drag_annual_bps, 0)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
