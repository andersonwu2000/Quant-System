import type { ReactNode } from "react";
import { Card } from "./Card";

interface Props {
  label: string;
  value: string;
  sub?: string;
  help?: ReactNode;
  className?: string;
}

export function MetricCard({ label, value, sub, help, className = "" }: Props) {
  return (
    <Card className={`p-5 ${className}`}>
      <p className="text-slate-600 dark:text-slate-400 text-sm font-medium mb-1">{label}{help}</p>
      <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      {sub && <p className="text-sm mt-1">{sub}</p>}
    </Card>
  );
}
