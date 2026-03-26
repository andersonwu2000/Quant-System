import { Check, X, AlertTriangle, Clock, Info } from "lucide-react";

const styles: Record<string, string> = {
  running: "bg-emerald-500/20 text-emerald-400",
  stopped: "bg-slate-500/20 text-slate-400",
  error: "bg-red-500/20 text-red-400",
  completed: "bg-blue-500/20 text-blue-400",
  failed: "bg-red-500/20 text-red-400",
  WARNING: "bg-amber-500/20 text-amber-400",
  CRITICAL: "bg-red-500/20 text-red-400",
  INFO: "bg-blue-500/20 text-blue-400",
};

const icons: Record<string, typeof Check> = {
  running: Check,
  completed: Check,
  stopped: Clock,
  error: X,
  failed: X,
  WARNING: AlertTriangle,
  CRITICAL: X,
  INFO: Info,
};

export function StatusBadge({ status }: { status: string }) {
  const Icon = icons[status];
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-semibold ${styles[status] || "bg-slate-500/20 text-slate-400"}`}>
      {Icon && <Icon size={11} />}
      {status}
    </span>
  );
}
