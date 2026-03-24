import { useState, useMemo } from "react";
import { useT } from "@core/i18n";
import { fmtPct, fmtNum } from "@quant/shared";
import { HelpTip } from "@shared/ui";
import { ChevronUp, ChevronDown } from "lucide-react";
import type { FactorReport } from "@core/api";

interface Props {
  factors: FactorReport[];
  selected: string | null;
  onSelect: (name: string) => void;
}

type SortKey = "name" | "ic_mean" | "icir" | "hit_rate" | "ls_sharpe" | "monotonicity" | "turnover" | "cost_drag";

function getValue(f: FactorReport, key: SortKey): number | string {
  switch (key) {
    case "name": return f.name;
    case "ic_mean": return f.ic.ic_mean;
    case "icir": return f.ic.icir;
    case "hit_rate": return f.ic.hit_rate;
    case "ls_sharpe": return f.long_short_sharpe;
    case "monotonicity": return f.monotonicity_score;
    case "turnover": return f.turnover.avg_turnover;
    case "cost_drag": return f.turnover.cost_drag_annual_bps;
  }
}

function SortIcon({ active, asc }: { active: boolean; asc: boolean }) {
  if (!active) return <span className="inline-block w-3 ml-0.5" />;
  return asc
    ? <ChevronUp size={12} className="inline ml-0.5" />
    : <ChevronDown size={12} className="inline ml-0.5" />;
}

export function FactorSummaryTable({ factors, selected, onSelect }: Props) {
  const { t } = useT();
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc((v) => !v);
    } else {
      setSortKey(key);
      setSortAsc(key === "name");
    }
  };

  const sorted = useMemo(() => {
    if (!sortKey) return factors;
    return [...factors].sort((a, b) => {
      const va = getValue(a, sortKey);
      const vb = getValue(b, sortKey);
      const cmp = typeof va === "string" ? va.localeCompare(vb as string) : (va as number) - (vb as number);
      return sortAsc ? cmp : -cmp;
    });
  }, [factors, sortKey, sortAsc]);

  const columns: { key: SortKey; label: React.ReactNode; align: string }[] = [
    { key: "name", label: <>{t.alpha.factors}<HelpTip term="factor" /></>, align: "text-left" },
    { key: "ic_mean", label: <>{t.alpha.icMean}<HelpTip term="ic_mean" /></>, align: "text-right" },
    { key: "icir", label: <>{t.alpha.icir}<HelpTip term="icir" /></>, align: "text-right" },
    { key: "hit_rate", label: <>{t.alpha.hitRate}<HelpTip term="hit_rate" /></>, align: "text-right" },
    { key: "ls_sharpe", label: <>{t.alpha.lsRatio}<HelpTip term="ls_sharpe" /></>, align: "text-right" },
    { key: "monotonicity", label: <>{t.alpha.monotonicity}<HelpTip term="monotonicity" /></>, align: "text-right" },
    { key: "turnover", label: <>{t.alpha.avgTurnover}<HelpTip term="turnover" /></>, align: "text-right" },
    { key: "cost_drag", label: <>{t.alpha.costDrag}<HelpTip term="cost_drag" /></>, align: "text-right" },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100 dark:border-surface-light text-slate-500 dark:text-slate-400 text-left">
            {columns.map(({ key, label, align }) => (
              <th
                key={key}
                onClick={() => handleSort(key)}
                className={`pb-2 pr-4 font-medium ${align} cursor-pointer select-none hover:text-slate-700 dark:hover:text-slate-200 transition-colors`}
              >
                {label}
                <SortIcon active={sortKey === key} asc={sortAsc} />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((f) => {
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
