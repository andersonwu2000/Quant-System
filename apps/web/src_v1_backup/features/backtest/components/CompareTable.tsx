import { fmtPct, fmtNum, fmtCurrency } from "@core/utils";
import { useT } from "@core/i18n";
import type { BacktestHistoryEntry } from "../hooks/useBacktestHistory";
import type { BacktestResult } from "@core/api";
import type { Translations } from "@core/i18n/locales/en";

interface Props {
  entries: BacktestHistoryEntry[];
}

type BT = Translations["backtest"];
type NumericKey = { [K in keyof BacktestResult]-?: BacktestResult[K] extends number ? K : never }[keyof BacktestResult];
const metricsDef: { key: NumericKey; labelKey: keyof BT; fmt: (v: number) => string }[] = [
  { key: "total_return", labelKey: "totalReturn", fmt: fmtPct },
  { key: "annual_return", labelKey: "annualReturn", fmt: fmtPct },
  { key: "sharpe", labelKey: "sharpe", fmt: (v) => fmtNum(v) },
  { key: "sortino", labelKey: "sortino", fmt: (v) => fmtNum(v) },
  { key: "calmar", labelKey: "calmar", fmt: (v) => fmtNum(v) },
  { key: "max_drawdown", labelKey: "maxDrawdown", fmt: fmtPct },
  { key: "volatility", labelKey: "volatility", fmt: fmtPct },
  { key: "win_rate", labelKey: "winRate", fmt: fmtPct },
  { key: "total_trades", labelKey: "trades", fmt: (v) => String(v) },
  { key: "total_commission", labelKey: "commission", fmt: fmtCurrency },
];

export function CompareTable({ entries }: Props) {
  const { t } = useT();
  if (entries.length < 2) return null;

  return (
    <div className="bg-surface rounded-xl p-5 overflow-x-auto">
      <p className="text-base font-semibold text-slate-400 mb-3">{t.backtest.comparison}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-500 border-b border-surface-light">
            <th className="text-left py-2">{t.backtest.metric}</th>
            {entries.map((e) => (
              <th key={e.id} className="text-right py-2">{e.result.strategy_name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {metricsDef.map(({ key, labelKey, fmt }) => (
            <tr key={key} className="border-b border-surface-light/50">
              <td className="py-2 text-slate-400">{t.backtest[labelKey] as string}</td>
              {entries.map((e) => (
                <td key={e.id} className="text-right py-2">
                  {fmt(e.result[key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
