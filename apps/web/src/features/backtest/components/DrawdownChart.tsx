import { useMemo } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useT } from "@core/i18n";
import { useTheme } from "@core/theme";
import { getChartColors } from "@shared/utils/chartColors";
import type { NavPoint } from "@core/api";

interface DrawdownPoint {
  date: string;
  drawdown: number; // negative percentage, e.g. -0.05 = -5%
}

function computeDrawdown(data: NavPoint[]): DrawdownPoint[] {
  let runningMax = -Infinity;
  return data.map((point) => {
    if (point.nav > runningMax) runningMax = point.nav;
    const dd = runningMax > 0 ? (point.nav - runningMax) / runningMax : 0;
    return { date: point.date, drawdown: dd * 100 };
  });
}

export function DrawdownChart({ data }: { data: NavPoint[] }) {
  const { t } = useT();
  const { isDark } = useTheme();
  const c = getChartColors(isDark);
  const ddData = useMemo(() => computeDrawdown(data), [data]);

  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
      <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">{t.backtest.drawdown}</p>
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={ddData}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis
            dataKey="date"
            tick={{ fill: c.tick, fontSize: 11 }}
            tickFormatter={(v: string) => v.slice(5)}
          />
          <YAxis
            tick={{ fill: c.tick, fontSize: 12 }}
            domain={["auto", 0]}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{ background: c.tooltip.bg, border: `1px solid ${c.tooltip.border}`, borderRadius: 8 }}
            formatter={(value: number) => [`${value.toFixed(2)}%`, t.backtest.drawdown]}
          />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="#ef4444"
            fill="#ef4444"
            fillOpacity={0.3}
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
