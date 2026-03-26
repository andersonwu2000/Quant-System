import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useT } from "@core/i18n";
import { useTheme } from "@core/theme";
import { getChartColors } from "@shared/utils/chartColors";
import { Card } from "@shared/ui";
import { fmtCurrency } from "@core/utils";

interface NavPoint {
  date: string;
  nav: number;
}

function fmtDate(v: string): string {
  return v.slice(0, 10);
}

function fmtYAxis(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

export function ResultChart({ data }: { data: NavPoint[] }) {
  const { t } = useT();
  const { isDark } = useTheme();
  const c = getChartColors(isDark);
  return (
    <Card className="p-5">
      <p className="text-base font-semibold text-slate-500 dark:text-slate-400 mb-3">{t.backtest.navCurve}</p>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis dataKey="date" tick={{ fill: c.tick, fontSize: 11 }} tickFormatter={fmtDate} minTickGap={40} />
          <YAxis tick={{ fill: c.tick, fontSize: 11 }} domain={["auto", "auto"]} tickFormatter={fmtYAxis} width={50} />
          <Tooltip
            contentStyle={{ background: c.tooltip.bg, border: `1px solid ${c.tooltip.border}`, borderRadius: 8 }}
            labelFormatter={fmtDate}
            formatter={(value: number) => [fmtCurrency(value), t.backtest.navCurve]}
          />
          <Line type="monotone" dataKey="nav" stroke="#3b82f6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
