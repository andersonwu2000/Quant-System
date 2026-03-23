import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import type { BacktestHistoryEntry } from "../hooks/useBacktestHistory";

const COLORS = ["#3B82F6", "#22C55E", "#F59E0B", "#EF4444"];

interface Props {
  entries: BacktestHistoryEntry[];
}

export function CompareChart({ entries }: Props) {
  if (entries.length < 2) return null;

  // Normalize NAV series to percentage returns (start at 0%)
  // Merge all entries by date
  const dateMap = new Map<string, Record<string, number>>();
  for (const entry of entries) {
    const series = entry.result.nav_series;
    if (!series || series.length === 0) continue;
    const initial = series[0].nav;
    for (const point of series) {
      const row = dateMap.get(point.date) || {};
      row[entry.result.strategy_name] = (point.nav / initial - 1) * 100;
      dateMap.set(point.date, row);
    }
  }

  const data = Array.from(dateMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, values]) => ({ date, ...values }));

  if (data.length === 0) return null;

  const names = entries.map((e) => e.result.strategy_name);

  return (
    <div className="bg-surface rounded-xl p-5">
      <p className="text-sm font-medium text-slate-400 mb-3">NAV Comparison (%)</p>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#64748B" }} tickFormatter={(v) => v.slice(5)} />
          <YAxis tick={{ fontSize: 11, fill: "#64748B" }} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1E293B", border: "none", borderRadius: "8px", fontSize: 12 }}
            formatter={(value: number) => [`${value.toFixed(2)}%`]}
          />
          <Legend />
          {names.map((name, i) => (
            <Line
              key={name}
              type="monotone"
              dataKey={name}
              stroke={COLORS[i % COLORS.length]}
              dot={false}
              strokeWidth={1.5}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
