import { useMemo } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useT } from "@core/i18n";

interface NavPoint {
  date: string;
  nav: number;
}

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
  const ddData = useMemo(() => computeDrawdown(data), [data]);

  return (
    <div className="bg-surface rounded-xl p-5">
      <p className="text-sm font-medium text-slate-400 mb-3">{t.backtest.drawdown}</p>
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={ddData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v: string) => v.slice(5)}
          />
          <YAxis
            tick={{ fill: "#94a3b8", fontSize: 12 }}
            domain={["auto", 0]}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
          />
          <Tooltip
            contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }}
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
