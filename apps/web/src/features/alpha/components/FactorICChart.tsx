import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import { useT } from "@core/i18n";
import type { ICResult } from "@core/api";

interface Props {
  ic: ICResult;
  factorName: string;
}

export function FactorICChart({ ic, factorName }: Props) {
  const { t } = useT();

  if (!ic.ic_series || ic.ic_series.length === 0) return null;

  const data = ic.ic_series.map((p) => ({
    date: p.date.slice(0, 7),
    ic: parseFloat(p.ic.toFixed(4)),
  }));

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
        {(t.alpha.factorNames as Record<string, string>)[factorName] ?? factorName} — {t.alpha.icTimeSeries}
      </p>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
          <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false} tickFormatter={(v) => v.toFixed(2)} />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#94a3b8" }}
            formatter={(v: number) => [v.toFixed(4), "IC"]}
          />
          <ReferenceLine y={0} stroke="rgba(148,163,184,0.4)" strokeDasharray="4 4" />
          <Line type="monotone" dataKey="ic" dot={false} strokeWidth={1.5}
            stroke="#3b82f6" activeDot={{ r: 3, fill: "#3b82f6" }} />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex gap-6 text-xs text-slate-500 dark:text-slate-400">
        <span>IC Mean: <span className={ic.ic_mean > 0 ? "text-emerald-500" : "text-red-400"}>{ic.ic_mean > 0 ? "+" : ""}{ic.ic_mean.toFixed(4)}</span></span>
        <span>ICIR: <span className={ic.icir > 0 ? "text-emerald-500" : "text-red-400"}>{ic.icir > 0 ? "+" : ""}{ic.icir.toFixed(2)}</span></span>
        <span>Hit Rate: {(ic.hit_rate * 100).toFixed(1)}%</span>
      </div>
    </div>
  );
}
