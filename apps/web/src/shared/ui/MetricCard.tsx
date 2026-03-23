interface Props {
  label: string;
  value: string;
  sub?: string;
  className?: string;
}

export function MetricCard({ label, value, sub, className = "" }: Props) {
  return (
    <div className={`bg-slate-50 dark:bg-surface rounded-xl p-5 shadow-sm dark:shadow-none ${className}`}>
      <p className="text-slate-600 dark:text-slate-400 text-sm font-medium mb-1">{label}</p>
      <p className="text-xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      {sub && <p className="text-sm mt-1">{sub}</p>}
    </div>
  );
}
