import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useT } from "@core/i18n";
import { useTheme } from "@core/theme";
import { getChartColors } from "@shared/utils/chartColors";

interface NavPoint {
  date: string;
  nav: number;
}

export function ResultChart({ data }: { data: NavPoint[] }) {
  const { t } = useT();
  const { isDark } = useTheme();
  const c = getChartColors(isDark);
  return (
    <div className="bg-slate-50 dark:bg-surface rounded-xl p-5 border border-slate-200 dark:border-transparent shadow-sm dark:shadow-none">
      <p className="text-sm font-medium text-slate-500 dark:text-slate-400 mb-3">{t.backtest.navCurve}</p>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={c.grid} />
          <XAxis dataKey="date" tick={{ fill: c.tick, fontSize: 11 }} />
          <YAxis tick={{ fill: c.tick, fontSize: 12 }} domain={["auto", "auto"]} />
          <Tooltip contentStyle={{ background: c.tooltip.bg, border: `1px solid ${c.tooltip.border}`, borderRadius: 8 }} />
          <Line type="monotone" dataKey="nav" stroke="#3b82f6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
