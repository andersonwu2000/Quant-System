import { fmtPct, fmtNum, fmtCurrency } from "@core/utils";
import type { BacktestHistoryEntry } from "../hooks/useBacktestHistory";

interface Props {
  entries: BacktestHistoryEntry[];
}

const metrics = [
  { key: "total_return", label: "Total Return", fmt: fmtPct },
  { key: "annual_return", label: "Annual Return", fmt: fmtPct },
  { key: "sharpe", label: "Sharpe", fmt: (v: number) => fmtNum(v) },
  { key: "sortino", label: "Sortino", fmt: (v: number) => fmtNum(v) },
  { key: "calmar", label: "Calmar", fmt: (v: number) => fmtNum(v) },
  { key: "max_drawdown", label: "Max Drawdown", fmt: fmtPct },
  { key: "volatility", label: "Volatility", fmt: fmtPct },
  { key: "win_rate", label: "Win Rate", fmt: fmtPct },
  { key: "total_trades", label: "Trades", fmt: (v: number) => String(v) },
  { key: "total_commission", label: "Commission", fmt: fmtCurrency },
] as const;

export function CompareTable({ entries }: Props) {
  if (entries.length < 2) return null;

  return (
    <div className="bg-surface rounded-xl p-5 overflow-x-auto">
      <p className="text-sm font-medium text-slate-400 mb-3">Comparison</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-500 border-b border-surface-light">
            <th className="text-left py-2">Metric</th>
            {entries.map((e) => (
              <th key={e.id} className="text-right py-2">{e.result.strategy_name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metrics.map(({ key, label, fmt }) => (
            <tr key={key} className="border-b border-surface-light/50">
              <td className="py-2 text-slate-400">{label}</td>
              {entries.map((e) => (
                <td key={e.id} className="text-right py-2">
                  {fmt(e.result[key] as number)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
