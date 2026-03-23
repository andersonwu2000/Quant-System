import { useMemo } from "react";
import { useT } from "@core/i18n";

interface NavPoint {
  date: string;
  nav: number;
}

interface MonthlyReturn {
  year: number;
  month: number; // 0-11
  value: number; // decimal, e.g. 0.05 = 5%
}

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

function cellColor(value: number | undefined): string {
  if (value === undefined) return "bg-surface-dark text-slate-600";
  if (value >= 0.08) return "bg-emerald-600 text-white";
  if (value >= 0.04) return "bg-emerald-500/80 text-white";
  if (value >= 0.02) return "bg-emerald-500/50 text-emerald-100";
  if (value >= 0) return "bg-emerald-500/20 text-emerald-300";
  if (value >= -0.02) return "bg-red-500/20 text-red-300";
  if (value >= -0.04) return "bg-red-500/50 text-red-100";
  if (value >= -0.08) return "bg-red-500/80 text-white";
  return "bg-red-600 text-white";
}

function deriveMonthlyReturns(data: NavPoint[]): MonthlyReturn[] {
  if (data.length < 2) return [];

  // Group nav by year-month, taking first and last nav in each month
  const monthlyMap = new Map<string, { first: number; last: number }>();

  for (const point of data) {
    const d = new Date(point.date);
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    const existing = monthlyMap.get(key);
    if (!existing) {
      monthlyMap.set(key, { first: point.nav, last: point.nav });
    } else {
      existing.last = point.nav;
    }
  }

  // We need the previous month's last NAV to compute returns
  const sortedKeys = Array.from(monthlyMap.keys()).sort((a, b) => {
    const [ay, am] = a.split("-").map(Number);
    const [by, bm] = b.split("-").map(Number);
    return ay !== by ? ay - by : am - bm;
  });

  const results: MonthlyReturn[] = [];
  for (let i = 1; i < sortedKeys.length; i++) {
    const prev = monthlyMap.get(sortedKeys[i - 1])!;
    const curr = monthlyMap.get(sortedKeys[i])!;
    const [year, month] = sortedKeys[i].split("-").map(Number);
    const ret = (curr.last - prev.last) / prev.last;
    results.push({ year, month, value: ret });
  }

  return results;
}

export function MonthlyHeatmap({ data }: { data: NavPoint[] }) {
  const { t } = useT();

  const { years, grid, yearlyReturns } = useMemo(() => {
    const monthly = deriveMonthlyReturns(data);
    if (monthly.length === 0) return { years: [], grid: new Map(), yearlyReturns: new Map() };

    const g = new Map<string, number>();
    for (const m of monthly) {
      g.set(`${m.year}-${m.month}`, m.value);
    }

    const yrs = Array.from(new Set(monthly.map((m) => m.year))).sort();

    // Compute yearly returns by compounding monthly
    const yr = new Map<number, number>();
    for (const year of yrs) {
      let compound = 1;
      for (let m = 0; m < 12; m++) {
        const v = g.get(`${year}-${m}`);
        if (v !== undefined) compound *= 1 + v;
      }
      yr.set(year, compound - 1);
    }

    return { years: yrs, grid: g, yearlyReturns: yr };
  }, [data]);

  if (years.length === 0) return null;

  return (
    <div className="bg-surface rounded-xl p-5">
      <p className="text-sm font-medium text-slate-400 mb-3">{t.backtest.monthlyReturns}</p>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="px-2 py-1.5 text-left text-slate-400 font-medium">{t.backtest.year}</th>
              {MONTH_LABELS.map((m) => (
                <th key={m} className="px-2 py-1.5 text-center text-slate-400 font-medium">{m}</th>
              ))}
              <th className="px-2 py-1.5 text-center text-slate-400 font-medium">{t.backtest.yearly}</th>
            </tr>
          </thead>
          <tbody>
            {years.map((year) => (
              <tr key={year}>
                <td className="px-2 py-1.5 text-slate-300 font-medium">{year}</td>
                {Array.from({ length: 12 }, (_, m) => {
                  const v = grid.get(`${year}-${m}`);
                  return (
                    <td key={m} className="px-1 py-1">
                      <div
                        className={`rounded px-1.5 py-1 text-center font-mono ${cellColor(v)}`}
                        title={v !== undefined ? `${(v * 100).toFixed(2)}%` : ""}
                      >
                        {v !== undefined ? `${(v * 100).toFixed(1)}%` : ""}
                      </div>
                    </td>
                  );
                })}
                <td className="px-1 py-1">
                  <div
                    className={`rounded px-1.5 py-1 text-center font-mono font-semibold ${cellColor(yearlyReturns.get(year))}`}
                  >
                    {yearlyReturns.has(year)
                      ? `${(yearlyReturns.get(year)! * 100).toFixed(1)}%`
                      : ""}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
