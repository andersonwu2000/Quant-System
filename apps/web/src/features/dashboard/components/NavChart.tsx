import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useT } from "@core/i18n";

interface Props {
  data: { time: string; nav: number }[];
}

export function NavChart({ data }: Props) {
  const { t } = useT();
  return (
    <div className="bg-surface rounded-xl p-5">
      <p className="text-sm font-medium text-slate-400 mb-3">{t.dashboard.navRealtime}</p>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="time" tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <YAxis tick={{ fill: "#94a3b8", fontSize: 12 }} domain={["auto", "auto"]} />
          <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8 }} />
          <Line type="monotone" dataKey="nav" stroke="#3b82f6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
