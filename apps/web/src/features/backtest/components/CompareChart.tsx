import { useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { useT } from "@core/i18n";
import { useTheme } from "@core/theme";
import { getChartColors } from "@shared/utils/chartColors";
import { Card } from "@shared/ui";
import type { BacktestHistoryEntry } from "../hooks/useBacktestHistory";

const COLORS = ["#3B82F6", "#22C55E", "#F59E0B", "#EF4444"];

interface Props {
  entries: BacktestHistoryEntry[];
}

export function CompareChart({ entries }: Props) {
  const { t } = useT();
  const { isDark } = useTheme();
  const c = getChartColors(isDark);
  const { data, names } = useMemo(() => {
    const dateMap = new Map<string, Record<string, number>>();
    const validNames: string[] = [];
    for (const entry of entries) {
      const series = entry.result?.nav_series;
      if (!series || series.length === 0) continue;
      const name = entry.result?.strategy_name ?? "Unknown";
      validNames.push(name);
      const initial = series[0].nav;
      for (const point of series) {
        const row = dateMap.get(point.date) || {};
        row[name] = (point.nav / initial - 1) * 100;
        dateMap.set(point.date, row);
      }
    }
    return {
      data: Array.from(dateMap.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, values]) => ({ date, ...values })),
      names: validNames,
    };
  }, [entries]);

  if (entries.length < 2 || data.length === 0) return null;

  return (
    <Card className="p-5">
      <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">{t.backtest.navComparison}</p>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: c.tick }} tickFormatter={(v) => v.slice(5)} />
          <YAxis tick={{ fontSize: 11, fill: c.tick }} tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
          <Tooltip
            contentStyle={{ backgroundColor: c.tooltip.bg, border: `1px solid ${c.tooltip.border}`, borderRadius: "8px", fontSize: 12 }}
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
    </Card>
  );
}
