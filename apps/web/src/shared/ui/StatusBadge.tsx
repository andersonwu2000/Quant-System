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

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`inline-block px-2.5 py-0.5 rounded-md text-xs font-semibold ${styles[status] || "bg-slate-500/20 text-slate-400"}`}>
      {status}
    </span>
  );
}
