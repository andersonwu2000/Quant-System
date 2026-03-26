// Re-export platform-agnostic formatters from shared
export { fmtCurrency, fmtPrice, fmtPct, fmtNum, fmtDate, fmtTime, fmtUptime } from "@quant/shared";

// Web-specific: Tailwind CSS class helpers (not shareable with mobile)
// Uses dark shades on light backgrounds for WCAG AA compliance (≥4.5:1 contrast)
export function pnlColor(v: number): string {
  if (v > 0) return "text-emerald-600 dark:text-emerald-400";
  if (v < 0) return "text-red-600 dark:text-red-400";
  return "text-slate-500 dark:text-slate-400";
}

export function pnlBg(v: number): string {
  const bg = v > 0 ? "bg-emerald-500/10" : v < 0 ? "bg-red-500/10" : "bg-slate-500/10";
  return `${bg} ${pnlColor(v)}`;
}
