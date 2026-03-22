// Re-export platform-agnostic formatters from shared
export { fmtCurrency, fmtPct, fmtNum, fmtDate, fmtTime } from "@quant/shared";

// Web-specific: Tailwind CSS class helpers (not shareable with mobile)
export function pnlColor(v: number): string {
  if (v > 0) return "text-emerald-400";
  if (v < 0) return "text-red-400";
  return "text-slate-400";
}

export function pnlBg(v: number): string {
  if (v > 0) return "bg-emerald-500/10 text-emerald-400";
  if (v < 0) return "bg-red-500/10 text-red-400";
  return "bg-slate-500/10 text-slate-400";
}
