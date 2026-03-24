import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer } from "recharts";
import { useT } from "@core/i18n";
import { fmtPct } from "@quant/shared";
import type { QuantileReturn } from "@core/api";

interface Props {
  quantileReturns: QuantileReturn[];
  factorName: string;
}

export function QuantileReturnChart({ quantileReturns, factorName }: Props) {
  const { t } = useT();

  const data = quantileReturns.map((q) => ({
    name: `Q${q.quantile}`,
    annual_return: parseFloat((q.annual_return * 100).toFixed(2)),
  }));

  const maxAbs = Math.max(...data.map((d) => Math.abs(d.annual_return)), 0.01);

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
        {(t.alpha.factorNames as Record<string, string>)[factorName] ?? factorName} — {t.alpha.quantileReturns}
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.15)" />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} />
          <YAxis
            tick={{ fontSize: 10, fill: "#94a3b8" }} tickLine={false} axisLine={false}
            domain={[-maxAbs * 1.2, maxAbs * 1.2]}
            tickFormatter={(v) => `${v.toFixed(1)}%`}
          />
          <Tooltip
            contentStyle={{ backgroundColor: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 12 }}
            labelStyle={{ color: "#94a3b8" }}
            formatter={(v: number) => [`${v.toFixed(2)}%`, "Annual Return"]}
          />
          <Bar dataKey="annual_return" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.annual_return >= 0 ? "#10b981" : "#f87171"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
